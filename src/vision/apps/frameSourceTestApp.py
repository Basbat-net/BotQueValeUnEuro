"""Phase 1 test: opens the configured source and reports what it delivers.

Run from the src/ folder:
    python3 -m vision.apps.frameSourceTestApp [configPath]
It stops after testMaxFrames frames, at the end of a video or folder,
or when 'q' is pressed in the window (only when showWindow is true).
"""

import logging
import time

import cv2

from vision.common.configLoader import loadAppConfig
from vision.common.visionConfig import VisionConfig
from vision.input.frameSource import FrameSource


def runFrameSourceTest(config: VisionConfig) -> None:
    """Reads up to testMaxFrames frames and prints the image size, the count and the rate."""
    frameSource: FrameSource = FrameSource(config.frameSource)
    validFrames: int = 0
    lastTimestampMs: int = 0
    if not frameSource.open():
        logging.error("could not open the frame source: %s", frameSource.lastError)
        return
    # Started after open(): opening a camera can take a second that is not part of the rate
    startTime: float = time.perf_counter()
    while validFrames < config.testMaxFrames:
        isValid, frame = frameSource.read()
        if not isValid:
            if not frameSource.hasEnded():
                logging.error("reading stopped: %s", frameSource.lastError)
            break
        validFrames += 1
        lastTimestampMs = frame.timestampMs
        if validFrames == 1:
            print("First frame:", frame.image.shape[1], "x", frame.image.shape[0], "px")
        if config.showWindow:
            cv2.imshow("frameSourceTest", frame.image)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    elapsedSeconds: float = max(time.perf_counter() - startTime, 1e-6)
    frameSource.close()
    cv2.destroyAllWindows()
    print("Valid frames:", validFrames, "| last timestamp (ms):", lastTimestampMs)
    print("Frames per second:", round(validFrames / elapsedSeconds, 1))


def main() -> None:
    isLoaded, config = loadAppConfig()
    if isLoaded:
        runFrameSourceTest(config)


if __name__ == "__main__":
    main()
