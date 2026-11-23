"""Makes the synthetic demo: a video of stones drawn by the computer, with the truth of every frame.

Run from the src/ folder:
    python3 -m vision.apps.syntheticVideoApp [--folder ~/visionTests/synthetic]
It writes demo.avi, calibration.json, demoConfig.json and truth.csv in that folder (outside the repo:
videos are heavy). Then open the demo with any app, for example:
    python3 -m vision.apps.dashboard.dashboardApp ~/visionTests/synthetic/demoConfig.json
It takes about a minute (the renderer is simple, not fast).
"""

import argparse

import numpy as np

from vision.simulation.demoScript import DemoTimeline, buildDemoBoxes, buildDemoOptions, describeTruth
from vision.simulation.demoWriter import DemoWriter
from vision.simulation.sceneRenderer import renderScene
from vision.simulation.sceneSetup import SceneSetup, SceneSetupConfig, buildSceneSetup


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Writes the synthetic demo video")
    parser.add_argument("--folder", default="~/visionTests/synthetic", help="where the demo files go")
    arguments: argparse.Namespace = parser.parse_args()
    randomGenerator: np.random.Generator = np.random.default_rng(2027)
    # Looking 20 degrees down (not 30) so the quarry at the back fits in the picture
    setup: SceneSetup = buildSceneSetup(SceneSetupConfig(pitchDeg=20.0), randomGenerator)
    writer: DemoWriter = DemoWriter(arguments.folder, setup, DemoTimeline.framesPerSecond)
    if not writer.open():
        print(writer.lastError)
        return
    frameCount: int = round(DemoTimeline.durationSeconds * DemoTimeline.framesPerSecond)
    for frameIndex in range(frameCount):
        boxes = buildDemoBoxes(frameIndex / DemoTimeline.framesPerSecond)
        image: np.ndarray = renderScene(setup.camera, boxes, setup.textures, buildDemoOptions(), randomGenerator)
        writer.addFrame(image, frameIndex, describeTruth(boxes))
        if frameIndex % 30 == 0:
            print(f"frame {frameIndex} of {frameCount}")
    if writer.close():
        print("Demo written in", writer.folder)
        print("Open it with: python3 -m vision.apps.dashboard.dashboardApp", writer.path("demoConfig.json"))
    else:
        print(writer.lastError)


if __name__ == "__main__":
    main()
