"""Pinhole camera of the synthetic scenes, built with its own look-at maths.

It does not use geometry/poseTransforms.py on purpose: the tests compare that file with this one,
so a sign error cannot hide in both. Only for tests and demos: the robot never renders anything.
World frame of the scenes = robot frame: x forward, y left, z up, origin on the floor, in mm.
"""

import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class SceneCamera:
    """A camera placed in the world. A world point p is seen at rotation @ p + translation."""

    widthPx: int
    heightPx: int
    # 3x3 matrix with fx, fy, cx, cy, as in a real calibration
    cameraMatrix: np.ndarray
    # Lens distortion k1, k2, p1, p2, k3: all zeros for a perfect lens
    distCoeffs: np.ndarray
    # Rows: the camera axes (x right, y down, z forward) written in world coordinates
    rotation: np.ndarray
    translation: np.ndarray
    positionMm: np.ndarray


def buildCameraMatrix(widthPx: int, heightPx: int, horizontalFovDeg: float) -> np.ndarray:
    """Square pixels and the optical centre in the middle of the image."""
    focalPx: float = (widthPx / 2) / math.tan(math.radians(horizontalFovDeg) / 2)
    return np.array([[focalPx, 0.0, widthPx / 2], [0.0, focalPx, heightPx / 2], [0.0, 0.0, 1.0]])


def buildLookAtCamera(positionMm: tuple[float, float, float], targetMm: tuple[float, float, float],
                      cameraMatrix: np.ndarray, imageSize: tuple[int, int]) -> SceneCamera:
    """A camera at positionMm looking at targetMm, with no roll. imageSize is (width, height)."""
    position: np.ndarray = np.array(positionMm, dtype=np.float64)
    forward: np.ndarray = np.array(targetMm, dtype=np.float64) - position
    forward /= np.linalg.norm(forward)
    # The right of the camera is horizontal (no roll): forward x up. Looking straight down has no right
    right: np.ndarray = np.cross(forward, np.array([0.0, 0.0, 1.0]))
    if np.linalg.norm(right) < 1e-9:
        right = np.array([0.0, -1.0, 0.0])
    right /= np.linalg.norm(right)
    down: np.ndarray = np.cross(forward, right)
    rotation: np.ndarray = np.vstack([right, down, forward])
    return SceneCamera(imageSize[0], imageSize[1], cameraMatrix, np.zeros(5), rotation, -rotation @ position,
                       position)


def buildMountedCamera(mountMm: tuple[float, float, float], pitchDeg: float, yawDeg: float,
                       cameraMatrix: np.ndarray, imageSize: tuple[int, int]) -> SceneCamera:
    """A camera on the robot: pitch down and yaw left, written with plain trigonometry.

    The point straight ahead of the lens, one metre away, is the look-at target.
    """
    pitch: float = math.radians(pitchDeg)
    yaw: float = math.radians(yawDeg)
    ahead: tuple[float, float, float] = (
        math.cos(pitch) * math.cos(yaw),
        math.cos(pitch) * math.sin(yaw),
        -math.sin(pitch),
    )
    targetMm: tuple[float, float, float] = (
        mountMm[0] + 1000.0 * ahead[0],
        mountMm[1] + 1000.0 * ahead[1],
        mountMm[2] + 1000.0 * ahead[2],
    )
    return buildLookAtCamera(mountMm, targetMm, cameraMatrix, imageSize)


def projectWorldPoints(camera: SceneCamera, pointsMm: np.ndarray) -> np.ndarray:
    """N x 3 world points to N x 2 pixels, with the lens distortion of the camera."""
    rotationVector, _ = cv2.Rodrigues(camera.rotation)
    pixels, _ = cv2.projectPoints(pointsMm.reshape(-1, 1, 3).astype(np.float64), rotationVector,
                                  camera.translation, camera.cameraMatrix, camera.distCoeffs)
    return pixels.reshape(-1, 2)


def worldToCamera(camera: SceneCamera, pointsMm: np.ndarray) -> np.ndarray:
    """N x 3 world points to the camera frame (x right, y down, z forward), in mm."""
    return (camera.rotation @ pointsMm.reshape(-1, 3).T).T + camera.translation


def buildPixelRays(camera: SceneCamera) -> np.ndarray:
    """Height x width x 3: the direction of every pixel in the camera frame, scaled to z = 1.

    It ignores the distortion: the renderer draws a perfect image and bends it at the end.
    """
    columns, rows = np.meshgrid(np.arange(camera.widthPx), np.arange(camera.heightPx))
    pixels: np.ndarray = np.stack([columns, rows, np.ones_like(columns)], axis=-1).astype(np.float64)
    return pixels @ np.linalg.inv(camera.cameraMatrix).T
