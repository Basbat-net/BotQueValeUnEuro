"""Claude Code hook: installs or updates the team plugins when a session starts.

The team plugins are the ones set to true under enabledPlugins in .claude/settings.json.
Enabling a plugin there does not download it, so this hook installs the missing ones
and updates the installed ones. Both run in the background with no time limit, so a slow
connection or a big plugin never delays or cuts the session start: the hook itself only
lists the installed plugins (local, about one second) and starts the work.
It installs with local scope: project scope rewrites the committed settings.json,
local scope writes .claude/settings.local.json, which is not committed.
It never blocks the session: when something fails it exits 0 and shows the manual command.
"""

import json
import os
import shutil
import subprocess
import sys
import time

INSTALL_SCOPE = "local"
# Only for 'claude plugin list', which is local; installs and updates have no time limit
LIST_TIMEOUT_SECONDS = 30
# A lock older than this was left by an install that died (for example, the computer was turned off)
STALE_LOCK_SECONDS = 30 * 60
# First argument of the background copy of this script that does one install
WORKER_FLAG = "--install-worker"
# Where to add a marketplace from when this person does not have it yet
KNOWN_MARKETPLACE_SOURCES = {"claude-plugins-official": "anthropics/claude-plugins-official"}


def loadSharedSettings(projectDir: str) -> dict:
    """Contents of .claude/settings.json, or an empty dict if it cannot be read."""
    settingsPath: str = os.path.join(projectDir, ".claude", "settings.json")
    try:
        with open(settingsPath, "r", encoding="utf-8") as settingsFile:
            return json.load(settingsFile)
    except (OSError, json.JSONDecodeError):
        return {}


def listTeamPlugins(settings: dict) -> list[str]:
    """Ids (name@marketplace) that the shared settings turn on."""
    enabledPlugins: dict = settings.get("enabledPlugins", {})
    return [pluginId for pluginId, isOn in enabledPlugins.items() if isOn is True and "@" in pluginId]


def findMarketplaceSource(settings: dict, marketplace: str) -> str:
    """Source to add the marketplace from, or '' if it is unknown."""
    declared: dict = settings.get("extraKnownMarketplaces", {}).get(marketplace, {}).get("source", {})
    for sourceKey in ("repo", "url", "path"):
        if sourceKey in declared:
            return declared[sourceKey]
    return KNOWN_MARKETPLACE_SOURCES.get(marketplace, "")


# The return type is in quotes so that Python 3.9 does not evaluate the '|' (it only exists from 3.10)
def listInstalledPlugins(claudePath: str, projectDir: str) -> "set[str] | None":
    """Ids of the plugins installed for this repo (user scope or this project). None on failure.
    A plugin that the person turned off is still installed, so it is not installed again."""
    try:
        result = subprocess.run([claudePath, "plugin", "list", "--json"], cwd=projectDir, capture_output=True,
                                text=True, timeout=LIST_TIMEOUT_SECONDS, stdin=subprocess.DEVNULL)
        entries: list = json.loads(result.stdout) if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None
    if result.returncode != 0:
        return None
    # normcase: on Windows C:\repo and c:\repo are the same folder
    projectRealPath: str = os.path.normcase(os.path.realpath(projectDir))
    installed: set[str] = set()
    for entry in entries:
        entryProject = entry.get("projectPath")
        if entryProject is None or os.path.normcase(os.path.realpath(entryProject)) == projectRealPath:
            installed.add(entry.get("id", ""))
    return installed


def startDetached(command: list[str], projectDir: str) -> bool:
    """Starts a command without waiting for it, so the session opens at once. True if it started."""
    # start_new_session detaches on Linux and macOS; Windows needs these flags (0 elsewhere)
    windowsFlags: int = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen(command, cwd=projectDir, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True, creationflags=windowsFlags)
    except OSError:
        return False
    return True


def buildStatePaths(pluginId: str) -> tuple[str, str]:
    """Lock and log files of one plugin install, in the temp folder: outside the repo, so never committed."""
    tempDir: str = os.environ.get("TMPDIR") or os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
    safeName: str = "".join(character if character.isalnum() or character in "-." else "_" for character in pluginId)
    stateDir: str = os.path.join(tempDir, "claudeTeamPlugins")
    return os.path.join(stateDir, safeName + ".lock"), os.path.join(stateDir, safeName + ".log")


def claimInstallLock(lockPath: str) -> bool:
    """Creates the lock of one install. False if another install of the same plugin is still running."""
    try:
        if time.time() - os.path.getmtime(lockPath) > STALE_LOCK_SECONDS:
            os.remove(lockPath)
    except OSError:
        # No lock yet: the normal case
        pass
    try:
        os.makedirs(os.path.dirname(lockPath), exist_ok=True)
        # O_EXCL: if two sessions start at the same time, only one of them gets the lock
        os.close(os.open(lockPath, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return False
    except OSError:
        # The temp folder cannot be written: install anyway, at worst two installs overlap
        return True
    return True


def runInstallWorker(pluginId: str, projectDir: str) -> int:
    """Background copy of this script: installs one plugin with no time limit.
    The log is kept only if the install fails, so the next session can point to it."""
    lockPath, logPath = buildStatePaths(pluginId)
    pluginName, marketplace = pluginId.split("@", 1)
    source: str = findMarketplaceSource(loadSharedSettings(projectDir), marketplace)
    if source != "":
        arguments: list[str] = ["plugin", "install", pluginName, "--marketplace", source]
    else:
        arguments = ["plugin", "install", pluginId]
    arguments += ["--scope", INSTALL_SCOPE]
    try:
        # No timeout: a slow connection or a big plugin only makes it take longer
        result = subprocess.run([shutil.which("claude") or "claude"] + arguments, cwd=projectDir,
                                stdin=subprocess.DEVNULL, capture_output=True, text=True)
        returnCode: int = result.returncode
        output: str = result.stdout + result.stderr
    except OSError as error:
        returnCode, output = 1, str(error)
    try:
        if returnCode == 0:
            os.remove(logPath)
        else:
            os.makedirs(os.path.dirname(logPath), exist_ok=True)
            with open(logPath, "w", encoding="utf-8") as logFile:
                logFile.write("claude " + " ".join(arguments) + "\n" + output)
    except OSError:
        # No old log to remove, or the log cannot be written: only the message gets shorter
        pass
    try:
        os.remove(lockPath)
    except OSError:
        pass
    return returnCode


def handleMissingPlugin(pluginId: str, projectDir: str) -> str:
    """Starts the background install of a plugin that is not installed. Returns the message for the person."""
    lockPath, logPath = buildStatePaths(pluginId)
    manualCommand: str = f"claude plugin install {pluginId} --scope {INSTALL_SCOPE}"
    if not claimInstallLock(lockPath):
        return f"Team plugin {pluginId} is still installing in the background."
    previousTryFailed: bool = os.path.exists(logPath)
    workerCommand: list[str] = [sys.executable, os.path.abspath(__file__), WORKER_FLAG, pluginId, projectDir]
    if not startDetached(workerCommand, projectDir):
        try:
            os.remove(lockPath)
        except OSError:
            pass
        return f"Could not install the team plugin {pluginId}. Run: {manualCommand}"
    message: str = (f"Installing the team plugin {pluginId} in the background. It will be ready in the next "
                    f"session, or earlier with /reload-plugins once it finishes.")
    if previousTryFailed:
        message += f" The last try failed (log: {logPath}). If it fails again, run: {manualCommand}"
    return message


def buildOutput(messages: list[str]) -> dict:
    """Hook answer: the messages for the person, and the same text for Claude. Empty if there are none."""
    if not messages:
        return {}
    text: str = "\n".join(messages)
    return {"systemMessage": text, "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def main() -> int:
    if len(sys.argv) == 4 and sys.argv[1] == WORKER_FLAG:
        return runInstallWorker(sys.argv[2], sys.argv[3])
    try:
        hookInput: dict = json.load(sys.stdin)
    except json.JSONDecodeError:
        hookInput = {}
    projectDir: str = os.environ.get("CLAUDE_PROJECT_DIR") or hookInput.get("cwd") or os.getcwd()
    teamPlugins: list[str] = listTeamPlugins(loadSharedSettings(projectDir))
    if not teamPlugins:
        return 0
    claudePath: str = shutil.which("claude") or ""
    installed = listInstalledPlugins(claudePath, projectDir) if claudePath != "" else None
    if installed is None:
        # Without the claude command in the PATH the plugins cannot be checked: show the manual way
        print(json.dumps(buildOutput([f"Could not check the team plugin {pluginId}. Run in a terminal: "
                                      f"claude plugin install {pluginId} --scope {INSTALL_SCOPE} "
                                      f"(or install it from /plugin inside Claude Code)" for pluginId in teamPlugins])))
        return 0
    messages: list[str] = []
    for pluginId in teamPlugins:
        if pluginId in installed:
            # Updating is optional: if it does not start, the plugin keeps the version it has
            startDetached([claudePath, "plugin", "update", pluginId], projectDir)
        else:
            messages.append(handleMissingPlugin(pluginId, projectDir))
    output: dict = buildOutput(messages)
    if output:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
