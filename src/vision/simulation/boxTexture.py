"""Pictures of the faces of a stone and the boxes placed in a synthetic scene.

The large faces are kraft cardboard with a white label and the ArUco 13 in the middle,
oriented as in Figure 5 of the rules: the x axis of the code along the 320 mm side.
"""

import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class StoneTextures:
    """The three kinds of faces of a stone, at pxPerMm pixels per millimetre."""

    labelledFace: np.ndarray
    # The same face with something grey over the code: it cannot be read
    coveredFace: np.ndarray
    endFace: np.ndarray
    pxPerMm: float


@dataclass
class SceneBox:
    """One stone in the scene. rotation columns = box axes in the world (x along the 320 mm side)."""

    centerMm: np.ndarray
    rotation: np.ndarray
    isMarkerCovered: bool = False
    # Sizes of the box: length along its x axis, and the square side of the other two
    lengthMm: float = 320.0
    widthMm: float = 110.0
    tags: list[str] = field(default_factory=list)


def buildKraftTexture(widthPx: int, heightPx: int, randomGenerator: np.random.Generator) -> np.ndarray:
    """Brown cardboard with a little noise and the faint stripes of the corrugation."""
    # Kraft brown in BGR order, the one OpenCV uses
    kraftColor: np.ndarray = np.array([105.0, 150.0, 192.0])
    noise: np.ndarray = randomGenerator.normal(0.0, 5.0, (heightPx, widthPx, 1))
    stripes: np.ndarray = 4.0 * np.sin(np.arange(widthPx) * 0.9)[np.newaxis, :, np.newaxis]
    return np.clip(kraftColor + noise + stripes, 0, 255).astype(np.uint8)


def buildStoneTextures(markerSideMm: float, labelSideMm: float, markerId: int, pxPerMm: float,
                       randomGenerator: np.random.Generator) -> StoneTextures:
    """Draws the faces of a 320 x 110 x 110 mm stone. The code is a 4x4 ArUco (DICT_4X4_50)."""
    lengthMm: float = 320.0
    widthMm: float = 110.0
    lengthPx: int = round(lengthMm * pxPerMm)
    widthPx: int = round(widthMm * pxPerMm)
    labelledFace: np.ndarray = buildKraftTexture(lengthPx, widthPx, randomGenerator)
    labelPx: int = min(round(labelSideMm * pxPerMm), widthPx)
    markerPx: int = round(markerSideMm * pxPerMm)
    labelLeft: int = (lengthPx - labelPx) // 2
    labelTop: int = (widthPx - labelPx) // 2
    labelledFace[labelTop : labelTop + labelPx, labelLeft : labelLeft + labelPx] = 245
    dictionary: cv2.aruco.Dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker: np.ndarray = cv2.aruco.generateImageMarker(dictionary, markerId, markerPx)
    markerLeft: int = (lengthPx - markerPx) // 2
    markerTop: int = (widthPx - markerPx) // 2
    labelledFace[markerTop : markerTop + markerPx, markerLeft : markerLeft + markerPx] = marker[:, :, np.newaxis]
    coveredFace: np.ndarray = labelledFace.copy()
    # A grey hand-sized patch over most of the code
    coverMarginPx: int = markerPx // 8
    coveredFace[markerTop - coverMarginPx : markerTop + markerPx + coverMarginPx,
                markerLeft + markerPx // 4 : markerLeft + markerPx + coverMarginPx] = (90, 90, 100)
    endFace: np.ndarray = buildKraftTexture(widthPx, widthPx, randomGenerator)
    return StoneTextures(labelledFace, coveredFace, endFace, pxPerMm)


def buildLyingBox(xMm: float, yMm: float, yawDeg: float, level: int = 0, isMarkerCovered: bool = False) -> SceneBox:
    """A stone lying on the floor (level 0) or on top of others: long side horizontal, turned yawDeg."""
    yaw: float = math.radians(yawDeg)
    longAxis: np.ndarray = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    sideAxis: np.ndarray = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    upAxis: np.ndarray = np.array([0.0, 0.0, 1.0])
    centerMm: np.ndarray = np.array([xMm, yMm, 55.0 + 110.0 * level])
    return SceneBox(centerMm, np.column_stack([longAxis, sideAxis, upAxis]), isMarkerCovered)


def buildStandingBox(xMm: float, yMm: float, yawDeg: float) -> SceneBox:
    """A stone standing on one of its small faces: long side vertical."""
    yaw: float = math.radians(yawDeg)
    longAxis: np.ndarray = np.array([0.0, 0.0, 1.0])
    sideAxis: np.ndarray = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    return SceneBox(np.array([xMm, yMm, 160.0]), np.column_stack([longAxis, sideAxis, np.cross(longAxis, sideAxis)]))


def buildBoxFaces(box: SceneBox) -> list[tuple[np.ndarray, np.ndarray, str]]:
    """The 6 faces of a box: (4 corners in the world, outward normal, kind of face).

    The corners follow the picture of the face: top-left, top-right, bottom-right, bottom-left.
    Along the picture width goes the axis a; down the picture goes b = a x normal, so the printed
    code keeps its x axis on a and its z axis on the outward normal, as a real printed label does.
    """
    faces: list[tuple[np.ndarray, np.ndarray, str]] = []
    halfLength: float = box.lengthMm / 2
    halfWidth: float = box.widthMm / 2
    longAxis, sideAxis, thirdAxis = box.rotation[:, 0], box.rotation[:, 1], box.rotation[:, 2]
    largeFaceKind: str = "covered" if box.isMarkerCovered else "labelled"
    for normal in (sideAxis, -sideAxis, thirdAxis, -thirdAxis):
        faceCenter: np.ndarray = box.centerMm + normal * halfWidth
        downAxis: np.ndarray = np.cross(longAxis, normal)
        faces.append((buildFaceCorners(faceCenter, longAxis * halfLength, downAxis * halfWidth), normal, largeFaceKind))
    for normal in (longAxis, -longAxis):
        faceCenter = box.centerMm + normal * halfLength
        downAxis = np.cross(sideAxis, normal)
        faces.append((buildFaceCorners(faceCenter, sideAxis * halfWidth, downAxis * halfWidth), normal, "end"))
    return faces


def buildFaceCorners(faceCenter: np.ndarray, halfAcross: np.ndarray, halfDown: np.ndarray) -> np.ndarray:
    """4 x 3 corners: top-left, top-right, bottom-right, bottom-left of the face picture."""
    return np.array([
        faceCenter - halfAcross - halfDown,
        faceCenter + halfAcross - halfDown,
        faceCenter + halfAcross + halfDown,
        faceCenter - halfAcross + halfDown,
    ])
