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
| `python3 -m vision.apps.viewer.visionViewerApp` | Shows live what the detectors find: markers, rejected candidates, numbers. Needs a screen |

A config file with an unknown key or a value of the wrong type is rejected, and the error says which one.
Without a screen (for example over SSH) the windows are turned off automatically.

## The viewer

It replaces a test app per detector. Press `h` in the window to see the keys:

| Key | What it does |
|---|---|
| `1` `2` `3` | ArUco, color (phase 3) or both |
| `space` / `n` | Pause or play / next frame while paused |
| `x` | Show the rejected candidates (squares the ArUco detector could not read) |
| `t` | Threshold view: about the black and white image where ArUco looks for squares |
| `r` / `s` | Start or stop a video / save a snapshot (raw and with drawings) |
| `c` | Reset the session numbers |
| `q` or `Esc` | Quit |

Videos and snapshots are saved without drawings in `viewer.recordingsFolder`, so they can be played back
with `frameSource.mode` set to `video`. Leave that folder outside the repo (for example `~/visionTests/videos`):
videos are heavy and are not committed. Empty means recording is off.
A recorded video plays as fast as the computer can: pause it and use `n` to look frame by frame.

## Tests

From the `src/` folder, with the virtual environment active:

```bash
python3 -m pytest ../tests/vision
```

They use pictures drawn by the computer, so they need no camera and no screen.

## Folders

| Folder | Content |
|---|---|
| `common/` | Data contract, internal types of the detectors, configuration and JSON loading |
| `input/` | Image source (camera, video or folder of pictures) |
| `aruco/` | ArUco detector (phase 2a: in pixels, no distance yet) |
| `apps/` | Programs to test each part; `apps/viewer/` is the viewer |
| `config/` | Parameters and camera calibration |
