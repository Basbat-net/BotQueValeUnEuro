# CLAUDE.md — src/vision

Rules that only apply to the vision subproject. The team rules in the root `CLAUDE.md` still apply.

## What it does

Detects the stones (cardboard boxes with an ArUco marker, ID 13, dictionary 4x4) from a camera on the robot.
Main detector: ArUco. Support detector: color + shape, for when the marker is not visible.

## Language exception

This subproject is written in **Python 3 + OpenCV**, not Arduino/C++.
The rules of `projectRules.md` that do not depend on the language still apply:

- Code and comments in English, `camelCase` names that explain themselves.
- Type hints on every function and `dataclass` for data (the equivalent of static typing).
- At most 15 functions per file and 150 lines per function.
- No global variables: parameters live in `config/visionConfig.json`.
- More than 5 parameters: use a `dataclass`.
- No inheritance.
- Functions return a success flag; exceptions are only for recovery, never part of the normal flow.

## The black box contract

`common/visionTypes.py` is the contract with the rest of the robot:

- **Input:** `FrameInput` (one image and its capture time in ms).
- **Output:** `VisionResult` (status, processing time and a list of `StoneDetection`: `xMm`, `yMm`, `yawDeg` in the robot frame — x forward, y left —, `confidence` and `source`).

Rules of the contract:

- One frame in, one result out, always. No stones means an empty list.
- It never blocks; a failure is reported in `status`.
- The box does not open the camera and does not send anything to the robot: `input/` and `output/` do that.
- **Do not change `visionTypes.py` without the team agreeing.** Other subprojects depend on it.

## Structure

| Folder | Content | State |
|---|---|---|
| `common/` | Contract, internal types of the detectors (`detectionTypes.py`), configuration and JSON loading | done |
| `input/` | Image source: camera, video or folder of pictures | done |
| `apps/` | Phase 1 test apps and `apps/viewer/`, the viewer of every detector | in progress |
| `config/` | Parameters and camera calibration | done |
| `aruco/` | ArUco detector | phase 2a done (pixels); pose in mm needs the calibration (2b) |
| `color/` | Color + shape detector | not started |
| `geometry/` | Camera to robot transforms | not started |
| `fusion/` | Merges both detectors into stones | not started |
| `output/` | Sends the result to the robot | not started |

Rules of the structure:

- The detectors do not know each other. Only `fusion/` knows there are two.
- Drawing on screen belongs to `apps/`, never to a detector: the robot has no screen.
- Only `visionTypes.py` is the contract. `detectionTypes.py` holds what the detectors return inside the module, debug data included.
- In `apps/viewer/`, only `viewerPipeline.py` knows the detectors and only `viewerDrawing.py` knows the drawings. Add a new detector there.
- Imports always start with the package name: `from vision.common.visionTypes import ...`.

## Run and test

From the `src/` folder, with the virtual environment active (`pip install -r vision/requirements.txt`):

```bash
python3 -m vision.apps.frameSourceTestApp        # opens the configured image source
python3 -m vision.apps.cameraCalibrationApp      # calibrates the camera with a chessboard
python3 -m vision.apps.viewer.visionViewerApp    # shows what the detectors find (keys: h)
python3 -m pytest ../tests/vision                # tests with drawn pictures, no camera
```

An app takes another config file as its first argument. To test without a camera, set `frameSource.mode` to `video` or `images`.
Recorded test videos are heavy: they are not committed.
