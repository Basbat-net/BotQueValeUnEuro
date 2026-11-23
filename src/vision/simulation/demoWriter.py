"""Writes the files of a synthetic demo: the video, its calibration, a config ready to use and the truth.

The config points to the video and the calibration with absolute paths, so the apps can open the demo
from any folder: python3 -m vision.apps.dashboard.dashboardApp <folder>/demoConfig.json
"""

import os

import cv2

from vision.common.configLoader import saveCameraCalibration, saveVisionConfig
from vision.common.visionConfig import FrameSourceMode
from vision.simulation.sceneSetup import SceneSetup


class DemoWriter:
    """Owns the files of one demo folder. Created once."""

    def __init__(self, folder: str, setup: SceneSetup, framesPerSecond: float) -> None:
        self.folder: str = os.path.abspath(os.path.expanduser(folder))
        self.setup: SceneSetup = setup
        self.framesPerSecond: float = framesPerSecond
        self.videoWriter: cv2.VideoWriter = cv2.VideoWriter()
        self.truthRows: list[list[object]] = []
        self.lastError: str = ""

    def open(self) -> bool:
        """Creates the folder and the video file. False if it cannot (see lastError)."""
        try:
            # Recovery only: a folder without permission is reported, not propagated
            os.makedirs(self.folder, exist_ok=True)
        except OSError as error:
            self.lastError = f"cannot create {self.folder}: {error.strerror}"
            return False
        videoSize: tuple[int, int] = (self.setup.camera.widthPx, self.setup.camera.heightPx)
        isOpen: bool = self.videoWriter.open(self.path("demo.avi"), cv2.VideoWriter.fourcc(*"MJPG"),
                                             self.framesPerSecond, videoSize)
        self.lastError = "" if isOpen else f"cannot create {self.path('demo.avi')}"
        return isOpen

    def path(self, fileName: str) -> str:
        """Absolute path of a file of the demo folder."""
        return os.path.join(self.folder, fileName)

    def addFrame(self, image: cv2.typing.MatLike, frameIndex: int, truth: list[list[float]]) -> None:
        """Adds one picture to the video and its stones to the truth table."""
        self.videoWriter.write(image)
        timeMs: int = round(frameIndex * 1000 / self.framesPerSecond)
        for stoneIndex, row in enumerate(truth):
            self.truthRows.append([frameIndex, timeMs, stoneIndex, *[round(value, 1) for value in row]])

    def close(self) -> bool:
        """Closes the video and writes the calibration, the config and the truth. False if a file failed."""
        self.videoWriter.release()
        if not saveCameraCalibration(self.path("calibration.json"), self.setup.calibration):
            return False
        config = self.setup.config
        config.frameSource.mode = FrameSourceMode.VIDEO
        config.frameSource.videoPath = self.path("demo.avi")
        config.calibrationFilePath = self.path("calibration.json")
        config.viewer.recordingsFolder = self.path("recordings")
        config.showWindow = True
        if not saveVisionConfig(self.path("demoConfig.json"), config):
            self.lastError = "cannot write demoConfig.json"
            return False
        try:
            # Recovery only: a full disk or a read-only folder is reported, not propagated
            with open(self.path("truth.csv"), "w", encoding="utf-8") as truthFile:
                truthFile.write("frame,timeMs,stone,xMm,yMm,zMm,yawDeg,isCovered\n")
                truthFile.writelines(",".join(str(value) for value in row) + "\n" for row in self.truthRows)
        except OSError as error:
            self.lastError = f"cannot write the demo files: {error.strerror}"
            return False
        return True

