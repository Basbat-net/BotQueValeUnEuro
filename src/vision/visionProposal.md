# Vision subproject: proposal

> **Status: proposal** (2026-11-13). Not approved yet. No vision code is in the repo: it is uploaded only after the team accepts this document.
> Rule references: `[2027 X]` = Eurobot 2027 game rules, official version 1.0.

## 1. Goal

Tell the robot **where the stones are**, so it can pick them up and place them.
First objective: detect the stones. Other objects (balls, the Grail, other robots) are out of scope for now.

What we know about the stones `[2027 D.4]`:

- Brown cardboard boxes of 320 × 110 × 110 mm.
- 30 stones, in quarries of 3 stacked stones. Their starting positions are fixed and given in the table plan.
- Each stone has an **ArUco marker, ID 13, 4x4 dictionary**, on its 4 large faces. The 2 small faces have none.

## 2. What is proposed

| Question | Proposal | Why |
|---|---|---|
| Where is the camera? | **On the robot**, high and tilted down | Picking a stone needs to see it up close and without delay. A camera off the robot depends on radio |
| What processes the images? | A small **computer on the robot**, which sends the result to the microcontroller | Marker detection with pose needs OpenCV; a microcontroller cannot run it fast enough |
| Main detector | **ArUco 13** | The marker is already on the stone. It gives exact position and orientation, with no training and no color tuning |
| Support detector | **Color + shape** | Finds the stone when the marker is not visible (covered, or seen from a small face) |
| Machine learning | Not for now | Most expensive in hours and does not give the pose. Only if tests show the two detectors are not enough |

The camera model and the computer are **not decided**. The code must not depend on either.

At the start of a match the stones are where the plan says, so the robot can reach a quarry without vision. Vision matters in the last half metre and once the stones have been moved.

## 3. Language: Python

This subproject would be written in **Python 3 + OpenCV**. It is an exception to "only Arduino and C++" in `projectRules.md`, requested because Python is the usual language for this kind of algorithm and the code runs on a computer, not on a microcontroller.

The rules that do not depend on the language are kept:

- Code and comments in English, `camelCase` names that explain themselves.
- Type hints on every function and `dataclass` for data (the equivalent of static typing).
- At most 15 functions per file and 150 lines per function.
- No global variables: parameters live in a configuration file.
- No inheritance.
- Functions return a success flag; exceptions only for recovery.
- Commits by hand, one file per commit.

## 4. The black box contract

The rest of the robot only needs to know this. What happens inside can change without affecting anyone.

```text
                ┌─────────────────────────────┐
  image    ───► │                             │ ───► list of stones
  + time        │      VISION BLACK BOX       │      (position, angle, confidence, source)
                │                             │ ───► status + processing time
  config   ───► │                             │
  (at startup)  └─────────────────────────────┘
```

**Input:** one image and the time it was captured (ms).

**Output**, one per image:

| Field | Meaning |
|---|---|
| `timestampMs` | Capture time of the image, so the receiver knows how old the measurement is |
| `processingTimeMs` | How long the detection took |
| `status` | `OK`, `NO_FRAME`, `NOT_CALIBRATED`... |
| `stones` | List of stones; may be empty |

Each stone:

| Field | Meaning |
|---|---|
| `xMm`, `yMm` | Position in the **robot frame**: x forward, y left, in millimetres |
| `yawDeg` | Orientation of the stone, in degrees |
| `confidence` | From 0 to 1 |
| `source` | `ARUCO`, `COLOR` or `BOTH` |

Rules of the contract:

- One image in, one result out, always. No stones means an empty list.
- It never blocks. A failure is reported in `status`.
- It knows nothing about motors, the gripper or the strategy.
- It does not open the camera and does not send anything: two separate modules do that, so the camera, the computer or the link to the microcontroller can change without touching the detection.

Positions are given in the robot frame because vision does not know where the robot is on the table; localisation does.

## 5. Structure

```text
src/vision/
├── CLAUDE.md, README.md, requirements.txt
├── config/      # parameters and camera calibration
├── common/      # the contract, the configuration and its loading
├── input/       # image source: camera, recorded video or folder of pictures
├── aruco/       # ArUco detector: image -> marker faces with their pose
├── color/       # color + shape detector: image -> box-shaped brown areas
├── geometry/    # camera frame -> robot frame
├── fusion/      # joins both detectors into a single list of stones
├── output/      # sends the result to the microcontroller
└── apps/        # one small program to test each part
tests/vision/    # tests against recorded videos
```

How it stays modular:

- **The two detectors do not know each other.** Only `fusion/` knows there are two, so adding a third one later is adding a folder.
- **The image source is interchangeable.** The same code reads a live camera or a recorded video, so everything can be tested without the robot.
- **Drawing on screen is only in `apps/`.** The robot has no screen.

## 6. Phases

Each phase is tested and delivered on its own. If time runs out after phase 2, the robot already detects stones.

| Phase | What | How we know it works |
|---|---|---|
| 0 | The team accepts this proposal | — |
| 1 | Base: contract, configuration, image source, camera calibration | The same code opens a camera and a recorded video; calibration error under 1 px |
| 2 | ArUco detector, alone | On recorded videos: % of frames detected per case, and position error against a tape measure |
| 3 | Color + shape detector, alone | Same videos: % of stones found and false positives per frame |
| 4 | Fusion and the black box | Never two stones where there is one; with the marker covered, the stone is still reported |
| 5 | Output to the microcontroller | The microcontroller receives and understands the message; total delay measured |
| 6 | On the robot, with the final camera and computer | Frames per second and delay measured on the real hardware |

Before phase 2, a set of test videos is recorded once (quarry, stone lying, standing, seen from a small face, covered, far, camera moving, different lights), with the real positions measured by hand. Every detector is tested against the same videos.

State on 2026-11-13: phase 1 is written and tested locally, not uploaded.

## 7. What this proposal asks the team to accept

1. **Python** for this subproject (section 3).
2. **A computer on the robot** for vision, besides the microcontroller.
3. **The contract** of section 4: fields, units and robot frame.
4. That the **message to the microcontroller** (format and link) is agreed with whoever writes that side, before phase 5.
