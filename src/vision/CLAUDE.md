# CLAUDE.md — src/vision

Rules that only apply to the vision subproject. The team rules in the root `CLAUDE.md` still apply.

## What it does

Detects the stones (cardboard boxes with an ArUco marker, ID 13, dictionary 4x4) from a camera on the robot.
Main detector: ArUco, with its pose in mm. Support detector: colour + shape, for when the marker is not visible.
Both are fused into stones in the robot frame and sent to the robot as a binary message.
How it works, with diagrams: `docs/vision/howVisionWorks.md` and the files next to it.

## Language exception

This subproject is written in **Python 3 + OpenCV**, not Arduino/C++.
The rules of `projectRules.md` that do not depend on the language still apply:

- Code and comments in English, `camelCase` names that explain themselves.
- Type hints on every function and `dataclass` for data (the equivalent of static typing).
- At most 15 functions and 6 imports per file, 150 lines per function.
- No global variables: parameters live in `config/visionConfig.json`; constants of a protocol are class attributes.
- More than 5 parameters: use a `dataclass`.
- No inheritance, also with Qt: build widgets and connect Qt's own signals (no subclass, no custom signal).
- Functions return a success flag; exceptions are only for recovery, never part of the normal flow.

Exception agreed with the owner of the subproject (2026-11-23): files and commits here may go over 250 lines.

## The black box contract

`common/visionTypes.py` is the contract with the rest of the robot:

- **Input:** `FrameInput` (one image and its capture time in ms).
- **Output:** `VisionResult` (status, processing time and a list of `StoneDetection`: `xMm`, `yMm`, `yawDeg` in the robot frame — x forward, y left —, `confidence` and `source`).

Rules of the contract:

- One frame in, one result out, always. No stones means an empty list.
- It never blocks; a failure is reported in `status`. `NOT_CALIBRATED` also means the camera mount is not measured.
- The box does not open the camera and does not send anything to the robot: `input/` and `output/` do that.
- **Do not change `visionTypes.py` without the team agreeing.** Other subprojects depend on it.
- The message to the robot (`output/messageFormat.py`, `docs/vision/visionMessage.md`) is frozen by a test: change its version, never its bytes.

## Structure

| Folder | Content | State |
|---|---|---|
| `common/` | Contract, internal types (`detectionTypes.py`), config split in `visionConfig.py`, `detectionConfig.py`, `outputConfig.py`, JSON loading | done |
| `input/` | Image source (camera, video, folder, stream) and `latestFrameReader.py` (thread, newest frame only) | done |
| `aruco/` | ArUco detector, pose in mm with `solvePnPGeneric` + IPPE_SQUARE (both solutions kept) | done |
| `color/` | Colour + shape detector; `blobFloorGeometry.py` places a blob from its floor-contact edge | done |
| `geometry/` | Camera to robot (`poseTransforms.py`), stones back on the picture (`boxProjection.py`) | done |
| `fusion/` | Merges both detectors into stones | done |
| `visionBlackBox.py`, `blackBoxFactory.py` | The black box, and the only place that builds it from the config | done |
| `output/` | Message format (standard library only), codec, publisher (UDP or serial) | done |
| `simulation/` | Synthetic scenes (own camera maths, renderer) for the tests and the demo video | done |
| `apps/` | `visionApp` (final program), `dashboard/` (Qt + 3D twin), `viewer/` (OpenCV), `link/`, `stream/`, calibration, synthetic demo | done |
| `config/` | Parameters and camera calibration | done; the mount, the marker size and the brown range must be measured on the real robot |

Rules of the structure:

- The detectors do not know each other. Only `fusion/` knows there are two.
- Drawing on screen belongs to `apps/`, never to a detector: the robot has no screen.
- Only `visionTypes.py` is the contract. `detectionTypes.py` holds what the detectors return inside the module, debug data included.
- `output/messageFormat.py` and `apps/link/` must keep working with the standard library and pyserial only: they run on the robot Raspberry.
- The tests must not use the geometry they check: synthetic scenes are built with `simulation/sceneCamera.py`, not with `geometry/`.
- In `apps/viewer/`, only `viewerPipeline.py` knows the black box and only `viewerDrawing.py` knows the drawings; the dashboard reuses both.
- Imports always start with the package name: `from vision.common.visionTypes import ...`.

## Run and test

From the `src/` folder, with the virtual environment active (`pip install -r vision/requirements.txt`, and
`vision/requirements-dashboard.txt` for the dashboard):

```bash
python3 -m pytest ../tests/vision                             # synthetic scenes, no camera, about 3 s
python3 -m vision.apps.syntheticVideoApp                      # demo video in ~/visionTests/synthetic
python3 -m vision.apps.dashboard.dashboardApp [config]        # dashboard (Ubuntu: sudo apt install libxcb-cursor0)
python3 -m vision.apps.visionApp [config]                     # the final program, no screen
```

The full list of programs and a step-by-step "try it on your computer" are in `README.md`.
An app takes another config file as its first argument. Recorded and synthetic videos are heavy: they are not committed.
Check the code with `ruff check --line-length 120 --ignore EXE,LOG015` and `pyright` before handing it over.

Gotchas:

- An `Enum` of the config is recognised with `hasattr(type(value), "__members__")`, not `isinstance(value, Enum)`: it saves an import in files already at 6.
- On a disk without symlinks (the NTFS drive of the team PC) create the environment with `python3 -m venv --copies` or outside the repo.
- The dashboard 3D view cannot be grabbed with `QT_QPA_PLATFORM=offscreen` (no OpenGL there): check it on a real screen (`--screenshot`).
