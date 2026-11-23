"""Tests of the camera to robot geometry, against numbers worked out by hand.

Run from the src/ folder:
    python3 -m pytest ../tests/vision
"""

import math

import numpy as np

from vision.common.detectionConfig import CameraMountConfig, StoneConfig
from vision.common.visionConfig import MarkerAxis
from vision.geometry.poseTransforms import (
    buildBoxFromMarker,
    buildCameraToRobotRotation,
    cameraToRobotPoints,
    computeYawDeg,
    estimateLevel,
    intersectRaysWithHeight,
    normalizeAxisAngleDeg,
    robotToCameraPoints,
    snapToFloor,
)


def testLevelCameraLooksAlongRobotX() -> None:
    rotation: np.ndarray = buildCameraToRobotRotation(CameraMountConfig(pitchDeg=0.0))
    # Lens (camera z) = robot x; picture right (camera x) = robot -y; picture down (camera y) = robot -z
    assert np.allclose(rotation @ [0, 0, 1], [1, 0, 0])
    assert np.allclose(rotation @ [1, 0, 0], [0, -1, 0])
    assert np.allclose(rotation @ [0, 1, 0], [0, 0, -1])


def testOpticalAxisHitsFloorAtHeightOverTanPitch() -> None:
    # 300 mm high, 30 degrees down: the centre of the picture is 300 / tan(30) = 519.6 mm ahead
    mount: CameraMountConfig = CameraMountConfig(zMm=300.0, pitchDeg=30.0)
    lens: np.ndarray = buildCameraToRobotRotation(mount) @ np.array([0.0, 0.0, 1.0])
    isValid, points = intersectRaysWithHeight(lens.reshape(1, 3), mount, 0.0)
    assert isValid[0]
    assert np.allclose(points[0], [300.0 / math.tan(math.radians(30.0)), 0.0, 0.0], atol=1e-6)


def testYawTurnsTheCameraLeft() -> None:
    mount: CameraMountConfig = CameraMountConfig(pitchDeg=0.0, yawDeg=90.0)
    assert np.allclose(buildCameraToRobotRotation(mount) @ [0, 0, 1], [0, 1, 0], atol=1e-9)


def testPositiveRollLowersTheRightSideOfThePicture() -> None:
    mount: CameraMountConfig = CameraMountConfig(pitchDeg=0.0, rollDeg=90.0)
    assert np.allclose(buildCameraToRobotRotation(mount) @ [1, 0, 0], [0, 0, -1], atol=1e-9)


def testRobotAndCameraPointsGoBackAndForth() -> None:
    mount: CameraMountConfig = CameraMountConfig(xMm=40.0, yMm=-20.0, zMm=250.0, pitchDeg=25.0, yawDeg=10.0,
                                                 rollDeg=3.0)
    rotation: np.ndarray = buildCameraToRobotRotation(mount)
    points: np.ndarray = np.array([[500.0, 100.0, 0.0], [800.0, -300.0, 55.0]])
    assert np.allclose(cameraToRobotPoints(robotToCameraPoints(points, rotation, mount), rotation, mount), points)


def testRayLookingUpNeverReachesTheFloor() -> None:
    isValid, _ = intersectRaysWithHeight(np.array([[1.0, 0.0, 0.2]]), CameraMountConfig(zMm=300.0), 0.0)
    assert not isValid[0]


def testBoxCentreIsHalfAWidthBehindTheCode() -> None:
    # Code facing the camera straight on, 600 mm ahead: its z axis points back to the camera
    markerRotation: np.ndarray = np.diag([1.0, -1.0, -1.0])
    rotation, center = buildBoxFromMarker(markerRotation, np.array([0.0, 0.0, 600.0]), StoneConfig(), MarkerAxis.X)
    assert np.allclose(center, [0.0, 0.0, 655.0])
    # The long side of the box follows the x axis of the code, as in Figure 5
    assert np.allclose(rotation[:, 0], [1.0, 0.0, 0.0])
    assert np.isclose(np.linalg.det(rotation), 1.0)


def testSnapRemovesASmallTiltAndKeepsTheYaw() -> None:
    tilt: float = math.radians(4.0)
    yaw: float = math.radians(30.0)
    longSide: np.ndarray = np.array([math.cos(yaw) * math.cos(tilt), math.sin(yaw) * math.cos(tilt), math.sin(tilt)])
    up: np.ndarray = np.array([0.0, 0.0, 1.0])
    shortSide: np.ndarray = np.cross(up, longSide)
    shortSide /= np.linalg.norm(shortSide)
    rotation: np.ndarray = np.column_stack([longSide, shortSide, np.cross(longSide, shortSide)])
    snapped, tiltDeg, verticalIndex = snapToFloor(rotation)
    assert verticalIndex == 2 and abs(tiltDeg - 4.0) < 0.1
    assert np.isclose(np.linalg.det(snapped), 1.0)
    isDefined, yawDeg = computeYawDeg(snapped, verticalIndex)
    assert isDefined and abs(yawDeg - 30.0) < 1e-6


def testStandingStoneHasNoYaw() -> None:
    standing: np.ndarray = np.column_stack([[0.0, 0.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    _, _, verticalIndex = snapToFloor(standing)
    isDefined, _ = computeYawDeg(standing, verticalIndex)
    assert verticalIndex == 0 and not isDefined
    assert estimateLevel(160.0, verticalIndex, StoneConfig()) == (0, 0.0)


def testYawIsALineNotAnArrow() -> None:
    assert normalizeAxisAngleDeg(100.0) == -80.0
    assert normalizeAxisAngleDeg(-90.0) == -90.0
    assert normalizeAxisAngleDeg(90.0) == -90.0
    assert normalizeAxisAngleDeg(179.0) == -1.0


def testLevelOfStackedStones() -> None:
    stone: StoneConfig = StoneConfig()
    assert estimateLevel(55.0, 2, stone) == (0, 0.0)
    assert estimateLevel(168.0, 2, stone) == (1, 3.0)
    assert estimateLevel(272.0, 2, stone) == (2, 3.0)
