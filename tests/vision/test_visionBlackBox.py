"""Tests of the black box (the contract) and of the fusion of both detectors."""

import numpy as np

from vision.blackBoxFactory import buildVisionBlackBox
from vision.common.detectionTypes import PipelineOptions, VisionDetails
from vision.common.visionTypes import DetectionSource, FrameInput, VisionResult, VisionStatus
from vision.simulation.boxTexture import SceneBox, buildLyingBox
from vision.simulation.sceneRenderer import SceneOptions, renderScene
from vision.simulation.sceneSetup import SceneSetup, SceneSetupConfig, buildSceneSetup


def runScene(boxes: list[SceneBox], setup: SceneSetup | None = None) -> VisionDetails:
    """Draws a scene and runs the whole black box (both detectors) on it."""
    sceneSetup: SceneSetup = setup if setup is not None else buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    image: np.ndarray = renderScene(sceneSetup.camera, boxes, sceneSetup.textures, SceneOptions(jpegQuality=85),
                                    np.random.default_rng(5))
    blackBox = buildVisionBlackBox(sceneSetup.config, sceneSetup.calibration)
    return blackBox.processWithDetails(FrameInput(image, 1234), PipelineOptions())


def testCodeAndBlobOfTheSameStoneGiveOneStoneFromBoth() -> None:
    details: VisionDetails = runScene([buildLyingBox(650.0, 50.0, 20.0)])
    assert details.result.status == VisionStatus.OK
    assert len(details.result.stones) == 1
    assert details.result.stones[0].source == DetectionSource.BOTH
    assert details.result.timestampMs == 1234


def testCoveredCodeGivesOneColourStoneWithLowConfidence() -> None:
    # The cover splits the long side in two blobs: the fusion joins them into one stone in the middle
    details: VisionDetails = runScene([buildLyingBox(650.0, 0.0, 90.0, isMarkerCovered=True)])
    assert [stone.source for stone in details.result.stones] == [DetectionSource.COLOR]
    assert details.result.stones[0].confidence <= 0.5
    assert np.hypot(details.result.stones[0].xMm - 650.0, details.result.stones[0].yMm) < 30.0


def testStonesAreSortedNearestFirst() -> None:
    details: VisionDetails = runScene([buildLyingBox(1100.0, 200.0, 0.0), buildLyingBox(550.0, -100.0, 30.0)])
    distances: list[float] = [float(np.hypot(stone.xMm, stone.yMm)) for stone in details.result.stones]
    assert len(distances) == 2 and distances == sorted(distances)


def testUnmeasuredMountGivesNotCalibratedAndNoStones() -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    setup.config.cameraMount.isMeasured = False
    details: VisionDetails = runScene([buildLyingBox(650.0, 50.0, 20.0)], setup)
    assert details.result.status == VisionStatus.NOT_CALIBRATED
    assert details.result.stones == []
    # The apps still get the provisional stones to draw them
    assert len(details.stones) == 1


def testNoCalibrationGivesNotCalibrated() -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    setup.config.calibrationFilePath = "/nonexistent/calibration.json"
    image: np.ndarray = np.full((480, 640, 3), 128, np.uint8)
    result: VisionResult = buildVisionBlackBox(setup.config).process(FrameInput(image, 0))
    assert result.status == VisionStatus.NOT_CALIBRATED and result.stones == []


def testWrongArucoConfigGivesConfigError() -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    setup.config.aruco.dictionaryName = "DICT_9X9_50"
    blackBox = buildVisionBlackBox(setup.config, setup.calibration)
    result: VisionResult = blackBox.process(FrameInput(np.full((480, 640, 3), 128, np.uint8), 0))
    assert result.status == VisionStatus.CONFIG_ERROR and blackBox.lastError != ""


def testStrangeImagesNeverRaise() -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    blackBox = buildVisionBlackBox(setup.config, setup.calibration)
    noise: np.ndarray = np.random.default_rng(0).integers(0, 256, (480, 640, 3), dtype=np.uint8)
    expected: list[tuple[np.ndarray, VisionStatus]] = [
        (np.zeros((0, 0, 3), np.uint8), VisionStatus.NO_FRAME),
        (np.zeros((480, 640), np.uint8), VisionStatus.NO_FRAME),
        # Not 8 bits per channel: OpenCV would raise inside the detectors (found by the code review)
        (np.zeros((480, 640, 3), np.float32), VisionStatus.NO_FRAME),
        (np.zeros((480, 640, 3), np.uint16), VisionStatus.NO_FRAME),
        (np.zeros((1, 1, 3), np.uint8), VisionStatus.NOT_CALIBRATED),
        (np.full((480, 640, 3), 128, np.uint8), VisionStatus.OK),
        (noise, VisionStatus.OK),
    ]
    for image, status in expected:
        result: VisionResult = blackBox.process(FrameInput(image, 0))
        assert result.status == status
        if status != VisionStatus.OK:
            assert result.stones == []


def testPileWithCoveredCodesGivesOneColourStonePerLevel() -> None:
    # A quarry of 2 whose codes cannot be read: the blob is 220 mm tall, so it is a pile of 2
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(pitchDeg=20.0), np.random.default_rng(1))
    pile: list[SceneBox] = [buildLyingBox(800.0, -100.0, 0.0, level, isMarkerCovered=True) for level in range(2)]
    details: VisionDetails = runScene(pile, setup)
    assert sorted(stone.level for stone in details.stones) == [0, 1]
    assert all(stone.source == DetectionSource.COLOR for stone in details.stones)
    for stone in details.stones:
        assert np.hypot(stone.centerMm[0] - 800.0, stone.centerMm[1] + 100.0) < 40.0
