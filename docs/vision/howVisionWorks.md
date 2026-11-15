# How the vision subproject works

Diagrams of `src/vision/`, from the big picture to the details.
They are written in [Mermaid](https://mermaid.js.org/): GitHub draws them, and so does VS Code with a Markdown preview that supports Mermaid.

> Checked against the code on 2026-11-15 (end of phase 1, branch `vision`).
> When `src/vision/` changes, this file changes in the same branch.

**Legend:** green = exists today (phase 1) · grey and dashed = planned in a later phase · white = outside the vision code.

## 1. The big picture

One image goes in, one result goes out. The black box never opens the camera and never talks to the robot: `input/` and `output/` do that.

```mermaid
flowchart LR
    camera["Camera, video<br/>or folder of pictures"] --> frameSource["input/frameSource.py<br/>FrameSource"]
    jsonFile["config/visionConfig.json"] -. "read at startup" .-> loader["common/configLoader.py"]
    loader -. "VisionConfig" .-> frameSource
    frameSource -- "FrameInput<br/>image + capture time" --> aruco
    frameSource -- "FrameInput" --> color
    subgraph blackBox ["Vision black box (phases 2 to 4)"]
        aruco["aruco/<br/>ArUco 13 detector"]
        color["color/<br/>colour + shape detector"]
        geometry["geometry/<br/>camera to robot frame"]
        fusion["fusion/<br/>one stone per stone"]
        aruco --> fusion
        color --> fusion
        fusion -. "uses" .-> geometry
    end
    fusion -- "VisionResult<br/>status + stones" --> publisher["output/<br/>resultPublisher"]
    publisher -- "message, format to agree" --> esp32["ESP32"]

    classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b1b1b
    classDef planned fill:#eeeeee,stroke:#9e9e9e,stroke-dasharray:4 3,color:#555555
    classDef outside fill:#ffffff,stroke:#616161,color:#1b1b1b
    class frameSource,loader,jsonFile done
    class aruco,color,geometry,fusion,publisher planned
    class camera,esp32 outside
```

## 2. Who imports whom today

Generated from the code with `pyreverse` and redrawn. Both apps import the same three modules; nothing in `common/` or `input/` imports an app.

```mermaid
flowchart TD
    apps["apps/ - the programs you run<br/>frameSourceTestApp.py: checks the image source<br/>cameraCalibrationApp.py: calibrates the camera"]
    frameSource["input/frameSource.py<br/>gives the images"]
    subgraph common ["common/"]
        loader["configLoader.py<br/>reads and checks the JSON files"]
        config["visionConfig.py<br/>parameters as dataclasses"]
        types["visionTypes.py<br/>the contract"]
    end
    apps --> loader
    apps --> frameSource
    apps --> config
    loader --> config
    frameSource --> config
    frameSource --> types

    classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b1b1b
    class apps,frameSource,loader,config,types done
```

## 3. The contract

`common/visionTypes.py`. `VisionResult`, `StoneDetection` and the two enums will reach the ESP32; `FrameInput` stays in Python. The enum numbers are message codes: never renumber, only add at the end.

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

Positions are in the robot frame: x forward, y left, in mm. `stones` is empty when `status` is not `OK`.

## 4. How the configuration is loaded

`common/configLoader.py`. Every app starts here. A missing key keeps its default; an unknown key or a wrong type stops the app and says which one.

```mermaid
flowchart TD
    start(["An app starts: main()"]) --> appConfig["loadAppConfig()<br/>logging, then the config path:<br/>first argument or config/visionConfig.json"]
    appConfig --> loadConfig["loadVisionConfig(path)<br/>starts from the defaults"]
    loadConfig --> readJson{"readJsonFile:<br/>exists, readable,<br/>a JSON object?"}
    readJson -- "no" --> failed(["False: the app stops<br/>and logs the reason"])
    readJson -- "yes" --> apply["applyJsonValues, 3 times:<br/>top level, frameSource,<br/>calibrationBoard"]
    apply --> convert{"convertJsonValue, per key:<br/>known key and right type?"}
    convert -- "yes" --> stored["value stored"]
    convert -- "no" --> rejected["logged as an error,<br/>default kept"]
    stored --> paths["resolveVisionPath:<br/>relative paths from vision/"]
    rejected --> paths
    paths --> valid{"every value accepted?"}
    valid -- "no" --> failed
    valid -- "yes" --> screen{"Linux without<br/>a screen?"}
    screen -- "yes" --> noWindow["showWindow turned off,<br/>with a warning"]
    screen -- "no" --> ready(["True + VisionConfig"])
    noWindow --> ready
```

## 5. Reading images

`input/frameSource.py`. The same four methods for a camera, a video or a folder of pictures. When `read()` gives `False`, `hasEnded()` tells a normal finish from a failure.

```mermaid
sequenceDiagram
    participant app as App
    participant source as FrameSource
    participant opencv as OpenCV
    app->>source: open()
    source->>opencv: VideoCapture.open, or list the pictures
    source-->>app: True, or False with lastError
    loop until the app stops
        app->>source: read()
        source->>opencv: capture.read(), or imread of the next picture
        alt an image arrived
            source-->>app: True and FrameInput with image and timestampMs
        else no image
            source-->>app: False, an empty frame and lastError
            app->>source: hasEnded()
            alt video or folder finished
                source-->>app: True, a normal finish
            else camera failed or unreadable picture
                source-->>app: False, a failure the app reports
            end
        end
    end
    app->>source: close()
```

## 6. The calibration app

`apps/cameraCalibrationApp.py`. A camera or video saves a view every `captureIntervalMs`, so the board can be moved; in a folder every picture is a view. Nothing is saved after a failure or without your confirmation.

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
    collect -- "the source could not open,<br/>the camera failed or<br/>a picture is unreadable" --> nothing(["nothing saved"])
    collect -- "requiredViews reached,<br/>video or folder finished,<br/>or q pressed" --> enough{"at least<br/>minimumViews?"}
    enough -- "no" --> stopped
    enough -- "yes" --> calibrate["calibrateCamera:<br/>fx, fy, cx, cy, distortion"]
    calibrate --> ask{"result shown:<br/>save it? y/N"}
    ask -- "n" --> notSaved(["not saved"])
    ask -- "y" --> write{"saveCameraCalibration:<br/>file written?"}
    write -- "yes" --> calibrationSaved(["calibration saved"])
    write -- "no" --> writeFailed(["error logged, not saved"])
```

## How to keep this file right

- Change it in the same branch as the code it describes, and update the date at the top.
- Check the imports of section 2 against the code. From `src/`, with `pylint` installed:
  `pyreverse -o mmd -p vision --source-roots . vision/common/*.py vision/input/*.py vision/apps/*.py`
  (the files are listed one by one because the folders have no `__init__.py`).
- Keep to the classic Mermaid diagrams (flowchart, sequence, class): GitHub may not draw the newest syntax.
