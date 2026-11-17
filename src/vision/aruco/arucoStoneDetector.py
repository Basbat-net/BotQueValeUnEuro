"""Finds the ArUco markers of the stones in one image.

Phase 2a: everything is in pixels. The pose in mm (phase 2b) needs a calibrated camera.
It only returns data: drawing belongs to the apps, because the robot has no screen.
"""

import time

import cv2
import numpy as np

from vision.common.detectionTypes import ArucoDetection, ArucoMarker
from vision.common.visionConfig import ArucoConfig


class ArucoStoneDetector:
    """Detects ArUco markers and separates the ones of the stones. Created once at startup."""

    def __init__(self, config: ArucoConfig) -> None:
        self.config: ArucoConfig = config
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
        for markerId, corners in zip(foundIds, cornersList):
            marker: ArucoMarker = self._buildMarker(markerId, corners.reshape(4, 2))
            if markerId == self.config.stoneMarkerId:
                result.stoneFaces.append(marker)
            else:
                result.otherMarkers.append(marker)
        result.rejectedCornersPx = [corners.reshape(4, 2) for corners in rejectedList]
        result.processingTimeMs = (time.perf_counter() - startTime) * 1000
        return result

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
