"""Window of the viewer: shows the picture, reads the keys and saves snapshots and videos."""

import cv2
import numpy as np

from vision.apps.viewer.frameRecorder import FrameRecorder
from vision.apps.viewer.viewerDrawing import drawViewerFrame
from vision.apps.viewer.viewerState import (
    ViewerAction,
    ViewerFrame,
    ViewerState,
    applyKey,
)


class ViewerScreen:
    """The window and everything the user does in it. Created once at startup."""

    def __init__(self, windowName: str, recordingsFolder: str) -> None:
        self.windowName: str = windowName
        self.recorder: FrameRecorder = FrameRecorder(recordingsFolder)
        # Last picture shown (with drawings and status bar), saved by the snapshot key
        self.lastShownImage: np.ndarray = np.zeros((0, 0, 3), dtype=np.uint8)

    def update(self, image: np.ndarray, viewerFrame: ViewerFrame, state: ViewerState, isNewFrame: bool) -> bool:
        """Shows one picture and handles the key pressed. Returns False when the user wants to quit."""
        # While paused nothing new arrives: waiting longer for a key leaves the processor free
        pausedWaitMs: int = 30
        playingWaitMs: int = 1
        if isNewFrame:
            # The video gets the image as it came, without drawings, so the detectors can read it again
            self.recorder.writeFrame(image)
        self.lastShownImage = drawViewerFrame(image, viewerFrame, state)
        cv2.imshow(self.windowName, self.lastShownImage)
        keyCode: int = cv2.waitKey(pausedWaitMs if state.isPaused else playingWaitMs)
        if self._isWindowClosed():
            return False
        # Some systems add flags in the high bits of the code: the key itself is in the low 8 bits
        action: ViewerAction = applyKey(state, keyCode & 0xFF if keyCode >= 0 else -1)
        if action == ViewerAction.SNAPSHOT:
            self._saveSnapshot(image, state)
        elif action == ViewerAction.TOGGLE_RECORDING:
            self._toggleRecording(image, state)
        return action != ViewerAction.QUIT

    def close(self) -> None:
        """Closes an open video (so the file is not left broken) and the window."""
        self.recorder.stopRecording()
        cv2.destroyAllWindows()

    def _isWindowClosed(self) -> bool:
        """True if the user closed the window with its X: imshow would open it again otherwise."""
        return cv2.getWindowProperty(self.windowName, cv2.WND_PROP_VISIBLE) < 1

    def _saveSnapshot(self, image: np.ndarray, state: ViewerState) -> None:
        """Saves the current image, raw and with drawings, and tells the result in the status bar."""
        isSaved, fileName = self.recorder.saveSnapshot(image, self.lastShownImage)
        state.message = f"snapshot saved: {fileName}" if isSaved else self.recorder.lastError

    def _toggleRecording(self, image: np.ndarray, state: ViewerState) -> None:
        """Starts a new video or closes the one being recorded."""
        if self.recorder.isRecording:
            state.message = f"video saved: {self.recorder.stopRecording()}"
        else:
            frameSize: tuple[int, int] = (image.shape[1], image.shape[0])
            isStarted: bool = self.recorder.startRecording(frameSize, state.stats.framesPerSecond)
            state.message = "recording: r to stop" if isStarted else self.recorder.lastError
        state.isRecording = self.recorder.isRecording
