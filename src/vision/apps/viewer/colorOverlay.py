"""Draws what the colour + shape detector found, and the mask it works on.

Shared by the OpenCV viewer and the dashboard. Texts are plain ASCII (OpenCV fonts have no accents).
"""

import cv2
import numpy as np

from vision.apps.viewer.hudOverlay import DrawStyle, putBoxedText
from vision.common.detectionTypes import ColorCandidate, ColorDetection


def drawColorDetection(image: np.ndarray, detection: ColorDetection, showRejected: bool, style: DrawStyle) -> None:
    """Accepted blobs in orange with their score; with showRejected, the rejected ones in red with the reason."""
    if showRejected:
        for candidate in detection.rejected:
            drawCandidate(image, candidate, style.errorColor, f"no: {candidate.rejectReason}", style)
    for candidate in detection.candidates:
        pileText: str = f" pile {candidate.stackLevels}" if candidate.stackLevels > 1 else ""
        drawCandidate(image, candidate, style.colorStoneColor, f"color {candidate.score:.2f}{pileText}", style)


def drawCandidate(image: np.ndarray, candidate: ColorCandidate, color: tuple[int, int, int], label: str,
                  style: DrawStyle) -> None:
    """Outline of the blob, its centre and a label under its lowest point."""
    contour: np.ndarray = candidate.contourPx.reshape(-1, 1, 2).astype(np.int32)
    cv2.polylines(image, [contour], True, color, 2, cv2.LINE_AA)
    centerPx: tuple[int, int] = (round(candidate.centerPx[0]), round(candidate.centerPx[1]))
    cv2.drawMarker(image, centerPx, color, cv2.MARKER_TILTED_CROSS, max(6, style.lineHeightPx // 2), 1, cv2.LINE_AA)
    labelX: int = int(candidate.contourPx[:, 0].min())
    labelY: int = min(image.shape[0] - 4, int(candidate.contourPx[:, 1].max()) + style.lineHeightPx)
    putBoxedText(image, label, (labelX, labelY), color, style)


def buildMaskView(image: np.ndarray, mask: np.ndarray, style: DrawStyle) -> np.ndarray:
    """The picture darkened, with the pixels taken as cardboard (or label) painted orange on top."""
    if mask.shape[:2] != image.shape[:2]:
        return image.copy()
    darkened: np.ndarray = (image * 0.35).astype(np.uint8)
    painted: np.ndarray = darkened.copy()
    painted[mask > 0] = style.colorStoneColor
    return cv2.addWeighted(painted, 0.6, darkened, 0.4, 0)
