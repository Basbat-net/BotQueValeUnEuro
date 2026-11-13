# CLAUDE.md — BotQueValeUnEuro

Shared instructions for everyone on the team who works on this repo with Claude.
Each subproject under `src/` has its own `CLAUDE.md` with the rules that only apply there.

## What this is

Code of the CREA team (UPM · ETSIDI) for **Eurobot 2027**: an autonomous robot.
The game rules are not in this repo; ask the person you are working with for the official PDF.

## Repository structure

How the repo is organised, what each folder contains and how to add new things:

@docs/repoStructure.md

Follow that document when creating files or folders. If something does not fit, ask before inventing a new place for it.

## Team rules

@projectRules.md

`projectRules.md` is the source of truth. If something here contradicts it, follow `projectRules.md` and say so.
A subproject may declare exceptions in its own `CLAUDE.md` (for example, the language); those exceptions only apply inside that folder.

## Git

Commits are made by hand by the person, never by AI.

- Do not run `git commit`, `git push`, `git pull`, `git merge`, `git rebase`, `git reset` or create branches.
- Read-only Git is fine: `status`, `log`, `diff`, `branch`.
- When a change is ready, explain it and give the person the exact commands to run, with the commit rules of `projectRules.md`.

For now this rule is only written here. It will be enforced by a hook in `.claude/` (not in the repo yet), and this section will then be shortened.

## How to work

- **Do not write code unless the person asks for it.** Research and explanations come first.
- **One subproject at a time.** Do not edit another subproject's folder without telling the person first.
- **Subprojects are black boxes.** They talk to each other only through a documented contract (inputs and outputs). Do not reach into the internals of another subproject, and do not change a contract without the team agreeing.
- **Explain what you write.** Every member must be able to defend their code. Comments should be written by the person whenever possible; if Claude writes them, the person reviews them.
- **Check before handing over.** Compile or run the code and say exactly what was tested and what was not.
- No parameter values hidden in the code: they go in the configuration of the subproject.
