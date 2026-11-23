"""Where a brown blob stands on the floor, measured in mm with a calibrated camera.

A blob in the picture has no depth. But a stone rests on the floor (z = 0), and the lowest part
of its outline is the line where it touches the floor. Each pixel of that line gives a ray from
the camera; where the ray meets the floor is a real point in mm. From that bottom edge:
- the upper part of the outline is the far top edge: where its rays cross the top of a lying
  stone (z = 110 mm) tells how deep the stone goes behind the edge, about 110 mm if we see a long
  side and 320 mm if we see an end. With the edge length, that says which side we see, even when
  part of the edge is hidden; the direction of the edge gives the yaw;
- the centre of the stone is half a stone behind the middle of the edge;
- the highest pixel of the blob, taken at the distance of the centre, gives how tall the thing is:
  a flat brown patch on the floor is not a stone, and a pile (a quarry) is about 110 mm per stone.
  For a pile, the depth is measured again on the top of the pile (220 or 330 mm high).
"""

import cv2
import numpy as np

from vision.common.detectionTypes import ColorCandidate
from vision.common.visionConfig import CameraCalibration, VisionConfig
from vision.geometry.poseTransforms import (
    buildCameraToRobotRotation,
    buildPixelRays,
    intersectRaysWithHeight,
    normalizeAxisAngleDeg,
)


class BlobFloorGeometry:
    """Measures blobs on the floor. Created once at startup, with the camera calibration."""

    def __init__(self, config: VisionConfig, calibration: CameraCalibration) -> None:
        self.config: VisionConfig = config
        self.calibration: CameraCalibration = calibration
        self.cameraToRobot: np.ndarray = buildCameraToRobotRotation(config.cameraMount)
        self.cameraFloorPoint: np.ndarray = np.array([config.cameraMount.xMm, config.cameraMount.yMm])

    def measure(self, candidate: ColorCandidate, imageHeightPx: int) -> None:
        """Fills the floor position, yaw, bottom edge and height of a candidate (hasPosition stays False if it cannot)."""
        bottomChain, topChain = self._splitOutline(candidate.contourPx)
        # A blob cut by the bottom of the picture does not show where it touches the floor
        touchesBottomBorder: bool = bool(np.any(bottomChain[:, 1] >= imageHeightPx - 2))
        if len(bottomChain) < 2 or touchesBottomBorder:
            return
        isOnFloor, floorPoints = intersectRaysWithHeight(
            buildPixelRays(bottomChain, self.calibration, self.cameraToRobot), self.config.cameraMount, 0.0)
        if not np.all(isOnFloor):
            return
        edgeStart, edgeEnd = self._findLongestEdge(floorPoints[:, :2])
        edgeVector: np.ndarray = edgeEnd - edgeStart
        edgeLengthMm: float = float(np.linalg.norm(edgeVector))
        if edgeLengthMm < 1.0:
            return
        topPixel: np.ndarray = candidate.contourPx[int(np.argmin(candidate.contourPx[:, 1]))]
        candidate.hasPosition = True
        candidate.bottomEdgeMm = edgeLengthMm
        candidate.bottomEdgeFloorMm = floorPoints[:, :2]
        # A blob cut by the top of the picture hides its far edge: then the depth is unknown (0)
        # and only the length of the edge decides which side we see
        touchesTopBorder: bool = bool(topChain[:, 1].min() <= 1)
        # First as one lying stone; if it stands much taller, again as a pile of that many stones
        self._placeOnFloor(candidate, (edgeStart, edgeEnd), topChain, topPixel, touchesTopBorder)
        stackLevels: int = self._countStackLevels(candidate)
        if stackLevels > 1:
            single = (candidate.depthMm, candidate.centerMm, candidate.yawDeg, candidate.sideMatchError,
                      candidate.heightMm)
            candidate.stackLevels = stackLevels
            self._placeOnFloor(candidate, (edgeStart, edgeEnd), topChain, topPixel, touchesTopBorder)
            # A tall-looking blob can be one stone seen end on (its far top edge is far away, so it
            # looks high): it is a pile only if the pile fits the measures better than one stone
            if candidate.sideMatchError > single[3]:
                candidate.stackLevels = 1
                (candidate.depthMm, candidate.centerMm, candidate.yawDeg, candidate.sideMatchError,
                 candidate.heightMm) = single

    def _placeOnFloor(self, candidate: ColorCandidate, edge: tuple[np.ndarray, np.ndarray], topChain: np.ndarray,
                      topPixel: np.ndarray, touchesTopBorder: bool) -> None:
        """Depth, centre, yaw and height of the candidate, taking it as a pile of stackLevels lying stones."""
        edgeStart, edgeEnd = edge
        topHeightMm: float = self.config.stone.widthMm * candidate.stackLevels
        candidate.depthMm = 0.0 if touchesTopBorder else self._measureDepthMm(topChain, edgeStart, edgeEnd, topHeightMm)
        candidate.centerMm, candidate.yawDeg, candidate.sideMatchError = self._placeStone(
            edgeStart, edgeEnd, candidate.depthMm)
        candidate.heightMm = self._measureHeightMm(topPixel, np.array(candidate.centerMm))

    def _countStackLevels(self, candidate: ColorCandidate) -> int:
        """How many lying stones high the blob is (1 to maxStackLevels), from its measured height."""
        levels: int = round(candidate.heightMm / self.config.stone.widthMm)
        return int(min(max(levels, 1), self.config.color.maxStackLevels))

    def _splitOutline(self, contourPx: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(bottom, top) parts of the convex outline, both from left to right.

        The convex hull goes round the blob; between its leftmost and rightmost points there are two
        paths, and the lower one (bigger y, the picture y goes down) is where the stone meets the floor.
        The steep ends of the bottom are vertical edges of the box, which do not touch the floor.
        """
        hull: np.ndarray = cv2.convexHull(contourPx.reshape(-1, 1, 2).astype(np.int32)).reshape(-1, 2)
        leftIndex: int = int(np.argmin(hull[:, 0]))
        rightIndex: int = int(np.argmax(hull[:, 0]))
        rolled: np.ndarray = np.roll(hull, -leftIndex, axis=0)
        splitIndex: int = (rightIndex - leftIndex) % len(hull)
        firstPath: np.ndarray = rolled[: splitIndex + 1]
        secondPath: np.ndarray = np.vstack([rolled[splitIndex:], rolled[:1]])[::-1]
        isFirstLower: bool = bool(firstPath[:, 1].mean() >= secondPath[:, 1].mean())
        lowerPath, upperPath = (firstPath, secondPath) if isFirstLower else (secondPath, firstPath)
        return self._trimSteepEnds(lowerPath.astype(np.float64)), upperPath.astype(np.float64)

    def _trimSteepEnds(self, chain: np.ndarray) -> np.ndarray:
        """Drops the segments at both ends of the chain that are steeper than maxBottomEdgeSlope."""
        maximumSlope: float = self.config.color.maxBottomEdgeSlope
        firstIndex: int = 0
        lastIndex: int = len(chain) - 1
        while lastIndex - firstIndex > 1 and isSteep(chain[firstIndex], chain[firstIndex + 1], maximumSlope):
            firstIndex += 1
        while lastIndex - firstIndex > 1 and isSteep(chain[lastIndex - 1], chain[lastIndex], maximumSlope):
            lastIndex -= 1
        return chain[firstIndex : lastIndex + 1]

    def _findLongestEdge(self, floorPoints: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """The longest straight part of the bottom edge on the floor: (start, end) in mm."""
        simplified: np.ndarray = cv2.approxPolyDP(floorPoints.reshape(-1, 1, 2).astype(np.float32),
                                                  self.config.color.edgeSimplifyMm, False).reshape(-1, 2)
        lengths: np.ndarray = np.linalg.norm(np.diff(simplified, axis=0), axis=1)
        longestIndex: int = int(np.argmax(lengths))
        return simplified[longestIndex].astype(np.float64), simplified[longestIndex + 1].astype(np.float64)

    def _placeStone(self, edgeStart: np.ndarray, edgeEnd: np.ndarray,
                    depthMm: float) -> tuple[tuple[float, float], float, float]:
        """Centre (x, y), yaw and match error of the stone whose bottom edge goes from edgeStart to edgeEnd.

        Two hypotheses: we see a long side (edge up to 320 mm, depth 110) or an end (edge up to
        110 mm, depth 320). An edge shorter than expected costs little (part of it may be hidden);
        a longer one or a wrong depth costs a lot. The one with the smaller relative error wins.
        Long side: the centre is 55 mm behind the edge. End: 160 mm behind, long side across the edge.
        """
        stone = self.config.stone
        edgeVector: np.ndarray = edgeEnd - edgeStart
        edgeLengthMm: float = float(np.linalg.norm(edgeVector))
        direction: np.ndarray = edgeVector / edgeLengthMm
        # A missing part of the edge costs a quarter of a longer one: hidden parts are common
        sideError: float = (max(0.0, edgeLengthMm - stone.lengthMm) / stone.lengthMm
                            + 0.25 * max(0.0, stone.lengthMm - edgeLengthMm) / stone.lengthMm
                            + abs(depthMm - stone.widthMm) / stone.widthMm)
        endError: float = (max(0.0, edgeLengthMm - stone.widthMm) / stone.widthMm
                           + 0.25 * max(0.0, stone.widthMm - edgeLengthMm) / stone.widthMm
                           + abs(depthMm - stone.lengthMm) / stone.lengthMm)
        isLongSide: bool = sideError <= endError
        behindDistanceMm: float = stone.widthMm / 2 if isLongSide else stone.lengthMm / 2
        middle: np.ndarray = (edgeStart + edgeEnd) / 2
        across: np.ndarray = np.array([-direction[1], direction[0]])
        # "Behind" is away from the camera: the stone is on the far side of the edge we see
        if float(np.dot(across, middle - self.cameraFloorPoint)) < 0:
            across = -across
        center: np.ndarray = middle + across * behindDistanceMm
        longDirection: np.ndarray = direction if isLongSide else across
        yawDeg: float = normalizeAxisAngleDeg(float(np.degrees(np.arctan2(longDirection[1], longDirection[0]))))
        return (float(center[0]), float(center[1])), yawDeg, min(sideError, endError)

    def _measureDepthMm(self, topChain: np.ndarray, edgeStart: np.ndarray, edgeEnd: np.ndarray,
                        topHeightMm: float) -> float:
        """How far behind the bottom edge the top of a lying stone (or pile) reaches, seen from above.

        The rays of the top of the outline cross the top plane (z = topHeightMm) on the far top edge;
        the farthest of those points behind the line of the bottom edge gives the depth.
        Points in front of the line (the ends of the outline, which are on the floor) do not count.
        """
        directions: np.ndarray = buildPixelRays(topChain, self.calibration, self.cameraToRobot)
        isValid, topPoints = intersectRaysWithHeight(directions, self.config.cameraMount, topHeightMm)
        if not np.any(isValid):
            return 0.0
        edgeDirection: np.ndarray = (edgeEnd - edgeStart) / max(float(np.linalg.norm(edgeEnd - edgeStart)), 1e-9)
        across: np.ndarray = np.array([-edgeDirection[1], edgeDirection[0]])
        # Behind = away from the camera, as in _placeStone
        if float(np.dot(across, (edgeStart + edgeEnd) / 2 - self.cameraFloorPoint)) < 0:
            across = -across
        behindDistances: np.ndarray = (topPoints[isValid, :2] - edgeStart) @ across
        return float(max(0.0, behindDistances.max()))

    def _measureHeightMm(self, topPixel: np.ndarray, centerMm: np.ndarray) -> float:
        """Height at which the ray of the highest blob pixel passes above the centre of the stone."""
        direction: np.ndarray = buildPixelRays(topPixel.reshape(1, 2), self.calibration, self.cameraToRobot)[0]
        horizontalSpeed: float = float(np.hypot(direction[0], direction[1]))
        if horizontalSpeed < 1e-9:
            return 0.0
        distanceToCenter: float = float(np.linalg.norm(centerMm - self.cameraFloorPoint))
        return float(self.config.cameraMount.zMm + direction[2] * distanceToCenter / horizontalSpeed)


def isSteep(firstPoint: np.ndarray, secondPoint: np.ndarray, maximumSlope: float) -> bool:
    """True if the segment rises more than maximumSlope times what it advances sideways."""
    deltaX: float = abs(float(secondPoint[0] - firstPoint[0]))
    deltaY: float = abs(float(secondPoint[1] - firstPoint[1]))
    return deltaY > maximumSlope * max(deltaX, 1e-9)
