"""Tests of the keys and numbers of the viewer: no screen needed.

Run from the src/ folder:
    python3 -m pytest ../tests/vision
"""

import numpy as np

from vision.apps.viewer.viewerState import (
    ViewerAction,
    ViewerMode,
    ViewerState,
    applyKey,
    stoneRatePercent,
    updateStats,
)
from vision.common.detectionTypes import ArucoDetection, ArucoMarker


def buildDetection(stoneSidesPx: list[float]) -> ArucoDetection:
    """A detection with one stone face per side given."""
    faces: list[ArucoMarker] = [ArucoMarker(13, np.zeros((4, 2)), (0.0, 0.0), sidePx) for sidePx in stoneSidesPx]
    return ArucoDetection(stoneFaces=faces)


def testNumberKeysChangeTheMode() -> None:
    state: ViewerState = ViewerState()
    expectedModes: dict[str, ViewerMode] = {"2": ViewerMode.COLOR, "3": ViewerMode.BOTH, "1": ViewerMode.ARUCO}
    for key, mode in expectedModes.items():
        applyKey(state, ord(key))
        assert state.mode == mode


def testStepOnlyWorksWhilePaused() -> None:
    state: ViewerState = ViewerState()
    applyKey(state, ord("n"))
    assert not state.isStepRequested
    applyKey(state, ord(" "))
    applyKey(state, ord("n"))
    assert state.isPaused and state.isStepRequested


def testKeysThatAskTheAppForSomething() -> None:
    state: ViewerState = ViewerState()
    escapeKeyCode: int = 27
    assert applyKey(state, ord("q")) == ViewerAction.QUIT
    assert applyKey(state, escapeKeyCode) == ViewerAction.QUIT
    assert applyKey(state, ord("s")) == ViewerAction.SNAPSHOT
    assert applyKey(state, ord("r")) == ViewerAction.TOGGLE_RECORDING
    # No key, and a key without a job
    assert applyKey(state, -1) == ViewerAction.NONE
    assert applyKey(state, ord("z")) == ViewerAction.NONE


def testSessionNumbers() -> None:
    state: ViewerState = ViewerState()
    updateStats(state.stats, buildDetection([50.0, 80.0]))
    updateStats(state.stats, buildDetection([]))
    updateStats(state.stats, buildDetection([100.0]))
    assert state.stats.processedFrames == 3
    assert state.stats.framesWithStone == 2
    assert (state.stats.minSidePx, state.stats.maxSidePx) == (50.0, 100.0)
    assert abs(stoneRatePercent(state.stats) - 200 / 3) < 0.01
    applyKey(state, ord("c"))
    assert state.stats.processedFrames == 0
