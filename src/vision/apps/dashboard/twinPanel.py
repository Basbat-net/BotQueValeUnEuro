"""The 3D twin of the dashboard: the floor in front of the robot, the camera and each stone as a box.

Robot frame, in mm: x forward, y left, z up. Drag to turn the view, wheel to zoom.
Each box is drawn where the black box says it is, coloured by who found it (see dashboardStyle).
The camera cone shows what the camera can see, from the calibration and the camera mount.
"""

import numpy as np
import pyqtgraph as pg
import pyqtgraph.opengl as gl

from vision.apps.dashboard.twinGeometry import (
    buildBoxMesh,
    buildEdgeSegments,
    buildLabelMesh,
    chooseBoxColor,
    chooseEdgeColor,
    shadeFaces,
)
from vision.apps.dashboard.twinSmoother import TwinStone
from vision.common.detectionConfig import StoneConfig


class TwinBox:
    """The GL items of one box. Created when a new track appears; hidden (not deleted) when it goes."""

    def __init__(self, view: gl.GLViewWidget) -> None:
        self.body: gl.GLMeshItem = gl.GLMeshItem(smooth=False, glOptions="translucent")
        self.labels: gl.GLMeshItem = gl.GLMeshItem(smooth=False, color=(0.96, 0.96, 0.96, 1.0), glOptions="opaque")
        self.codes: gl.GLMeshItem = gl.GLMeshItem(smooth=False, color=(0.08, 0.08, 0.08, 1.0), glOptions="opaque")
        self.edges: gl.GLLinePlotItem = gl.GLLinePlotItem(mode="lines", width=2.0, antialias=True)
        self.tag: gl.GLTextItem = gl.GLTextItem()
        for item in (self.body, self.labels, self.codes, self.edges, self.tag):
            view.addItem(item)

    def setVisible(self, isVisible: bool) -> None:
        for item in (self.body, self.labels, self.codes, self.edges, self.tag):
            item.setVisible(isVisible)

    def removeFrom(self, view: gl.GLViewWidget) -> None:
        """Takes the items out of the view (the track is gone for good)."""
        for item in (self.body, self.labels, self.codes, self.edges, self.tag):
            view.removeItem(item)


class TwinPanel:
    """Owns the 3D view. Created once."""

    def __init__(self, stone: StoneConfig, markerSideMm: float, viewCone: list[list[float]]) -> None:
        self.stone: StoneConfig = stone
        self.markerSideMm: float = markerSideMm
        self.widget: gl.GLViewWidget = gl.GLViewWidget()
        self.widget.setBackgroundColor((17, 19, 24))
        self.boxes: dict[int, TwinBox] = {}
        self._addFloorAndRobot()
        # Empty without a calibration: then there is no cone to draw
        if len(viewCone) == 5:
            self._addViewCone(np.array(viewCone))
        self.resetView()

    def resetView(self) -> None:
        """A view from behind and above the robot, looking at the floor in front of it."""
        self.widget.setCameraPosition(pos=pg.Vector(750.0, 0.0, 60.0), distance=1700.0, elevation=30.0,
                                      azimuth=195.0)

    def showTwin(self, tracks: list[TwinStone], selectedTrackId: int) -> None:
        """Moves each box to its track; hides the boxes whose track is gone."""
        shownIds: set[int] = set()
        for track in tracks:
            # A new track gets its GL items once; later they are only moved
            if track.trackId not in self.boxes:
                self.boxes[track.trackId] = TwinBox(self.widget)
            self._placeBox(self.boxes[track.trackId], track, track.trackId == selectedTrackId)
            shownIds.add(track.trackId)
        # Tracks that are gone free their GL items, so a long session does not get slower
        for trackId in [trackId for trackId in self.boxes if trackId not in shownIds]:
            self.boxes.pop(trackId).removeFrom(self.widget)

    def _placeBox(self, twinBox: TwinBox, track: TwinStone, isSelected: bool) -> None:
        """Body, labels, codes, edges and tag of one box, in its current place and colour."""
        corners, triangles = buildBoxMesh(track.centerMm, track.rotation, self.stone)
        twinBox.body.setMeshData(vertexes=corners, faces=triangles,
                                 faceColors=shadeFaces(track.rotation, chooseBoxColor(track.source, track.isGhost,
                                                                                      isSelected)))
        labelVertices, labelTriangles = buildLabelMesh(track.centerMm, track.rotation, self.stone, self.stone.labelSideMm)
        twinBox.labels.setMeshData(vertexes=labelVertices, faces=labelTriangles)
        codeVertices, codeTriangles = buildLabelMesh(track.centerMm, track.rotation, self.stone, self.markerSideMm)
        twinBox.codes.setMeshData(vertexes=codeVertices, faces=codeTriangles)
        twinBox.edges.setData(pos=buildEdgeSegments(corners),
                              color=chooseEdgeColor(track.source, track.isGhost, isSelected))
        tagText: str = f"#{track.trackId} {track.source.name} {track.confidence:.0%}"
        tagText += " lost" if track.isGhost else ""
        twinBox.tag.setData(pos=track.centerMm + np.array([0.0, 0.0, self.stone.widthMm * 0.9]), text=tagText,
                            color=(230, 232, 238, 255))
        twinBox.setVisible(True)

    def _addFloorAndRobot(self) -> None:
        """A 100 mm grid on the floor in front of the robot, the robot outline and its x, y, z arrows."""
        grid: gl.GLGridItem = gl.GLGridItem(color=(255, 255, 255, 28))
        grid.setSize(3000, 3000)
        grid.setSpacing(100, 100)
        grid.translate(1200, 0, 0)
        self.widget.addItem(grid)
        footprint: np.ndarray = np.array([[-150, -150, 0], [150, -150, 0], [150, 150, 0], [-150, 150, 0],
                                          [-150, -150, 0]], dtype=np.float64)
        self.widget.addItem(gl.GLLinePlotItem(pos=footprint, color=(0.55, 0.58, 0.65, 1.0), width=2.0))
        arrowLengthMm: float = 250.0
        for axis, color in enumerate(((1.0, 0.35, 0.3, 1.0), (0.3, 0.85, 0.4, 1.0), (0.35, 0.55, 1.0, 1.0))):
            tip: np.ndarray = np.zeros(3)
            tip[axis] = arrowLengthMm
            self.widget.addItem(gl.GLLinePlotItem(pos=np.array([np.zeros(3), tip]), color=color, width=3.0))
        self.widget.addItem(gl.GLTextItem(pos=np.array([-150.0, -150.0, 20.0]), text="robot", color=(138, 147, 166, 255)))

    def _addViewCone(self, viewCone: np.ndarray) -> None:
        """Lines from the camera to the 4 corners of what it sees, and the frame of the picture."""
        apex: np.ndarray = viewCone[0]
        corners: np.ndarray = viewCone[1:]
        segments: list[np.ndarray] = []
        for index in range(4):
            segments.extend([apex, corners[index], corners[index], corners[(index + 1) % 4]])
        self.widget.addItem(gl.GLLinePlotItem(pos=np.array(segments), mode="lines", color=(0.13, 0.76, 0.9, 0.7),
                                              width=1.5, antialias=True))
        self.widget.addItem(gl.GLTextItem(pos=apex + np.array([0.0, 0.0, 30.0]), text="camera",
                                          color=(34, 195, 230, 255)))
