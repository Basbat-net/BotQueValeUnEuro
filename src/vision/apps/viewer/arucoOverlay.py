"""Draws what the ArUco detector found, and the black and white image it searches in.

Only the viewer uses it: the detectors never draw, because the robot has no screen.
"""

import cv2
import numpy as np

from vision.apps.viewer.hudOverlay import DrawStyle, putBoxedText
from vision.common.detectionTypes import ArucoDetection, ArucoMarker


def drawArucoDetection(image: np.ndarray, detection: ArucoDetection, showRejected: bool, style: DrawStyle) -> None:
    """Stone markers in green, other IDs in grey and, if asked, the rejected squares in red."""
    if showRejected:
        for cornersPx in detection.rejectedCornersPx:
            cv2.polylines(image, [np.round(cornersPx).astype(np.int32)], True, style.errorColor, 1, cv2.LINE_AA)
    for marker in detection.otherMarkers:
        drawMarker(image, marker, style.neutralColor, f"id {marker.markerId}", style)
    for marker in detection.stoneFaces:
        drawMarker(image, marker, style.goodColor, f"{marker.markerId} | {marker.sidePx:.0f} px", style)


def drawMarker(image: np.ndarray, marker: ArucoMarker, color: tuple[int, int, int], label: str,
               style: DrawStyle) -> None:
    """Outline, first corner, center and a label above the marker."""
    cornersPx: np.ndarray = np.round(marker.cornersPx).astype(np.int32)
    centerPx: tuple[int, int] = (round(marker.centerPx[0]), round(marker.centerPx[1]))
    cv2.polylines(image, [cornersPx], True, color, 2, cv2.LINE_AA)
    # Corner 0 is the top-left of the printed code: if the code is upside down, it is not top-left on screen
    cornerZero: tuple[int, int] = (int(cornersPx[0][0]), int(cornersPx[0][1]))
    cv2.circle(image, cornerZero, max(3, style.lineHeightPx // 4), style.cornerZeroColor, cv2.FILLED, cv2.LINE_AA)
    cv2.drawMarker(image, centerPx, color, cv2.MARKER_CROSS, max(6, style.lineHeightPx // 2), 1, cv2.LINE_AA)
    # Label just above the highest corner, but never out of the image
    labelX: int = int(cornersPx[:, 0].min())
    labelY: int = max(style.lineHeightPx, int(cornersPx[:, 1].min()) - style.lineHeightPx // 3)
    putBoxedText(image, label, (labelX, labelY), color, style)


def buildThresholdView(image: np.ndarray) -> np.ndarray:
    """About the black and white image where ArUco looks for squares (dark parts become white).

    OpenCV tries several window sizes (from adaptiveThreshWinSizeMin to Max): this shows the second one.
    With little light or reflections, the black border of the code breaks here and the code is lost.
    """
    # Same defaults as the detector, so the view does not hide numbers of its own
    parameters: cv2.aruco.DetectorParameters = cv2.aruco.DetectorParameters()
    windowSizePx: int = min(
        parameters.adaptiveThreshWinSizeMin + parameters.adaptiveThreshWinSizeStep,
        parameters.adaptiveThreshWinSizeMax,
    )
    # The window of an adaptive threshold must have an odd size: | 1 turns an even number into the next odd one
    windowSizePx = windowSizePx | 1
    grayImage: np.ndarray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binaryImage: np.ndarray = cv2.adaptiveThreshold(
        grayImage,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        windowSizePx,
        parameters.adaptiveThreshConstant,
    )
    # Back to 3 channels, so the colored drawings can go on top
    return cv2.cvtColor(binaryImage, cv2.COLOR_GRAY2BGR)
