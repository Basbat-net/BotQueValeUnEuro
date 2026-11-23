"""Video sender: serves the configured image source as MJPEG over HTTP (sender section of the config).

Run from the src/ folder:
    python3 -m vision.apps.stream.videoSenderApp [configPath]
Then open http://<this computer>:<sender.port>/video in a browser, in VLC, or in the vision
(frameSource.mode "stream", streamUrl that address). Ctrl+C stops it.
"""

import logging
import signal

from vision.apps.stream.videoSender import VideoSender
from vision.common.configLoader import loadAppConfig


def main() -> None:
    isLoaded, config = loadAppConfig()
    if not isLoaded:
        return
    sender: VideoSender = VideoSender(config)
    signal.signal(signal.SIGINT, lambda signalNumber, frame: sender.requestStop())
    signal.signal(signal.SIGTERM, lambda signalNumber, frame: sender.requestStop())
    logging.info("sending %s as MJPEG on http://0.0.0.0:%d/video (Ctrl+C to stop)", config.frameSource.mode.value,
                 config.sender.port)
    errorText: str = sender.run()
    if errorText != "":
        logging.error(errorText)
    logging.info("%d frames sent", sender.sentCount)


if __name__ == "__main__":
    main()
