"""Sends each black box result to the robot, by the transport chosen in the config.

- udp: one datagram per result to the robot Raspberry over Wi-Fi (the proposal of 2026-11-23).
- serial: a serial port or a pyserial URL. It covers a UART or USB cable, a Bluetooth serial
  port and an ESP-NOW bridge plugged by USB: changing the radio is changing the config.
- none: nothing is sent (tests, viewer).
Sending never blocks for long: UDP never waits, and a serial write waits at most serialWriteTimeoutMs.
If a message cannot go out, it is counted as failed and the next result goes on: a late result is
worse than a lost one.
"""

import logging
import socket

import serial

from vision.common.outputConfig import OutputConfig, OutputTransport
from vision.common.visionTypes import VisionResult
from vision.output.messageCodec import encodeResult


class ResultPublisher:
    """Owns the socket or the serial port. Created once at startup."""

    def __init__(self, config: OutputConfig) -> None:
        self.config: OutputConfig = config
        self.udpSocket: socket.socket | None = None
        # Address of the robot, looked up once in open(): a name lookup on every send could block
        self.udpAddress: tuple[str, int] = ("", 0)
        self.serialPort: serial.Serial | None = None
        # Message number, +1 per send (the receiver sees a jump when messages are lost)
        self.counter: int = 0
        self.sentCount: int = 0
        self.failedCount: int = 0
        # Why the last open or send failed. Empty if nothing failed
        self.lastError: str = ""

    def open(self) -> bool:
        """Opens the socket or the port. False if it cannot (see lastError)."""
        self.lastError = ""
        isUdpPortValid: bool = 0 < self.config.udpPort < 65536
        if not isUdpPortValid or self.config.serialBaudRate <= 0:
            self.lastError = f"wrong output config: udpPort {self.config.udpPort}, baud {self.config.serialBaudRate}"
            logging.error(self.lastError)
            return False
        try:
            # Recovery only: a missing port, an unknown host or a busy network is reported, not propagated
            if self.config.transport == OutputTransport.UDP:
                addresses: list = socket.getaddrinfo(self.config.udpHost, self.config.udpPort, socket.AF_INET,
                                                     socket.SOCK_DGRAM)
                self.udpAddress = addresses[0][4]
                self.udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udpSocket.setblocking(False)
            elif self.config.transport == OutputTransport.SERIAL:
                self.serialPort = serial.serial_for_url(self.config.serialPort, baudrate=self.config.serialBaudRate,
                                                        timeout=0,
                                                        write_timeout=self.config.serialWriteTimeoutMs / 1000)
        except (OSError, serial.SerialException) as error:
            self.lastError = f"cannot open the {self.config.transport.value} output: {error}"
            logging.error(self.lastError)
            return False
        return True

    def send(self, result: VisionResult, ageMs: float) -> bool:
        """Encodes and sends one result. False if it could not go out now."""
        message: bytes = encodeResult(result, self.counter, ageMs, self.config.maxStones)
        self.counter = (self.counter + 1) & 0xFFFF
        try:
            # Recovery only: a full buffer or a lost network drops this message, not the program
            if self.udpSocket is not None:
                self.udpSocket.sendto(message, self.udpAddress)
            elif self.serialPort is not None:
                self.serialPort.write(message)
        except (OSError, serial.SerialException) as error:
            self.failedCount += 1
            self.lastError = f"message {self.counter} not sent: {error}"
            return False
        self.sentCount += 1
        return True

    def close(self) -> None:
        """Releases the socket or the port."""
        if self.udpSocket is not None:
            self.udpSocket.close()
            self.udpSocket = None
        if self.serialPort is not None:
            self.serialPort.close()
            self.serialPort = None
