"""The vision black box: one image in, one result out (the contract of common/visionTypes.py).

Inside: the ArUco detector, the colour + shape detector and the fusion, one after the other.
It never opens the camera and never sends anything: input/ and output/ do that.
It is built with its parts by blackBoxFactory.buildVisionBlackBox, which reads the config.

Status of the result:
- NO_FRAME: the image is empty or not a colour picture.
- CONFIG_ERROR: the ArUco config is wrong (unknown dictionary or ID).
- NOT_CALIBRATED: no camera calibration at this image size, or the camera mount is not measured.
  The detections are still in the details (for the apps), but the result carries no stones.
- OK: the stones are in the result, nearest first (it may be empty).
"""

import time

from vision.aruco.arucoStoneDetector import ArucoStoneDetector
from vision.color.colorShapeDetector import ColorShapeDetector
from vision.common.detectionTypes import PipelineOptions, VisionDetails
from vision.common.visionTypes import FrameInput, VisionResult, VisionStatus
from vision.fusion.stoneFusion import StoneFusion, toStoneDetection


class VisionBlackBox:
    """Processes one image at a time. Created once at startup."""

    def __init__(self, arucoDetector: ArucoStoneDetector, colorDetector: ColorShapeDetector, fusion: StoneFusion,
                 isMountMeasured: bool) -> None:
        self.arucoDetector: ArucoStoneDetector = arucoDetector
        self.colorDetector: ColorShapeDetector = colorDetector
        self.fusion: StoneFusion = fusion
        self.isMountMeasured: bool = isMountMeasured
        # Why the box cannot work (wrong detector config), for the apps to print. Empty if it can
        self.lastError: str = arucoDetector.lastError

    def process(self, frame: FrameInput) -> VisionResult:
        """The contract: always returns a result, never raises, never waits."""
        return self.processWithDetails(frame, PipelineOptions()).result

    def processWithDetails(self, frame: FrameInput, options: PipelineOptions) -> VisionDetails:
        """The result plus what each detector found, for the apps that draw it."""
        startTime: float = time.perf_counter()
        details: VisionDetails = VisionDetails()
        image = frame.image
        # 8 bits per channel, as cameras and OpenCV give them: other types would make OpenCV raise
        isColourPicture: bool = image.ndim == 3 and image.shape[2] == 3 and image.size > 0 and image.dtype == "uint8"
        if not isColourPicture:
            details.result = VisionResult(frame.timestampMs, elapsedMs(startTime), VisionStatus.NO_FRAME)
            return details
        if not self.arucoDetector.isReady:
            details.result = VisionResult(frame.timestampMs, elapsedMs(startTime), VisionStatus.CONFIG_ERROR)
            return details
        if options.useAruco:
            details.aruco = self.arucoDetector.detect(image)
        if options.useColor:
            details.color = self.colorDetector.detect(image)
        details.isCalibrationUsable, details.calibrationText = self._describeCalibration(image.shape[1], image.shape[0])
        details.isMountMeasured = self.isMountMeasured
        if details.isCalibrationUsable:
            fusionStart: float = time.perf_counter()
            details.stones = self.fusion.merge(details.aruco, details.color)
            details.fusionTimeMs = elapsedMs(fusionStart)
        isOk: bool = details.isCalibrationUsable and self.isMountMeasured
        status: VisionStatus = VisionStatus.OK if isOk else VisionStatus.NOT_CALIBRATED
        stones = [toStoneDetection(stone) for stone in details.stones] if isOk else []
        details.result = VisionResult(frame.timestampMs, elapsedMs(startTime), status, stones)
        return details

    def _describeCalibration(self, imageWidth: int, imageHeight: int) -> tuple[bool, str]:
        """Whether the calibration fits this image size, and a text for the apps."""
        calibration = self.arucoDetector.calibration
        if calibration is None:
            return False, "NOT CALIBRATED: run cameraCalibrationApp (distances need it)"
        calibrationSize: str = f"{calibration.widthPx}x{calibration.heightPx}"
        if (calibration.widthPx, calibration.heightPx) != (imageWidth, imageHeight):
            return False, f"calibration made at {calibrationSize}, image is {imageWidth}x{imageHeight}: not usable"
        return True, f"calibrated at {calibrationSize} (reprojection error {calibration.reprojectionErrorPx:.2f} px)"


def elapsedMs(startTime: float) -> float:
    """Milliseconds since startTime (taken with time.perf_counter)."""
    return (time.perf_counter() - startTime) * 1000
