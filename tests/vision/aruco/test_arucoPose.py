"""Tests of the pose of the stones (phase 2b) on synthetic scenes with a known truth.

The scene camera is built with simulation/sceneCamera.py (its own maths), and the black box
measures with geometry/poseTransforms.py: if one of them had a sign wrong, these tests fail.
"""

import numpy as np
import pytest

from vision.blackBoxFactory import buildVisionBlackBox
from vision.common.detectionTypes import PipelineOptions, StoneEstimate
from vision.common.visionTypes import FrameInput
from vision.simulation.boxTexture import SceneBox, buildLyingBox, buildStandingBox
from vision.simulation.sceneRenderer import SceneOptions, renderScene
from vision.simulation.sceneSetup import SceneSetup, SceneSetupConfig, buildSceneSetup


def measureArucoStones(setup: SceneSetup, boxes: list[SceneBox], options: SceneOptions) -> list[StoneEstimate]:
    """Draws the scene and returns the stones found by the ArUco detector alone."""
    randomGenerator: np.random.Generator = np.random.default_rng(7)
    image: np.ndarray = renderScene(setup.camera, boxes, setup.textures, options, randomGenerator)
    blackBox = buildVisionBlackBox(setup.config, setup.calibration)
    return blackBox.processWithDetails(FrameInput(image, 0), PipelineOptions(useColor=False)).stones


def yawErrorDeg(measuredDeg: float, trueDeg: float) -> float:
    """Difference between two line angles (180 degrees apart are the same line)."""
    return abs((measuredDeg - trueDeg + 90.0) % 180.0 - 90.0)


# Near (code 40-70 px wide): 15 mm. Far (about 20 px): the error grows, 30-40 mm
@pytest.mark.parametrize("xMm, yMm, yawDeg, maxErrorMm", [
    (550.0, 80.0, 20.0, 15.0),
    (650.0, -200.0, -50.0, 15.0),
    (800.0, 150.0, 75.0, 15.0),
    (1200.0, 100.0, 0.0, 30.0),
    (1500.0, -150.0, 35.0, 40.0),
])
def testLyingStoneIsFoundWhereItIs(xMm: float, yMm: float, yawDeg: float, maxErrorMm: float) -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    stones: list[StoneEstimate] = measureArucoStones(setup, [buildLyingBox(xMm, yMm, yawDeg)],
                                                     SceneOptions(jpegQuality=85))
    assert len(stones) == 1
    stone: StoneEstimate = stones[0]
    assert np.hypot(stone.centerMm[0] - xMm, stone.centerMm[1] - yMm) < maxErrorMm
    assert stone.isYawDefined and yawErrorDeg(stone.yawDeg, yawDeg) < 3.0
    assert stone.level == 0


def testPoseSurvivesBlurNoiseAndALensWithDistortion() -> None:
    setupConfig: SceneSetupConfig = SceneSetupConfig(distortion=(-0.25, 0.08, 0.0, 0.0, 0.0))
    setup: SceneSetup = buildSceneSetup(setupConfig, np.random.default_rng(2))
    degraded: SceneOptions = SceneOptions(jpegQuality=70, blurKernelPx=3, noiseSigma=3.0)
    stones: list[StoneEstimate] = measureArucoStones(setup, [buildLyingBox(700.0, 200.0, -30.0)], degraded)
    assert len(stones) == 1
    assert np.hypot(stones[0].centerMm[0] - 700.0, stones[0].centerMm[1] - 200.0) < 15.0
    assert yawErrorDeg(stones[0].yawDeg, -30.0) < 3.0


def testSideFaceSeenAtAnAngleIsNotTiltedNorFloating() -> None:
    # Here the wrong pose solution has the smaller error (found while developing): the physics decides
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(2))
    stones: list[StoneEstimate] = measureArucoStones(setup, [buildLyingBox(800.0, -150.0, -50.0)],
                                                     SceneOptions(jpegQuality=85))
    assert len(stones) == 1
    assert abs(stones[0].centerMm[2] - 55.0) < 10.0
    assert np.hypot(stones[0].centerMm[0] - 800.0, stones[0].centerMm[1] + 150.0) < 15.0


def testStandingStoneIsFoundWithoutYaw() -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(3))
    stones: list[StoneEstimate] = measureArucoStones(setup, [buildStandingBox(700.0, 200.0, 10.0)],
                                                     SceneOptions(jpegQuality=85))
    assert len(stones) == 1
    assert not stones[0].isYawDefined
    assert abs(stones[0].centerMm[2] - 160.0) < 10.0


def testQuarryGivesOneStonePerLevel() -> None:
    # A camera 300 mm high looking 30 degrees down does not see the code of the third stone
    # (found with these scenes, a point for where the camera is mounted): here it looks 10 degrees down
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(pitchDeg=10.0), np.random.default_rng(4))
    quarry: list[SceneBox] = [buildLyingBox(800.0, 0.0, 90.0, level) for level in range(3)]
    stones: list[StoneEstimate] = measureArucoStones(setup, quarry, SceneOptions(jpegQuality=85))
    assert sorted(stone.level for stone in stones) == [0, 1, 2]
    for stone in stones:
        assert np.hypot(stone.centerMm[0] - 800.0, stone.centerMm[1]) < 15.0


def testCalibrationOfAnotherSizeGivesNoPose() -> None:
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(5))
    setup.calibration.widthPx = 1280
    stones: list[StoneEstimate] = measureArucoStones(setup, [buildLyingBox(600.0, 0.0, 0.0)], SceneOptions())
    assert stones == []
