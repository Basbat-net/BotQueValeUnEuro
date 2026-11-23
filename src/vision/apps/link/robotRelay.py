"""Runs on the robot Raspberry: receives the vision messages by Wi-Fi (UDP) and passes them to the ESP32 by UART.

Only the standard library and pyserial: no numpy or OpenCV on the robot for this.
Each datagram is checked (magic, length, CRC) before it is written to the serial port,
so damaged datagrams never reach the ESP32. Little is waited for: if the UART cannot take a
message within writeTimeoutMs, the rest of it is dropped and counted; part of it may already be
on the line, so the ESP32 must check the CRC and look for the next 'VS' (docs/vision/visionMessage.md).
"""

import logging
import selectors
import socket
import time

import serial

from vision.output.messageFormat import decodeMessage


class RobotRelay:
    """UDP in, UART out. Created once at startup."""

    def __init__(self, udpPort: int, serialPortName: str, baudRate: int, writeTimeoutMs: int = 50) -> None:
        self.udpPort: int = udpPort
        self.serialPortName: str = serialPortName
        self.baudRate: int = baudRate
        # A UART write waits at most this long; then the message is dropped (the next one is fresher)
        self.writeTimeoutMs: int = writeTimeoutMs
        self.udpSocket: socket.socket | None = None
        self.serialPort: serial.Serial | None = None
        self.selector: selectors.DefaultSelector = selectors.DefaultSelector()
        self.forwardedCount: int = 0
        self.rejectedCount: int = 0
        self.droppedCount: int = 0
        self.lastReport: float = time.perf_counter()
        self.isStopRequested: bool = False
        self.lastError: str = ""

    def open(self) -> bool:
        """Listens on the UDP port and opens the UART. False if either fails (see lastError)."""
        try:
            # Recovery only: a busy port or a missing UART is reported, not propagated
            self.udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udpSocket.bind(("0.0.0.0", self.udpPort))
            self.udpSocket.setblocking(False)
            self.serialPort = serial.serial_for_url(self.serialPortName, baudrate=self.baudRate, timeout=0,
                                                    write_timeout=self.writeTimeoutMs / 1000)
        except (OSError, serial.SerialException) as error:
            self.lastError = f"cannot open the relay: {error}"
            return False
        self.selector.register(self.udpSocket, selectors.EVENT_READ)
        return True

    def requestStop(self) -> None:
        """Asks the loop to finish."""
        self.isStopRequested = True

    def run(self, reportIntervalSeconds: float) -> None:
        """Forwards messages until a stop is requested. Waits at most half a second at a time."""
        maximumWaitSeconds: float = 0.5
        while not self.isStopRequested:
            if self.selector.select(timeout=maximumWaitSeconds):
                self.forwardOne()
            if time.perf_counter() - self.lastReport >= reportIntervalSeconds:
                logging.info("forwarded %d | rejected %d (damaged) | dropped %d (UART busy)",
                             self.forwardedCount, self.rejectedCount, self.droppedCount)
                self.lastReport = time.perf_counter()

    def forwardOne(self) -> None:
        """Reads one waiting datagram and writes it to the UART if it is a valid message."""
        if self.udpSocket is None or self.serialPort is None:
            return
        maximumDatagramBytes: int = 2048
        try:
            # Recovery only: select said it is ready, but the network can still fail
            datagram, _ = self.udpSocket.recvfrom(maximumDatagramBytes)
        except OSError as error:
            self.lastError = f"receive failed: {error}"
            return
        isValid, _, reason = decodeMessage(datagram)
        if not isValid:
            self.rejectedCount += 1
            self.lastError = reason
            return
        try:
            # Recovery only: a full UART buffer drops this message; the next one is fresher anyway
            self.serialPort.write(datagram)
            self.forwardedCount += 1
        except serial.SerialException:
            self.droppedCount += 1

    def close(self) -> None:
        """Releases the socket and the UART."""
        self.selector.close()
        if self.udpSocket is not None:
            self.udpSocket.close()
        if self.serialPort is not None:
            self.serialPort.close()
