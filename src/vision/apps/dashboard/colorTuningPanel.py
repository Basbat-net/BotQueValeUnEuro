"""Colour tuning of the dashboard: the HSV range taken as cardboard, by hand or with a click on a stone.

The sliders change the config in memory, so the detector uses the new range from the next image.
"Pick on image" measures the colour around a click (the median of a small square) and opens a range
around it; "Save to config" writes the range in the JSON file, for the robot to use it too.
This is the tool for the 3 minutes of preparation on the real table [vision.md, colour].
"""

from collections.abc import Callable

import cv2
import numpy as np
from pyqtgraph.Qt import QtCore, QtWidgets

from vision.common.detectionConfig import ColorConfig


class ColorTuningPanel:
    """Six sliders (min and max of hue, saturation and value) and three buttons. Created once."""

    def __init__(self, colorConfig: ColorConfig) -> None:
        self.colorConfig: ColorConfig = colorConfig
        self.originalValues: dict[str, int] = self.readValues()
        self.group: QtWidgets.QGroupBox = QtWidgets.QGroupBox("Cardboard colour (HSV)")
        layout: QtWidgets.QGridLayout = QtWidgets.QGridLayout(self.group)
        # Name in ColorConfig, label, highest value (OpenCV hue goes 0-179, the others 0-255)
        rows: list[tuple[str, str, int]] = [("hueMin", "Hue min", 179), ("hueMax", "Hue max", 179),
                                            ("saturationMin", "Saturation min", 255),
                                            ("saturationMax", "Saturation max", 255),
                                            ("valueMin", "Value min", 255), ("valueMax", "Value max", 255)]
        self.sliders: dict[str, QtWidgets.QSlider] = {}
        self.valueLabels: dict[str, QtWidgets.QLabel] = {}
        for row, (name, label, highest) in enumerate(rows):
            slider: QtWidgets.QSlider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
            slider.setRange(0, highest)
            slider.setValue(int(getattr(colorConfig, name)))
            slider.valueChanged.connect(lambda value, sliderName=name: self._handleSlider(sliderName, value))
            self.sliders[name] = slider
            self.valueLabels[name] = QtWidgets.QLabel(str(slider.value()))
            layout.addWidget(QtWidgets.QLabel(label), row, 0)
            layout.addWidget(slider, row, 1)
            layout.addWidget(self.valueLabels[name], row, 2)
        self.pickButton: QtWidgets.QPushButton = QtWidgets.QPushButton("Pick on image (P)")
        self.pickButton.setCheckable(True)
        self.resetButton: QtWidgets.QPushButton = QtWidgets.QPushButton("Reset")
        self.saveButton: QtWidgets.QPushButton = QtWidgets.QPushButton("Save to config")
        buttons: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        for button in (self.pickButton, self.resetButton, self.saveButton):
            buttons.addWidget(button)
        layout.addLayout(buttons, len(rows), 0, 1, 3)
        self.hint: QtWidgets.QLabel = QtWidgets.QLabel("Tip: press Pick, then click on the cardboard of a stone.")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint, len(rows) + 1, 0, 1, 3)
        # Set by the session: called after any change of the range
        self.onRangeChanged: Callable[[], None] | None = None
        self.resetButton.clicked.connect(lambda: self.setValues(self.originalValues))

    def readValues(self) -> dict[str, int]:
        """The six numbers of the range, as they are now in the config."""
        names: list[str] = ["hueMin", "hueMax", "saturationMin", "saturationMax", "valueMin", "valueMax"]
        return {name: int(getattr(self.colorConfig, name)) for name in names}

    def setValues(self, values: dict[str, int]) -> None:
        """Moves the sliders (and so the config) to these values."""
        for name, value in values.items():
            self.sliders[name].setValue(value)

    def pickFrom(self, image: np.ndarray, xPx: float, yPx: float) -> str:
        """Measures the colour around a pixel and opens the range around it. Returns a message for the user."""
        config: ColorConfig = self.colorConfig
        halfSidePx: int = config.pickHalfSidePx
        column, row = int(xPx), int(yPx)
        patch: np.ndarray = image[max(0, row - halfSidePx) : row + halfSidePx + 1,
                                  max(0, column - halfSidePx) : column + halfSidePx + 1]
        if patch.size == 0:
            return "no picture under the click"
        hue, saturation, value = np.median(cv2.cvtColor(patch, cv2.COLOR_BGR2HSV).reshape(-1, 3), axis=0)
        self.setValues({
            "hueMin": int(max(0, hue - config.pickHueMargin)), "hueMax": int(min(179, hue + config.pickHueMargin)),
            "saturationMin": int(max(0, saturation - config.pickSaturationMargin)), "saturationMax": 255,
            "valueMin": int(max(0, value - config.pickValueMargin)), "valueMax": 255,
        })
        self.pickButton.setChecked(False)
        return f"colour picked: H {hue:.0f}, S {saturation:.0f}, V {value:.0f}"

    def _handleSlider(self, name: str, value: int) -> None:
        """Writes the slider into the config and keeps each minimum below its maximum."""
        setattr(self.colorConfig, name, value)
        self.valueLabels[name].setText(str(value))
        pairs: dict[str, str] = {"hueMin": "hueMax", "saturationMin": "saturationMax", "valueMin": "valueMax"}
        partners: dict[str, str] = {**pairs, **{maximum: minimum for minimum, maximum in pairs.items()}}
        partner: str = partners[name]
        isMinimum: bool = name in pairs
        partnerValue: int = self.sliders[partner].value()
        if (isMinimum and value > partnerValue) or (not isMinimum and value < partnerValue):
            self.sliders[partner].setValue(value)
        if self.onRangeChanged is not None:
            self.onRangeChanged()
