"""A ready synthetic set-up: camera on a robot, stone textures, and the config and calibration that match.

Used by the tests and by syntheticVideoApp, so every synthetic run uses the same camera.
The camera is built with sceneCamera (its own maths); the config only repeats the same numbers,
so the black box measures with poseTransforms what sceneCamera drew.
"""

from dataclasses import dataclass

import numpy as np

from vision.common.detectionConfig import CameraMountConfig
from vision.common.visionConfig import CameraCalibration, VisionConfig
from vision.simulation.boxTexture import StoneTextures, buildStoneTextures
from vision.simulation.sceneCamera import SceneCamera, buildCameraMatrix, buildMountedCamera


@dataclass
class SceneSetupConfig:
    """Numbers of the synthetic camera: like the robot camera of the proposal, 300 mm high, 30 degrees down."""

    widthPx: int = 640
    heightPx: int = 480
    horizontalFovDeg: float = 70.0
    mountHeightMm: float = 300.0
    pitchDeg: float = 30.0
    yawDeg: float = 0.0
    # The printed code and its white label (the real ones are still to be measured)
    markerSideMm: float = 80.0
    labelSideMm: float = 104.0
    texturePxPerMm: float = 3.0
    # Lens distortion k1, k2, p1, p2, k3 of the synthetic camera (all zero: a perfect lens)
    distortion: tuple[float, float, float, float, float] = (0.0, 0.0, 0.0, 0.0, 0.0)


@dataclass
class SceneSetup:
    """Everything needed to draw a scene and to measure it with the black box."""

    camera: SceneCamera
    textures: StoneTextures
    config: VisionConfig
    calibration: CameraCalibration


def buildSceneSetup(setupConfig: SceneSetupConfig, randomGenerator: np.random.Generator) -> SceneSetup:
    """The synthetic camera and a VisionConfig whose mount and calibration describe that same camera."""
    imageSize: tuple[int, int] = (setupConfig.widthPx, setupConfig.heightPx)
    cameraMatrix: np.ndarray = buildCameraMatrix(setupConfig.widthPx, setupConfig.heightPx,
                                                 setupConfig.horizontalFovDeg)
    camera: SceneCamera = buildMountedCamera((0.0, 0.0, setupConfig.mountHeightMm), setupConfig.pitchDeg,
                                             setupConfig.yawDeg, cameraMatrix, imageSize)
    camera.distCoeffs = np.array(setupConfig.distortion, dtype=np.float64)
    textures: StoneTextures = buildStoneTextures(setupConfig.markerSideMm, setupConfig.labelSideMm, 13,
                                                 setupConfig.texturePxPerMm, randomGenerator)
    config: VisionConfig = VisionConfig()
    config.showWindow = False
    config.aruco.markerSideMm = setupConfig.markerSideMm
    config.cameraMount = CameraMountConfig(True, 0.0, 0.0, setupConfig.mountHeightMm, setupConfig.pitchDeg,
                                           setupConfig.yawDeg, 0.0)
    calibration: CameraCalibration = CameraCalibration(cameraMatrix.copy(), camera.distCoeffs.copy(),
                                                       setupConfig.widthPx, setupConfig.heightPx, 0.0)
    return SceneSetup(camera, textures, config, calibration)
