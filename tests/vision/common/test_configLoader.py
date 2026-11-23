"""Tests of the JSON config: new sections, enums, unknown keys and saving one section."""

import json
from pathlib import Path

from vision.common.configLoader import loadVisionConfig, resolveVisionPath, saveConfigSection
from vision.common.outputConfig import OutputTransport
from vision.common.visionConfig import FrameSourceMode, MarkerAxis


def writeConfig(folder: Path, content: dict) -> str:
    path: Path = folder / "config.json"
    path.write_text(json.dumps(content), encoding="utf-8")
    return str(path)


def testTheConfigOfTheRepoLoads() -> None:
    isLoaded, config = loadVisionConfig(resolveVisionPath("config/visionConfig.json"))
    assert isLoaded
    assert config.aruco.markerLongAxis == MarkerAxis.X
    assert config.stone.lengthMm == 320.0


def testEnumsAreReadFromTheirText(tmp_path: Path) -> None:
    content: dict = {"frameSource": {"mode": "stream", "streamUrl": "http://robot:8080/video"},
                     "output": {"transport": "udp", "udpPort": 6000}, "aruco": {"markerLongAxis": "y"}}
    isLoaded, config = loadVisionConfig(writeConfig(tmp_path, content))
    assert isLoaded
    assert config.frameSource.mode == FrameSourceMode.STREAM
    assert config.output.transport == OutputTransport.UDP and config.output.udpPort == 6000
    assert config.aruco.markerLongAxis == MarkerAxis.Y


def testUnknownKeyOrWrongValueIsRejected(tmp_path: Path) -> None:
    for content in ({"cameraMount": {"heightMm": 300}}, {"output": {"transport": "carrier pigeon"}},
                    {"color": {"hueMin": "brown"}}):
        isLoaded, _ = loadVisionConfig(writeConfig(tmp_path, content))
        assert not isLoaded


def testSaveSectionKeepsTheRestOfTheFile(tmp_path: Path) -> None:
    path: str = writeConfig(tmp_path, {"color": {"hueMin": 5, "minAreaPx": 600}, "showWindow": False})
    assert saveConfigSection(path, "color", {"hueMin": 8, "hueMax": 22})
    saved: dict = json.loads(Path(path).read_text(encoding="utf-8"))
    assert saved == {"color": {"hueMin": 8, "minAreaPx": 600, "hueMax": 22}, "showWindow": False}
    assert not saveConfigSection(str(tmp_path / "missing.json"), "color", {"hueMin": 1})
