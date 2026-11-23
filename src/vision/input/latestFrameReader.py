"""Reads frames in a background thread, so the main loop always gets the newest one.

- Live sources (camera, stream): when the processing is slower than the camera, old frames are
  dropped. Without this, frames pile up in the network and driver buffers and the robot would
  act on images that get older and older.
- Recorded sources (video, folder): no frame is dropped; the thread waits until each one is taken.
  With playbackFramesPerSecond above 0 they are played at that rate (the dashboard does it).
The thread never draws and never processes: it only reads.
"""

import threading
import time

import numpy as np

from vision.common.visionConfig import FrameSourceConfig, FrameSourceMode
from vision.common.visionTypes import FrameInput
from vision.input.frameSource import FrameSource


class LatestFrameReader:
    """Owns the reading thread of one FrameSource. Created once at startup."""

    def __init__(self, frameSource: FrameSource, playbackFramesPerSecond: float = 0.0) -> None:
        self.frameSource: FrameSource = frameSource
        self.isLive: bool = frameSource.config.mode in (FrameSourceMode.CAMERA, FrameSourceMode.STREAM)
        self.playbackFramesPerSecond: float = playbackFramesPerSecond
        # One lock and its signal for everything the two threads share
        self.condition: threading.Condition = threading.Condition()
        self.latestFrame: FrameInput = FrameInput(np.zeros((0, 0, 3), dtype=np.uint8), 0)
        self.hasNewFrame: bool = False
        self.isRunning: bool = False
        self.isPaused: bool = False
        self.isStepRequested: bool = False
        # A recorded source that ran out, and a source that failed (camera unplugged): both stop the thread
        self.hasEnded: bool = False
        self.hasFailed: bool = False
        self.lastError: str = ""
        self.droppedCount: int = 0
        self.thread: threading.Thread = threading.Thread(target=self._readLoop, daemon=True)

    def start(self) -> bool:
        """Opens the source and starts reading. False if the source cannot be opened (see lastError)."""
        if not self.frameSource.open():
            self.lastError = self.frameSource.lastError
            return False
        self.isRunning = True
        self.thread.start()
        return True

    def takeLatest(self, waitSeconds: float) -> tuple[bool, FrameInput]:
        """The newest frame not taken yet, waiting at most waitSeconds. (False, empty frame) if none came."""
        with self.condition:
            if not self.hasNewFrame:
                self.condition.wait(timeout=waitSeconds)
            if not self.hasNewFrame:
                return False, FrameInput(np.zeros((0, 0, 3), dtype=np.uint8), 0)
            self.hasNewFrame = False
            self.condition.notify_all()
            return True, self.latestFrame

    def setPaused(self, isPaused: bool) -> None:
        """While paused nothing is read, so a video does not move on."""
        with self.condition:
            self.isPaused = isPaused
            self.condition.notify_all()

    def requestStep(self) -> None:
        """While paused: read exactly one more frame."""
        with self.condition:
            self.isStepRequested = True
            self.condition.notify_all()

    def stop(self) -> None:
        """Stops the thread. The thread itself closes the source when it ends, never this caller:
        closing a capture that the thread is still opening or reading could crash the program.
        """
        with self.condition:
            self.isRunning = False
            self.condition.notify_all()
        if not self.thread.is_alive():
            self.frameSource.close()
            return
        # A read or an open waits at most streamTimeoutMs each; if it takes longer, the thread
        # (a daemon) closes the source on its own when it ends
        self.thread.join(timeout=2 * self.frameSource.config.streamTimeoutMs / 1000 + 1.0)

    def _readLoop(self) -> None:
        """Body of the thread: read, keep the newest, repeat until stopped, ended or failed."""
        nextFrameTime: float = time.perf_counter()
        while self._waitUntilReadIsAllowed():
            isRead, frame = self.frameSource.read()
            if not isRead and not self._handleReadFailure():
                break
            if isRead:
                self._storeFrame(frame)
            if not self.isLive and self.playbackFramesPerSecond > 0:
                # Never behind "now": after a pause the video goes on at its rate, without a burst
                nextFrameTime = max(nextFrameTime + 1.0 / self.playbackFramesPerSecond, time.perf_counter())
                time.sleep(max(0.0, nextFrameTime - time.perf_counter()))
        self.frameSource.close()
        with self.condition:
            self.condition.notify_all()

    def _waitUntilReadIsAllowed(self) -> bool:
        """Waits while paused, or while a recorded frame has not been taken. False when it must stop."""
        pollSeconds: float = 0.1
        with self.condition:
            while self.isRunning:
                isHeldByPause: bool = self.isPaused and not self.isStepRequested
                isHeldByConsumer: bool = not self.isLive and self.hasNewFrame
                if not isHeldByPause and not isHeldByConsumer:
                    self.isStepRequested = False
                    return True
                self.condition.wait(timeout=pollSeconds)
            return False

    def _handleReadFailure(self) -> bool:
        """After a failed read: True to go on, False to stop the thread.

        One bad read must not end the vision of a match: a stream or a camera is opened again
        (a cut Wi-Fi, a USB hiccup), and an unreadable picture of a folder is skipped.
        """
        if self.frameSource.hasEnded():
            self.hasEnded = True
            return False
        self.lastError = self.frameSource.lastError
        mode: FrameSourceMode = self.frameSource.config.mode
        if mode == FrameSourceMode.IMAGES:
            return self.isRunning
        if mode not in (FrameSourceMode.STREAM, FrameSourceMode.CAMERA):
            self.hasFailed = True
            return False
        # Opening again waits at most streamTimeoutMs. A refused connection fails at once:
        # then wait reconnectDelayMs (stop() wakes this wait up)
        if self.isRunning and not self.frameSource.reconnect():
            with self.condition:
                self.condition.wait(timeout=self.frameSource.config.reconnectDelayMs / 1000)
        return self.isRunning

    def _storeFrame(self, frame: FrameInput) -> None:
        """Keeps the frame as the newest one; a frame nobody took is counted as dropped."""
        with self.condition:
            if self.hasNewFrame:
                self.droppedCount += 1
            # Images arrive again: an old error (a cut that was reconnected) is no longer true
            self.lastError = ""
            self.latestFrame = frame
            self.hasNewFrame = True
            self.condition.notify_all()


def buildLatestFrameReader(sourceConfig: FrameSourceConfig, playbackFramesPerSecond: float = 0.0) -> LatestFrameReader:
    """A reader with its own FrameSource, ready to start()."""
    return LatestFrameReader(FrameSource(sourceConfig), playbackFramesPerSecond)
