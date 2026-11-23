"""Tests of the smoothing and the geometry of the 3D twin: numpy only, no screen."""

import math

import numpy as np

from vision.apps.dashboard.twinGeometry import buildBoxMesh, buildLabelMesh
from vision.apps.dashboard.twinSmoother import TwinSmoother, buildBoxSymmetries
from vision.common.detectionConfig import StoneConfig
from vision.common.detectionTypes import StoneEstimate
from vision.common.visionTypes import DetectionSource


def buildStone(xMm: float, yMm: float, yawDeg: float, level: int = 0) -> StoneEstimate:
    yaw: float = math.radians(yawDeg)
    rotation: np.ndarray = np.array([[math.cos(yaw), -math.sin(yaw), 0.0], [math.sin(yaw), math.cos(yaw), 0.0],
                                     [0.0, 0.0, 1.0]])
    return StoneEstimate(np.array([xMm, yMm, 55.0 + 110.0 * level]), rotation, yawDeg, True, level,
                         DetectionSource.ARUCO, 0.9)


def testSymmetriesAreRotationsThatKeepTheBox() -> None:
    symmetries: list[np.ndarray] = buildBoxSymmetries()
    assert len(symmetries) == 8
    for symmetry in symmetries:
        assert np.allclose(symmetry @ symmetry.T, np.eye(3)) and np.isclose(np.linalg.det(symmetry), 1.0)
        # The long axis stays on itself (maybe reversed)
        assert np.isclose(abs(symmetry[0, 0]), 1.0)


def testATrackKeepsItsNumberAndMovesSmoothly() -> None:
    smoother: TwinSmoother = TwinSmoother(smoothing=0.5, matchDistanceMm=150.0, ghostSeconds=1.0)
    first = smoother.update([buildStone(600.0, 0.0, 20.0)], 0.0)
    second = smoother.update([buildStone(640.0, 0.0, 20.0)], 0.1)
    assert first[0].trackId == second[0].trackId
    assert np.allclose(second[0].centerMm[:2], [620.0, 0.0])


def testTheSameBoxTurnedHalfARoundDoesNotSpin() -> None:
    smoother: TwinSmoother = TwinSmoother(smoothing=0.5, matchDistanceMm=150.0, ghostSeconds=1.0)
    smoother.update([buildStone(600.0, 0.0, 10.0)], 0.0)
    # Yaw 190 is the same box as yaw 10: the twin must stay near 10, not turn half a circle
    tracks = smoother.update([buildStone(600.0, 0.0, 190.0)], 0.1)
    assert np.allclose(tracks[0].rotation, buildStone(600.0, 0.0, 10.0).rotation, atol=1e-6)


def testLostStoneBecomesAGhostAndThenGoes() -> None:
    smoother: TwinSmoother = TwinSmoother(smoothing=0.5, matchDistanceMm=150.0, ghostSeconds=1.0)
    smoother.update([buildStone(600.0, 0.0, 0.0)], 0.0)
    assert smoother.update([], 0.5)[0].isGhost
    assert smoother.update([], 1.5) == []


def testStackedStonesKeepTheirOwnTracks() -> None:
    smoother: TwinSmoother = TwinSmoother(smoothing=0.5, matchDistanceMm=100.0, ghostSeconds=1.0)
    pile: list[StoneEstimate] = [buildStone(800.0, 0.0, 0.0, level) for level in range(3)]
    smoother.update(pile, 0.0)
    tracks = smoother.update(pile, 0.1)
    assert sorted(track.level for track in tracks) == [0, 1, 2] and len({track.trackId for track in tracks}) == 3


def testBoxMeshHasSixClosedFaces() -> None:
    corners, triangles = buildBoxMesh(np.zeros(3), np.eye(3), StoneConfig())
    assert corners.shape == (8, 3) and triangles.shape == (12, 3)
    # Every edge of a closed box is shared by exactly two triangles
    edges: dict[tuple[int, int], int] = {}
    for triangle in triangles:
        for first, second in ((0, 1), (1, 2), (2, 0)):
            corner, otherCorner = int(triangle[first]), int(triangle[second])
            key: tuple[int, int] = (min(corner, otherCorner), max(corner, otherCorner))
            edges[key] = edges.get(key, 0) + 1
    assert all(count == 2 for count in edges.values())


def testLabelsSitOnTheFourLongFaces() -> None:
    vertices, triangles = buildLabelMesh(np.zeros(3), np.eye(3), StoneConfig(), 104.0)
    assert vertices.shape == (16, 3) and triangles.shape == (8, 3)
    # Just outside the 110 mm faces, never on the small ends
    assert np.all(np.abs(vertices[:, 0]) <= 52.0 + 1e-9)
    assert np.all(np.isclose(np.maximum(np.abs(vertices[:, 1]), np.abs(vertices[:, 2])), 55.3))
