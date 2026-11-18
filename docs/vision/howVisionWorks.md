# How the vision subproject works

Diagrams of `src/vision/`, from the big picture to the details.
They are written in [Mermaid](https://mermaid.js.org/): GitHub draws them, and so does VS Code with a Markdown preview that supports Mermaid.

> Checked against the code on 2026-11-17 (end of phase 2a, branch `vision`).
> When `src/vision/` changes, this file changes in the same branch.

**Legend:** green = exists today (phases 1 and 2a) · grey and dashed = planned in a later phase · white = outside the vision code.

## 1. The big picture

One image goes in, one result goes out. The black box never opens the camera and never talks to the robot: `input/` and `output/` do that. The ArUco detector works in pixels (phase 2a); the viewer shows what it finds.

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
    aruco -. "ArucoDetection" .-> viewer["apps/viewer/<br/>shows what the detectors find"]

    classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b1b1b
    classDef planned fill:#eeeeee,stroke:#9e9e9e,stroke-dasharray:4 3,color:#555555
    classDef outside fill:#ffffff,stroke:#616161,color:#1b1b1b
    class frameSource,loader,jsonFile,aruco,viewer done
    class color,geometry,fusion,publisher planned
    class camera,esp32 outside
```

## 2. Who imports whom today

Generated from the code with `pyreverse` and redrawn. The viewer is one box here (its insides are in section 8). Nothing in `common/`, `input/` or `aruco/` imports an app.

```mermaid
flowchart TD
    apps["apps/ - phase 1 programs<br/>frameSourceTestApp.py: checks the image source<br/>cameraCalibrationApp.py: calibrates the camera"]
    viewer["apps/viewer/<br/>visionViewerApp.py and its modules"]
    frameSource["input/frameSource.py<br/>gives the images"]
    aruco["aruco/arucoStoneDetector.py<br/>finds the markers"]
    subgraph common ["common/"]
        loader["configLoader.py<br/>reads and checks the JSON files"]
        config["visionConfig.py<br/>parameters as dataclasses"]
        types["visionTypes.py<br/>the contract"]
        detectionTypes["detectionTypes.py<br/>internal data of the detectors"]
    end
    apps --> loader & frameSource & config
    viewer --> loader & frameSource & config & aruco & detectionTypes
    aruco --> detectionTypes & config
    loader --> config
    frameSource --> config & types

    classDef done fill:#c8e6c9,stroke:#2e7d32,color:#1b1b1b
    class apps,viewer,frameSource,aruco,loader,config,types,detectionTypes done
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
    readJson -- "yes" --> apply["applyJsonValues, 5 times: top level,<br/>frameSource, calibrationBoard,<br/>aruco, viewer"]
    apply --> convert{"convertJsonValue, per key:<br/>known key and right type?"}
    convert -- "yes" --> stored["value stored"]
    convert -- "no" --> rejected["logged as an error,<br/>default kept"]
    stored --> paths["resolveVisionPath:<br/>relative paths from vision/,<br/>~ allowed in recordingsFolder"]
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

## 7. The ArUco detector

`aruco/arucoStoneDetector.py`, phase 2a: everything in pixels. A wrong dictionary name or stone ID is found when the detector is created: `isReady` is `False` and `lastError` says why. It never draws: the viewer does.

```mermaid
flowchart TD
    start(["detect(image)"]) --> ready{"isReady and the<br/>image not empty?"}
    ready -- "no" --> empty(["ArucoDetection<br/>with empty lists"])
    ready -- "yes" --> gray["cvtColor to gray<br/>if the image has colour"]
    gray --> detectMarkers["detectMarkers:<br/>corners, ids, rejected"]
    detectMarkers --> eachMarker
    subgraph eachMarker ["repeated for each marker found"]
        build["_buildMarker:<br/>center and mean side in px"] --> isStone{"id == stoneMarkerId?"}
        isStone -- "yes" --> stone["stoneFaces"]
        isStone -- "no" --> other["otherMarkers"]
    end
    eachMarker --> result(["ArucoDetection: stoneFaces, otherMarkers,<br/>rejectedCornersPx, processingTimeMs"])
```

## 8. The viewer

`apps/viewer/`, run with `python3 -m vision.apps.viewer.visionViewerApp`. Each file has one job, so none goes over the 6 imports of the team rules. Only `viewerPipeline` knows the detectors and only `viewerDrawing` knows the drawings.

```mermaid
flowchart TD
    app["visionViewerApp.py<br/>main()"] --> session["viewerSession.py<br/>the loop"]
    pipeline["viewerPipeline.py<br/>runs the detectors, loads the calibration"]
    screen["viewerScreen.py<br/>window, keys, snapshots"]
    recorder["frameRecorder.py<br/>videos and pictures"]
    drawing["viewerDrawing.py<br/>puts the picture together"]
    arucoOverlay["arucoOverlay.py<br/>markers, threshold view"]
    hud["hudOverlay.py<br/>status bar, help, colours"]
    state["viewerState.py<br/>mode, keys, session numbers"]
    session --> pipeline & screen
    screen --> recorder & drawing
    drawing --> arucoOverlay & hud
    arucoOverlay --> hud
    session & pipeline & screen & drawing & hud --> state
```

What `ViewerSession.run()` does in each loop, until `q`, `Esc` or the window is closed:

1. If playing, or after `n` while paused: `FrameSource.read()` gives a new image. At the end of a video it pauses on the last one.
2. `ViewerPipeline.process()` runs the detectors of the mode and returns a `ViewerFrame`. While paused the same image is processed again (so a change is seen at once) but counted once.
3. `ViewerScreen.update()` records the raw image if `r` is on, draws, shows, reads a key with `applyKey` and returns `False` to quit.

## How to keep this file right

- Change it in the same branch as the code it describes, and update the date at the top.
- Check the imports of section 2 against the code. From `src/`, with `pylint` installed:
  `pyreverse -o mmd -p vision --source-roots . vision/*/*.py vision/apps/viewer/*.py`
  (the files are listed one by one because the folders have no `__init__.py`).
- Keep to the classic Mermaid diagrams (flowchart, sequence, class): GitHub may not draw the newest syntax.
