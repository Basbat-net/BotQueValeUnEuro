"""Claude Code hook: checks the size limits of projectRules.md after an edit.

Limits: at most 15 functions per file and 150 lines per function.
It only warns (exit code 2 shows the message to Claude); it never blocks the edit.
Python files are parsed exactly; C++ and Arduino files are estimated from braces.
"""

import ast
import json
import re
import sys

MAX_FUNCTIONS_PER_FILE = 15
MAX_LINES_PER_FUNCTION = 150
PYTHON_EXTENSIONS = (".py",)
CPP_EXTENSIONS = (".cpp", ".h", ".ino")


def listPythonFunctions(sourceText: str) -> list[tuple[str, int]]:
    """Returns (name, lineCount) of every function, methods included."""
    try:
        tree = ast.parse(sourceText)
    except SyntaxError:
        # A file that does not parse yet is not this hook's problem
        return []
    return [
        (node.name, node.end_lineno - node.lineno + 1)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def listCppFunctions(sourceText: str) -> list[tuple[str, int]]:
    """Estimates (name, lineCount) of every function from its braces."""
    functionStart = re.compile(r"^\s*[\w:<>~&\s]+?\b([\w:~]+)\s*\([^;{}]*\)\s*(const)?\s*\{\s*$")
    controlWords = ("if", "for", "while", "switch", "catch", "else")
    functions: list[tuple[str, int]] = []
    lines: list[str] = sourceText.splitlines()
    lineIndex: int = 0
    while lineIndex < len(lines):
        match = functionStart.match(lines[lineIndex])
        if match is None or match.group(1) in controlWords:
            lineIndex += 1
            continue
        depth: int = 0
        endIndex: int = lineIndex
        while endIndex < len(lines):
            depth += lines[endIndex].count("{") - lines[endIndex].count("}")
            if depth <= 0:
                break
            endIndex += 1
        functions.append((match.group(1), endIndex - lineIndex + 1))
        lineIndex = endIndex + 1
    return functions


def findViolations(filePath: str) -> list[str]:
    """Returns one message per broken limit. An unknown file type gives none."""
    lowerPath: str = filePath.lower()
    if not lowerPath.endswith(PYTHON_EXTENSIONS + CPP_EXTENSIONS):
        return []
    try:
        with open(filePath, "r", encoding="utf-8", errors="replace") as sourceFile:
            sourceText: str = sourceFile.read()
    except OSError:
        return []
    if lowerPath.endswith(PYTHON_EXTENSIONS):
        functions = listPythonFunctions(sourceText)
    else:
        functions = listCppFunctions(sourceText)
    violations: list[str] = []
    if len(functions) > MAX_FUNCTIONS_PER_FILE:
        violations.append(f"{len(functions)} functions (limit: {MAX_FUNCTIONS_PER_FILE} per file)")
    for name, lineCount in functions:
        if lineCount > MAX_LINES_PER_FUNCTION:
            violations.append(f"function '{name}' has {lineCount} lines (limit: {MAX_LINES_PER_FUNCTION})")
    return violations


def main() -> int:
    try:
        hookInput: dict = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    filePath: str = hookInput.get("tool_input", {}).get("file_path", "")
    violations: list[str] = findViolations(filePath)
    if not violations:
        return 0
    print(f"projectRules.md limits broken in {filePath}:", file=sys.stderr)
    for violation in violations:
        print(f"  - {violation}", file=sys.stderr)
    print("Split the file or the function before handing it over.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
