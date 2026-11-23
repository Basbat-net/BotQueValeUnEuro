"""Parameters of the output side: where the result is sent and how the video is streamed.

The values live in config/visionConfig.json, never in the code.
VisionConfig (visionConfig.py) puts these sections together with the rest.
"""

from dataclasses import dataclass
from enum import Enum


class OutputTransport(Enum):
    """How the result leaves the program. The value is the text written in the JSON file."""

    # Nothing is sent: for tests and for the viewer
    NONE = "none"
    # A UDP datagram per result, over Wi-Fi (the proposal of 2026-11-23)
    UDP = "udp"
    # A serial port: UART, USB, a Bluetooth serial port or an ESP-NOW bridge plugged by USB
    SERIAL = "serial"


@dataclass
class OutputConfig:
    """Where the black box result goes. Changing the radio only changes this section."""

    transport: OutputTransport = OutputTransport.NONE
    # Address of the robot (its Raspberry) on the Wi-Fi network
    udpHost: str = "127.0.0.1"
    udpPort: int = 5005
    # A port name (/dev/ttyUSB0, COM3) or a pyserial URL (loop:// for tests)
    serialPort: str = "/dev/ttyUSB0"
    serialBaudRate: int = 115200
    # A serial write waits at most this long (a USB port whose reader stopped could block forever);
    # a message that does not fit in time is dropped and counted
    serialWriteTimeoutMs: int = 50
    # Stones per message: more are cut (the nearest ones are kept). The message format allows 255
    maxStones: int = 32
    # visionApp writes a summary to the log every this many ms
    statsIntervalMs: int = 2000


@dataclass
class SenderConfig:
    """Video sender of the robot: serves the camera images as MJPEG over HTTP."""

    port: int = 8080
    # 0 to 100: lower is a smaller frame but blurs the marker edges
    jpegQuality: int = 80
    # The sender never goes faster than this, even if the camera does
    maxFramesPerSecond: float = 30.0
