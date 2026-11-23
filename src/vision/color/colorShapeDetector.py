"""Finds stones by their colour and shape, for when the ArUco code cannot be read.

1. Colour: pixels whose HSV is cardboard brown, plus the white label pixels that touch them
   (the label nearly splits a face in two, and it is part of the stone).
2. Cleaning: opening removes specks, closing fills small holes.
3. Shape: each blob must be big enough and convex (solidity), as the outline of a box is.
4. Floor: with a calibrated camera, the bottom edge of the blob gives its position, yaw and height
   (blobFloorGeometry.py); a blob with no height is a brown patch on the floor, not a stone.
It only returns data: drawing belongs to the apps.
"""

import time

import cv2
import numpy as np

from vision.color.blobFloorGeometry import BlobFloorGeometry
from vision.common.detectionTypes import ColorCandidate, ColorDetection
from vision.common.visionConfig import CameraCalibration, VisionConfig


class ColorShapeDetector:
    """Detects box-shaped brown blobs. Created once at startup."""

    def __init__(self, config: VisionConfig, calibration: CameraCalibration | None = None) -> None:
        self.config: VisionConfig = config
        self.calibration: CameraCalibration | None = calibration
        self.floorGeometry: BlobFloorGeometry | None = (
            None if calibration is None else BlobFloorGeometry(config, calibration))

    def detect(self, image: np.ndarray) -> ColorDetection:
        """Every brown blob of one image, split into accepted candidates and rejected ones."""
        startTime: float = time.perf_counter()
        result: ColorDetection = ColorDetection()
        if image.size == 0 or image.ndim != 3:
            return result
        mask, labelMask = self.buildMask(image)
        result.maskPx = mask
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        canMeasureFloor: bool = self._canMeasureFloor(image)
        for contour in contours:
            if cv2.contourArea(contour) < self.config.color.minAreaPx:
                continue
            candidate: ColorCandidate = self._measureBlob(contour.reshape(-1, 2), labelMask)
            if canMeasureFloor and self.floorGeometry is not None:
                self.floorGeometry.measure(candidate, image.shape[0])
            self._judgeCandidate(candidate)
            (result.candidates if candidate.rejectReason == "" else result.rejected).append(candidate)
        result.processingTimeMs = (time.perf_counter() - startTime) * 1000
        return result

    def buildMask(self, image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Returns (mask of the stone pixels, mask of the label pixels among them). 255 = yes."""
        colorConfig = self.config.color
        blurKernelPx: int = max(1, colorConfig.blurKernelPx) | 1
        blurred: np.ndarray = cv2.GaussianBlur(image, (blurKernelPx, blurKernelPx), 0)
        hsvImage: np.ndarray = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        brownMask: np.ndarray = cv2.inRange(
            hsvImage, (colorConfig.hueMin, colorConfig.saturationMin, colorConfig.valueMin),
            (colorConfig.hueMax, colorConfig.saturationMax, colorConfig.valueMax))
        # The label is "whiter than the cardboard around it": the threshold follows the light of the room
        brownBrightness: float = float(cv2.mean(hsvImage[:, :, 2], mask=brownMask)[0])
        labelValueMin: int = int(max(colorConfig.labelValueMin, colorConfig.labelBrightnessRatio * brownBrightness))
        whiteMask: np.ndarray = cv2.inRange(hsvImage, (0, 0, min(labelValueMin, 255)),
                                            (179, colorConfig.labelSaturationMax, 255))
        cleanKernel: np.ndarray = cv2.getStructuringElement(
            cv2.MORPH_RECT, (colorConfig.cleanKernelPx, colorConfig.cleanKernelPx))
        # Opening only on the brown: on the joined mask it would erase the thin white frame of the
        # label, which is what keeps the two halves of a face in one blob
        brownMask = cv2.morphologyEx(brownMask, cv2.MORPH_OPEN, cleanKernel)
        labelMask: np.ndarray = self._findLabelPixels(brownMask, whiteMask, cleanKernel)
        mask: np.ndarray = cv2.morphologyEx(cv2.bitwise_or(brownMask, labelMask), cv2.MORPH_CLOSE, cleanKernel)
        # Fill the holes (the black code inside the white frame): every outer outline drawn full
        outlines, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(mask, outlines, -1, 255, cv2.FILLED)
        return mask, labelMask

    def _findLabelPixels(self, brownMask: np.ndarray, whiteMask: np.ndarray, cleanKernel: np.ndarray) -> np.ndarray:
        """The white areas that are labels: each one touches brown and is not bigger than that brown.

        A label is a white frame round the code that nearly splits a face; taking the whole white
        area (not just its edge) keeps the face in one blob. A white wall or line touching a stone
        is bigger than the stone, so it stays out.
        """
        whiteCount, whiteLabels, whiteStats, _ = cv2.connectedComponentsWithStats(whiteMask)
        brownCount, brownLabels, brownStats, _ = cv2.connectedComponentsWithStats(brownMask)
        nearBrownLabels: np.ndarray = cv2.dilate(brownLabels.astype(np.float32), cleanKernel).astype(np.int32)
        labelMask: np.ndarray = np.zeros(whiteMask.shape, dtype=np.uint8)
        for whiteIndex in range(1, whiteCount):
            left, top, width, height, areaPx = whiteStats[whiteIndex]
            area: tuple[slice, slice] = (slice(top, top + height), slice(left, left + width))
            isThisWhite: np.ndarray = whiteLabels[area] == whiteIndex
            touchedBrown: np.ndarray = np.unique(nearBrownLabels[area][isThisWhite])
            touchedBrown = touchedBrown[(touchedBrown > 0) & (touchedBrown < brownCount)]
            if len(touchedBrown) > 0 and areaPx <= brownStats[touchedBrown, cv2.CC_STAT_AREA].sum():
                labelMask[area][isThisWhite] = 255
        return labelMask

    def _canMeasureFloor(self, image: np.ndarray) -> bool:
        """True if the calibration was made at the size of this image."""
        if self.calibration is None:
            return False
        imageHeight, imageWidth = image.shape[:2]
        return (self.calibration.widthPx, self.calibration.heightPx) == (imageWidth, imageHeight)

    def _measureBlob(self, contourPx: np.ndarray, labelMask: np.ndarray) -> ColorCandidate:
        """Area, centre, solidity and how much of the blob is label."""
        areaPx: float = float(cv2.contourArea(contourPx))
        hullAreaPx: float = float(cv2.contourArea(cv2.convexHull(contourPx)))
        moments: dict = cv2.moments(contourPx)
        centerPx: tuple[float, float] = (moments["m10"] / max(moments["m00"], 1e-9),
                                         moments["m01"] / max(moments["m00"], 1e-9))
        blobMask: np.ndarray = np.zeros(labelMask.shape, dtype=np.uint8)
        cv2.drawContours(blobMask, [contourPx.reshape(-1, 1, 2)], -1, 255, cv2.FILLED)
        labelPixels: int = cv2.countNonZero(cv2.bitwise_and(labelMask, blobMask))
        return ColorCandidate(contourPx, centerPx, areaPx, areaPx / max(hullAreaPx, 1e-9),
                              labelPixels / max(areaPx, 1.0))

    def _judgeCandidate(self, candidate: ColorCandidate) -> None:
        """Gives the score (0 to 1) and, if it is not a stone, the reason.

        Score = 35 % shape (solidity) + 45 % size (edge and depth of the side we see) + 20 % label.
        Without a floor position the size is unknown and counts half.
        """
        colorConfig = self.config.color
        solidityScore: float = float(np.clip((candidate.solidity - colorConfig.minSolidity)
                                             / max(1.0 - colorConfig.minSolidity, 1e-9), 0.0, 1.0))
        sizeScore: float = 0.5
        if candidate.hasPosition:
            sizeScore = 1.0 - min(1.0, candidate.sideMatchError / colorConfig.sideTolerance)
        labelScore: float = 1.0 if candidate.labelRatio > colorConfig.minLabelRatio else 0.0
        candidate.score = 0.35 * solidityScore + 0.45 * sizeScore + 0.2 * labelScore
        if candidate.solidity < colorConfig.minSolidity:
            candidate.rejectReason = "irregular shape"
        elif candidate.hasPosition and candidate.heightMm < colorConfig.minHeightMm:
            candidate.rejectReason = "flat: no height"
        elif candidate.score < colorConfig.minScore:
            candidate.rejectReason = "low score"
