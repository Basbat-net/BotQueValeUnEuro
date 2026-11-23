"""Binary message with the stones, from the vision computer to the robot. Version 1.

Only the Python standard library: the robot Raspberry runs this file (to check and forward the
messages) without numpy or OpenCV. The byte table, for whoever writes the ESP32 side, is in
docs/vision/visionMessage.md. All numbers are little-endian (the ESP32 and the PCs are too).

    offset  size  field
    0       2     magic: the letters 'V' 'S' (0x56 0x53), to find the start of a message
    2       1     version: 1
    3       1     status: VisionStatus code (0 OK, 1 NO_FRAME, 2 NOT_CALIBRATED, 3 CONFIG_ERROR)
    4       2     counter: +1 per message, wraps 65535 -> 0 (a jump means lost messages)
    6       4     timestampMs: capture time, wraps after 49.7 days
    10      2     ageMs: from the frame reaching the vision program to the send (clocks differ!)
    12      2     processing time in tenths of ms
    14      1     stone count N (at most 255)
    15      8*N   per stone: x mm (int16), y mm (int16), yaw in tenths of degree (int16),
                  confidence in % (uint8), source code (uint8: 0 ARUCO, 1 COLOR, 2 BOTH)
    15+8N   2     CRC-16/CCITT-FALSE of every byte before it
"""

import binascii
import struct
from dataclasses import dataclass, field


@dataclass
class MessageStone:
    """One stone as it travels: whole numbers only."""

    xMm: int
    yMm: int
    yawDeciDeg: int
    confidencePercent: int
    sourceCode: int


@dataclass
class MessageFields:
    """Everything in one message, as whole numbers ready to pack."""

    statusCode: int
    counter: int
    timestampMs: int
    ageMs: int
    processingDeciMs: int
    stones: list[MessageStone] = field(default_factory=list)


class MessageLayout:
    """Byte layout of version 1. Class attributes, not global variables (team rule)."""

    magic: bytes = b"VS"
    version: int = 1
    # magic, version, status, counter, timestamp, age, processing time, stone count
    headerFormat: str = "<2sBBHIHHB"
    # x, y, yaw, confidence, source
    stoneFormat: str = "<hhhBB"
    crcFormat: str = "<H"
    headerSize: int = struct.calcsize(headerFormat)
    stoneSize: int = struct.calcsize(stoneFormat)
    crcSize: int = struct.calcsize(crcFormat)
    maxStones: int = 255


def computeCrc(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (polynomial 0x1021, start 0xFFFF): b'123456789' gives 0x29B1."""
    return binascii.crc_hqx(data, 0xFFFF)


def clampToRange(value: float, lowest: int, highest: int) -> int:
    """Rounds and keeps a number inside what its field can hold, instead of failing to pack it."""
    return int(min(max(round(value), lowest), highest))


def encodeMessage(fields: MessageFields) -> bytes:
    """Packs the fields into the bytes of one message (stones beyond 255 are cut)."""
    stones: list[MessageStone] = fields.stones[: MessageLayout.maxStones]
    header: bytes = struct.pack(
        MessageLayout.headerFormat, MessageLayout.magic, MessageLayout.version,
        clampToRange(fields.statusCode, 0, 255), fields.counter & 0xFFFF, fields.timestampMs & 0xFFFFFFFF,
        clampToRange(fields.ageMs, 0, 0xFFFF), clampToRange(fields.processingDeciMs, 0, 0xFFFF), len(stones))
    body: bytes = b"".join(
        struct.pack(MessageLayout.stoneFormat, clampToRange(stone.xMm, -32768, 32767),
                    clampToRange(stone.yMm, -32768, 32767), clampToRange(stone.yawDeciDeg, -32768, 32767),
                    clampToRange(stone.confidencePercent, 0, 100), clampToRange(stone.sourceCode, 0, 255))
        for stone in stones)
    return header + body + struct.pack(MessageLayout.crcFormat, computeCrc(header + body))


def expectedLength(stoneCount: int) -> int:
    """Bytes of a whole message with that many stones."""
    return MessageLayout.headerSize + MessageLayout.stoneSize * stoneCount + MessageLayout.crcSize


def decodeMessage(data: bytes) -> tuple[bool, MessageFields, str]:
    """Unpacks one whole message. Returns (isValid, fields, reason it is not valid)."""
    emptyFields: MessageFields = MessageFields(0, 0, 0, 0, 0)
    if len(data) < expectedLength(0) or data[:2] != MessageLayout.magic:
        return False, emptyFields, "too short or no 'VS' at the start"
    if data[2] != MessageLayout.version:
        return False, emptyFields, f"version {data[2]} is not {MessageLayout.version}"
    stoneCount: int = data[MessageLayout.headerSize - 1]
    if len(data) != expectedLength(stoneCount):
        return False, emptyFields, f"{len(data)} bytes, {expectedLength(stoneCount)} expected"
    crcStart: int = len(data) - MessageLayout.crcSize
    (receivedCrc,) = struct.unpack(MessageLayout.crcFormat, data[crcStart:])
    if receivedCrc != computeCrc(data[:crcStart]):
        return False, emptyFields, "wrong CRC: the message was damaged on the way"
    _, _, statusCode, counter, timestampMs, ageMs, processingDeciMs, _ = struct.unpack(
        MessageLayout.headerFormat, data[: MessageLayout.headerSize])
    stones: list[MessageStone] = [
        MessageStone(*struct.unpack_from(MessageLayout.stoneFormat, data,
                                         MessageLayout.headerSize + index * MessageLayout.stoneSize))
        for index in range(stoneCount)]
    return True, MessageFields(statusCode, counter, timestampMs, ageMs, processingDeciMs, stones), ""


def findNextValidStart(buffer: bytearray) -> int:
    """Index (after 0) where a whole valid message starts, or -1 if there is none yet."""
    start: int = buffer.find(MessageLayout.magic, 1)
    while start > 0:
        if len(buffer) - start >= MessageLayout.headerSize:
            length: int = expectedLength(buffer[start + MessageLayout.headerSize - 1])
            if len(buffer) - start >= length and decodeMessage(bytes(buffer[start : start + length]))[0]:
                return start
        start = buffer.find(MessageLayout.magic, start + 1)
    return -1


def extractMessages(buffer: bytearray) -> tuple[list[bytes], int]:
    """Takes every whole valid message out of a byte stream (a serial port). Returns (messages, bytes dropped).

    Bytes are removed from the buffer as they are used; an incomplete message stays for the next call.
    After garbage or a damaged message it searches the next 'VS', so one bad byte loses one message.
    """
    messages: list[bytes] = []
    droppedBytes: int = 0
    while True:
        start: int = buffer.find(MessageLayout.magic)
        if start < 0:
            # Keep a last 'V': it may be the first half of the next magic
            keptBytes: int = 1 if buffer[-1:] == MessageLayout.magic[:1] else 0
            droppedBytes += len(buffer) - keptBytes
            del buffer[: len(buffer) - keptBytes]
            return messages, droppedBytes
        droppedBytes += start
        del buffer[:start]
        if len(buffer) < MessageLayout.headerSize:
            return messages, droppedBytes
        length: int = expectedLength(buffer[MessageLayout.headerSize - 1])
        if len(buffer) < length:
            # A false 'VS' can announce many stones and make us wait for bytes that never form a message:
            # if a whole valid message already starts later, this start was false
            laterStart: int = findNextValidStart(buffer)
            if laterStart < 0:
                return messages, droppedBytes
            droppedBytes += laterStart
            del buffer[:laterStart]
            continue
        isValid, _, _ = decodeMessage(bytes(buffer[:length]))
        if isValid:
            messages.append(bytes(buffer[:length]))
            del buffer[:length]
        else:
            # Not a real start (or damaged): skip this 'V' and look again
            droppedBytes += 1
            del buffer[:1]
