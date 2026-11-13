# Repository structure

> **Status: proposal** (2026-11-13). Not approved yet: the team reviews it and the tech lead decides.
> Once approved, this file is the reference for where things go. `CLAUDE.md` imports it, so Claude follows it too.

## 1. Principles

1. **Code lives in `src/`, one folder per subproject.** Everything else (tests, documents, tools, AI setup) lives outside `src/`.
2. **A subproject is a black box.** It has its own instructions and a documented contract (what goes in, what comes out). Other subprojects only use that contract.
3. **Rules live in one place.** `projectRules.md` is the source of truth for coding and Git rules. Other files point to it; they do not copy it.
4. **If it is not in this document, ask before creating it.** A new top-level folder is a team decision.

## 2. The tree

```text
BotQueValeUnEuro/
├── CLAUDE.md            # instructions for Claude, shared by the team
├── README.md            # what the repo is, for GitHub
├── projectRules.md      # coding and Git rules of the team
├── .gitignore
├── .claude/             # shared AI setup
│   ├── settings.json    #   permissions and hooks
│   ├── hooks/           #   scripts run by the hooks
│   ├── skills/          #   one folder per skill
│   └── agents/          #   one file per subagent
├── src/                 # all the code of the robot
│   └── <subproject>/    #   one folder per subproject (section 4)
├── tests/               # tests
│   └── <subproject>/
├── docs/                # documentation
│   ├── repoStructure.md #   this file
│   └── <subproject>/
└── scripts/             # tools that are not part of the robot
```

Git does not store empty folders: a folder appears when its first file is committed. Do not add placeholder files to create one.

## 3. What each folder contains

| Path | Contains | Does not contain |
|---|---|---|
| `CLAUDE.md` | What the project is, how to work, links to the rules. Short: under 200 lines | Rules of one subproject (they go in that subproject) |
| `README.md` | Presentation of the repo for someone who arrives from GitHub | — |
| `projectRules.md` | The rules. Changed only by the tech lead | — |
| `.claude/settings.json` | Permissions and hooks shared by the whole team | Personal preferences (they go in `.claude/settings.local.json`, not committed) |
| `.claude/hooks/` | Scripts the hooks run. Small, one job each | Code of the robot |
| `.claude/skills/<name>/` | `SKILL.md` with the steps of one repeatable task | — |
| `.claude/agents/` | One `.md` per subagent, with the minimum tools it needs | — |
| `src/<subproject>/` | The code of one part of the robot, with its own instructions and README | Tests, heavy data, another subproject's code |
| `tests/<subproject>/` | Tests of that subproject and the small data they need | Recorded videos or large datasets |
| `docs/` | Documents that apply to the whole repo | — |
| `docs/<subproject>/` | Design notes and the contract of that subproject | Meeting minutes, task boards (they live in Notion) |
| `scripts/` | Tools used around the robot: flashing, checks, converters | Anything the robot runs during a match |

**If the team uses other AI assistants:** for now the instructions live in `CLAUDE.md`, which only Claude reads. `AGENTS.md` is the equivalent file that most assistants read. If someone uses another tool, move the text of each `CLAUDE.md` to an `AGENTS.md` in the same folder and leave `CLAUDE.md` with the single line `@AGENTS.md`. Do not confuse it with `.claude/agents/`, which holds subagents.

**Never committed:** passwords, tokens and personal data; virtual environments and build output; videos, datasets and CAD files; personal AI settings.

## 4. Anatomy of a subproject

```text
src/<subproject>/
├── CLAUDE.md      # rules that only apply here, and the contract
├── README.md      # how to install, build and run it
├── <name>Proposal.md  # the proposal presented to the team, if there is one
└── ...            # the code, in folders with descriptive names
```

Every subproject `CLAUDE.md` answers the same questions, in this order:

1. **What it does**, in two or three lines.
2. **Exceptions** to `projectRules.md`, if any (for example, the language), and which rules still apply.
3. **The contract:** inputs, outputs, units, and what happens when something fails.
4. **Structure:** what each folder inside contains.
5. **How to build, run and test it.**

Subproject rules:

- The name is short, lowercase and says what the part does: `vision`, `motion`, `gripper`. Not the name of a person, not `test1`.
- Parameters live in a configuration file or header of the subproject, never as loose numbers in the code.
- An Arduino sketch needs its `.ino` inside a folder with the same name: `src/motion/motion.ino`.
- Experiments and throwaway tests go in the author's branch. They reach `main` only once they have a place in this structure.

Subprojects:

| Subproject | What it does | Language | State |
|---|---|---|---|
| `src/vision/` | Detects the stones with a camera | Python + OpenCV | Proposed: `src/vision/visionProposal.md`. Code not uploaded yet |

## 5. How to add things

| I want to add... | Where | Steps |
|---|---|---|
| **A new subproject** | `src/<name>/` | 1. Agree the name with the team. 2. Write its `CLAUDE.md` with the five points of section 4, starting with the contract. 3. Add its `README.md`. 4. Add a row to the table of section 4. 5. Then the code |
| **Code to a subproject** | A folder inside it | Use an existing folder if the file belongs to it; otherwise create one with a descriptive name and add it to the structure list of that `CLAUDE.md` |
| **A test** | `tests/<subproject>/` | Same folder layout as the code it tests. Explain in the subproject `README.md` how to run it |
| **A document** | `docs/` or `docs/<subproject>/` | Whole repo: `docs/`. One subproject: its folder. File names in camelCase, like `projectRules.md` |
| **A tool** | `scripts/` | One job per script, with a comment at the top saying what it does and how to run it |
| **A dependency** | The subproject that needs it | Justify it (rule of `projectRules.md`), pin the version and write it in the subproject `README.md` |
| **A skill** | `.claude/skills/<name>/SKILL.md` | Only for a task the team repeats. Name in kebab-case. Mention it in the root `CLAUDE.md` |
| **A hook** | `.claude/settings.json` + `.claude/hooks/` | Only for a rule that must never fail. It affects everyone: agree it with the team first |
| **A subagent** | `.claude/agents/<name>.md` | Give it the minimum tools (read-only if it only reviews) |
| **A change to the contract** | The subproject `CLAUDE.md` and its code | Agree it with the people working on the subprojects that use it **before** changing the code |
| **A new top-level folder** | — | Team decision. Update this document in the same change |

When the structure changes, this document changes in the same branch. A structure that is not written here does not exist.

## 6. Branches and commits

The rules are in `projectRules.md`. What matters for the structure:

- Every file is its own commit (one file, at most 250 lines), so a new subproject is several commits. Commit in an order that leaves the repo working after each one: instructions and contract first, code after.
- Structure and AI setup affect everybody: they go in their own branch and are merged early, not inside the branch of a subproject.
- Commits are made by hand. AI assistants prepare the change and explain it; they do not commit, push or merge.
