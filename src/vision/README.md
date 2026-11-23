# Vision

Stone detection for the robot: ArUco 13 as main detector, colour + shape as support, fused into one list of stones
in the robot frame and sent to the robot as a small binary message.
The module works as a black box: one image in, one list of stones out. The data contract is in `common/visionTypes.py`.
How it works, with diagrams: `docs/vision/howVisionWorks.md` and the files next to it.

## Install

Needs Python 3.12 or newer (numpy 2.5 asks for it; JetPack 6 on a Jetson ships Python 3.10, so there numpy and
OpenCV must be pinned to older versions). On Windows, write `py` instead of `python3`.

```bash
cd src
python3 -m venv .venv                              # on a disk without symlinks (NTFS): python3 -m venv --copies .venv
source .venv/bin/activate                          # Windows: .venv\Scripts\activate
pip install -r vision/requirements.txt             # the robot code and the tests
pip install -r vision/requirements-dashboard.txt   # only for the dashboard (Qt + 3D)
```

On Ubuntu with X11 the dashboard also needs, once: `sudo apt install libxcb-cursor0` (without it Qt does not open windows).

## Try it on your computer

Everything below works without a robot, a stone or a printed code. Run it from `src/` with the environment active.

1. **The tests** (about 3 s, no camera, no screen): `python3 -m pytest ../tests/vision`. You should see `81 passed`.
2. **The synthetic demo** (about 1 minute to make): `python3 -m vision.apps.syntheticVideoApp`.
   It writes a video, its calibration, a config and the truth of every frame in `~/visionTests/synthetic/`.
3. **The dashboard with the demo:** `python3 -m vision.apps.dashboard.dashboardApp ~/visionTests/synthetic/demoConfig.json`.
   You should see a stone moving and turning, followed by a box in the 3D twin (green or cyan); from 6 to 9 s its code
   is covered and the box turns orange (found by colour only); a quarry of 2 at the back; the brown stripe on the floor
   never becomes a stone. The cards say `OK`, `calibration OK`, `mount measured`, about 30 images/s.
4. **The dashboard with your webcam:** `python3 -m vision.apps.dashboard.dashboardApp` (default config, camera 0).
   Without a calibration you see the codes and the brown blobs in 2D, the cards say `NOT_CALIBRATED` and there is no 3D box.
   Show it an ArUco 13 (`DICT_4X4_50`) on a phone, and any cardboard box. To get the 3D: calibrate (step 6) and measure the
   camera mount (`cameraMount` in the config, then `isMeasured: true`).
5. **The OpenCV viewer** (no Qt): `python3 -m vision.apps.viewer.visionViewerApp ~/visionTests/synthetic/demoConfig.json`
   (keys: `h`).
6. **Calibrate the camera:** `python3 -m vision.apps.cameraCalibrationApp` with a 10 x 7 squares chessboard (9 x 6 inner
   corners). Printed is best; a board shown full screen on a laptop or phone also works if you measure one square with a
   ruler and write it in `calibrationBoard.squareSizeMm`.
7. **The whole chain to the robot**, in four terminals (the second one is the robot side):
   ```bash
   python3 -m vision.apps.link.resultReceiverApp --udp-port 5005           # stands in for the ESP32
   python3 -m vision.apps.stream.videoSenderApp ~/visionTests/synthetic/demoConfig.json   # stands in for the robot camera
   python3 -m vision.apps.visionApp <a config with frameSource.mode "stream", streamUrl "http://127.0.0.1:8080/video",
                                     output.transport "udp", output.udpPort 5005>
   ```
   The receiver prints one line per second: messages per second, lost ones, damaged bytes, the nearest stone.
   To add the robot Raspberry in the middle: `python3 -m vision.apps.link.robotRelayApp --udp-port 5005 --serial <port>`.

On another computer (for example the laptop), the code arrives with Git (or Drive) but the environment and
`~/visionTests` do not: create the environment (Install) and make the demo again (step 2).

## Programs

All from `src/`. Every app reads `vision/config/visionConfig.json` unless another config path is given as argument.
Relative paths inside the config file are resolved from the `vision/` folder.

| App | What it does |
|---|---|
| `python3 -m vision.apps.visionApp` | **The final program**: images in, results out to the robot. No screen. Ctrl+C stops it |
| `python3 -m vision.apps.dashboard.dashboardApp` | Dashboard: picture, 3D twin, stone table, colour tuning (`docs/vision/howDashboardWorks.md`) |
| `python3 -m vision.apps.viewer.visionViewerApp` | OpenCV viewer: the same drawings, no Qt (keys: `h`) |
| `python3 -m vision.apps.cameraCalibrationApp` | Calibrates the camera with a chessboard and, after asking, saves `config/cameraCalibration.json` |
| `python3 -m vision.apps.frameSourceTestApp` | Opens the image source and prints size and frames per second |
| `python3 -m vision.apps.syntheticVideoApp` | Makes the synthetic demo (`--folder` to choose where) |
| `python3 -m vision.apps.stream.videoSenderApp` | Serves the image source as MJPEG at `http://<host>:<sender.port>/video` |
| `python3 -m vision.apps.link.robotRelayApp` | On the robot Raspberry: UDP from the vision to the UART of the ESP32. Needs only pyserial |
| `python3 -m vision.apps.link.resultReceiverApp` | Stands in for the ESP32: decodes and checks the messages |

A config file with an unknown key or a value of the wrong type is rejected, and the error says which one.

## Configuration

`config/visionConfig.json`, one section per part:

| Section | What it sets |
|---|---|
| `frameSource` | `camera` (with `fourcc` "MJPG": 20 instead of 10 images/s at 1280 x 720 on the team PC), `video`, `images` or `stream` (a URL, with `streamTimeoutMs` and `reconnectDelayMs`) |
| `calibrationBoard`, `calibrationFilePath` | The chessboard of the calibration and where the calibration is saved |
| `aruco` | Dictionary, ID 13, size of the printed code (**measure it**), axis of the code along the long side |
| `stone` | 320 x 110 mm, size of the white label |
| `cameraMount` | Where the camera is on the robot. **To measure**: until then `isMeasured` is false and the robot gets `NOT_CALIBRATED` |
| `color` | The brown range and the shape filters (the dashboard tunes and saves the range) |
| `fusion` | Distances to join detections, and the confidence rules |
| `output` | `none`, `udp` (Wi-Fi) or `serial` (UART, USB, Bluetooth serial port, ESP-NOW bridge) |
| `sender` | Port, JPEG quality and rate of the video sender |
| `viewer` | Recordings folder, demo playback rate and the smoothing of the 3D twin |

## Tests

From `src/`: `python3 -m pytest ../tests/vision`. They use scenes drawn by the computer (`simulation/`), so they need no
camera and no screen. They check the geometry against numbers worked out by hand, the pose and the colour detector
against the known truth of each scene, the fusion, the black box statuses, the message bytes (frozen) and the links
(UDP on 127.0.0.1, serial on pyserial's `loop://`).

## Folders

| Folder | Content |
|---|---|
| `common/` | Contract, internal types, configuration (3 files) and JSON loading |
| `input/` | Image source (camera, video, folder, stream) and the reader thread that keeps the newest image |
| `aruco/` | ArUco detector and its pose in mm |
| `color/` | Colour + shape detector, and the measure of a blob on the floor |
| `geometry/` | Camera to robot, and stones back on the picture |
| `fusion/` | Merges both detectors into stones |
| `visionBlackBox.py`, `blackBoxFactory.py` | The black box and the place where it is built |
| `output/` | The message to the robot and the transports |
| `simulation/` | Synthetic scenes for the tests and the demo |
| `apps/` | Programs: `visionApp`, `dashboard/`, `viewer/`, `link/`, `stream/`, calibration, synthetic demo |
| `config/` | Parameters and camera calibration |
