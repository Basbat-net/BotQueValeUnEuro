# Vision message to the robot (version 1)

For whoever writes the ESP32 side. It is a **proposal** (2026-11-23): agree it before writing the parser.
The Python side is `src/vision/output/messageFormat.py`; its tests freeze the bytes below.

## Bytes

Little-endian (the ESP32 is little-endian too, so a packed struct reads it directly).

| Offset | Size | Type | Field | Meaning |
|---|---|---|---|---|
| 0 | 2 | char | magic | `'V'` `'S'` (0x56 0x53): start of a message |
| 2 | 1 | uint8 | version | 1 |
| 3 | 1 | uint8 | status | 0 OK, 1 NO_FRAME, 2 NOT_CALIBRATED, 3 CONFIG_ERROR |
| 4 | 2 | uint16 | counter | +1 per message, 65535 then 0. A jump = lost messages |
| 6 | 4 | uint32 | timestampMs | Capture time of the picture (clock of the vision computer; wraps after 49.7 days) |
| 10 | 2 | uint16 | ageMs | From the picture reaching the vision program to the send |
| 12 | 2 | uint16 | processingDeciMs | Processing time in tenths of ms |
| 14 | 1 | uint8 | stoneCount | N, at most 255 (the config sends at most 32) |
| 15 + 8k | 2 | int16 | xMm | Stone k: forward of the robot origin, mm |
| 17 + 8k | 2 | int16 | yMm | Stone k: to the left, mm |
| 19 + 8k | 2 | int16 | yawDeciDeg | Stone k: angle of its long side, tenths of a degree, -900 to 899 |
| 21 + 8k | 1 | uint8 | confidencePercent | Stone k: 0 to 100 |
| 22 + 8k | 1 | uint8 | source | Stone k: 0 ARUCO, 1 COLOR, 2 BOTH |
| 15 + 8N | 2 | uint16 | crc | CRC-16/CCITT-FALSE of bytes 0 to 14 + 8N |

Length: 17 + 8N bytes. Stones come nearest first. With a status other than 0 there are no stones.

**CRC-16/CCITT-FALSE:** polynomial 0x1021, initial value 0xFFFF, no reflection, no final XOR. Check: the bytes of the text `123456789` give `0x29B1`.

## Reference message

`565301000201040302010c00550002c20188ff2c015f02fbffe8037dfc2801db95`

Status OK, counter 258, timestamp 0x01020304, age 12 ms, 8.5 ms of processing, 2 stones:
(450, -120) mm, yaw 30.0 degrees, 95 %, BOTH; and (-5, 1000) mm, yaw -89.9 degrees, 40 %, COLOR.

## Reading it from a byte stream (UART)

1. Keep a buffer of received bytes.
2. Look for `0x56 0x53`. Drop the bytes before it.
3. Wait for 15 bytes; read N at offset 14; wait for 17 + 8N bytes.
4. Compute the CRC of the first 15 + 8N bytes. If it matches the last two: a valid message, use it and drop it from the buffer.
   If not: drop one byte (the `0x56`) and go back to step 2.
5. Compare the counter with the last one: `(counter - last - 1) mod 65536` messages were lost.

What to do when no message arrives for a while is up to the strategy (go on with the plan and the odometry).
