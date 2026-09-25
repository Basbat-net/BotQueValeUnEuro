# BotQueValeUnEuro
Repositorio oficial del Crea para competiciones de robotica

COPY OF PROJECTRULES.MD, for updated rules please check projectRules.md file
# Project Rules
Last edited: 25-9-26 22:30pm by Baselga

## Repository Structure (placeholder for now)

```text
src/        # Main source code
tests/      # Tests
docs/       # Documentation
scripts/    # Utility scripts
```

## Rules

### SCHEMA BASIS
- The main language for code is English (its more token efficient for AIs)
- File structure must remain modular, folders must be utilized when necessary and names must be descriptive
- The only coding languages allowed are Arduino and c++, so all files must be uploaded as .ino or .cpp (or .h in the case of import headers)

### File structure
- The main loop execution must be kept to as small of a size as possible
- All code must be done inside self contained functions and/or class elements
- Comments must be frequent and explain behavior in a concise condensed way, they must be written by hand whenever possible
- Dependencies must be properly justified, and a file must not call more than 6 import files

### Variable assignation
- Variables must me declared with static typing, dynamic typing is forbidden
- Names must be written with camel notation (exampleOfVariableName) and have self explaining names (no randomVar123)
- Global variables are not allowed in .cpp files, and must be declared in proper .h or .env files
- Declarations must remain at the top of the context they are used in, and not be recycled besides from function invocation
- Recycling of variables is recommended when possible

### Memory allocation
- Use of pointers is forbidden under all circumstances
- Memory must be managed via either the garbage collector or by local instancing, no direct heap manipulation

### Function Declaration

## File limits
- A file must not contain more than 15 functions
- A function must not be longer than 150 lines
- Function names must be self explaining
- Usage of sets of parameters longer than 5 must be handled via hash maps or structures, avoid arrays as inputs whenever possible

## Behavior Limitations
- Recursive calls must ALWAYS have an invocation limit, infinite recursion must never happen
- Function nesting calls must never exceed two levels from the top
- For long running functions, the code should not be blocked for a not reasonable amount of time

### Classes
- Classes must always be declared at the top of the file
- Usage of private and protected is encouraged for functions that do not need public calling
- Each class must have a constructor
- Creation of the class must happen under declaration and should only happen once per execution
- Inheritance is to be avoided, if needed a class must not have more than two generations of children

### Data management
- Hash maps and dictionaries must be used whenever possible
- Matrices must be used only for numeric applications and never for data storage
- Esoteric storage uses like deques are allowed if they save up on runtime

### Error handling
- A code must NEVER use try, catch or any error handling exceptions as part of its runtime routine, they must only be used for recovery
- A code must never throw errors by design
- Compilation of all code before committing is mandatory, any pushes with coding errors will be revoked

### Git usage
- Commits are limited to 250 lines of code and must only have one file modified per commit
- Commit titles must be explaining, must use the proper release number and have detailed modifications in the description, with line number explanations whenever possible
- All commits must be done by hand (no AI commits ever), and must include at the end a specific sentence that will be updated each week for every scrum meeting
- All work must be done in separate branches, that are to be united for every release
- Merge conflicts must be dealt with in combination with the author of the conflicted previous line, no overwriting without consent
- For every release, the wiki corresponding to EACH file must me modified, and a file's wiki must not spend more than 3 weeks without any revision
- In the description, there must always be an Added: Changed: and Deleted: sections if needed
