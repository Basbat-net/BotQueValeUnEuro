"""Smooths the stones for the 3D twin of the dashboard, so the boxes glide instead of trembling.

Only for drawing: the robot receives the raw stones of each image (the contract), never these.
- Each stone is paired with the nearest twin of the last image (a "track" with a number).
- Position: a mix of the old and the new one (smoothing = how much of the old one stays).
- Rotation: a box looks the same turned 180 degrees about any axis, or 90 degrees about its long
  side (square ends). The new rotation is first turned to the look-alike closest to the old one,
  so the twin never spins round to show the same box, and then mixed.
- A stone that stops being seen stays a little while as a grey ghost, then goes away.
"""

from dataclasses import dataclass

import numpy as np

from vision.common.detectionTypes import StoneEstimate
from vision.common.visionTypes import DetectionSource


@dataclass
class TwinStone:
    """One box of the 3D twin."""

    trackId: int
    centerMm: np.ndarray
    rotation: np.ndarray
    source: DetectionSource
    confidence: float
    level: int
    lastSeenSeconds: float
    isGhost: bool = False


class TwinSmoother:
    """Keeps the tracks between images. Created once."""

    def __init__(self, smoothing: float, matchDistanceMm: float, ghostSeconds: float) -> None:
        # 0 shows the raw stones; 0.9 is very smooth but late
        self.smoothing: float = min(max(smoothing, 0.0), 0.95)
        self.matchDistanceMm: float = matchDistanceMm
        self.ghostSeconds: float = ghostSeconds
        self.tracks: list[TwinStone] = []
        self.nextTrackId: int = 1
        self.symmetries: list[np.ndarray] = buildBoxSymmetries()

    def update(self, stones: list[StoneEstimate], nowSeconds: float) -> list[TwinStone]:
        """The twin after one image: matched tracks move, new stones get a track, lost ones fade to ghosts."""
        unmatchedTracks: list[TwinStone] = list(self.tracks)
        updatedTracks: list[TwinStone] = []
        for stone in sorted(stones, key=lambda item: -item.confidence):
            track: TwinStone | None = self._findNearestTrack(stone, unmatchedTracks)
            if track is None:
                track = TwinStone(self.nextTrackId, stone.centerMm.copy(), stone.rotation.copy(), stone.source,
                                  stone.confidence, stone.level, nowSeconds)
                self.nextTrackId += 1
            else:
                unmatchedTracks.remove(track)
                self._blendInto(track, stone)
            track.source, track.confidence, track.level = stone.source, stone.confidence, stone.level
            track.lastSeenSeconds, track.isGhost = nowSeconds, False
            updatedTracks.append(track)
        for track in unmatchedTracks:
            if nowSeconds - track.lastSeenSeconds < self.ghostSeconds:
                track.isGhost = True
                updatedTracks.append(track)
        self.tracks = updatedTracks
        return list(self.tracks)

    def clear(self) -> None:
        """Forgets every track (a new video, or the user asked)."""
        self.tracks = []

    def _findNearestTrack(self, stone: StoneEstimate, candidates: list[TwinStone]) -> TwinStone | None:
        """The closest track within matchDistanceMm (in 3D, so stacked stones keep their own track)."""
        distances: list[float] = [float(np.linalg.norm(track.centerMm - stone.centerMm)) for track in candidates]
        if not distances or min(distances) > self.matchDistanceMm:
            return None
        return candidates[int(np.argmin(distances))]

    def _blendInto(self, track: TwinStone, stone: StoneEstimate) -> None:
        """Mixes the new position and rotation into the track."""
        keep: float = self.smoothing
        track.centerMm = keep * track.centerMm + (1.0 - keep) * stone.centerMm
        aligned: np.ndarray = alignToReference(stone.rotation, track.rotation, self.symmetries)
        track.rotation = orthonormalize(keep * track.rotation + (1.0 - keep) * aligned)


def buildBoxSymmetries() -> list[np.ndarray]:
    """The 8 turns that leave the box looking the same (in its own frame, x = long side)."""
    halfTurns: list[np.ndarray] = [np.diag(signs) for signs in ([1, 1, 1], [1, -1, -1], [-1, 1, -1], [-1, -1, 1])]
    quarterTurnAboutX: np.ndarray = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])
    return halfTurns + [turn @ quarterTurnAboutX for turn in halfTurns]


def alignToReference(rotation: np.ndarray, reference: np.ndarray, symmetries: list[np.ndarray]) -> np.ndarray:
    """Among the look-alikes of rotation, the one closest to reference (largest trace of the difference)."""
    lookAlikes: list[np.ndarray] = [rotation @ symmetry for symmetry in symmetries]
    closeness: list[float] = [float(np.trace(reference.T @ lookAlike)) for lookAlike in lookAlikes]
    return lookAlikes[int(np.argmax(closeness))]


def orthonormalize(matrix: np.ndarray) -> np.ndarray:
    """The rotation closest to a mixed matrix (the mix of two rotations is not a rotation)."""
    leftVectors, _, rightVectors = np.linalg.svd(matrix)
    rotation: np.ndarray = leftVectors @ rightVectors
    if np.linalg.det(rotation) < 0:
        leftVectors[:, -1] *= -1
        rotation = leftVectors @ rightVectors
    return rotation
