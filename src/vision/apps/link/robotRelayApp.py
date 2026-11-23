"""Runs on the robot Raspberry: vision messages from Wi-Fi (UDP) to the ESP32 (UART).

Run from the src/ folder:
    python3 -m vision.apps.link.robotRelayApp --udp-port 5005 --serial /dev/serial0 --baud 115200
To try it without an ESP32, --serial loop:// sends the bytes back to itself.
Needs only Python 3 and pyserial (pip install pyserial). Ctrl+C stops it.
"""

import argparse
import logging
import signal

from vision.apps.link.robotRelay import RobotRelay


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="UDP to UART relay of the vision messages")
    parser.add_argument("--udp-port", type=int, default=5005, help="port where the vision sends (output.udpPort)")
    parser.add_argument("--serial", default="/dev/serial0", help="UART of the ESP32, or a pyserial URL")
    parser.add_argument("--baud", type=int, default=115200, help="speed of the UART, the same as the ESP32")
    parser.add_argument("--write-timeout-ms", type=int, default=50, help="longest wait to write one message")
    parser.add_argument("--report-seconds", type=float, default=5.0, help="how often the counters are logged")
    arguments: argparse.Namespace = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    relay: RobotRelay = RobotRelay(arguments.udp_port, arguments.serial, arguments.baud, arguments.write_timeout_ms)
    if not relay.open():
        logging.error(relay.lastError)
        return
    signal.signal(signal.SIGINT, lambda signalNumber, frame: relay.requestStop())
    signal.signal(signal.SIGTERM, lambda signalNumber, frame: relay.requestStop())
    logging.info("relaying UDP %d -> %s at %d baud (Ctrl+C to stop)", arguments.udp_port, arguments.serial,
                 arguments.baud)
    relay.run(arguments.report_seconds)
    relay.close()


if __name__ == "__main__":
    main()
