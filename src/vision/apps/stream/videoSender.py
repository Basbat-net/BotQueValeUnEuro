"""The video sender of the robot: reads the camera and serves it as MJPEG over HTTP.

On the robot Raspberry it reads a USB camera with OpenCV (the Camera Module 3 would need picamera2
or rpicam-vid: see docs/emisor-video.md in the team notes). On a PC it also sends a recorded video,
to test the whole chain (sender -> network -> vision -> relay) without the robot.
"""

import time

import cv2

from vision.apps.stream.mjpegServer import MjpegServer
from vision.common.visionConfig import VisionConfig
from vision.input.frameSource import FrameSource


class VideoSender:
    """Camera (or video) in, MJPEG server out. Created once at startup."""

    def __init__(self, config: VisionConfig) -> None:
        self.config: VisionConfig = config
        self.frameSource: FrameSource = FrameSource(config.frameSource)
        self.server: MjpegServer = MjpegServer(config.sender.port)
        self.isStopRequested: bool = False
        self.sentCount: int = 0
        self.lastError: str = ""

    def requestStop(self) -> None:
        """Asks the loop to finish."""
        self.isStopRequested = True

    def run(self) -> str:
        """Sends frames until the source ends or a stop is requested. Returns why it failed, or empty."""
        if not self.server.start():
            return self.server.lastError
        if not self.frameSource.open():
            self.server.stop()
            return f"could not open the frame source: {self.frameSource.lastError}"
        framePeriodSeconds: float = 1.0 / max(self.config.sender.maxFramesPerSecond, 0.1)
        jpegOptions: list[int] = [cv2.IMWRITE_JPEG_QUALITY, self.config.sender.jpegQuality]
        nextFrameTime: float = time.perf_counter()
        errorText: str = ""
        while not self.isStopRequested:
            isRead, frame = self.frameSource.read()
            if not isRead:
                errorText = "" if self.frameSource.hasEnded() else f"reading stopped: {self.frameSource.lastError}"
                break
            isEncoded, jpegBytes = cv2.imencode(".jpg", frame.image, jpegOptions)
            if isEncoded:
                self.server.publishFrame(jpegBytes.tobytes())
                self.sentCount += 1
            # Never faster than maxFramesPerSecond: a recorded video plays at its own speed too
            nextFrameTime = max(nextFrameTime + framePeriodSeconds, time.perf_counter() - framePeriodSeconds)
            time.sleep(max(0.0, nextFrameTime - time.perf_counter()))
        self.frameSource.close()
        self.server.stop()
        return errorText
