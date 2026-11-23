# How the vision subproject works

Diagrams of `src/vision/`, from the big picture to the details.
They are written in [Mermaid](https://mermaid.js.org/): GitHub draws them, and so does VS Code with a Markdown preview that supports Mermaid.

> Checked against the code on 2026-11-23 (phases 1 to 5 done, phase 6 without hardware, branch `vision`).
> When `src/vision/` changes, these files change in the same branch.

**The other files of this folder:**

| File | What it explains |
|---|---|
| `howDetectionWorks.md` | The two detectors: ArUco with its pose in mm, and colour + shape |
| `howFusionWorks.md` | How both detectors become one list of stones, and the black box |
| `howOutputWorks.md` | The message to the robot, the transports, the video stream and the relay of the Raspberry |
| `visionMessage.md` | The byte table of the message, for whoever writes the ESP32 side |
| `howDashboardWorks.md` | The dashboard (Qt, with the 3D twin) and the OpenCV viewer |

**Legend:** green = exists today · white = outside the vision code (hardware, other subprojects).

## 1. The big picture

One image goes in, one result goes out. The black box never opens the camera and never talks to the robot: `input/` and `output/` do that.
Since 2026-11-18 the images are processed on a Jetson on the central platform: the camera of the robot sends them over Wi-Fi, and the result goes back the same way.

```mermaid
flowchart LR
    camera["Robot camera<br/>+ video sender"] -- "MJPEG over Wi-Fi" --> reader
    files["Video or folder<br/>of pictures (tests)"] --> reader
    reader["input/<br/>FrameSource + LatestFrameReader<br/>always the newest image"]
    reader -- "FrameInput<br/>image + capture time" --> blackBox
    subgraph blackBox ["Vision black box: visionBlackBox.py"]
        aruco["aruco/<br/>ArUco 13 + pose in mm"]
        color["color/<br/>colour + shape"]
        fusion["fusion/<br/>one stone per stone"]
        geometry["geometry/<br/>camera to robot"]
        aruco --> fusion
        color --> fusion
        fusion -. "uses" .-> geometry
        color -. "uses" .-> geometry
    end
    blackBox -- "VisionResult<br/>status + stones" --> publisher["output/<br/>binary message + CRC<br/>UDP or serial"]
    publisher -- "Wi-Fi" --> relay["Robot Raspberry<br/>apps/link/robotRelayApp"]
    relay -- "UART" --> esp32["ESP32<br/>(motors, strategy)"]
    blackBox -. "VisionDetails" .-> apps["apps/dashboard and apps/viewer<br/>show what it found, with a 3D twin"]

    classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b1b1b
    classDef outside fill:#ffffff,stroke:#616161,color:#1b1b1b
    class reader,aruco,color,fusion,geometry,publisher,relay,apps done
    class camera,files,esp32 outside
```

## 2. Who imports whom (by folder)

Made from the imports of the code (a script reads every `from vision...` line). An arrow means "uses". No detector imports an app, and `apps/link/` only needs `output/messageFormat.py`, which uses the standard library only: the robot Raspberry runs it with Python and pyserial, without numpy or OpenCV.

```mermaid
flowchart TD
    dashboard["apps/dashboard<br/>Qt window + 3D twin"] --> viewer
    viewer["apps/viewer<br/>OpenCV viewer, shared drawings"] --> factory
    mainApps["apps/*.py<br/>visionApp, calibration, synthetic video"] --> factory
    stream["apps/stream<br/>MJPEG video sender"] --> input
    link["apps/link<br/>robot relay, test receiver"] --> output
    factory["blackBoxFactory.py<br/>builds the box from the config"] --> box["visionBlackBox.py"]
    box --> aruco["aruco/"] & color["color/"] & fusion["fusion/"]
    color --> geometry["geometry/"]
    fusion --> geometry
    dashboard & viewer --> geometry
    mainApps --> input["input/"] & output["output/"] & simulation["simulation/<br/>synthetic scenes for tests and demos"]
    dashboard & viewer --> input
    aruco & color & fusion & geometry & input & output & simulation & box --> common["common/<br/>contract, internal types, config"]

    classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b1b1b
    class dashboard,viewer,mainApps,stream,link,factory,box,aruco,color,fusion,geometry,input,output,simulation,common done
```

## 3. The contract

`common/visionTypes.py`, unchanged since phase 1. `VisionResult`, `StoneDetection` and the two enums reach the ESP32 in the message (`visionMessage.md`); `FrameInput` stays in Python. The enum numbers are message codes: never renumber, only add at the end (a test freezes them).

```mermaid
classDiagram
    direction LR
    class FrameInput {
        image : ndarray BGR uint8
        timestampMs : int
    }
    class VisionResult {
        timestampMs : int
        processingTimeMs : float
        status : VisionStatus
        stones : list~StoneDetection~
    }
    class StoneDetection {
        xMm : float
        yMm : float
        yawDeg : float
        confidence : float 0 to 1
        source : DetectionSource
    }
    class VisionStatus {
        <<enumeration>>
        OK = 0
        NO_FRAME = 1
        NOT_CALIBRATED = 2
        CONFIG_ERROR = 3
    }
    class DetectionSource {
        <<enumeration>>
        ARUCO = 0
        COLOR = 1
        BOTH = 2
    }
    FrameInput ..> VisionResult : the black box turns one into the other
    VisionResult "1" *-- "0..*" StoneDetection : stones
    VisionResult --> VisionStatus
    StoneDetection --> DetectionSource
```

What each field means since phases 2b to 4 (in the robot frame: x forward, y left, origin on the floor under the robot, mm):

| Field | Meaning |
|---|---|
| `xMm`, `yMm` | Centre of the stone seen from above. A pile gives one stone per level, with the same x and y (team question 7) |
| `yawDeg` | Angle of the 320 mm side from the robot x axis, to the left, in [-90, 90): a stone turned 180 degrees is the same stone. A standing stone has no long side on the floor: the angle of a short side is given (team question 6) |
| `confidence` | ArUco 0.9 (0.7 if its pose was a doubt), +0.05 per extra face and +0.05 if the colour agrees; colour alone at most 0.5 |
| `stones` | Nearest first. Empty unless the status is `OK` |

`NOT_CALIBRATED` now also covers a camera mount that nobody has measured (`cameraMount.isMeasured` false): made-up positions never reach the robot.

## 4. How the configuration is loaded

`common/configLoader.py`. A missing key keeps its default; an unknown key or a wrong type stops the app and says which one. Since phase 3 the sections are split in three files: `visionConfig.py` (frame source, calibration board, ArUco, viewer and the whole `VisionConfig`), `detectionConfig.py` (stone, camera mount, colour, fusion) and `outputConfig.py` (output, video sender). Any `Enum` is written in the JSON as its text (`"mode": "stream"`, `"transport": "udp"`).

```mermaid
flowchart TD
    start(["An app starts: main()"]) --> appConfig["loadAppConfig(path)<br/>path given, else first argument,<br/>else config/visionConfig.json"]
    appConfig --> loadConfig["loadVisionConfig(path)<br/>starts from the defaults"]
    loadConfig --> readJson{"readJsonFile:<br/>exists, readable,<br/>a JSON object?"}
    readJson -- "no" --> failed(["False: the app stops<br/>and logs the reason"])
    readJson -- "yes" --> apply["applyJsonValues for the top level and<br/>the 10 sections: frameSource, calibrationBoard,<br/>aruco, viewer, stone, cameraMount, color,<br/>fusion, output, sender"]
    apply --> convert{"convertJsonValue, per key:<br/>known key and right type?<br/>an Enum: one of its texts?"}
    convert -- "yes" --> stored["value stored"]
    convert -- "no" --> rejected["logged as an error,<br/>default kept"]
    stored --> paths["resolveVisionPath:<br/>relative paths from vision/"]
    rejected --> paths
    paths --> valid{"every value accepted?"}
    valid -- "no" --> failed
    valid -- "yes" --> ready(["True + VisionConfig"])
```

The dashboard writes back too: `saveConfigSection` replaces only the colour range and keeps the rest of the file; `saveVisionConfig` writes a whole config (the synthetic demo uses it).

## 5. Reading images

`input/frameSource.py` gives one image at a time from a camera, a video, a folder or a **stream** (a URL, opened with a time limit so a dead sender never blocks). `input/latestFrameReader.py` reads it in a thread:

```mermaid
sequenceDiagram
    participant main as Main loop
    participant reader as LatestFrameReader thread
    participant source as FrameSource
    main->>reader: start()
    reader->>source: open()
    loop reading, in the thread
        reader->>source: read()
        alt live source: camera or stream
            source-->>reader: a frame
            Note over reader: replaces the frame not taken yet (counted as dropped)
        else recorded source: video or folder
            source-->>reader: a frame
            Note over reader: waits until the main loop takes it (none dropped)
        else the stream was cut
            reader->>source: reconnect(), then wait reconnectDelayMs
        end
    end
    main->>reader: takeLatest(wait)
    reader-->>main: the newest frame, or nothing yet
    main->>reader: stop()
```

Why: measured on 2026-11-23 with the MJPEG sender on this computer, a reader that takes one image every 200 ms straight from the stream ends up 38 images (1.3 s) late after 1.6 s, and the delay keeps growing. With `LatestFrameReader` the delay stayed at 0 images.

## 6. The calibration app

`apps/cameraCalibrationApp.py`, unchanged since phase 1. A camera or video saves a view every `captureIntervalMs`, so the board can be moved; in a folder every picture is a view. Nothing is saved after a failure or without your confirmation.

```mermaid
flowchart TD
    start(["main()"]) --> config{"loadAppConfig OK?"}
    config -- "no" --> stopped(["stop"])
    config -- "yes" --> collect
    subgraph collect ["collectBoardViews: repeated for each image"]
        read["read() an image"] --> found{"board found and<br/>a view is due?"}
        found -- "yes" --> sameSize{"same size as<br/>the first view?"}
        sameSize -- "yes" --> saved["cornerSubPix,<br/>view saved"]
        sameSize -- "no" --> skipped["warning:<br/>view skipped"]
    end
    collect -- "the source failed" --> nothing(["nothing saved"])
    collect -- "requiredViews reached,<br/>video or folder finished,<br/>or q pressed" --> enough{"at least<br/>minimumViews?"}
    enough -- "no" --> stopped
    enough -- "yes" --> calibrate["calibrateCamera:<br/>fx, fy, cx, cy, distortion"]
    calibrate --> ask{"result shown:<br/>save it? y/N"}
    ask -- "n" --> notSaved(["not saved"])
    ask -- "y" --> write(["saveCameraCalibration"])
```

## 7. How it was tested (without any real stone)

There is no box, printed code or calibrated camera yet, so everything is tested on **synthetic scenes** (`simulation/`): a pinhole camera with its own look-at maths (it does not use `geometry/`, so a sign error cannot hide in both), stones drawn face by face with a depth buffer, JPEG, noise, blur and lens distortion. `pytest ../tests/vision` runs 81 tests; the main numbers are in each file of this folder. What only the real hardware can tell is listed in the team notes (calibration at the stream resolution, the real code size, the camera mount, the brown of the real mat, motion blur, Wi-Fi delay).

## How to keep these files right

- Change them in the same branch as the code they describe, and update the date at the top.
- Check the imports of section 2 against the code (the folders have no `__init__.py`, so list the files): from `src/`, `pyreverse -o mmd -p vision --source-roots . vision/*.py vision/*/*.py vision/apps/*/*.py`.
- Keep to the classic Mermaid diagrams (flowchart, sequence, class): GitHub may not draw the newest syntax.
