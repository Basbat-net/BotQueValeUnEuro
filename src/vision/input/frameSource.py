"""Gives images to the vision module, one at a time.

The rest of the code never knows if a frame comes from a live camera, a recorded video,
a folder of pictures or a stream sent over the network: that is chosen in the config.
"""

import os
import time

import cv2
import numpy as np

from vision.common.visionConfig import FrameSourceConfig, FrameSourceMode
from vision.common.visionTypes import FrameInput


class FrameSource:
    """Single entry point for images. Created once at startup."""

    def __init__(self, config: FrameSourceConfig) -> None:
        self.config: FrameSourceConfig = config
        self.capture: cv2.VideoCapture = cv2.VideoCapture()
        self.imagePaths: list[str] = []
        self.frameIndex: int = 0
        self.isOpen: bool = False
        # Why the last open() or read() failed, for the apps to print. Empty if nothing failed
        self.lastError: str = ""

    def open(self) -> bool:
        """Opens the source selected in the config. Returns False if it fails (see lastError)."""
        errorText: str = ""
        self.frameIndex = 0
        if self.config.mode == FrameSourceMode.CAMERA:
            self.isOpen = self.capture.open(self.config.cameraIndex)
            # Asked before the size: some drivers only offer the big sizes at full rate in MJPG
            if len(self.config.fourcc) == 4:
                self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*self.config.fourcc))
            # Only a request: the driver may choose another size (the real one is in frame.image.shape)
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.widthPx)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.heightPx)
            errorText = f"camera {self.config.cameraIndex} not found or busy"
        elif self.config.mode == FrameSourceMode.VIDEO:
            self.isOpen = self.capture.open(self.config.videoPath)
            errorText = f"cannot open the video '{self.config.videoPath}'"
        elif self.config.mode == FrameSourceMode.STREAM:
            # Both waits are bounded: a dead sender must never block the program
            timeouts: list[int] = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, self.config.streamTimeoutMs,
                                   cv2.CAP_PROP_READ_TIMEOUT_MSEC, self.config.streamTimeoutMs]
            self.isOpen = self.capture.open(self.config.streamUrl, cv2.CAP_FFMPEG, timeouts)
            errorText = f"cannot open the stream '{self.config.streamUrl}'"
        else:
            self.imagePaths = self._listImagePaths()
            self.isOpen = len(self.imagePaths) > 0
            errorText = f"no .png, .jpg or .bmp pictures in '{self.config.imagesFolder}'"
        self.lastError = "" if self.isOpen else errorText
        return self.isOpen

    def read(self) -> tuple[bool, FrameInput]:
        """Returns (isValid, frame). On False, hasEnded() tells if the source simply ran out."""
        emptyFrame: FrameInput = FrameInput(np.zeros((0, 0, 3), dtype=np.uint8), 0)
        self.lastError = ""
        if not self.isOpen:
            self.lastError = "the source is not open"
            return False, emptyFrame
        if self.config.mode == FrameSourceMode.IMAGES:
            isValid, image = self._readNextImage()
        else:
            isValid, image = self.capture.read()
        if not isValid or image is None:
            if self.lastError == "":
                self.lastError = f"no image from the {self.config.mode.value}"
            return False, emptyFrame
        # The timestamp of a picture comes from frameIndex, so it is taken before moving on
        frame: FrameInput = FrameInput(image, self._computeTimestampMs())
        self.frameIndex += 1
        return True, frame

    def hasEnded(self) -> bool:
        """After read() returned False: True if a recorded source simply ran out of frames.

        The end of a video or folder is normal. A live camera or a stream never ends: False means it
        failed (for a stream, the app can call reconnect()).
        """
        if self.config.mode == FrameSourceMode.IMAGES:
            return self.frameIndex >= len(self.imagePaths)
        return self.config.mode == FrameSourceMode.VIDEO

    def reconnect(self) -> bool:
        """Closes and opens the source again: after a stream was cut. False if it is still down."""
        self.capture.release()
        return self.open()

    def close(self) -> None:
        """Releases the camera or the video file."""
        self.capture.release()
        self.isOpen = False

    def _listImagePaths(self) -> list[str]:
        """Pictures of the folder, sorted by name.

        The sort is by text (img10 goes before img2), so name the pictures with zeros: img02.
        """
        validExtensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".bmp")
        if not os.path.isdir(self.config.imagesFolder):
            return []
        fileNames: list[str] = sorted(os.listdir(self.config.imagesFolder))
        return [
            os.path.join(self.config.imagesFolder, fileName)
            for fileName in fileNames
            if fileName.lower().endswith(validExtensions)
        ]

    def _readNextImage(self) -> tuple[bool, np.ndarray | None]:
        """Loads the next picture of the folder. False at the end or for an unreadable picture."""
        if self.frameIndex >= len(self.imagePaths):
            return False, None
        imagePath: str = self.imagePaths[self.frameIndex]
        image = cv2.imread(imagePath)
        if image is None:
            # Move past it, so the next read() tries the following picture, not this one again
            self.frameIndex += 1
            self.lastError = f"cannot read the picture '{imagePath}'"
            return False, None
        return True, image

    def _computeTimestampMs(self) -> int:
        """Capture time: system clock for live sources, position for recorded data."""
        if self.config.mode in (FrameSourceMode.CAMERA, FrameSourceMode.STREAM):
            # Taken when the frame arrives, so it includes the delay of the camera driver (and of the network)
            return int(time.time() * 1000)
        if self.config.mode == FrameSourceMode.VIDEO:
            return int(self.capture.get(cv2.CAP_PROP_POS_MSEC))
        return self.frameIndex * self.config.imagesPeriodMs
