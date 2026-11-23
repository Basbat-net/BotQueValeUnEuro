"""Test receiver that stands in for the ESP32: prints what arrives and how well.

Run from the src/ folder, one of:
    python3 -m vision.apps.link.resultReceiverApp --udp-port 5005
    python3 -m vision.apps.link.resultReceiverApp --serial /dev/ttyUSB0 --baud 115200
Every second it prints the messages per second, the lost ones (counter jumps), the damaged bytes,
the mean age (time inside the vision program) and the nearest stone. --every-message prints them all.
"""

import argparse
import logging
import signal
import time

from vision.apps.link.messageReceiver import MessageReceiver


def describeNearestStone(receiver: MessageReceiver) -> str:
    """The first stone of the last message (the nearest one), in plain words."""
    fields = receiver.lastFields
    if not fields.stones:
        return f"status {fields.statusCode}, no stones"
    stone = fields.stones[0]
    sourceNames: dict[int, str] = {0: "ARUCO", 1: "COLOR", 2: "BOTH"}
    return (f"status {fields.statusCode}, {len(fields.stones)} stones, nearest at x {stone.xMm} mm, y {stone.yMm} mm, "
            f"yaw {stone.yawDeciDeg / 10:.1f} deg, {stone.confidencePercent}% {sourceNames.get(stone.sourceCode, '?')}")


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Receives and checks the vision messages")
    parser.add_argument("--udp-port", type=int, default=0, help="listen on this UDP port (0: use --serial)")
    parser.add_argument("--serial", default="/dev/ttyUSB0", help="serial port or pyserial URL")
    parser.add_argument("--baud", type=int, default=115200, help="speed of the serial port")
    parser.add_argument("--every-message", action="store_true", help="print every message, not one line per second")
    arguments: argparse.Namespace = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    receiver: MessageReceiver = MessageReceiver(arguments.udp_port, arguments.serial, arguments.baud)
    if not receiver.open():
        logging.error(receiver.lastError)
        return
    signal.signal(signal.SIGINT, lambda signalNumber, frame: receiver.requestStop())
    windowStart: float = time.perf_counter()
    windowCount: int = 0
    windowAgeMs: float = 0.0
    while not receiver.isStopRequested:
        for fields in receiver.readAvailable(0.2):
            windowCount += 1
            windowAgeMs += fields.ageMs
            if arguments.every_message:
                logging.info("#%d %s", fields.counter, describeNearestStone(receiver))
        elapsedSeconds: float = time.perf_counter() - windowStart
        if elapsedSeconds >= 1.0:
            logging.info("%.1f msg/s | lost %d | damaged bytes %d | mean age %.1f ms | %s", windowCount / elapsedSeconds,
                         receiver.lostCount, receiver.damagedBytes, windowAgeMs / max(windowCount, 1),
                         describeNearestStone(receiver))
            windowStart, windowCount, windowAgeMs = time.perf_counter(), 0, 0.0
    receiver.close()


if __name__ == "__main__":
    main()
