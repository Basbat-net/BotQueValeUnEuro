"""State of the viewer app: what is shown, if it is paused, and the numbers of the session.

No OpenCV here: keys arrive as numbers, so this logic can be tested without a screen.
"""

import time
from dataclasses import dataclass, field
from enum import Enum

from vision.common.detectionTypes import ArucoDetection


class ViewerMode(Enum):
    """Which detectors run. The value is the text shown in the status bar."""

    ARUCO = "ArUco"
    COLOR = "color"
    BOTH = "ArUco + color"


class ViewerAction(Enum):
    """What a key asks for, besides the state changes that applyKey already makes."""

    NONE = 0
    QUIT = 1
    SNAPSHOT = 2
    TOGGLE_RECORDING = 3


@dataclass
class SessionStats:
    """Numbers of the session, counted on new frames only (not while paused)."""

    processedFrames: int = 0
    framesWithStone: int = 0
    # Smallest and largest side of a stone marker seen, in px. 0 until the first one
    minSidePx: float = 0.0
    maxSidePx: float = 0.0
    framesPerSecond: float = 0.0
    lastFrameTime: float = 0.0


@dataclass
class ViewerFrame:
    """Results of one image, ready to be drawn."""

    aruco: ArucoDetection = field(default_factory=ArucoDetection)
    # Text about the calibration for the status bar, and if it can be used with this image
    calibrationText: str = ""
    isCalibrationUsable: bool = False


@dataclass
class ViewerState:
    """Everything the user can change with the keys."""

    mode: ViewerMode = ViewerMode.ARUCO
    isPaused: bool = False
    # True for one loop after 'n': read one frame although the viewer is paused
    isStepRequested: bool = False
    showRejected: bool = False
    showThreshold: bool = False
    showHelp: bool = False
    isRecording: bool = False
    # Last message for the user (snapshot saved, end of the video...), shown in the status bar
    message: str = ""
    stats: SessionStats = field(default_factory=SessionStats)


def applyKey(state: ViewerState, keyCode: int) -> ViewerAction:
    """Changes the state for one key and returns what else the app must do. -1 means no key."""
    modeKeys: dict[str, ViewerMode] = {"1": ViewerMode.ARUCO, "2": ViewerMode.COLOR, "3": ViewerMode.BOTH}
    escapeKeyCode: int = 27
    if keyCode < 0:
        return ViewerAction.NONE
    if keyCode == escapeKeyCode:
        return ViewerAction.QUIT
    key: str = chr(keyCode).lower()
    if key in modeKeys:
        state.mode = modeKeys[key]
    elif key == " ":
        state.isPaused = not state.isPaused
    elif key == "n":
        # Only meaningful while paused: when playing, frames already come one after another
        state.isStepRequested = state.isPaused
    elif key == "x":
        state.showRejected = not state.showRejected
    elif key == "t":
        state.showThreshold = not state.showThreshold
    elif key == "h":
        state.showHelp = not state.showHelp
    elif key == "c":
        state.stats = SessionStats()
        state.message = "session numbers reset"
    else:
        return {"q": ViewerAction.QUIT, "s": ViewerAction.SNAPSHOT, "r": ViewerAction.TOGGLE_RECORDING}.get(
            key, ViewerAction.NONE
        )
    return ViewerAction.NONE


def updateStats(stats: SessionStats, detection: ArucoDetection) -> None:
    """Adds one new frame to the session numbers."""
    stats.processedFrames += 1
    if len(detection.stoneFaces) == 0:
        return
    stats.framesWithStone += 1
    sides: list[float] = [face.sidePx for face in detection.stoneFaces]
    stats.minSidePx = min(sides) if stats.minSidePx == 0.0 else min(stats.minSidePx, *sides)
    stats.maxSidePx = max(stats.maxSidePx, *sides)


def updateFramesPerSecond(stats: SessionStats) -> None:
    """Measures the rate of new frames, smoothed so the number does not jump every frame."""
    # Weight of the newest measure: small means smooth but slow to react
    smoothingWeight: float = 0.1
    now: float = time.perf_counter()
    elapsedSeconds: float = now - stats.lastFrameTime
    if stats.lastFrameTime > 0.0 and elapsedSeconds > 0.0:
        newRate: float = 1.0 / elapsedSeconds
        isFirstMeasure: bool = stats.framesPerSecond == 0.0
        stats.framesPerSecond = newRate if isFirstMeasure else (
            (1 - smoothingWeight) * stats.framesPerSecond + smoothingWeight * newRate
        )
    stats.lastFrameTime = now


def stoneRatePercent(stats: SessionStats) -> float:
    """Percentage of the processed frames where at least one stone marker was found."""
    if stats.processedFrames == 0:
        return 0.0
    return 100.0 * stats.framesWithStone / stats.processedFrames
