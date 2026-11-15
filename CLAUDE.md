# CLAUDE.md — BotQueValeUnEuro

Shared instructions for everyone on the team who works on this repo with Claude.
Each subproject under `src/` has its own `CLAUDE.md` with the rules that only apply there; read it before touching that folder.

## What this is

Code of the CREA team (UPM · ETSIDI) for **Eurobot 2027**: an autonomous robot.
The game rules are not in this repo; ask the person you are working with for the official PDF. Do not state a game rule from memory.

## Repository structure

How the repo is organised, what each folder contains and how to add new things:

@docs/repoStructure.md

Follow that document when creating files or folders. If something does not fit, ask before inventing a new place for it.

## Team rules

@projectRules.md

`projectRules.md` is the source of truth. If something here contradicts it, follow `projectRules.md` and say so.
A subproject may declare exceptions in its own `CLAUDE.md` (for example, the language); those exceptions only apply inside that folder.

## Language

- Code, comments, file names and documents in the repo: English.
- Answers to the person: the language they write in.

## Git

Commits are made by hand by the person, never by AI.

- Do not commit, push, pull, merge, rebase, reset, revert, cherry-pick or create branches. A hook blocks these commands; if it stops one, do not look for another way to run it.
- Read-only Git is fine: `status`, `log`, `diff`, `branch`.
- When a change is ready, explain it and give the person the exact commands to run, following the commit rules of `projectRules.md`: one file per commit, at most 250 lines, compiled or run first.
- Before a commit, offer to review the file with the `/rules-check` skill.

## How to work

- **Do not write code unless the person asks for it.** Research and explanations come first.
- **One subproject at a time.** Do not edit another subproject's folder without telling the person first.
- **Subprojects are black boxes.** They talk to each other only through a documented contract (inputs and outputs). Do not reach into the internals of another subproject, and do not change a contract without the team agreeing.
- **Explain what you write.** Every member must be able to defend their code. Comments should be written by the person whenever possible; if Claude writes them, the person reviews them.
- **Check before handing over.** Compile or run the code and say exactly what was tested and what was not.
- **No parameter values hidden in the code:** they go in the configuration of the subproject.
- **When changing a `CLAUDE.md`,** review it with the `claude-md-improver` skill.
- **No secrets or personal data** in any file of the repo: it is public.
