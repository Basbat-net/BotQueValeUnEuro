"""Saves what the camera sees: videos and pictures for the bank of test videos.

Videos are saved without drawings, so they can be fed back to the detectors
(frameSource in video mode) and every test runs on exactly the same images.
"""

import os
import time

import cv2
import numpy as np


class FrameRecorder:
    """Writes videos and snapshots into one folder. Created once at startup."""

    def __init__(self, folder: str) -> None:
        # Empty folder means recording is turned off in the config
        self.folder: str = folder
        self.writer: cv2.VideoWriter = cv2.VideoWriter()
        self.videoPath: str = ""
        self.isRecording: bool = False
        # Why the last start or snapshot failed, for the viewer to show. Empty if nothing failed
        self.lastError: str = ""

    def startRecording(self, frameSize: tuple[int, int], framesPerSecond: float) -> bool:
        """Opens a new video file. frameSize is (width, height) in px. False if it cannot."""
        # The rate is only used to play the video back: it does not change the saved images
        minimumRate: float = 1.0
        maximumRate: float = 60.0
        if not self._ensureFolder():
            return False
        self.videoPath = self._buildPath("video", ".avi")
        # MJPG: every frame is a JPEG of good quality. Bigger files, but any OpenCV can read them
        codec: int = cv2.VideoWriter.fourcc(*"MJPG")
        playbackRate: float = min(max(framesPerSecond, minimumRate), maximumRate)
        self.isRecording = self.writer.open(self.videoPath, codec, playbackRate, frameSize)
        self.lastError = "" if self.isRecording else f"cannot create the video '{self.videoPath}'"
        return self.isRecording

    def writeFrame(self, image: np.ndarray) -> None:
        """Adds one image to the open video. Does nothing if it is not recording."""
        if self.isRecording:
            self.writer.write(image)

    def stopRecording(self) -> str:
        """Closes the video and returns its file name (empty if it was not recording)."""
        savedName: str = os.path.basename(self.videoPath) if self.isRecording else ""
        self.writer.release()
        self.isRecording = False
        return savedName

    def saveSnapshot(self, rawImage: np.ndarray, annotatedImage: np.ndarray) -> tuple[bool, str]:
        """Saves the image as it came and as it is shown. Returns (isSaved, file name of the raw one)."""
        if not self._ensureFolder():
            return False, ""
        rawPath: str = self._buildPath("snapshot", "-raw.png")
        annotatedPath: str = rawPath.replace("-raw.png", "-annotated.png")
        isSaved: bool = cv2.imwrite(rawPath, rawImage) and cv2.imwrite(annotatedPath, annotatedImage)
        self.lastError = "" if isSaved else f"cannot write the pictures in '{self.folder}'"
        return isSaved, os.path.basename(rawPath)

    def _ensureFolder(self) -> bool:
        """Creates the folder if it does not exist yet. False if it is not set or cannot be created."""
        if self.folder == "":
            self.lastError = "recordings are off: set viewer.recordingsFolder in the config"
            return False
        try:
            # Recovery only: a path without permission must not end the viewer
            os.makedirs(self.folder, exist_ok=True)
        except OSError as error:
            self.lastError = f"cannot create '{self.folder}': {error.strerror}"
            return False
        return True

    def _buildPath(self, prefix: str, ending: str) -> str:
        """Path of a new file named after the date and time, so files never overwrite each other."""
        # Milliseconds too: two snapshots in the same second must not share a name
        milliseconds: int = int(time.time() * 1000) % 1000
        timeText: str = time.strftime("%Y%m%d-%H%M%S") + f"-{milliseconds:03d}"
        return os.path.join(self.folder, f"{prefix}-{timeText}{ending}")
