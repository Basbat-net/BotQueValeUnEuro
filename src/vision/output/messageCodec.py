"""Turns a VisionResult (the contract) into the bytes of the message, and back.

The byte layout lives in messageFormat.py, which does not know the contract,
so the robot Raspberry can use it without numpy (visionTypes.py needs numpy).
"""

import math

from vision.common.visionTypes import DetectionSource, StoneDetection, VisionResult, VisionStatus
from vision.output.messageFormat import MessageFields, MessageStone, decodeMessage, encodeMessage


def buildMessageFields(result: VisionResult, counter: int, ageMs: float, maxStones: int) -> MessageFields:
    """The whole-number fields of one result. Only the nearest maxStones stones are kept.

    A stone with a value that is not a number (NaN, infinite) is left out: it cannot be sent.
    """
    finiteStones: list[StoneDetection] = [
        stone for stone in result.stones
        if all(math.isfinite(value) for value in (stone.xMm, stone.yMm, stone.yawDeg, stone.confidence))]
    stones: list[MessageStone] = [
        MessageStone(round(stone.xMm), round(stone.yMm), round(stone.yawDeg * 10), round(stone.confidence * 100),
                     stone.source.value)
        for stone in finiteStones[: max(0, maxStones)]]
    safeAgeMs: float = ageMs if math.isfinite(ageMs) else 0.0
    safeProcessingMs: float = result.processingTimeMs if math.isfinite(result.processingTimeMs) else 0.0
    return MessageFields(result.status.value, counter, result.timestampMs, round(safeAgeMs),
                         round(safeProcessingMs * 10), stones)


def encodeResult(result: VisionResult, counter: int, ageMs: float, maxStones: int) -> bytes:
    """The bytes sent to the robot for one result."""
    return encodeMessage(buildMessageFields(result, counter, ageMs, maxStones))


def decodeResult(data: bytes) -> tuple[bool, VisionResult, MessageFields]:
    """A message back into a VisionResult, for the test receiver. False for a damaged or unknown message."""
    emptyResult: VisionResult = VisionResult(0, 0.0, VisionStatus.NO_FRAME)
    isValid, fields, _ = decodeMessage(data)
    knownStatus: list[int] = [status.value for status in VisionStatus]
    knownSources: list[int] = [source.value for source in DetectionSource]
    if not isValid or fields.statusCode not in knownStatus:
        return False, emptyResult, fields
    if any(stone.sourceCode not in knownSources for stone in fields.stones):
        return False, emptyResult, fields
    stones: list[StoneDetection] = [
        StoneDetection(float(stone.xMm), float(stone.yMm), stone.yawDeciDeg / 10, stone.confidencePercent / 100,
                       DetectionSource(stone.sourceCode))
        for stone in fields.stones]
    return True, VisionResult(fields.timestampMs, fields.processingDeciMs / 10, VisionStatus(fields.statusCode),
                              stones), fields
