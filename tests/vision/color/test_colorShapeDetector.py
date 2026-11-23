"""Tests of the colour + shape detector on synthetic scenes with a known truth."""

import numpy as np
import pytest

from vision.color.colorShapeDetector import ColorShapeDetector
from vision.common.detectionTypes import ColorCandidate, ColorDetection
from vision.simulation.boxTexture import SceneBox, buildLyingBox
from vision.simulation.sceneRenderer import SceneOptions, renderScene
from vision.simulation.sceneSetup import SceneSetup, SceneSetupConfig, buildSceneSetup


def detectColor(boxes: list[SceneBox], options: SceneOptions, withCalibration: bool = True) -> ColorDetection:
    """Draws the scene with the standard synthetic camera and runs the colour detector on it."""
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(3))
    image: np.ndarray = renderScene(setup.camera, boxes, setup.textures, options, np.random.default_rng(11))
    detector: ColorShapeDetector = ColorShapeDetector(setup.config, setup.calibration if withCalibration else None)
    return detector.detect(image)


def biggestCandidate(detection: ColorDetection) -> ColorCandidate:
    assert detection.candidates, f"nothing accepted; rejected: {[c.rejectReason for c in detection.rejected]}"
    return max(detection.candidates, key=lambda candidate: candidate.areaPx)


def yawErrorDeg(measuredDeg: float, trueDeg: float) -> float:
    return abs((measuredDeg - trueDeg + 90.0) % 180.0 - 90.0)


@pytest.mark.parametrize("xMm, yMm, yawDeg", [(550.0, 0.0, 0.0), (750.0, 250.0, 30.0), (1000.0, -250.0, 90.0),
                                              (700.0, -100.0, -60.0)])
def testFindsAStoneOnTheFloor(xMm: float, yMm: float, yawDeg: float) -> None:
    candidate: ColorCandidate = biggestCandidate(detectColor([buildLyingBox(xMm, yMm, yawDeg)],
                                                             SceneOptions(jpegQuality=85)))
    assert candidate.hasPosition
    assert np.hypot(candidate.centerMm[0] - xMm, candidate.centerMm[1] - yMm) < 30.0
    assert yawErrorDeg(candidate.yawDeg, yawDeg) < 5.0
    assert candidate.labelRatio > 0.0


@pytest.mark.parametrize("lightFactor", [0.6, 0.8, 1.2, 1.3])
def testSurvivesADarkerOrBrighterRoom(lightFactor: float) -> None:
    candidate: ColorCandidate = biggestCandidate(detectColor([buildLyingBox(750.0, 100.0, 90.0)],
                                                             SceneOptions(jpegQuality=85, lightFactor=lightFactor)))
    assert np.hypot(candidate.centerMm[0] - 750.0, candidate.centerMm[1] - 100.0) < 30.0


def testStillFindsTheStoneWhenTheCodeIsCovered() -> None:
    # Part of the face is hidden: the yaw stays right, the position can move along the stone
    candidate: ColorCandidate = biggestCandidate(detectColor([buildLyingBox(700.0, 0.0, -60.0, isMarkerCovered=True)],
                                                             SceneOptions(jpegQuality=85)))
    assert yawErrorDeg(candidate.yawDeg, -60.0) < 8.0
    assert np.hypot(candidate.centerMm[0] - 700.0, candidate.centerMm[1]) < 120.0


def testFlatBrownPatchIsNotAStone() -> None:
    # A brown rectangle painted on the floor, the size of a stone: same colour, no height
    detection: ColorDetection = detectColor([], SceneOptions(brownPatchesMm=[(650.0, -55.0, 970.0, 55.0)]))
    assert detection.candidates == []
    assert [candidate.rejectReason for candidate in detection.rejected] == ["flat: no height"]


def testTwoSeparateStonesAreTwoCandidates() -> None:
    boxes: list[SceneBox] = [buildLyingBox(600.0, 200.0, 10.0), buildLyingBox(900.0, -250.0, 60.0)]
    detection: ColorDetection = detectColor(boxes, SceneOptions(jpegQuality=85))
    found: list[tuple[float, float]] = sorted(candidate.centerMm for candidate in detection.candidates)
    assert len(found) == 2
    assert np.hypot(found[0][0] - 600.0, found[0][1] - 200.0) < 30.0
    assert np.hypot(found[1][0] - 900.0, found[1][1] + 250.0) < 30.0


def testWithoutCalibrationThereIsNoPosition() -> None:
    detection: ColorDetection = detectColor([buildLyingBox(650.0, 0.0, 0.0)], SceneOptions(), withCalibration=False)
    assert len(detection.candidates) == 1
    assert not detection.candidates[0].hasPosition


def testEmptyOrGreyPicturesGiveNothing() -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    detector: ColorShapeDetector = ColorShapeDetector(setup.config, setup.calibration)
    for image in (np.zeros((0, 0, 3), np.uint8), np.full((480, 640, 3), 128, np.uint8), np.zeros((1, 1, 3), np.uint8)):
        detection: ColorDetection = detector.detect(image)
        assert detection.candidates == [] and detection.rejected == []
