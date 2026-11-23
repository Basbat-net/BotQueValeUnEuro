"""Puts together everything the viewer draws on one image.

The screen asks this file for the final picture, and this file asks each overlay for its part:
ArUco markers, colour blobs, the wire boxes of the stones and the status bar.
"""

import numpy as np

from vision.apps.viewer.arucoOverlay import buildThresholdView, drawArucoDetection
from vision.apps.viewer.colorOverlay import buildMaskView, drawColorDetection
from vision.apps.viewer.hudOverlay import (
    DrawStyle,
    addStatusBar,
    buildDrawStyle,
    buildStatusLines,
    drawHelp,
    putBoxedText,
)
from vision.apps.viewer.poseOverlay import drawProjectedStones
from vision.apps.viewer.viewerState import ViewerFrame, ViewerMode, ViewerState


def drawViewerFrame(image: np.ndarray, viewerFrame: ViewerFrame, state: ViewerState) -> np.ndarray:
    """Returns a new picture: the image (or a debug view of it) with the detections and the status bar."""
    style: DrawStyle = buildDrawStyle(image.shape[1])
    canvas: np.ndarray = drawDetections(image, viewerFrame, state)
    if state.showHelp:
        drawHelp(canvas, style)
    return addStatusBar(canvas, buildStatusLines(viewerFrame, state, image, style), style)


def drawDetections(image: np.ndarray, viewerFrame: ViewerFrame, state: ViewerState) -> np.ndarray:
    """The picture with what the detectors found, without the status bar (the dashboard has its own panels)."""
    style: DrawStyle = buildDrawStyle(image.shape[1])
    canvas: np.ndarray = buildBackground(image, viewerFrame, state, style)
    if state.mode in (ViewerMode.COLOR, ViewerMode.BOTH):
        drawColorDetection(canvas, viewerFrame.details.color, state.showRejected, style)
    if state.mode in (ViewerMode.ARUCO, ViewerMode.BOTH):
        drawArucoDetection(canvas, viewerFrame.details.aruco, state.showRejected, style)
    drawProjectedStones(canvas, viewerFrame.projectedStones, style)
    return canvas


def buildBackground(image: np.ndarray, viewerFrame: ViewerFrame, state: ViewerState, style: DrawStyle) -> np.ndarray:
    """The picture to draw on: the image itself, or the threshold view (t), or the colour mask (m)."""
    if state.showMask:
        canvas: np.ndarray = buildMaskView(image, viewerFrame.details.color.maskPx, style)
        viewName: str = "mask view: what color takes as cardboard (m to go back)"
    elif state.showThreshold:
        canvas = buildThresholdView(image)
        viewName = "threshold view (approx.): t to go back"
    else:
        return image.copy()
    putBoxedText(canvas, viewName, (style.lineHeightPx // 2, image.shape[0] - style.lineHeightPx // 2),
                 style.warningColor, style)
    return canvas
