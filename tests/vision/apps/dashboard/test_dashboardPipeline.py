"""Tests of what the dashboard does with the images, without any window (no Qt, no screen)."""

import time
from pathlib import Path

import cv2
import numpy as np

from vision.apps.dashboard.dashboardPipeline import DashboardPipeline
from vision.common.visionConfig import FrameSourceMode
from vision.common.visionTypes import DetectionSource
from vision.simulation.boxTexture import buildLyingBox
from vision.simulation.sceneRenderer import SceneOptions, renderScene
from vision.simulation.sceneSetup import SceneSetup, SceneSetupConfig, buildSceneSetup


def buildPipeline(folder: Path, frameCount: int) -> DashboardPipeline:
    """A pipeline reading a folder of synthetic pictures of one stone moving forward, as fast as it can."""
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(), np.random.default_rng(1))
    for index in range(frameCount):
        boxes = [buildLyingBox(800.0 - 20.0 * index, 50.0, 30.0)]
        image: np.ndarray = renderScene(setup.camera, boxes, setup.textures, SceneOptions(), np.random.default_rng(2))
        cv2.imwrite(str(folder / f"frame{index:03d}.png"), image)
    calibrationPath: Path = folder / "calibration.json"
    calibrationPath.write_text(
        '{"cameraMatrix": ' + str(setup.calibration.cameraMatrix.tolist()) + ', "distCoeffs": [0, 0, 0, 0, 0], '
        '"widthPx": 640, "heightPx": 480, "reprojectionErrorPx": 0.0}', encoding="utf-8")
    setup.config.frameSource.mode = FrameSourceMode.IMAGES
    setup.config.frameSource.imagesFolder = str(folder)
    setup.config.calibrationFilePath = str(calibrationPath)
    setup.config.viewer.playbackFramesPerSecond = 0.0
    return DashboardPipeline(setup.config)


def runUntil(pipeline: DashboardPipeline, frameCount: int, timeoutSeconds: float = 10.0) -> None:
    deadline: float = time.perf_counter() + timeoutSeconds
    while pipeline.processedCount < frameCount and time.perf_counter() < deadline:
        pipeline.update()


def testEveryPictureIsProcessedAndTheTwinFollowsTheStone(tmp_path: Path) -> None:
    pipeline: DashboardPipeline = buildPipeline(tmp_path, 6)
    assert pipeline.start() == ""
    runUntil(pipeline, 6)
    pipeline.stop()
    assert pipeline.processedCount == 6
    assert len(pipeline.tracks) == 1 and pipeline.tracks[0].source == DetectionSource.BOTH
    # The twin is smoothed: a 50 % mix lags about one step (20 mm) behind a steady move, never ahead of it
    assert 690.0 < pipeline.tracks[0].centerMm[0] < 740.0
    assert pipeline.describeSource() == "end of the video or folder"


def testChangingTheModeWhilePausedRedoesTheSameImage(tmp_path: Path) -> None:
    pipeline: DashboardPipeline = buildPipeline(tmp_path, 2)
    assert pipeline.start() == ""
    runUntil(pipeline, 1)
    pipeline.setPaused(True)
    countBefore: int = pipeline.processedCount
    pipeline.setMode("aruco")
    assert pipeline.update()
    assert pipeline.processedCount == countBefore
    assert [track.source for track in pipeline.tracks] == [DetectionSource.ARUCO]
    pipeline.stop()
