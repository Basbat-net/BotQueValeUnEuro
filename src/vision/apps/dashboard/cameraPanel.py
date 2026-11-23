"""The camera view of the dashboard: the picture with what the detectors found drawn on it.

The drawings are the same as in the OpenCV viewer (apps/viewer/), so both tools show the same thing.
The view can be zoomed with the wheel and moved by dragging; a click is passed on (to pick the colour).
"""

from collections.abc import Callable

import cv2
import numpy as np
import pyqtgraph as pg

from vision.apps.viewer.viewerDrawing import drawDetections
from vision.apps.viewer.viewerState import ViewerFrame, ViewerState


class CameraPanel:
    """Owns the picture widget. Created once."""

    def __init__(self) -> None:
        self.widget: pg.GraphicsLayoutWidget = pg.GraphicsLayoutWidget()
        self.widget.setBackground("#0b0c10")
        self.viewBox: pg.ViewBox = self.widget.ci.addViewBox(lockAspect=True, invertY=True, enableMenu=False)
        self.imageItem: pg.ImageItem = pg.ImageItem(axisOrder="row-major")
        self.viewBox.addItem(self.imageItem)
        # Set by the session: what to do with a click on the picture (x, y in image pixels)
        self.onImageClicked: Callable[[float, float], None] | None = None
        self.imageSize: tuple[int, int] = (0, 0)
        # The last picture shown, with its drawings (BGR): the snapshot saves it
        self.lastCanvas: np.ndarray = np.zeros((0, 0, 3), dtype=np.uint8)
        # pyqtgraph passes a click event; only its position in the scene is needed
        scene = self.widget.sceneObj
        if scene is not None:
            scene.sigMouseClicked.connect(lambda event: self._handleClick(event.scenePos()))

    def showFrame(self, image: np.ndarray, viewerFrame: ViewerFrame, state: ViewerState) -> None:
        """Draws the detections on the picture and shows it (the first time, fitted to the panel)."""
        canvas: np.ndarray = drawDetections(image, viewerFrame, state)
        self.lastCanvas = canvas
        self.imageItem.setImage(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB), autoLevels=False, levels=(0, 255))
        imageSize: tuple[int, int] = (image.shape[1], image.shape[0])
        if imageSize != self.imageSize:
            self.imageSize = imageSize
            self.viewBox.autoRange(padding=0.0)

    def fitView(self) -> None:
        """Back to the whole picture after zooming."""
        self.viewBox.autoRange(padding=0.0)

    def _handleClick(self, scenePosition: pg.QtCore.QPointF) -> None:
        """Turns a click on the widget into image coordinates and passes it on."""
        imagePoint = self.viewBox.mapSceneToView(scenePosition)
        isInside: bool = 0 <= imagePoint.x() < self.imageSize[0] and 0 <= imagePoint.y() < self.imageSize[1]
        if isInside and self.onImageClicked is not None:
            self.onImageClicked(imagePoint.x(), imagePoint.y())
