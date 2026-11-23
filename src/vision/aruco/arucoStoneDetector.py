"""Finds the ArUco markers of the stones in one image and, with a calibrated camera, their pose.

Without a calibration (or with one made at another image size) everything stays in pixels.
With it, solvePnP gives the position and rotation of each code in the camera frame, in mm.
It only returns data: drawing belongs to the apps, because the robot has no screen.
"""

import time

import cv2
import numpy as np

from vision.common.detectionTypes import ArucoDetection, ArucoMarker
from vision.common.visionConfig import ArucoConfig, CameraCalibration


class ArucoStoneDetector:
    """Detects ArUco markers and separates the ones of the stones. Created once at startup."""

    def __init__(self, config: ArucoConfig, calibration: CameraCalibration | None = None) -> None:
        self.config: ArucoConfig = config
        # None or an empty calibration (widthPx 0): the detector works in pixels only
        self.calibration: CameraCalibration | None = calibration
        halfSide: float = config.markerSideMm / 2
        # Corners of the code in its own frame (x right, y up, z out of the face), in the order
        # detectMarkers gives them and SOLVEPNP_IPPE_SQUARE requires: top-left, top-right, bottom-right, bottom-left
        self.markerCornersMm: np.ndarray = np.array(
            [[-halfSide, halfSide, 0.0], [halfSide, halfSide, 0.0], [halfSide, -halfSide, 0.0], [-halfSide, -halfSide, 0.0]])
        # Why the detector cannot work (wrong config), for the apps to print. Empty if it can
        self.lastError: str = ""
        isLoaded, dictionary = self._loadDictionary()
        parameters: cv2.aruco.DetectorParameters = cv2.aruco.DetectorParameters()
        if config.useSubPixRefinement:
            parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
        self.detector: cv2.aruco.ArucoDetector = cv2.aruco.ArucoDetector(dictionary, parameters)
        self.isReady: bool = isLoaded

    def detect(self, image: np.ndarray) -> ArucoDetection:
        """Returns every marker found in one image. Empty lists if there is none or it is not ready."""
        startTime: float = time.perf_counter()
        result: ArucoDetection = ArucoDetection()
        if not self.isReady or image.size == 0:
            return result
        # The search works on brightness only; a picture that is already gray is used as it is
        grayImage: np.ndarray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        cornersList, markerIds, rejectedList = self.detector.detectMarkers(grayImage)
        # markerIds is None when nothing was found, and an N x 1 array otherwise
        foundIds: list[int] = [] if markerIds is None else [int(markerId) for markerId in markerIds.flatten()]
        canEstimatePose: bool = self.canEstimatePose(image)
        for markerId, corners in zip(foundIds, cornersList):
            marker: ArucoMarker = self._buildMarker(markerId, corners.reshape(4, 2))
            if canEstimatePose:
                self._estimatePose(marker)
            if markerId == self.config.stoneMarkerId:
                result.stoneFaces.append(marker)
            else:
                result.otherMarkers.append(marker)
        result.rejectedCornersPx = [corners.reshape(4, 2) for corners in rejectedList]
        result.processingTimeMs = (time.perf_counter() - startTime) * 1000
        return result

    def canEstimatePose(self, image: np.ndarray) -> bool:
        """True if there is a calibration made at the size of this image."""
        if self.calibration is None:
            return False
        imageHeight, imageWidth = image.shape[:2]
        return (self.calibration.widthPx, self.calibration.heightPx) == (imageWidth, imageHeight)

    def _estimatePose(self, marker: ArucoMarker) -> None:
        """Fills the pose of the marker: the best solution and, if there is one, the other one."""
        if self.calibration is None:
            return
        # IPPE_SQUARE is the method made for a square of known side: it gives both solutions
        solutionCount, rotationVectors, translationVectors, errors = cv2.solvePnPGeneric(
            self.markerCornersMm, marker.cornersPx.astype(np.float64), self.calibration.cameraMatrix,
            self.calibration.distCoeffs, flags=cv2.SOLVEPNP_IPPE_SQUARE)
        if solutionCount == 0:
            return
        # The solutions come sorted: the first one has the smallest reprojection error
        errorList: list[float] = [float(error) for error in np.asarray(errors).flatten()]
        marker.hasPose = True
        marker.rotationVector = toTriple(rotationVectors[0])
        marker.translationMm = toTriple(translationVectors[0])
        marker.reprojectionErrorPx = errorList[0]
        if solutionCount > 1:
            marker.hasAlternativePose = True
            marker.alternativeRotationVector = toTriple(rotationVectors[1])
            marker.alternativeTranslationMm = toTriple(translationVectors[1])
            marker.alternativeErrorPx = errorList[1]

    def _loadDictionary(self) -> tuple[bool, cv2.aruco.Dictionary]:
        """Builds the dictionary named in the config. False if the name or the stone ID are wrong."""
        # Any valid dictionary, only used when the configured one fails (then isReady is False)
        fallbackDictionary: cv2.aruco.Dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        dictionaryCode: object = getattr(cv2.aruco, self.config.dictionaryName, None)
        if not self.config.dictionaryName.startswith("DICT_") or not isinstance(dictionaryCode, int):
            self.lastError = f"unknown ArUco dictionary '{self.config.dictionaryName}'"
            return False, fallbackDictionary
        dictionary: cv2.aruco.Dictionary = cv2.aruco.getPredefinedDictionary(dictionaryCode)
        # bytesList holds one row per marker of the dictionary: DICT_4X4_50 has IDs 0 to 49
        markerCount: int = dictionary.bytesList.shape[0]
        if not 0 <= self.config.stoneMarkerId < markerCount:
            self.lastError = f"ID {self.config.stoneMarkerId} is not in {self.config.dictionaryName}"
            return False, fallbackDictionary
        return True, dictionary

    def _buildMarker(self, markerId: int, cornersPx: np.ndarray) -> ArucoMarker:
        """Turns the 4 corners given by OpenCV into an ArucoMarker (center and mean side, in px)."""
        center: np.ndarray = cornersPx.mean(axis=0)
        # Each corner minus the one before it (np.roll moves the list one place) gives the 4 sides
        sideLengths: np.ndarray = np.linalg.norm(cornersPx - np.roll(cornersPx, 1, axis=0), axis=1)
        return ArucoMarker(markerId, cornersPx, (float(center[0]), float(center[1])), float(sideLengths.mean()))


def toTriple(vector: np.ndarray) -> tuple[float, float, float]:
    """A 3 x 1 OpenCV vector as a plain tuple of 3 floats."""
    flat: np.ndarray = np.asarray(vector, dtype=np.float64).flatten()
    return (float(flat[0]), float(flat[1]), float(flat[2]))
