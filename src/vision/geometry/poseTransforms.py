"""Geometry between the camera, the robot and the stones.

Frames used everywhere in the vision module:
- Camera (OpenCV): x right, y down, z forward along the lens, in mm.
- Robot: x forward, y left, z up, origin on the floor under the robot, in mm.
- Box: x along the 320 mm side, y and z along the two 110 mm sides, origin at the centre.
A rotation matrix R "from A to B" turns a vector written in A into B: vB = R @ vA.
"""

import math

import cv2
import numpy as np

from vision.common.detectionConfig import CameraMountConfig, StoneConfig
from vision.common.visionConfig import CameraCalibration, MarkerAxis


def buildCameraToRobotRotation(mount: CameraMountConfig) -> np.ndarray:
    """Rotation from the camera frame to the robot frame.

    Start from a level camera looking forward: its z (lens) is the robot x, its x (right) is the
    robot -y and its y (down) is the robot -z. Then roll about the lens (positive lowers the right
    side of the picture), pitch (positive looks down) and yaw (positive turns left).
    """
    levelCamera: np.ndarray = np.array([[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]])
    roll: float = math.radians(mount.rollDeg)
    pitch: float = math.radians(mount.pitchDeg)
    yaw: float = math.radians(mount.yawDeg)
    rollRotation: np.ndarray = np.array(
        [[1.0, 0.0, 0.0], [0.0, math.cos(roll), -math.sin(roll)], [0.0, math.sin(roll), math.cos(roll)]])
    # About the robot y axis: a positive angle takes the x axis down, which is "looking down"
    pitchRotation: np.ndarray = np.array(
        [[math.cos(pitch), 0.0, math.sin(pitch)], [0.0, 1.0, 0.0], [-math.sin(pitch), 0.0, math.cos(pitch)]])
    yawRotation: np.ndarray = np.array(
        [[math.cos(yaw), -math.sin(yaw), 0.0], [math.sin(yaw), math.cos(yaw), 0.0], [0.0, 0.0, 1.0]])
    return yawRotation @ pitchRotation @ rollRotation @ levelCamera


def cameraToRobotPoints(pointsMm: np.ndarray, cameraToRobot: np.ndarray, mount: CameraMountConfig) -> np.ndarray:
    """N x 3 (or 3) points from the camera frame to the robot frame."""
    mountPosition: np.ndarray = np.array([mount.xMm, mount.yMm, mount.zMm])
    return pointsMm @ cameraToRobot.T + mountPosition


def robotToCameraPoints(pointsMm: np.ndarray, cameraToRobot: np.ndarray, mount: CameraMountConfig) -> np.ndarray:
    """N x 3 (or 3) points from the robot frame to the camera frame (the inverse of the one above)."""
    mountPosition: np.ndarray = np.array([mount.xMm, mount.yMm, mount.zMm])
    return (pointsMm - mountPosition) @ cameraToRobot


def buildPixelRays(pixelsPx: np.ndarray, calibration: CameraCalibration, cameraToRobot: np.ndarray) -> np.ndarray:
    """N x 2 pixels to N x 3 ray directions in the robot frame (not unit length), lens distortion removed."""
    normalized: np.ndarray = cv2.undistortPoints(pixelsPx.reshape(-1, 1, 2).astype(np.float64),
                                                 calibration.cameraMatrix, calibration.distCoeffs).reshape(-1, 2)
    raysCamera: np.ndarray = np.column_stack([normalized, np.ones(len(normalized))])
    return raysCamera @ cameraToRobot.T


def intersectRaysWithHeight(directions: np.ndarray, mount: CameraMountConfig,
                            heightMm: float) -> tuple[np.ndarray, np.ndarray]:
    """Where each ray from the camera crosses the horizontal plane z = heightMm (robot frame).

    Returns (isValid, points): a ray that never reaches the plane (it looks up or away) is not valid.
    """
    origin: np.ndarray = np.array([mount.xMm, mount.yMm, mount.zMm])
    verticalSpeed: np.ndarray = directions[:, 2]
    isValid: np.ndarray = np.abs(verticalSpeed) > 1e-9
    distanceAlong: np.ndarray = (heightMm - origin[2]) / np.where(isValid, verticalSpeed, 1.0)
    isValid &= distanceAlong > 0
    return isValid, origin + directions * distanceAlong[:, np.newaxis]


def buildBoxFromMarker(markerRotation: np.ndarray, markerTranslationMm: np.ndarray, stone: StoneConfig,
                       longAxis: MarkerAxis) -> tuple[np.ndarray, np.ndarray]:
    """Box rotation and centre (camera frame) from the pose of one of its codes.

    The code lies on a large face: its z axis points out of the box, so the centre is half a
    box width behind it. Returns (rotation with columns long side, short side, face normal; centre).
    """
    codeX, codeY, faceNormal = markerRotation[:, 0], markerRotation[:, 1], markerRotation[:, 2]
    # Both choices keep a right-handed frame: long x side = normal
    longSide, shortSide = (codeX, codeY) if longAxis == MarkerAxis.X else (codeY, -codeX)
    centerMm: np.ndarray = markerTranslationMm - faceNormal * (stone.widthMm / 2)
    return np.column_stack([longSide, shortSide, faceNormal]), centerMm


def snapToFloor(rotation: np.ndarray) -> tuple[np.ndarray, float, int]:
    """A box resting on something has one axis exactly vertical: snap the nearest one.

    Returns (snapped rotation, tilt in degrees that was removed, index of the vertical axis).
    The tilt tells how plausible the pose is: a box on the floor is never tilted.
    """
    upward: np.ndarray = np.array([0.0, 0.0, 1.0])
    alignment: np.ndarray = rotation.T @ upward
    verticalIndex: int = int(np.argmax(np.abs(alignment)))
    tiltDeg: float = math.degrees(math.acos(min(1.0, abs(float(alignment[verticalIndex])))))
    snapped: np.ndarray = np.zeros((3, 3))
    snapped[:, verticalIndex] = upward * math.copysign(1.0, float(alignment[verticalIndex]))
    # A second axis made horizontal; the third one comes from the cross product (right-handed)
    secondIndex: int = (verticalIndex + 1) % 3
    horizontal: np.ndarray = rotation[:, secondIndex] - upward * float(rotation[2, secondIndex])
    snapped[:, secondIndex] = horizontal / max(float(np.linalg.norm(horizontal)), 1e-9)
    thirdIndex: int = (verticalIndex + 2) % 3
    snapped[:, thirdIndex] = np.cross(snapped[:, verticalIndex], snapped[:, secondIndex])
    return snapped, tiltDeg, verticalIndex


def computeYawDeg(snappedRotation: np.ndarray, verticalIndex: int) -> tuple[bool, float]:
    """Angle of the long side seen from above, from the robot x axis to the left, in [-90, 90).

    The stone looks the same turned 180 degrees, so -90 and 90 are the same stone.
    A standing stone has its long side vertical: its yaw is not defined (False), and the angle of
    a short side is given instead (team question 6).
    """
    isStanding: bool = verticalIndex == 0
    horizontalAxis: np.ndarray = snappedRotation[:, 1] if isStanding else snappedRotation[:, 0]
    yawDeg: float = math.degrees(math.atan2(float(horizontalAxis[1]), float(horizontalAxis[0])))
    return not isStanding, normalizeAxisAngleDeg(yawDeg)


def normalizeAxisAngleDeg(angleDeg: float) -> float:
    """An angle of a line (not an arrow) in [-90, 90): 100 degrees and -80 degrees are the same line."""
    return (angleDeg + 90.0) % 180.0 - 90.0


def estimateLevel(centerZMm: float, verticalIndex: int, stone: StoneConfig) -> tuple[int, float]:
    """Which floor of a pile the stone is on (0 = on the floor) and how far its height is from it.

    Lying stones have their centre at 55, 165, 275 mm; a standing one at 160 mm.
    """
    if verticalIndex == 0:
        return 0, abs(centerZMm - stone.lengthMm / 2)
    halfWidth: float = stone.widthMm / 2
    level: int = max(0, round((centerZMm - halfWidth) / stone.widthMm))
    return level, abs(centerZMm - (halfWidth + stone.widthMm * level))
