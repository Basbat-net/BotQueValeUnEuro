"""Triangles and colours of the 3D twin: the boxes, their labels, the floor marks. Only numpy, no Qt.

A box is 8 corners and 12 triangles (2 per face). Each long face also gets a white square label
and a black square code on top of it, a hair outside the face so they are drawn over it.
"""

import numpy as np

from vision.common.detectionConfig import StoneConfig
from vision.common.visionTypes import DetectionSource
from vision.geometry.boxProjection import buildBoxCorners, listBoxEdges


def buildBoxMesh(centerMm: np.ndarray, rotation: np.ndarray, stone: StoneConfig) -> tuple[np.ndarray, np.ndarray]:
    """(8 x 3 corners, 12 x 3 triangles) of one box. Corner numbering as in buildBoxCorners.

    Triangles go face by face: axis x (- then +), axis y, axis z; two triangles per face.
    """
    corners: np.ndarray = buildBoxCorners(centerMm, rotation, stone)
    triangles: list[list[int]] = []
    for axis in range(3):
        for side in (0, 1):
            # The 4 corners of this face, in order round the face
            others: list[int] = [otherAxis for otherAxis in range(3) if otherAxis != axis]
            square: list[int] = []
            for firstBit, secondBit in ((0, 0), (1, 0), (1, 1), (0, 1)):
                square.append((side << axis) | (firstBit << others[0]) | (secondBit << others[1]))
            triangles.extend([[square[0], square[1], square[2]], [square[0], square[2], square[3]]])
    return corners, np.array(triangles)


def buildLabelMesh(centerMm: np.ndarray, rotation: np.ndarray, stone: StoneConfig,
                   sideMm: float) -> tuple[np.ndarray, np.ndarray]:
    """Squares of side sideMm centred on the 4 long faces (labels or codes), as 2 triangles each."""
    vertices: list[np.ndarray] = []
    triangles: list[list[int]] = []
    # A hair outside the face, so the square is drawn over it; the code a hair more than the label
    outsideMm: float = 0.6 if sideMm < stone.widthMm * 0.9 else 0.3
    halfSide: float = sideMm / 2
    for normalAxis in (1, 2):
        acrossAxis: int = 3 - normalAxis
        for sign in (-1.0, 1.0):
            faceCenter: np.ndarray = centerMm + rotation[:, normalAxis] * sign * (stone.widthMm / 2 + outsideMm)
            alongLong: np.ndarray = rotation[:, 0] * halfSide
            alongAcross: np.ndarray = rotation[:, acrossAxis] * halfSide
            start: int = len(vertices)
            vertices.extend([faceCenter - alongLong - alongAcross, faceCenter + alongLong - alongAcross,
                             faceCenter + alongLong + alongAcross, faceCenter - alongLong + alongAcross])
            triangles.extend([[start, start + 1, start + 2], [start, start + 2, start + 3]])
    return np.array(vertices), np.array(triangles)


def shadeFaces(rotation: np.ndarray, color: tuple[float, float, float, float]) -> np.ndarray:
    """12 x 4 colours, one per triangle: brighter where the face looks up, as with a lamp above the table.

    Done by hand (not by the GL shader) so the look does not depend on the graphics card.
    """
    lightDirection: np.ndarray = np.array([-0.35, 0.25, 0.9]) / np.linalg.norm([-0.35, 0.25, 0.9])
    colors: list[list[float]] = []
    for axis in range(3):
        for sign in (-1.0, 1.0):
            facing: float = max(0.0, float(np.dot(rotation[:, axis] * sign, lightDirection)))
            brightness: float = 0.55 + 0.45 * facing
            faceColor: list[float] = [min(1.0, channel * brightness) for channel in color[:3]] + [color[3]]
            colors.extend([faceColor, faceColor])
    return np.array(colors)


def chooseBoxColor(source: DetectionSource, isGhost: bool, isSelected: bool) -> tuple[float, float, float, float]:
    """RGBA (0 to 1) of a box: kraft tinted by its source, grey and see-through when it is a ghost."""
    if isGhost:
        return (0.55, 0.55, 0.6, 0.35)
    tints: dict[DetectionSource, tuple[float, float, float]] = {
        DetectionSource.ARUCO: (0.62, 0.72, 0.45),
        DetectionSource.COLOR: (0.95, 0.6, 0.25),
        DetectionSource.BOTH: (0.55, 0.75, 0.8),
    }
    red, green, blue = tints[source]
    boost: float = 1.15 if isSelected else 1.0
    return (min(1.0, red * boost), min(1.0, green * boost), min(1.0, blue * boost), 0.95)


def chooseEdgeColor(source: DetectionSource, isGhost: bool, isSelected: bool) -> tuple[float, float, float, float]:
    """RGBA of the edges: the source colour of the 2D view (green, orange, cyan), yellow when selected."""
    if isSelected:
        return (1.0, 0.9, 0.2, 1.0)
    if isGhost:
        return (0.7, 0.7, 0.75, 0.5)
    colors: dict[DetectionSource, tuple[float, float, float, float]] = {
        DetectionSource.ARUCO: (0.31, 0.86, 0.31, 1.0),
        DetectionSource.COLOR: (1.0, 0.55, 0.0, 1.0),
        DetectionSource.BOTH: (0.0, 0.78, 0.9, 1.0),
    }
    return colors[source]


def buildEdgeSegments(corners: np.ndarray) -> np.ndarray:
    """24 x 3 points: the two ends of each of the 12 edges, as GLLinePlotItem draws them in 'lines' mode."""
    return np.array([corners[index] for edge in listBoxEdges() for index in edge])
