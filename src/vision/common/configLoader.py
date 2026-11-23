"""Reads and writes the JSON files of the vision module.

Every function returns a success flag instead of raising errors,
so the caller decides what to do when a file is missing or broken.
The reason of each failure is written with logging.
"""

import json
import logging
import os
import sys

import numpy as np

from vision.common.visionConfig import CameraCalibration, VisionConfig


def resolveVisionPath(path: str) -> str:
    """Turns a path relative to the vision/ folder into an absolute one.

    Absolute paths and empty paths (a setting that is not used) are returned unchanged.
    """
    if path == "" or os.path.isabs(path):
        return path
    visionFolder: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(visionFolder, path)


def readJsonFile(filePath: str) -> tuple[bool, dict]:
    """Returns (isRead, content). A missing, unreadable or invalid file gives (False, {})."""
    if not os.path.isfile(filePath):
        logging.warning("file not found: %s", filePath)
        return False, {}
    try:
        # Recovery only: a broken or wrongly encoded file is reported, not propagated.
        # utf-8-sig also reads the files that some Windows editors save with a BOM
        with open(filePath, encoding="utf-8-sig") as jsonFile:
            content: object = json.load(jsonFile)
    except (OSError, ValueError) as error:
        logging.warning("cannot read %s: %s", filePath, error)
        return False, {}
    if not isinstance(content, dict):
        logging.warning("%s: the file must hold a JSON object {...}", filePath)
        return False, {}
    return True, content


def convertJsonValue(value: object, defaultValue: object) -> tuple[bool, object]:
    """Checks a JSON value against the type of the default it replaces. Returns (isValid, value)."""
    # An Enum (frame source mode, transport...) is written in the JSON as its text value.
    # Every Enum class has __members__: checking it avoids one more import (team rule: at most 6)
    if hasattr(type(defaultValue), "__members__"):
        enumType: type = type(defaultValue)
        # The type checker cannot know enumType is an Enum class (checked just above), hence the ignore
        allowedTexts: list[object] = [member.value for member in enumType]  # pyright: ignore[reportGeneralTypeIssues]
        if value in allowedTexts:
            return True, enumType(value)
        return False, value
    # bool goes before int because in Python True is also an int
    if isinstance(defaultValue, bool) or isinstance(value, bool):
        return isinstance(defaultValue, bool) and isinstance(value, bool), value
    # JSON writes 25.0 as 25: an int is accepted where a float is expected
    if isinstance(defaultValue, float) and isinstance(value, int):
        return True, float(value)
    return isinstance(value, type(defaultValue)), value


def applyJsonValues(target: object, jsonValues: object, sectionName: str) -> bool:
    """Copies the values of one JSON section onto a config dataclass, checking each one.

    An unknown key or a value of the wrong type is reported and keeps its default.
    Returns False if any value was rejected.
    """
    if not isinstance(jsonValues, dict):
        logging.error("%s: expected a JSON object {...}", sectionName)
        return False
    currentValues: dict = vars(target)
    isValid: bool = True
    for key, value in jsonValues.items():
        if key not in currentValues:
            logging.error("%s: unknown key '%s'", sectionName, key)
            isValid = False
            continue
        isAccepted, convertedValue = convertJsonValue(value, currentValues[key])
        if isAccepted:
            setattr(target, key, convertedValue)
        else:
            logging.error("%s.%s: wrong value %r", sectionName, key, value)
            isValid = False
    return isValid


def loadVisionConfig(filePath: str) -> tuple[bool, VisionConfig]:
    """Builds the configuration from the JSON file. Missing keys keep their default value.

    Returns False if the file cannot be read or holds an unknown key or a wrong value.
    """
    config: VisionConfig = VisionConfig()
    isRead, content = readJsonFile(filePath)
    if not isRead:
        return False, config
    sections: dict = {
        "frameSource": config.frameSource,
        "calibrationBoard": config.calibrationBoard,
        "aruco": config.aruco,
        "viewer": config.viewer,
        "stone": config.stone,
        "cameraMount": config.cameraMount,
        "color": config.color,
        "fusion": config.fusion,
        "output": config.output,
        "sender": config.sender,
    }
    topLevelValues: dict = {key: value for key, value in content.items() if key not in sections}
    isValid: bool = applyJsonValues(config, topLevelValues, "config")
    for sectionName, section in sections.items():
        isValid = applyJsonValues(section, content.get(sectionName, {}), sectionName) and isValid
    # Resolved from vision/, so they do not depend on the folder the app is launched from
    config.calibrationFilePath = resolveVisionPath(config.calibrationFilePath)
    config.frameSource.videoPath = resolveVisionPath(config.frameSource.videoPath)
    config.frameSource.imagesFolder = resolveVisionPath(config.frameSource.imagesFolder)
    # The recordings go outside the repo, so a path starting with ~ (home folder) is accepted
    config.viewer.recordingsFolder = resolveVisionPath(os.path.expanduser(config.viewer.recordingsFolder))
    return isValid, config


def chooseConfigPath(argumentPath: str = "") -> str:
    """The config file given by the app, else the first command line argument, else the default one."""
    if argumentPath != "":
        return argumentPath
    # Options such as --screenshot are not a config path
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        return sys.argv[1]
    return resolveVisionPath("config/visionConfig.json")


def loadAppConfig(configPath: str = "") -> tuple[bool, VisionConfig]:
    """Common start of every app: logging, config file and screen check.

    configPath empty means: the first command line argument, or config/visionConfig.json.
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    chosenPath: str = chooseConfigPath(configPath)
    isLoaded, config = loadVisionConfig(chosenPath)
    if not isLoaded:
        logging.error("could not use the config file: %s", chosenPath)
        return False, config
    # On Linux without a screen (the robot over SSH) cv2.imshow kills the program
    hasScreen: bool = os.environ.get("DISPLAY", "") != "" or os.environ.get("WAYLAND_DISPLAY", "") != ""
    if config.showWindow and sys.platform.startswith("linux") and not hasScreen:
        logging.warning("no screen found: showWindow turned off")
        config.showWindow = False
    return True, config


def loadCameraCalibration(filePath: str) -> tuple[bool, CameraCalibration]:
    """Reads the camera matrix and distortion saved by the calibration app.

    On failure the calibration is empty (widthPx 0): never use it when the flag is False.
    """
    emptyCalibration: CameraCalibration = CameraCalibration(np.eye(3), np.zeros(5), 0, 0, 0.0)
    requiredKeys: tuple[str, ...] = (
        "cameraMatrix",
        "distCoeffs",
        "widthPx",
        "heightPx",
        "reprojectionErrorPx",
    )
    isRead, content = readJsonFile(filePath)
    if not isRead or not all(key in content for key in requiredKeys):
        logging.warning("no complete calibration in %s", filePath)
        return False, emptyCalibration
    try:
        # Recovery only: a file edited by hand may hold text or null instead of numbers
        calibration: CameraCalibration = CameraCalibration(
            cameraMatrix=np.array(content["cameraMatrix"], dtype=np.float64),
            distCoeffs=np.array(content["distCoeffs"], dtype=np.float64).flatten(),
            widthPx=int(content["widthPx"]),
            heightPx=int(content["heightPx"]),
            reprojectionErrorPx=float(content["reprojectionErrorPx"]),
        )
    except (TypeError, ValueError):
        logging.warning("%s: the calibration values are not numbers", filePath)
        return False, emptyCalibration
    if calibration.cameraMatrix.shape != (3, 3) or calibration.distCoeffs.shape != (5,):
        logging.warning("%s: expected a 3x3 matrix and 5 distortion values", filePath)
        return False, emptyCalibration
    return True, calibration


def saveCameraCalibration(filePath: str, calibration: CameraCalibration) -> bool:
    """Writes the calibration as JSON. Returns False if the file cannot be written."""
    content: dict = {
        "cameraMatrix": calibration.cameraMatrix.tolist(),
        "distCoeffs": calibration.distCoeffs.tolist(),
        "widthPx": calibration.widthPx,
        "heightPx": calibration.heightPx,
        "reprojectionErrorPx": calibration.reprojectionErrorPx,
    }
    try:
        # Recovery only: a missing or read-only folder must not end the program
        with open(filePath, "w", encoding="utf-8") as jsonFile:
            json.dump(content, jsonFile, indent=2)
    except OSError as error:
        logging.error("could not write %s: %s", filePath, error)
        return False
    return True


def saveVisionConfig(filePath: str, config: VisionConfig) -> bool:
    """Writes a whole config as JSON: each section (a dataclass) as its fields, each mode (Enum) as its text."""
    temporaryPath: str = filePath + ".tmp"
    try:
        # Recovery only: a full disk or a read-only folder must not end the program.
        # Written aside and then renamed: a failure halfway never leaves a broken config
        with open(temporaryPath, "w", encoding="utf-8") as jsonFile:
            json.dump(config, jsonFile, indent=2,
                      default=lambda value: value.value if hasattr(type(value), "__members__") else vars(value))
            jsonFile.write("\n")
        os.replace(temporaryPath, filePath)
    except OSError as error:
        logging.error("could not write %s: %s", filePath, error)
        return False
    return True


def saveConfigSection(filePath: str, sectionName: str, values: dict) -> bool:
    """Replaces some keys of one section of a config file and keeps everything else as it was.

    Used by the dashboard to save the colour range measured on the table. False if it cannot.
    """
    isRead, content = readJsonFile(filePath)
    if not isRead:
        return False
    section: object = content.get(sectionName, {})
    if not isinstance(section, dict):
        logging.error("%s: section '%s' is not a JSON object", filePath, sectionName)
        return False
    section.update(values)
    content[sectionName] = section
    temporaryPath: str = filePath + ".tmp"
    try:
        # Recovery only: a read-only file must not end the program. Written aside, then renamed
        with open(temporaryPath, "w", encoding="utf-8") as jsonFile:
            json.dump(content, jsonFile, indent=2)
            jsonFile.write("\n")
        os.replace(temporaryPath, filePath)
    except OSError as error:
        logging.error("could not write %s: %s", filePath, error)
        return False
    return True
