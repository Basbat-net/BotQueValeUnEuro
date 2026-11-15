# Vision

Stone detection for the robot (ArUco 13 as main detector, color + shape as support).
The module works as a black box: one image in, one list of stones out.
The data contract is in `common/visionTypes.py`.

## Install

Needs Python 3.10 or newer (tested with 3.14). On Windows, write `py` instead of `python3`.

```bash
cd src
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r vision/requirements.txt
```

## Run

Always from the `src/` folder. Every app reads `vision/config/visionConfig.json`
unless another config path is given as argument.
Relative paths inside the config file are resolved from the `vision/` folder.

| App | What it does |
|---|---|
| `python3 -m vision.apps.frameSourceTestApp` | Opens the image source (camera, video or folder) and prints size and frames per second |
| `python3 -m vision.apps.cameraCalibrationApp` | Calibrates the camera with a printed chessboard and, after asking, saves `vision/config/cameraCalibration.json` |

A config file with an unknown key or a value of the wrong type is rejected, and the error says which one.
Without a screen (for example over SSH) the windows are turned off automatically.

## Folders

| Folder | Content |
|---|---|
| `common/` | Data contract, configuration and JSON loading |
| `input/` | Image source (camera, video or folder of pictures) |
| `apps/` | Programs to test each part |
| `config/` | Parameters and camera calibration |
