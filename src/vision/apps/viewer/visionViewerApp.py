"""Viewer of the vision module: shows live what the detectors find, to understand and tune them.

Run from the src/ folder:
    python3 -m vision.apps.viewer.visionViewerApp [configPath]
Press h in the window to see the keys; q or Esc quits.
It replaces a test app per detector: 1 shows ArUco, 2 color (phase 3), 3 both.
"""

import logging

from vision.apps.viewer.viewerSession import ViewerSession
from vision.common.configLoader import loadAppConfig


def main() -> None:
    isLoaded, config = loadAppConfig()
    if not isLoaded:
        return
    viewerSession: ViewerSession = ViewerSession(config)
    errorText: str = viewerSession.run()
    if errorText != "":
        logging.error(errorText)


if __name__ == "__main__":
    main()
