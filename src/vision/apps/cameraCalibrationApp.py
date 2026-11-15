"""Phase 1 tool: calibrates the camera with a printed chessboard.

Run from the src/ folder:
    python3 -m vision.apps.cameraCalibrationApp [configPath]
Camera or video: move the board in front of the camera (different angles and distances);
a view is saved when the board is found and captureIntervalMs has passed since the last one.
Folder of pictures: every picture where the board is found is a view.
It stops at requiredViews, at the end of a video or folder, or when 'q' is pressed in the window.
Before saving, it shows the result and asks for confirmation.
"""

import logging

import cv2
import numpy as np

from vision.common.configLoader import loadAppConfig, saveCameraCalibration
from vision.common.visionConfig import (
    CalibrationBoardConfig,
    CameraCalibration,
    FrameSourceMode,
    VisionConfig,
)
from vision.input.frameSource import FrameSource


def buildBoardPoints(board: CalibrationBoardConfig) -> np.ndarray:
    """Real position (mm) of every inner corner, with the board lying on z = 0."""
    boardPoints: np.ndarray = np.zeros((board.innerCornersX * board.innerCornersY, 3), dtype=np.float32)
    # .T makes x change first, the same order in which findChessboardCorners gives the corners
    grid: np.ndarray = np.mgrid[0 : board.innerCornersX, 0 : board.innerCornersY].T.reshape(-1, 2)
    boardPoints[:, :2] = grid * board.squareSizeMm
    return boardPoints


def collectBoardViews(config: VisionConfig) -> tuple[bool, list[np.ndarray], tuple[int, int]]:
    """Returns (isUsable, views, imageSize): the corners (px) found in each saved view.

    isUsable is False when the source could not be opened or failed in the middle
    (camera unplugged, unreadable picture): then the views must not be used.
    """
    board: CalibrationBoardConfig = config.calibrationBoard
    patternSize: tuple[int, int] = (board.innerCornersX, board.innerCornersY)
    subPixWindow: tuple[int, int] = (board.subPixHalfWindowPx, board.subPixHalfWindowPx)
    refineCriteria: tuple[int, int, float] = (
        cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
        board.subPixMaxIterations,
        board.subPixEpsilonPx,
    )
    isEveryFrameAView: bool = config.frameSource.mode == FrameSourceMode.IMAGES
    frameSource: FrameSource = FrameSource(config.frameSource)
    savedViews: list[np.ndarray] = []
    imageSize: tuple[int, int] = (0, 0)
    # Starts one interval in the past, so the first board found is saved at once
    lastCaptureMs: int = -board.captureIntervalMs
    isUsable: bool = True
    if not frameSource.open():
        logging.error("could not open the frame source: %s", frameSource.lastError)
        return False, savedViews, imageSize
    while len(savedViews) < board.requiredViews:
        isValid, frame = frameSource.read()
        if not isValid:
            isUsable = frameSource.hasEnded()
            if not isUsable:
                logging.error("reading stopped: %s", frameSource.lastError)
            break
        grayImage: np.ndarray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        frameSize: tuple[int, int] = (grayImage.shape[1], grayImage.shape[0])
        isFound, corners = cv2.findChessboardCorners(grayImage, patternSize)
        isDue: bool = isEveryFrameAView or frame.timestampMs - lastCaptureMs >= board.captureIntervalMs
        if isFound and isDue and len(savedViews) > 0 and frameSize != imageSize:
            # The calibration is only valid at one resolution, so every view must share it
            logging.warning("view skipped: %s px, the first views were %s px", frameSize, imageSize)
        elif isFound and isDue:
            # Sub-pixel refinement: the calibration quality depends on it
            corners = cv2.cornerSubPix(grayImage, corners, subPixWindow, (-1, -1), refineCriteria)
            savedViews.append(corners)
            imageSize = frameSize
            lastCaptureMs = frame.timestampMs
            print("Saved view", len(savedViews), "of", board.requiredViews)
        if config.showWindow:
            cv2.drawChessboardCorners(frame.image, patternSize, corners, isFound)
            cv2.imshow("cameraCalibration", frame.image)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    frameSource.close()
    cv2.destroyAllWindows()
    return isUsable, savedViews, imageSize


def computeCalibration(
    board: CalibrationBoardConfig, savedViews: list[np.ndarray], imageSize: tuple[int, int]
) -> CameraCalibration:
    """Solves the camera matrix and the lens distortion from the saved views."""
    boardPoints: np.ndarray = buildBoardPoints(board)
    objectPoints: list[np.ndarray] = [boardPoints for _ in savedViews]
    reprojectionError, cameraMatrix, distCoeffs, _, _ = cv2.calibrateCamera(
        objectPoints, savedViews, imageSize, None, None
    )
    # OpenCV gives the distortion as a 1x5 array: it is stored flat, as the loader reads it
    return CameraCalibration(
        cameraMatrix, distCoeffs.flatten(), imageSize[0], imageSize[1], float(reprojectionError)
    )


def confirmSave(calibration: CameraCalibration) -> bool:
    """Shows the result and asks before overwriting the saved calibration.

    A low error is not enough: views that are too alike give a tiny error and absurd values.
    """
    cameraMatrix: np.ndarray = calibration.cameraMatrix
    print("Reprojection error (px):", round(calibration.reprojectionErrorPx, 3))
    print("Focal length fx, fy (px):", round(cameraMatrix[0, 0], 1), round(cameraMatrix[1, 1], 1))
    print(
        "Optical center cx, cy (px):",
        round(cameraMatrix[0, 2], 1),
        round(cameraMatrix[1, 2], 1),
        "| image center:",
        calibration.widthPx / 2,
        calibration.heightPx / 2,
    )
    print("Check: fx and fy similar, optical center near the image center")
    answer: str = input("Save this calibration? [y/N] ")
    return answer.strip().lower() == "y"


def main() -> None:
    isLoaded, config = loadAppConfig()
    if not isLoaded:
        return
    minimumViews: int = config.calibrationBoard.minimumViews
    isUsable, savedViews, imageSize = collectBoardViews(config)
    if not isUsable:
        logging.error("nothing saved: the source failed before the end")
        return
    if len(savedViews) < minimumViews:
        logging.error("only %d views with the board, at least %d needed", len(savedViews), minimumViews)
        return
    calibration: CameraCalibration = computeCalibration(config.calibrationBoard, savedViews, imageSize)
    if not confirmSave(calibration):
        print("Not saved")
        return
    if saveCameraCalibration(config.calibrationFilePath, calibration):
        print("Calibration saved in", config.calibrationFilePath)


if __name__ == "__main__":
    main()
