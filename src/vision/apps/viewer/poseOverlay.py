"""Draws each stone the black box believes in as a wire box over the picture.

If the wire box sits on the real one, the pose, the calibration and the camera mount are all right;
if it floats or turns, one of them is wrong. Colour by source: green ArUco, orange colour, cyan both.
"""

import cv2
import numpy as np

from vision.apps.viewer.hudOverlay import DrawStyle, putBoxedText
from vision.common.detectionTypes import ProjectedStone
from vision.common.visionTypes import DetectionSource
from vision.geometry.boxProjection import listBoxEdges


def sourceColor(source: DetectionSource, style: DrawStyle) -> tuple[int, int, int]:
    """The drawing colour of each source."""
    colors: dict[DetectionSource, tuple[int, int, int]] = {
        DetectionSource.ARUCO: style.goodColor,
        DetectionSource.COLOR: style.colorStoneColor,
        DetectionSource.BOTH: style.bothColor,
    }
    return colors[source]


def drawProjectedStones(image: np.ndarray, projectedStones: list[ProjectedStone], style: DrawStyle) -> None:
    """Every stone as 12 edges, with a label: source, x and y (mm), yaw and confidence."""
    edges: list[tuple[int, int]] = listBoxEdges()
    for projected in projectedStones:
        if not projected.isInFront:
            continue
        color: tuple[int, int, int] = sourceColor(projected.stone.source, style)
        cornersPx: np.ndarray = np.round(projected.cornersPx).astype(np.int32)
        for firstCorner, secondCorner in edges:
            cv2.line(image, tuple(int(value) for value in cornersPx[firstCorner]),
                     tuple(int(value) for value in cornersPx[secondCorner]), color, 2, cv2.LINE_AA)
        putBoxedText(image, describeStone(projected), topLeftOfLabel(cornersPx, style), color, style)


def describeStone(projected: ProjectedStone) -> str:
    """Short ASCII text of a stone, for the label over its wire box."""
    stone = projected.stone
    yawText: str = f"{stone.yawDeg:+.0f}deg" if stone.isYawDefined else "standing"
    levelText: str = f" L{stone.level}" if stone.level > 0 else ""
    return (f"{stone.source.name} x{stone.centerMm[0]:.0f} y{stone.centerMm[1]:.0f} {yawText} "
            f"{stone.confidence:.0%}{levelText}")


def topLeftOfLabel(cornersPx: np.ndarray, style: DrawStyle) -> tuple[int, int]:
    """Just above the highest corner of the box, but never out of the picture."""
    labelX: int = max(0, int(cornersPx[:, 0].min()))
    labelY: int = max(style.lineHeightPx, int(cornersPx[:, 1].min()) - style.lineHeightPx // 3)
    return labelX, labelY
