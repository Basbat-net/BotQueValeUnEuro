"""Status bar and help of the viewer, and the colors and sizes of everything it draws.

The texts are plain ASCII: the OpenCV fonts cannot draw accents or symbols.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from vision.apps.viewer.viewerState import (
    SessionStats,
    ViewerFrame,
    ViewerMode,
    ViewerState,
    stoneRatePercent,
)
from vision.common.detectionTypes import ArucoDetection, VisionDetails


@dataclass
class DrawStyle:
    """Colors (in BGR order, as OpenCV uses them) and sizes of the drawings, in one place."""

    fontScale: float = 0.5
    lineHeightPx: int = 22
    textColor: tuple[int, int, int] = (255, 255, 255)
    barColor: tuple[int, int, int] = (30, 30, 30)
    goodColor: tuple[int, int, int] = (80, 220, 80)
    warningColor: tuple[int, int, int] = (0, 170, 255)
    errorColor: tuple[int, int, int] = (60, 60, 255)
    neutralColor: tuple[int, int, int] = (170, 170, 170)
    # The first corner of a marker (top-left of the printed code), to see how it reads the rotation
    cornerZeroColor: tuple[int, int, int] = (255, 0, 255)
    # Stones by source: ArUco uses goodColor, colour only is orange, both detectors is cyan
    colorStoneColor: tuple[int, int, int] = (0, 140, 255)
    bothColor: tuple[int, int, int] = (230, 200, 0)


def buildDrawStyle(imageWidthPx: int) -> DrawStyle:
    """Text grows with the image, so it reads the same at 640 and at 1280 px wide."""
    referenceWidthPx: int = 1280
    referenceFontScale: float = 0.6
    minimumFontScale: float = 0.45
    fontScale: float = max(minimumFontScale, referenceFontScale * imageWidthPx / referenceWidthPx)
    # A Hershey letter is about 22 px high at scale 1: the line leaves some room around it
    return DrawStyle(fontScale=fontScale, lineHeightPx=int(40 * fontScale))


def putBoxedText(image: np.ndarray, text: str, origin: tuple[int, int], color: tuple[int, int, int],
                 style: DrawStyle) -> None:
    """Writes text on a dark box, so it can be read over any background. origin is the bottom-left."""
    font: int = cv2.FONT_HERSHEY_SIMPLEX
    paddingPx: int = 2
    (textWidthPx, textHeightPx), baselinePx = cv2.getTextSize(text, font, style.fontScale, 1)
    topLeft: tuple[int, int] = (origin[0] - paddingPx, origin[1] - textHeightPx - paddingPx)
    bottomRight: tuple[int, int] = (origin[0] + textWidthPx + paddingPx, origin[1] + baselinePx)
    cv2.rectangle(image, topLeft, bottomRight, style.barColor, cv2.FILLED)
    cv2.putText(image, text, origin, font, style.fontScale, color, 1, cv2.LINE_AA)


def buildStatusLines(viewerFrame: ViewerFrame, state: ViewerState, image: np.ndarray,
                     style: DrawStyle) -> list[tuple[str, tuple[int, int, int]]]:
    """The lines of the status bar, each one with its color. Always the same number of lines."""
    imageHeight, imageWidth = image.shape[:2]
    stats: SessionStats = state.stats
    details: VisionDetails = viewerFrame.details
    aruco: ArucoDetection = details.aruco
    arucoText: str = f"aruco {aruco.processingTimeMs:.1f} ms" if state.mode != ViewerMode.COLOR else "no aruco"
    colorText: str = f"color {details.color.processingTimeMs:.1f} ms" if state.mode != ViewerMode.ARUCO else "no color"
    otherIds: list[int] = sorted({marker.markerId for marker in aruco.otherMarkers})
    sideText: str = f", side {stats.minSidePx:.0f}-{stats.maxSidePx:.0f} px" if stats.framesWithStone > 0 else ""
    stateText: str = ("PAUSED (space: play, n: next)  " if state.isPaused else "") + ("REC  " if state.isRecording else "")
    isPoseUsable: bool = details.isCalibrationUsable and details.isMountMeasured
    calibrationColor: tuple[int, int, int] = style.goodColor if isPoseUsable else style.warningColor
    mountText: str = "" if details.isMountMeasured else " | camera mount NOT MEASURED: positions are provisional"
    stateColor: tuple[int, int, int] = style.errorColor if state.isRecording else style.warningColor
    sourceText: str = f"{state.mode.value} | {stats.framesPerSecond:.1f} fps | {arucoText} | {colorText}"
    detectionText: str = (f"now: {len(details.stones)} stones ({details.result.status.name}) | "
                          f"{len(aruco.stoneFaces)} codes, {len(details.color.candidates)} blobs, other ids {otherIds}")
    return [
        (f"{sourceText} | {imageWidth}x{imageHeight} | h: help", style.textColor),
        (details.calibrationText + mountText, calibrationColor),
        (f"{detectionText}, {len(aruco.rejectedCornersPx)} rejected", style.textColor),
        (f"session: stone seen in {stoneRatePercent(stats):.0f}% of {stats.processedFrames} frames{sideText}",
         style.textColor),
        (stateText + state.message, stateColor),
    ]


def addStatusBar(image: np.ndarray, lines: list[tuple[str, tuple[int, int, int]]], style: DrawStyle) -> np.ndarray:
    """Returns a new image: a dark band with the lines on top, and the image below it."""
    marginPx: int = style.lineHeightPx // 3
    bandHeightPx: int = len(lines) * style.lineHeightPx + marginPx
    band: np.ndarray = np.full((bandHeightPx, image.shape[1], 3), style.barColor, dtype=np.uint8)
    for lineIndex, (text, color) in enumerate(lines):
        baselineY: int = (lineIndex + 1) * style.lineHeightPx - marginPx // 2
        putBoxedText(band, text, (marginPx, baselineY), color, style)
    return np.vstack([band, image])


def drawHelp(image: np.ndarray, style: DrawStyle) -> None:
    """Draws the list of keys over the image, on a dark see-through box."""
    helpLines: list[str] = [
        "1 ArUco   2 color   3 both",
        "space    pause / play",
        "n        next frame (when paused)",
        "x        show rejected candidates (ArUco and color)",
        "t        threshold view (what ArUco sees)",
        "m        mask view (what color takes as cardboard)",
        "r        start / stop recording",
        "s        snapshot (raw + annotated)",
        "c        reset session numbers",
        "h        hide this help",
        "q / Esc  quit",
    ]
    # How much of the box covers the image: 1 hides it, 0 leaves it untouched
    boxOpacity: float = 0.7
    boxHeightPx: int = (len(helpLines) + 1) * style.lineHeightPx
    boxWidthPx: int = min(image.shape[1], int(style.lineHeightPx * 18))
    overlay: np.ndarray = image.copy()
    cv2.rectangle(overlay, (0, 0), (boxWidthPx, boxHeightPx), style.barColor, cv2.FILLED)
    cv2.addWeighted(overlay, boxOpacity, image, 1 - boxOpacity, 0, dst=image)
    for lineIndex, text in enumerate(helpLines):
        putBoxedText(image, text, (style.lineHeightPx // 2, (lineIndex + 1) * style.lineHeightPx), style.textColor,
                        style)
