"""The final vision program (phase 5): images in, results out to the robot. No screen, no keys.

Run from the src/ folder:
    python3 -m vision.apps.visionApp [configPath]
Where the images come from (frameSource) and where the results go (output) are in the config.
Ctrl+C (or the system stopping it) ends it cleanly, closing the camera and the port.
"""

import logging
import signal

from vision.apps.visionRunner import VisionRunner
from vision.common.configLoader import loadAppConfig


def main() -> None:
    isLoaded, config = loadAppConfig()
    if not isLoaded:
        return
    runner: VisionRunner = VisionRunner(config)
    # The handler only raises a flag: the loop ends after the current image, with everything closed
    signal.signal(signal.SIGINT, lambda signalNumber, frame: runner.requestStop())
    signal.signal(signal.SIGTERM, lambda signalNumber, frame: runner.requestStop())
    logging.info("vision running: frames from %s, results by %s (Ctrl+C to stop)",
                 config.frameSource.mode.value, config.output.transport.value)
    errorText: str = runner.run()
    if errorText != "":
        logging.error(errorText)


if __name__ == "__main__":
    main()
