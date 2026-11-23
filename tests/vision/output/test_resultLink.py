"""Tests of the link to the robot: publisher (UDP and serial), relay of the Raspberry and test receiver.

UDP goes through 127.0.0.1 and the serial port is pyserial's loop:// (what is written comes back),
so no robot, cable or Wi-Fi is needed.
"""

import socket
import time

from vision.apps.link.messageReceiver import MessageReceiver
from vision.apps.link.robotRelay import RobotRelay
from vision.common.outputConfig import OutputConfig, OutputTransport
from vision.common.visionTypes import DetectionSource, StoneDetection, VisionResult, VisionStatus
from vision.output.messageCodec import decodeResult
from vision.output.messageFormat import extractMessages
from vision.output.resultPublisher import ResultPublisher


def buildResult() -> VisionResult:
    return VisionResult(1000, 5.0, VisionStatus.OK, [StoneDetection(600.0, 50.0, 30.0, 0.9, DetectionSource.ARUCO)])


def findFreeUdpPort() -> int:
    probe: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    probe.bind(("127.0.0.1", 0))
    port: int = probe.getsockname()[1]
    probe.close()
    return port


def testUdpPublisherReachesTheReceiver() -> None:
    port: int = findFreeUdpPort()
    receiver: MessageReceiver = MessageReceiver(port, "", 0)
    assert receiver.open()
    publisher: ResultPublisher = ResultPublisher(OutputConfig(OutputTransport.UDP, "127.0.0.1", port))
    assert publisher.open()
    for _ in range(3):
        assert publisher.send(buildResult(), 2.0)
    received = []
    deadline: float = time.perf_counter() + 2.0
    while len(received) < 3 and time.perf_counter() < deadline:
        received.extend(receiver.readAvailable(0.1))
    publisher.close()
    receiver.close()
    assert [fields.counter for fields in received] == [0, 1, 2]
    assert receiver.lostCount == 0 and receiver.receivedCount == 3


def testSerialPublisherWritesWholeMessages() -> None:
    publisher: ResultPublisher = ResultPublisher(OutputConfig(OutputTransport.SERIAL, serialPort="loop://"))
    assert publisher.open() and publisher.serialPort is not None
    publisher.send(buildResult(), 1.0)
    publisher.send(buildResult(), 1.0)
    buffer: bytearray = bytearray(publisher.serialPort.read(1000))
    messages, droppedBytes = extractMessages(buffer)
    publisher.close()
    assert len(messages) == 2 and droppedBytes == 0
    isValid, decoded, _ = decodeResult(messages[0])
    assert isValid and decoded.stones[0].xMm == 600.0


def testNoneTransportSendsNothingAndNeverFails() -> None:
    publisher: ResultPublisher = ResultPublisher(OutputConfig())
    assert publisher.open() and publisher.send(buildResult(), 0.0)


def testMissingSerialPortOrWrongConfigIsReportedNotRaised() -> None:
    publisher: ResultPublisher = ResultPublisher(OutputConfig(OutputTransport.SERIAL, serialPort="/dev/noSuchPort"))
    assert not publisher.open() and publisher.lastError != ""
    for config in (OutputConfig(OutputTransport.UDP, udpPort=70000), OutputConfig(OutputTransport.SERIAL, serialBaudRate=0),
                   OutputConfig(OutputTransport.UDP, udpHost="no.such.host.invalid")):
        assert not ResultPublisher(config).open()


def testRelayForwardsValidMessagesAndRejectsDamagedOnes() -> None:
    port: int = findFreeUdpPort()
    relay: RobotRelay = RobotRelay(port, "loop://", 115200)
    assert relay.open() and relay.serialPort is not None
    sender: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    publisher: ResultPublisher = ResultPublisher(OutputConfig(OutputTransport.UDP, "127.0.0.1", port))
    publisher.open()
    publisher.send(buildResult(), 1.0)
    sender.sendto(b"VS not a message", ("127.0.0.1", port))
    deadline: float = time.perf_counter() + 2.0
    while relay.forwardedCount + relay.rejectedCount < 2 and time.perf_counter() < deadline:
        if relay.selector.select(timeout=0.1):
            relay.forwardOne()
    forwarded: bytes = relay.serialPort.read(1000)
    relay.close()
    publisher.close()
    sender.close()
    assert relay.forwardedCount == 1 and relay.rejectedCount == 1
    assert decodeResult(forwarded)[0]
