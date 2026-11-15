"""Claude Code hook: blocks the Git commands that change the repository history.

projectRules.md: "All commits must be done by hand (no AI commits ever)".
Runs before every Bash command. Exit code 2 cancels the command and shows
the message to Claude. Read-only Git (status, log, diff, branch) is allowed.
"""

import json
import re
import shlex
import sys

BLOCKED_SUBCOMMANDS = ("commit", "push", "pull", "merge", "rebase", "reset", "cherry-pick", "revert", "am")
# Git options that take a value as the next word, e.g. git -C <path> commit
OPTIONS_WITH_VALUE = ("-C", "-c", "--git-dir", "--work-tree", "--namespace")
SHELL_NAMES = ("sh", "bash", "zsh")
# Limit for commands nested inside other commands (rule: recursion always bounded)
MAX_NESTING_DEPTH = 3
BRANCH_CREATION_FLAGS = {"checkout": ("-b", "-B"), "switch": ("-c", "-C", "--create")}


def splitIntoWords(command: str) -> list[str]:
    """Words of the command. Quoted text stays as one word, so a search for
    the text "git commit" is not mistaken for a real git call."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        # Unbalanced quotes: fall back to a rough split
        return re.sub(r"[;&|()`'\"\n{}$]", " ", command).split()


def listNestedCommands(command: str, words: list[str]) -> list[str]:
    """Commands hidden inside the main one: $(...), `...` and sh -c "..."."""
    nested: list[str] = re.findall(r"\$\(([^()]*)\)", command) + re.findall(r"`([^`]*)`", command)
    for position in range(2, len(words)):
        isShell: bool = words[position - 2].split("/")[-1] in SHELL_NAMES
        if isShell and words[position - 1] == "-c":
            nested.append(words[position])
    return nested


def findGitSubcommands(words: list[str]) -> list[tuple[str, list[str]]]:
    """Returns (subcommand, following words) for every git call in the command."""
    calls: list[tuple[str, list[str]]] = []
    for position, word in enumerate(words):
        if word != "git" and not word.endswith("/git"):
            continue
        index: int = position + 1
        while index < len(words) and words[index].startswith("-"):
            # Skip the options placed before the subcommand
            index += 2 if words[index] in OPTIONS_WITH_VALUE else 1
        if index < len(words):
            calls.append((words[index], words[index + 1:]))
    return calls


def findBlockedCall(command: str, depth: int = 0) -> str:
    """Returns the forbidden git call found in the command, or '' if there is none."""
    words: list[str] = splitIntoWords(command)
    for subcommand, followingWords in findGitSubcommands(words):
        if subcommand in BLOCKED_SUBCOMMANDS:
            return "git " + subcommand
        creationFlags: tuple = BRANCH_CREATION_FLAGS.get(subcommand, ())
        if any(word in creationFlags for word in followingWords):
            return "git " + subcommand + " (new branch)"
    if depth >= MAX_NESTING_DEPTH:
        return ""
    for nestedCommand in listNestedCommands(command, words):
        blockedCall: str = findBlockedCall(nestedCommand, depth + 1)
        if blockedCall != "":
            return blockedCall
    return ""


def main() -> int:
    try:
        hookInput: dict = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command: str = hookInput.get("tool_input", {}).get("command", "")
    blockedCall: str = findBlockedCall(command)
    if blockedCall == "":
        return 0
    print(f"Blocked by the team rules: '{blockedCall}' must be run by hand by the person.", file=sys.stderr)
    print("Do not retry it in another form. Explain the change and give the person", file=sys.stderr)
    print("the exact commands to run, with the commit rules of projectRules.md.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
