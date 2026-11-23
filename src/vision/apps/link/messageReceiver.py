"""Stand-in for the ESP32: receives the vision messages (UDP or serial) and checks them.

It does what the ESP32 will have to do: find each message in the byte stream, check its CRC,
read the stones and notice lost messages (a jump in the counter). Only the standard library
and pyserial, like the relay.
"""

import selectors
import socket
import time

import serial

from vision.output.messageFormat import MessageFields, decodeMessage, extractMessages


class MessageReceiver:
    """Reads messages from a UDP port or a serial port. Created once at startup."""

    def __init__(self, udpPort: int, serialPortName: str, baudRate: int) -> None:
        # udpPort > 0 listens on UDP; otherwise it reads serialPortName
        self.udpPort: int = udpPort
        self.serialPortName: str = serialPortName
        self.baudRate: int = baudRate
        self.udpSocket: socket.socket | None = None
        self.serialPort: serial.Serial | None = None
        self.selector: selectors.DefaultSelector = selectors.DefaultSelector()
        self.serialBuffer: bytearray = bytearray()
        self.receivedCount: int = 0
        self.lostCount: int = 0
        self.damagedBytes: int = 0
        self.lastCounter: int = -1
        self.lastFields: MessageFields = MessageFields(0, 0, 0, 0, 0)
        self.isStopRequested: bool = False
        self.lastError: str = ""

    def open(self) -> bool:
        """Opens the UDP port or the serial port. False if it fails (see lastError)."""
        try:
            # Recovery only: a busy or missing port is reported, not propagated
            if self.udpPort > 0:
                self.udpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.udpSocket.bind(("0.0.0.0", self.udpPort))
                self.udpSocket.setblocking(False)
                self.selector.register(self.udpSocket, selectors.EVENT_READ)
            else:
                self.serialPort = serial.serial_for_url(self.serialPortName, baudrate=self.baudRate, timeout=0)
        except (OSError, serial.SerialException) as error:
            self.lastError = f"cannot open the receiver: {error}"
            return False
        return True

    def requestStop(self) -> None:
        """Asks the loop to finish."""
        self.isStopRequested = True

    def readAvailable(self, waitSeconds: float) -> list[MessageFields]:
        """Every whole valid message that arrived, waiting at most waitSeconds for the first one."""
        rawMessages: list[bytes] = self._readUdp(waitSeconds) if self.udpSocket is not None else self._readSerial(
            waitSeconds)
        validFields: list[MessageFields] = []
        for rawMessage in rawMessages:
            isValid, fields, _ = decodeMessage(rawMessage)
            if not isValid:
                self.damagedBytes += len(rawMessage)
                continue
            self._countMessage(fields)
            validFields.append(fields)
        return validFields

    def _readUdp(self, waitSeconds: float) -> list[bytes]:
        """Each datagram is one message."""
        datagrams: list[bytes] = []
        maximumDatagramBytes: int = 2048
        if self.udpSocket is None or not self.selector.select(timeout=waitSeconds):
            return datagrams
        while self.selector.select(timeout=0):
            try:
                # Recovery only: select said it is ready, but the network can still fail
                datagram, _ = self.udpSocket.recvfrom(maximumDatagramBytes)
            except OSError as error:
                self.lastError = f"receive failed: {error}"
                break
            datagrams.append(datagram)
        return datagrams

    def _readSerial(self, waitSeconds: float) -> list[bytes]:
        """A serial port gives a stream of bytes: the messages are cut out of it by their 'VS' and CRC."""
        if self.serialPort is None:
            return []
        time.sleep(waitSeconds if self.serialPort.in_waiting == 0 else 0.0)
        self.serialBuffer.extend(self.serialPort.read(self.serialPort.in_waiting))
        messages, droppedBytes = extractMessages(self.serialBuffer)
        self.damagedBytes += droppedBytes
        return messages

    def _countMessage(self, fields: MessageFields) -> None:
        """Counts the message and the ones lost before it (the counter wraps at 65536)."""
        if self.lastCounter >= 0:
            self.lostCount += (fields.counter - self.lastCounter - 1) % 0x10000
        self.lastCounter = fields.counter
        self.receivedCount += 1
        self.lastFields = fields

    def close(self) -> None:
        """Releases the port."""
        self.selector.close()
        if self.udpSocket is not None:
            self.udpSocket.close()
        if self.serialPort is not None:
            self.serialPort.close()
