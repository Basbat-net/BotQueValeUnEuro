"""Tests of the ArUco detector with pictures drawn by the computer: no camera needed.

Run from the src/ folder:
    python3 -m pytest ../tests/vision
"""

import cv2
import numpy as np

from vision.aruco.arucoStoneDetector import ArucoStoneDetector
from vision.common.visionConfig import ArucoConfig


def buildImageWithMarker(markerId: int, sidePx: int, topLeft: tuple[int, int], quarterTurns: int = 0) -> np.ndarray:
    """Gray 640 x 480 picture with one marker on a white label, like the ones of the stones."""
    labelMarginPx: int = sidePx // 6
    dictionary: cv2.aruco.Dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    marker: np.ndarray = np.rot90(cv2.aruco.generateImageMarker(dictionary, markerId, sidePx), quarterTurns)
    image: np.ndarray = np.full((480, 640, 3), 128, dtype=np.uint8)
    x, y = topLeft
    image[y - labelMarginPx : y + sidePx + labelMarginPx, x - labelMarginPx : x + sidePx + labelMarginPx] = 255
    image[y : y + sidePx, x : x + sidePx] = marker[:, :, np.newaxis]
    return image


def testFindsStoneMarker() -> None:
    image: np.ndarray = buildImageWithMarker(13, 120, (100, 100))
    result = ArucoStoneDetector(ArucoConfig()).detect(image)
    assert len(result.stoneFaces) == 1
    assert result.otherMarkers == []
    face = result.stoneFaces[0]
    assert face.cornersPx.shape == (4, 2)
    # Drawn with a side of 120 px, from x = y = 100: the center is at 160, 160
    assert abs(face.sidePx - 120) < 2
    assert abs(face.centerPx[0] - 160) < 2 and abs(face.centerPx[1] - 160) < 2
    # Phase 2a: no pose without a calibrated camera
    assert not face.hasPose


def testKeepsCornerOrderOfTheCode() -> None:
    # Turned 180 degrees: the top-left corner of the code is now at the bottom-right of the picture
    image: np.ndarray = buildImageWithMarker(13, 120, (100, 100), quarterTurns=2)
    firstCorner: np.ndarray = ArucoStoneDetector(ArucoConfig()).detect(image).stoneFaces[0].cornersPx[0]
    assert firstCorner[0] > 200 and firstCorner[1] > 200


def testOtherIdIsNotAStone() -> None:
    image: np.ndarray = buildImageWithMarker(7, 120, (100, 100))
    result = ArucoStoneDetector(ArucoConfig()).detect(image)
    assert result.stoneFaces == []
    assert [marker.markerId for marker in result.otherMarkers] == [7]


def testEmptyAndBlankPicturesGiveNothing() -> None:
    detector: ArucoStoneDetector = ArucoStoneDetector(ArucoConfig())
    emptyResult = detector.detect(np.zeros((0, 0, 3), dtype=np.uint8))
    blankResult = detector.detect(np.full((480, 640, 3), 128, dtype=np.uint8))
    assert emptyResult.stoneFaces == [] and emptyResult.otherMarkers == []
    assert blankResult.stoneFaces == [] and blankResult.otherMarkers == []


def testWrongConfigIsReportedNotRaised() -> None:
    image: np.ndarray = buildImageWithMarker(13, 120, (100, 100))
    # An unknown dictionary, a name that is not a dictionary, and an ID out of DICT_4X4_50 (0 to 49)
    wrongConfigs: list[ArucoConfig] = [
        ArucoConfig(dictionaryName="DICT_9X9_50"),
        ArucoConfig(dictionaryName="getPredefinedDictionary"),
        ArucoConfig(stoneMarkerId=50),
    ]
    for config in wrongConfigs:
        detector: ArucoStoneDetector = ArucoStoneDetector(config)
        assert not detector.isReady
        assert detector.lastError != ""
        assert detector.detect(image).stoneFaces == []
