"""Turns what the two detectors found into one list of stones, in the robot frame.

1. Each stone code (ArUco face) with a pose gives a box: centre and rotation in the robot frame.
   When its two pose solutions are a real doubt, the physics decides: a stone rests on something,
   so it is not tilted and its centre is at 55, 165, 275 mm (lying) or 160 mm (standing).
2. Faces whose box centres are close (in 3D) are the same stone. Stacked stones stay apart.
3. A brown blob that holds a code (or is next to its stone on the floor) confirms it: BOTH.
   A blob alone is a stone found only by colour, with a low confidence: COLOR.
Only this module knows that there are two detectors.
"""

import cv2
import numpy as np

from vision.common.detectionTypes import ArucoDetection, ArucoMarker, ColorCandidate, ColorDetection, StoneEstimate
from vision.common.visionConfig import VisionConfig
from vision.common.visionTypes import DetectionSource, StoneDetection
from vision.geometry.poseTransforms import (
    buildBoxFromMarker,
    buildCameraToRobotRotation,
    cameraToRobotPoints,
    computeYawDeg,
    estimateLevel,
    snapToFloor,
)


class StoneFusion:
    """Merges the detections of one image. Created once at startup."""

    def __init__(self, config: VisionConfig) -> None:
        self.config: VisionConfig = config
        self.cameraToRobot: np.ndarray = buildCameraToRobotRotation(config.cameraMount)

    def merge(self, aruco: ArucoDetection, color: ColorDetection) -> list[StoneEstimate]:
        """All the stones of one image, nearest first. Needs the poses: without them, only colour stones."""
        faceStones: list[StoneEstimate] = []
        for faceIndex, marker in enumerate(aruco.stoneFaces):
            if marker.hasPose:
                faceStones.append(self._buildFaceStone(faceIndex, marker))
        stones: list[StoneEstimate] = self._groupFaces(faceStones, aruco)
        stones = self._attachColor(stones, aruco, color)
        stones.sort(key=lambda stone: float(np.hypot(stone.centerMm[0], stone.centerMm[1])))
        return stones

    def _buildFaceStone(self, faceIndex: int, marker: ArucoMarker) -> StoneEstimate:
        """The box behind one code. Chooses between its two poses when they are a real doubt."""
        bestBox: tuple[np.ndarray, np.ndarray, float] = self._evaluatePose(marker.rotationVector, marker.translationMm)
        isAmbiguous: bool = False
        if marker.hasAlternativePose:
            alternativeBox = self._evaluatePose(marker.alternativeRotationVector, marker.alternativeTranslationMm)
            # The ratio is near 0 when the best pose is clearly better, near 1 when both fit the corners
            errorRatio: float = marker.reprojectionErrorPx / max(marker.alternativeErrorPx, 1e-9)
            normalAngleDeg: float = angleBetweenDeg(bestBox[1][:, 2], alternativeBox[1][:, 2])
            isAmbiguous = (errorRatio > self.config.fusion.ambiguityErrorRatio
                           and normalAngleDeg > self.config.fusion.ambiguityMinAngleDeg)
            if isAmbiguous and alternativeBox[2] < bestBox[2]:
                bestBox = alternativeBox
        centerMm, rotation, _ = bestBox
        snapped, _, verticalIndex = snapToFloor(rotation)
        isYawDefined, yawDeg = computeYawDeg(snapped, verticalIndex)
        level, _ = estimateLevel(float(centerMm[2]), verticalIndex, self.config.stone)
        confidence: float = self.config.fusion.ambiguousConfidence if isAmbiguous else self.config.fusion.arucoConfidence
        return StoneEstimate(centerMm, rotation, yawDeg, isYawDefined, level, DetectionSource.ARUCO, confidence,
                             [faceIndex], -1, isAmbiguous)

    def _evaluatePose(self, rotationVector: tuple[float, float, float],
                      translationMm: tuple[float, float, float]) -> tuple[np.ndarray, np.ndarray, float]:
        """Box centre and rotation in the robot frame, and how implausible they are (0 = a perfect resting stone).

        The centre is half a stone width behind the code, along the face normal snapped to vertical or
        horizontal: a code seen from the side has a poor normal, and 55 mm times that error adds up.
        The cost adds the tilt (degrees) and the height error (mm, divided by 10 to weigh about the same).
        """
        markerRotation, _ = cv2.Rodrigues(np.array(rotationVector, dtype=np.float64))
        boxRotation, _ = buildBoxFromMarker(markerRotation, np.array(translationMm), self.config.stone,
                                            self.config.aruco.markerLongAxis)
        rotation: np.ndarray = self.cameraToRobot @ boxRotation
        snapped, tiltDeg, verticalIndex = snapToFloor(rotation)
        markerCenterMm: np.ndarray = cameraToRobotPoints(np.array(translationMm), self.cameraToRobot,
                                                         self.config.cameraMount)
        centerMm: np.ndarray = markerCenterMm - snapped[:, 2] * (self.config.stone.widthMm / 2)
        _, heightErrorMm = estimateLevel(float(centerMm[2]), verticalIndex, self.config.stone)
        return centerMm, rotation, tiltDeg + heightErrorMm / 10.0

    def _groupFaces(self, faceStones: list[StoneEstimate], aruco: ArucoDetection) -> list[StoneEstimate]:
        """Joins the faces of the same stone. Each group is led by its code with the largest area in the picture."""
        bySize: list[StoneEstimate] = sorted(
            faceStones, key=lambda stone: -apparentAreaPx(aruco.stoneFaces[stone.faceIndexes[0]]))
        groups: list[list[StoneEstimate]] = []
        for faceStone in bySize:
            matchingGroup: list[StoneEstimate] | None = None
            for group in groups:
                distanceMm: float = float(np.linalg.norm(group[0].centerMm - faceStone.centerMm))
                if distanceMm < self.config.fusion.sameStoneDistanceMm:
                    matchingGroup = group
                    break
            if matchingGroup is None:
                groups.append([faceStone])
            else:
                matchingGroup.append(faceStone)
        return [self._mergeGroup(group) for group in groups]

    def _mergeGroup(self, group: list[StoneEstimate]) -> StoneEstimate:
        """One stone from the faces of a group: position and rotation of the code with the largest area.

        That code is the nearest or the most seen from the front, so its pose is the best one.
        Averaging with a code seen from the side made the position worse (measured on synthetic scenes:
        median error 8.6 mm with the mean, 5.0 mm with the largest code).
        """
        stone: StoneEstimate = group[0]
        stone.faceIndexes = [faceStone.faceIndexes[0] for faceStone in group]
        stone.wasAmbiguous = all(faceStone.wasAmbiguous for faceStone in group)
        bonus: float = self.config.fusion.extraFaceBonus * (len(group) - 1)
        stone.confidence = min(1.0, max(faceStone.confidence for faceStone in group) + bonus)
        _, _, verticalIndex = snapToFloor(stone.rotation)
        stone.level, _ = estimateLevel(float(stone.centerMm[2]), verticalIndex, self.config.stone)
        return stone

    def _attachColor(self, stones: list[StoneEstimate], aruco: ArucoDetection,
                     color: ColorDetection) -> list[StoneEstimate]:
        """Confirms the ArUco stones with the blobs, and adds the blobs that have no code as COLOR stones."""
        colorStones: list[StoneEstimate] = []
        for colorIndex, candidate in enumerate(color.candidates):
            matchedStones: list[StoneEstimate] = [
                stone for stone in stones
                if any(isInsideBlob(aruco.stoneFaces[faceIndex].centerPx, candidate) for faceIndex in stone.faceIndexes)
            ]
            if not matchedStones and candidate.hasPosition:
                matchedStones = [stone for stone in stones
                                 if floorDistanceMm(stone, candidate) < self.config.fusion.colorMatchDistanceMm][:1]
            for stone in matchedStones:
                if stone.source == DetectionSource.ARUCO:
                    stone.source = DetectionSource.BOTH
                    stone.colorIndex = colorIndex
                    stone.confidence = min(1.0, stone.confidence + self.config.fusion.colorAgreementBonus)
            if not matchedStones and candidate.hasPosition:
                colorStones.extend(self._buildColorStones(colorIndex, candidate))
        return stones + self._joinColorPieces(colorStones)

    def _joinColorPieces(self, colorStones: list[StoneEstimate]) -> list[StoneEstimate]:
        """Two blobs that fit inside one stone are two pieces of it (something covers its middle).

        Same yaw, closer than 80 % of the length along the stone and than half a width across it
        (pieceYawToleranceDeg and pieceAlongFraction in the config):
        two real stones end to end are 320 mm apart, side by side 110 mm, so they are never joined.
        The joined stone is in the middle of both pieces.
        """
        stone = self.config.stone
        fusionConfig = self.config.fusion
        joined: list[StoneEstimate] = []
        for piece in colorStones:
            partner: StoneEstimate | None = None
            for other in joined:
                yawGapDeg: float = abs((piece.yawDeg - other.yawDeg + 90.0) % 180.0 - 90.0)
                gap: np.ndarray = piece.centerMm[:2] - other.centerMm[:2]
                alongMm: float = abs(float(np.dot(gap, other.rotation[:2, 0])))
                acrossMm: float = abs(float(np.dot(gap, other.rotation[:2, 1])))
                isSameYaw: bool = yawGapDeg < fusionConfig.pieceYawToleranceDeg and piece.level == other.level
                if isSameYaw and alongMm < fusionConfig.pieceAlongFraction * stone.lengthMm and acrossMm < stone.widthMm / 2:
                    partner = other
                    break
            if partner is None:
                joined.append(piece)
            else:
                partner.centerMm = (partner.centerMm + piece.centerMm) / 2
                partner.confidence = max(partner.confidence, piece.confidence)
        return joined

    def _buildColorStones(self, colorIndex: int, candidate: ColorCandidate) -> list[StoneEstimate]:
        """Stones seen only by colour: lying, with the position and yaw of the bottom edge, one per level of a pile."""
        yaw: float = float(np.radians(candidate.yawDeg))
        rotation: np.ndarray = np.array([[np.cos(yaw), -np.sin(yaw), 0.0], [np.sin(yaw), np.cos(yaw), 0.0],
                                         [0.0, 0.0, 1.0]])
        confidence: float = candidate.score * self.config.fusion.colorConfidenceMax
        halfWidth: float = self.config.stone.widthMm / 2
        return [StoneEstimate(np.array([candidate.centerMm[0], candidate.centerMm[1],
                                        halfWidth + self.config.stone.widthMm * level]),
                              rotation.copy(), candidate.yawDeg, True, level, DetectionSource.COLOR, confidence,
                              [], colorIndex, False)
                for level in range(candidate.stackLevels)]


def toStoneDetection(stone: StoneEstimate) -> StoneDetection:
    """The contract view of a stone: what the robot receives (x, y, yaw, confidence, source)."""
    return StoneDetection(float(stone.centerMm[0]), float(stone.centerMm[1]), stone.yawDeg, stone.confidence,
                          stone.source)


def apparentAreaPx(marker: ArucoMarker) -> float:
    """Area of the code in the picture, in px: bigger when nearer and when seen more from the front."""
    return float(cv2.contourArea(marker.cornersPx.astype(np.float32)))


def angleBetweenDeg(firstVector: np.ndarray, secondVector: np.ndarray) -> float:
    """Angle between two directions, in degrees."""
    cosine: float = float(np.dot(firstVector, secondVector)
                          / max(float(np.linalg.norm(firstVector) * np.linalg.norm(secondVector)), 1e-12))
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def isInsideBlob(pointPx: tuple[float, float], candidate: ColorCandidate) -> bool:
    """True if a pixel is inside (or on the edge of) the outline of a blob."""
    contour: np.ndarray = candidate.contourPx.reshape(-1, 1, 2).astype(np.float32)
    return cv2.pointPolygonTest(contour, (float(pointPx[0]), float(pointPx[1])), False) >= 0


def floorDistanceMm(stone: StoneEstimate, candidate: ColorCandidate) -> float:
    """Distance seen from above between a stone and the floor position of a blob."""
    return float(np.hypot(stone.centerMm[0] - candidate.centerMm[0], stone.centerMm[1] - candidate.centerMm[1]))
