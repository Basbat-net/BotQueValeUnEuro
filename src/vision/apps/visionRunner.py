"""The loop of the final program: take the newest image, run the black box, send the result. No screen.

Images are read by a LatestFrameReader thread: with a live camera or stream the loop always gets
the newest image (old ones are dropped), so the delay never grows; a recorded video loses none.
Every statsIntervalMs it writes one line to the log, so a match can be followed (and kept)
without a screen: images per second, processing time, how many stones and how many sends failed.
"""

import logging
import time

from vision.blackBoxFactory import buildVisionBlackBox
from vision.common.visionConfig import FrameSourceMode, VisionConfig
from vision.input.latestFrameReader import LatestFrameReader, buildLatestFrameReader
from vision.output.resultPublisher import ResultPublisher


class VisionRunner:
    """One run of the vision program, from opening the source to closing it. Created once."""

    def __init__(self, config: VisionConfig) -> None:
        self.config: VisionConfig = config
        self.frameReader: LatestFrameReader = buildLatestFrameReader(config.frameSource)
        self.blackBox = buildVisionBlackBox(config)
        self.publisher: ResultPublisher = ResultPublisher(config.output)
        # Set by the signal handler of the app (Ctrl+C or the system stopping the program)
        self.isStopRequested: bool = False
        self.windowStart: float = time.perf_counter()
        self.windowFrames: int = 0
        self.windowProcessingMs: float = 0.0
        self.lastStatusName: str = ""
        self.lastStoneCount: int = 0

    def requestStop(self) -> None:
        """Asks the loop to finish after the current image."""
        self.isStopRequested = True

    def run(self) -> str:
        """Processes images until the source ends or a stop is requested. Returns why it failed, or empty."""
        if self.blackBox.lastError != "":
            return f"wrong detector config: {self.blackBox.lastError}"
        if not self.publisher.open():
            return self.publisher.lastError
        if not self.frameReader.start():
            self.publisher.close()
            return f"could not open the frame source: {self.frameReader.lastError}"
        errorText: str = ""
        while not self.isStopRequested and errorText == "":
            errorText = self._processNextFrame()
        self.frameReader.stop()
        self.publisher.close()
        return "" if errorText == "end" else errorText

    def _processNextFrame(self) -> str:
        """One image through the box and out. Returns "" to go on, "end" at the end of a recording, or an error.

        A stream that was cut is reconnected by the reader thread; meanwhile this loop just waits.
        """
        maximumWaitSeconds: float = 0.5
        isNew, frame = self.frameReader.takeLatest(maximumWaitSeconds)
        if not isNew:
            if self.frameReader.hasEnded:
                return "end"
            if self.frameReader.hasFailed:
                return f"reading stopped: {self.frameReader.lastError}"
            return ""
        arrivalTime: float = time.perf_counter()
        result = self.blackBox.process(frame)
        processingAgeMs: float = (time.perf_counter() - arrivalTime) * 1000
        # Live sources carry the wall clock of arrival: the age also counts the wait in the reader
        isLive: bool = self.config.frameSource.mode in (FrameSourceMode.CAMERA, FrameSourceMode.STREAM)
        ageMs: float = time.time() * 1000 - frame.timestampMs if isLive else processingAgeMs
        self.publisher.send(result, max(ageMs, processingAgeMs))
        self.windowFrames += 1
        self.windowProcessingMs += result.processingTimeMs
        self.lastStatusName = result.status.name
        self.lastStoneCount = len(result.stones)
        self._logStatsWhenDue()
        return ""

    def _logStatsWhenDue(self) -> None:
        """Writes the summary line every statsIntervalMs and starts a new window."""
        elapsedSeconds: float = time.perf_counter() - self.windowStart
        if elapsedSeconds * 1000 < self.config.output.statsIntervalMs:
            return
        logging.info("%.1f fps | %.1f ms per image | status %s | %d stones | sent %d, failed %d",
                     self.windowFrames / elapsedSeconds, self.windowProcessingMs / max(self.windowFrames, 1),
                     self.lastStatusName, self.lastStoneCount, self.publisher.sentCount, self.publisher.failedCount)
        self.windowStart = time.perf_counter()
        self.windowFrames = 0
        self.windowProcessingMs = 0.0
