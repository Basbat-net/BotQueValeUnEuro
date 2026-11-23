"""The vision dashboard: the camera with what is detected, a 3D twin of the stones, the numbers and the colour.

Run from the src/ folder (needs requirements-dashboard.txt; on Ubuntu, once: sudo apt install libxcb-cursor0):
    python3 -m vision.apps.dashboard.dashboardApp [configPath]
The synthetic demo:  python3 -m vision.apps.syntheticVideoApp, then open ~/visionTests/synthetic/demoConfig.json
Options for an automatic check: --screenshot window.png --frames 60 saves the window and quits.
"""

import argparse
import logging

import pyqtgraph as pg

from vision.apps.dashboard.dashboardSession import DashboardSession
from vision.apps.dashboard.dashboardStyle import applyStyle
from vision.common.configLoader import chooseConfigPath, loadAppConfig


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Vision dashboard")
    parser.add_argument("configPath", nargs="?", default="", help="config file (default: config/visionConfig.json)")
    parser.add_argument("--screenshot", default="", help="save a picture of the window here and quit")
    parser.add_argument("--frames", type=int, default=60, help="images to process before the screenshot")
    arguments: argparse.Namespace = parser.parse_args()
    isLoaded, config = loadAppConfig(arguments.configPath)
    if not isLoaded:
        return
    if not config.showWindow:
        logging.error("the dashboard needs a screen: showWindow is false or there is no display")
        return
    application = pg.mkQApp("Vision dashboard")
    pg.setConfigOptions(antialias=True, imageAxisOrder="row-major")
    applyStyle(application)
    session: DashboardSession = DashboardSession(config, chooseConfigPath(arguments.configPath),
                                                 arguments.screenshot, arguments.frames)
    errorText: str = session.start()
    if errorText != "":
        logging.error(errorText)
        return
    application.aboutToQuit.connect(session.stop)
    application.exec()


if __name__ == "__main__":
    main()
