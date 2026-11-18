"""Puts together everything the viewer draws on one image.

The screen asks this file for the final picture, and this file asks each overlay for its part.
Phase 3 adds the color overlay here.
"""

import numpy as np

from vision.apps.viewer.arucoOverlay import buildThresholdView, drawArucoDetection
from vision.apps.viewer.hudOverlay import (
    DrawStyle,
    addStatusBar,
    buildDrawStyle,
    buildStatusLines,
    drawHelp,
    putBoxedText,
)
from vision.apps.viewer.viewerState import ViewerFrame, ViewerMode, ViewerState


def drawViewerFrame(image: np.ndarray, viewerFrame: ViewerFrame, state: ViewerState) -> np.ndarray:
    """Returns a new picture: the image (or its threshold view) with the detections and the status bar."""
    style: DrawStyle = buildDrawStyle(image.shape[1])
    canvas: np.ndarray = buildThresholdView(image) if state.showThreshold else image.copy()
    if state.showThreshold:
        bottomY: int = image.shape[0] - style.lineHeightPx // 2
        putBoxedText(canvas, "threshold view (approx.): t to go back", (style.lineHeightPx // 2, bottomY),
                        style.warningColor, style)
    if state.mode in (ViewerMode.ARUCO, ViewerMode.BOTH):
        drawArucoDetection(canvas, viewerFrame.aruco, state.showRejected, style)
    if state.showHelp:
        drawHelp(canvas, style)
    return addStatusBar(canvas, buildStatusLines(viewerFrame, state, image, style), style)
