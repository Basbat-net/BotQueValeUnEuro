"""The script of the synthetic demo video: what is on the table at each moment.

- A stone moves along a curve and turns (ArUco and colour see it: BOTH).
- From 6 s to 9 s something covers its code: only the colour sees it (COLOR).
- A second stone stays still, and a quarry of 2 stones stands at the back.
- A brown stripe painted on the floor must never become a stone (it is flat).
"""

import math

import numpy as np

from vision.simulation.boxTexture import SceneBox, buildLyingBox
from vision.simulation.sceneRenderer import SceneOptions


class DemoTimeline:
    """Times of the demo, in seconds. Class attributes, not globals (team rule)."""

    durationSeconds: float = 15.0
    framesPerSecond: float = 30.0
    coverStartSeconds: float = 6.0
    coverEndSeconds: float = 9.0


def buildDemoBoxes(timeSeconds: float) -> list[SceneBox]:
    """The stones on the table at that moment. The moving one is always the first of the list."""
    progress: float = min(max(timeSeconds / DemoTimeline.durationSeconds, 0.0), 1.0)
    # A curve from the left to near right, turning 150 degrees on the way. At 640 x 480 the code is lost
    # beyond about 1 m when seen at an angle (measured with these scenes), so the path stays closer
    movingX: float = 900.0 - 400.0 * progress
    movingY: float = 250.0 - 400.0 * progress + 100.0 * math.sin(2.0 * math.pi * progress)
    movingYawDeg: float = 10.0 + 150.0 * progress
    isCovered: bool = DemoTimeline.coverStartSeconds <= timeSeconds < DemoTimeline.coverEndSeconds
    return [
        buildLyingBox(movingX, movingY, movingYawDeg, isMarkerCovered=isCovered),
        buildLyingBox(750.0, 420.0, 80.0),
        buildLyingBox(1050.0, -380.0, 0.0, level=0),
        buildLyingBox(1050.0, -380.0, 0.0, level=1),
    ]


def buildDemoOptions() -> SceneOptions:
    """A slightly imperfect camera (JPEG and noise) and the brown stripe on the floor."""
    return SceneOptions(brownPatchesMm=[(600.0, -750.0, 1400.0, -690.0)], jpegQuality=85, noiseSigma=2.0)


def describeTruth(boxes: list[SceneBox]) -> list[list[float]]:
    """One row per stone: x, y, z (mm), yaw (degrees, -90 to 90) and 1 if its code is covered."""
    rows: list[list[float]] = []
    for box in boxes:
        longSide: np.ndarray = box.rotation[:, 0]
        yawDeg: float = (math.degrees(math.atan2(float(longSide[1]), float(longSide[0]))) + 90.0) % 180.0 - 90.0
        rows.append([float(box.centerMm[0]), float(box.centerMm[1]), float(box.centerMm[2]), yawDeg,
                     1.0 if box.isMarkerCovered else 0.0])
    return rows
