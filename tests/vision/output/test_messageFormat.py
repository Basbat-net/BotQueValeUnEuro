"""Tests of the message to the robot. The reference bytes freeze version 1: if a test here fails,
the ESP32 side would read the messages wrong, so change the version instead of the bytes.
"""

from vision.common.visionTypes import DetectionSource, StoneDetection, VisionResult, VisionStatus
from vision.output.messageCodec import decodeResult, encodeResult
from vision.output.messageFormat import (
    MessageFields,
    MessageStone,
    computeCrc,
    decodeMessage,
    encodeMessage,
    extractMessages,
)

# Checked by hand against the table in messageFormat.py (little-endian):
# 5653 'VS' | 01 version | 00 status OK | 0201 counter 258 | 04030201 timestamp | 0c00 age 12 | 5500 85 tenths
# | 02 stones | c201 x 450 | 88ff y -120 | 2c01 yaw 300 | 5f 95% | 02 BOTH | fbff -5 | e803 1000 | 7dfc -899
# | 28 40% | 01 COLOR | db95 CRC
REFERENCE_HEX: str = "565301000201040302010c00550002c20188ff2c015f02fbffe8037dfc2801db95"


def buildReferenceFields() -> MessageFields:
    return MessageFields(0, 258, 0x01020304, 12, 85,
                         [MessageStone(450, -120, 300, 95, 2), MessageStone(-5, 1000, -899, 40, 1)])


def testCrcIsTheStandardOne() -> None:
    # The published check value of CRC-16/CCITT-FALSE: the ESP32 code must give the same
    assert computeCrc(b"123456789") == 0x29B1


def testReferenceBytesDoNotChange() -> None:
    assert encodeMessage(buildReferenceFields()).hex() == REFERENCE_HEX


def testEnumCodesDoNotChange() -> None:
    # These numbers travel in the message: renumbering them breaks the robot side
    assert [status.value for status in VisionStatus] == [0, 1, 2, 3]
    assert [source.value for source in DetectionSource] == [0, 1, 2]


def testDecodeGivesBackTheFields() -> None:
    isValid, fields, _ = decodeMessage(bytes.fromhex(REFERENCE_HEX))
    assert isValid and fields == buildReferenceFields()


def testOneChangedByteIsDetected() -> None:
    damaged: bytearray = bytearray.fromhex(REFERENCE_HEX)
    damaged[17] ^= 0x01
    isValid, _, reason = decodeMessage(bytes(damaged))
    assert not isValid and "CRC" in reason


def testValuesOutOfRangeAreClampedNotFailed() -> None:
    fields: MessageFields = MessageFields(1, 70000, 1_763_000_000_000, 99999, -3,
                                          [MessageStone(50000, -50000, 0, 150, 0)])
    isValid, decoded, _ = decodeMessage(encodeMessage(fields))
    assert isValid
    # Counter and timestamp wrap; the rest is held at the edge of what the field can hold
    assert decoded.counter == 70000 & 0xFFFF and decoded.timestampMs == 1_763_000_000_000 & 0xFFFFFFFF
    assert decoded.ageMs == 0xFFFF and decoded.processingDeciMs == 0
    assert (decoded.stones[0].xMm, decoded.stones[0].yMm, decoded.stones[0].confidencePercent) == (32767, -32768, 100)


def testStreamResynchronisesAfterGarbageAndASplitMessage() -> None:
    message: bytes = bytes.fromhex(REFERENCE_HEX)
    damaged: bytearray = bytearray(message)
    damaged[20] ^= 0xFF
    buffer: bytearray = bytearray(b"\x00VSxx" + bytes(damaged) + message + message[:10])
    messages, droppedBytes = extractMessages(buffer)
    assert messages == [message]
    assert droppedBytes > 0
    # The first 10 bytes of the next message wait in the buffer for the rest
    assert bytes(buffer) == message[:10]
    buffer.extend(message[10:])
    messages, _ = extractMessages(buffer)
    assert messages == [message] and len(buffer) == 0


def testResultGoesAndComesBack() -> None:
    result: VisionResult = VisionResult(123456, 8.37, VisionStatus.OK,
                                        [StoneDetection(512.4, -87.6, -45.27, 0.95, DetectionSource.BOTH)])
    isValid, decoded, fields = decodeResult(encodeResult(result, 7, 3.2, 32))
    assert isValid and fields.counter == 7 and fields.ageMs == 3
    assert decoded.status == VisionStatus.OK and decoded.timestampMs == 123456
    stone: StoneDetection = decoded.stones[0]
    # Whole mm, tenths of a degree and whole percent: the precision the message keeps
    assert (stone.xMm, stone.yMm, stone.yawDeg, stone.confidence) == (512.0, -88.0, -45.3, 0.95)
    assert stone.source == DetectionSource.BOTH


def testStonesThatAreNotNumbersAreLeftOut() -> None:
    stones: list[StoneDetection] = [StoneDetection(float("nan"), 0.0, 0.0, 0.9, DetectionSource.ARUCO),
                                    StoneDetection(500.0, 0.0, float("inf"), 0.9, DetectionSource.ARUCO),
                                    StoneDetection(600.0, 10.0, 5.0, 0.9, DetectionSource.ARUCO)]
    isValid, decoded, fields = decodeResult(encodeResult(VisionResult(0, float("nan"), VisionStatus.OK, stones), 0,
                                                         float("nan"), 32))
    assert isValid and [stone.xMm for stone in decoded.stones] == [600.0] and fields.ageMs == 0
    _, noStones, _ = decodeResult(encodeResult(VisionResult(0, 1.0, VisionStatus.OK, stones), 0, 0.0, -1))
    assert noStones.stones == []


def testOnlyTheNearestStonesAreSent() -> None:
    stones: list[StoneDetection] = [StoneDetection(100.0 * index, 0.0, 0.0, 0.9, DetectionSource.ARUCO)
                                    for index in range(1, 6)]
    _, decoded, _ = decodeResult(encodeResult(VisionResult(0, 1.0, VisionStatus.OK, stones), 0, 0.0, 3))
    assert [stone.xMm for stone in decoded.stones] == [100.0, 200.0, 300.0]
