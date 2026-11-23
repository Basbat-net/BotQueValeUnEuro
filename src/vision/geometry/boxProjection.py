"""From a stone in the robot frame back to the picture: its 8 corners in px, to draw it over the image.

The apps use it to draw what the black box believes (a wire box on top of the real box):
if the drawn box sits on the real one, the pose, the calibration and the camera mount are right.
It also gives the viewing cone of the camera, for the 3D view of the dashboard.
"""

import cv2
import numpy as np

from vision.common.detectionConfig import StoneConfig
from vision.common.detectionTypes import ProjectedStone, StoneEstimate
from vision.common.visionConfig import CameraCalibration, VisionConfig
from vision.geometry.poseTransforms import buildCameraToRobotRotation, cameraToRobotPoints, robotToCameraPoints


class BoxProjector:
    """Projects stones on the picture with the calibration and the camera mount. Created once."""

    def __init__(self, config: VisionConfig, calibration: CameraCalibration) -> None:
        self.config: VisionConfig = config
        self.calibration: CameraCalibration = calibration
        self.cameraToRobot: np.ndarray = buildCameraToRobotRotation(config.cameraMount)

    def projectStone(self, stone: StoneEstimate) -> ProjectedStone:
        """The 8 corners of the stone in px, and whether all of them are in front of the camera."""
        cornersMm: np.ndarray = buildBoxCorners(stone.centerMm, stone.rotation, self.config.stone)
        cornersCamera: np.ndarray = robotToCameraPoints(cornersMm, self.cameraToRobot, self.config.cameraMount)
        isInFront: bool = bool(np.all(cornersCamera[:, 2] > 1.0))
        cornersPx: np.ndarray = np.zeros((8, 2))
        if isInFront:
            projected, _ = cv2.projectPoints(cornersCamera.reshape(-1, 1, 3), np.zeros(3), np.zeros(3),
                                             self.calibration.cameraMatrix, self.calibration.distCoeffs)
            cornersPx = projected.reshape(-1, 2)
        return ProjectedStone(stone, cornersPx, isInFront)

    def buildViewCone(self, depthMm: float) -> np.ndarray:
        """5 x 3 robot points: the camera, then the 4 picture corners seen at depthMm (for the 3D view)."""
        width: int = self.calibration.widthPx
        height: int = self.calibration.heightPx
        cornersPx: np.ndarray = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float64)
        normalized: np.ndarray = cv2.undistortPoints(cornersPx.reshape(-1, 1, 2), self.calibration.cameraMatrix,
                                                     self.calibration.distCoeffs).reshape(-1, 2)
        cornersCamera: np.ndarray = np.column_stack([normalized * depthMm, np.full(4, depthMm)])
        cameraPoint: np.ndarray = np.zeros((1, 3))
        return cameraToRobotPoints(np.vstack([cameraPoint, cornersCamera]), self.cameraToRobot,
                                   self.config.cameraMount)


def buildBoxCorners(centerMm: np.ndarray, rotation: np.ndarray, stone: StoneConfig) -> np.ndarray:
    """8 x 3 corners of a stone. Corner i takes the + side of the box axis k when bit k of i is 1."""
    halfSizes: np.ndarray = np.array([stone.lengthMm, stone.widthMm, stone.widthMm]) / 2
    signs: np.ndarray = np.array([[1 if index & (1 << axis) else -1 for axis in range(3)] for index in range(8)])
    return centerMm + (signs * halfSizes) @ rotation.T


def listBoxEdges() -> list[tuple[int, int]]:
    """The 12 edges of a box: pairs of corners that differ in exactly one axis."""
    return [(index, index ^ bit) for index in range(8) for bit in (1, 2, 4) if index < index ^ bit]
