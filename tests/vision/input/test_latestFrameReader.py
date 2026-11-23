"""Tests of the reader thread: a recorded source loses no frame, and one bad picture does not stop it."""

import time
from pathlib import Path

import cv2
import numpy as np

from vision.common.visionConfig import FrameSourceConfig, FrameSourceMode
from vision.input.latestFrameReader import LatestFrameReader, buildLatestFrameReader


def takeEverything(reader: LatestFrameReader) -> list[int]:
    """The grey level of every frame the reader gives, until the source ends (at most 5 s)."""
    levels: list[int] = []
    deadline: float = time.perf_counter() + 5.0
    while time.perf_counter() < deadline:
        isNew, frame = reader.takeLatest(0.1)
        if isNew:
            levels.append(int(frame.image[0, 0, 0]))
        elif reader.hasEnded or reader.hasFailed:
            break
    return levels


def testFolderWithAnUnreadablePictureIsReadToTheEnd(tmp_path: Path) -> None:
    for index in range(5):
        cv2.imwrite(str(tmp_path / f"frame{index:02d}.png"), np.full((48, 64, 3), index * 40, np.uint8))
    # A broken file in the middle (found by the code review: it used to stop the whole reader)
    (tmp_path / "frame02b.png").write_bytes(b"not a picture")
    reader: LatestFrameReader = buildLatestFrameReader(
        FrameSourceConfig(mode=FrameSourceMode.IMAGES, imagesFolder=str(tmp_path)))
    assert reader.start()
    levels: list[int] = takeEverything(reader)
    reader.stop()
    # Every good picture, in order, none dropped (a recorded source waits until each frame is taken)
    assert levels == [0, 40, 80, 120, 160]
    assert reader.hasEnded and not reader.hasFailed


def testStopEndsTheThreadAndClosesTheSource(tmp_path: Path) -> None:
    cv2.imwrite(str(tmp_path / "frame00.png"), np.zeros((48, 64, 3), np.uint8))
    reader: LatestFrameReader = buildLatestFrameReader(
        FrameSourceConfig(mode=FrameSourceMode.IMAGES, imagesFolder=str(tmp_path)))
    assert reader.start()
    reader.stop()
    assert not reader.thread.is_alive() and not reader.frameSource.isOpen
