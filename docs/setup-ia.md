---
up: "[[EUROBOT]]"
tipo: nota
area: proyectos
aliases:
  - Plan del setup de IA del equipo
---
# Plan del setup de IA del equipo

> Investigación y plan de Víctor con Claude, 2026-11-15. **No hay nada montado**: es para analizarlo y luego presentarlo al equipo.
> Concreta [[docs/propuesta-ia|la propuesta de IA]] (principios, IA local del Framework, otras herramientas): aquí van las piezas que ya existen y las que hay que crear, con el orden para montarlas.
> Datos sacados el 2026-11-15 de la documentación oficial de Claude Code (versión 2.1.325) y de los repositorios de cada herramienta. Lo marcado **(por comprobar)** no se ha probado.

## 1. Punto de partida

**Ya en `main`** (PR #2, 2026-11-15): `CLAUDE.md` en la raíz y en `src/vision/`, `docs/repoStructure.md`, `.gitignore` y `.claude/settings.json`, que trae:

- `permissions.deny` para los comandos de Git que escriben;
- tres hooks: `blockGitWrites.py` bloquea commit, push, merge y demás; `checkFileLimits.py` avisa si hay más de 15 funciones en un archivo o más de 150 líneas en una función; `ensureTeamPlugins.py` instala los plugins del equipo;
- el plugin `claude-md-management`.

**Falta:** skills (la `rules-check` local se descartó por pobre), subagentes, MCP y una red de seguridad que no dependa de la IA (Git y GitHub).

## 2. Criterios: por qué no se instala todo

1. **Cada archivo cuesta un commit a mano** (1 archivo, ≤250 líneas). Pocas piezas, y que cada una ahorre trabajo de verdad.
2. **El contexto se paga en todas las sesiones de todos.** La descripción de cada skill y de cada subagente se carga en cada turno. Lo que use un solo departamento va en el ordenador de esa persona o dentro de un subagente: los MCP declarados en un subagente (`mcpServers`) no entran en la conversación principal. Las herramientas de un MCP se cargan solo cuando hacen falta (*tool search*, activado por defecto).
3. **Nada que haga commits.** Se descartan las piezas que commitean, aunque sean oficiales.
4. **El repo es público:** sin claves. Los servicios con cuenta van con OAuth (cada uno inicia sesión con la suya) o con variables de entorno que nunca se suben.
5. **Lo que no puede fallar no puede depender de la IA:** `pre-commit` y GitHub Actions, para que valga también para quien no la use.
6. **Lo que no se use, se quita.** En cada retrospectiva, `/skill-doctor` dice qué skills se usan y cuánto contexto ocupan.

## 3. Lo que ya existe fuera

### 3.1 Para todo el equipo

| Herramienta | Qué da | Cómo | Notas |
|---|---|---|---|
| **Notion MCP** (oficial) | Leer y actualizar el tablero desde Claude | `.mcp.json` con `https://mcp.notion.com/mcp`; cada uno entra con `/mcp` | Sin claves en el repo. Claude pide permiso a cada persona antes de usar un servidor del repo |
| **`gh`** (CLI oficial de GitHub) | Issues, PR, diffs y estado de las Actions | Instalado en cada ordenador | Mejor que el MCP de GitHub: no ocupa contexto. Añadir `gh pr merge` al `deny` |
| **Skills que ya trae Claude Code** | `/code-review` (revisa los cambios de la rama), `/security-review`, `/simplify`, `/doctor`, `/skill-doctor` | Nada que instalar | `/code-review` antes de abrir un PR, como primera revisión |
| **Context7** (plugin oficial `context7`) | Documentación al día de las librerías, para que Claude no use APIs viejas | `enabledPlugins` | Comprobar si tiene Arduino-ESP32, FreeRTOS y OpenCV **(por comprobar)**. Antes hay que arreglar `ensureTeamPlugins.py` (§4.4) |

### 3.2 Para el firmware (cuando se decida la placa)

| Herramienta | Qué da | Estado | Veredicto |
|---|---|---|---|
| **Wokwi MCP** (`wokwi-cli mcp`) + Wokwi CI | Simular el ESP32 con FreeRTOS sin placa y lanzar tests que esperan un texto por el puerto serie; tiene Action de GitHub | Oficial de Wokwi, **experimental**; token por persona (`WOKWI_CLI_TOKEN`); límites del plan gratis **(por comprobar)** | **Sí.** Hay un robot para 8 personas. Probarlo antes con los ejercicios de mutex de `Practica/` |
| **arduino-mcp-server** (hardware-mcp) | Compilar, subir, abrir el puerto serie y esperar un texto (`serial_expect`); avisa de pines peligrosos del ESP32 (flash, arranque, solo entrada) | MIT, 26 estrellas, sin releases, Node 20+ | **A prueba**, dentro del subagente `firmware-tester` |
| **platformio.mcp** | 44 herramientas: build, flash, tests Unity, `cppcheck` y `clang-tidy`, descifra *backtraces* del ESP32, informe de memoria | MIT, 10 estrellas; envía analítica (se apaga con `DO_NOT_TRACK=1`) | Solo si el equipo usa PlatformIO |
| **`clangd-lsp`** (plugin oficial) | Claude ve los errores de compilación nada más editar y salta a definiciones | Hay que instalar `clangd` y generar `compile_commands.json` (`arduino-cli compile --only-compilation-database`). `clangd` no entiende algunas opciones del compilador del ESP32 y hay que quitarlas con un `.clangd` **(por probar)** | **Opcional por persona**: si se activa para todos, a quien no tenga `clangd` le sale un error |
| **`pyright-lsp`** (plugin oficial) | Lo mismo para Python (visión) | Hay que instalar `pyright` | Opcional por persona |

### 3.3 Para electrónica, mecánica y diseño (en el ordenador de cada uno)

| Herramienta | Qué da | Veredicto |
|---|---|---|
| **KiCad MCP** (`mixelpixx/KiCAD-MCP-Server`, `oaslananka/kicad-mcp-pro`, MIT) | Revisión de esquema y PCB (ERC, DRC, fabricación), lista de materiales | Si electrónica usa KiCad. Ninguno se presenta como revisión definitiva, solo como primera pasada |
| **SolidWorks MCP** (varios, por la API COM) | Crear piezas desde Claude | Solo Windows y con licencia; proyectos jóvenes y uno de pago. Experimento personal, no de equipo |
| **build123d MCP / FreeCAD MCP** (MIT) | CAD por código: piezas sencillas (soportes, separadores) que se exportan a STEP y se abren en SolidWorks | Para quien quiera probarlo. Funciona en Linux |
| **draw.io MCP** (oficial, `mcp.draw.io`) | Diagramas editables; acepta Mermaid | Personal. En el repo, mejor **Mermaid dentro del `.md`**: GitHub lo dibuja y no hace falta herramienta (la rama `joel` tiene diagramas en SVG) |
| **Skills de documentos de Claude** (Word, PowerPoint, PDF; ya en claude.ai) | Dossier de patrocinio, presentaciones de reunión, póster A1 `[Gen E]` | Para gestión y comunicación, sin montar nada |

### 3.4 Para quien mantenga el setup

| Plugin oficial | Para qué |
|---|---|
| `claude-code-setup` | Analiza el repo y recomienda hooks, skills, MCP y subagentes: pasarlo una vez y compararlo con este plan |
| `skill-creator` | Crear skills y medir si funcionan (casos de prueba) |
| `hookify` | Escribir hooks a partir de reglas en texto |
| `learning-output-style` | Claude deja huecos para que escribas tú las partes clave: encaja con «tienes que saber defender tu código». Recomendable para cada persona |

### 3.5 Descartado

| Herramienta | Por qué no |
|---|---|
| `commit-commands`, `ralph-loop` | Hacen commits, o trabajan en bucle sin que nadie revise |
| `superpowers` | Es buena (lluvia de ideas, planes, depuración paso a paso), pero sus skills trabajan con ramas, *worktrees* y cierres de rama. Para quien quiera usarla en su ordenador, no para todo el equipo |
| Code Review de Anthropic en los PR | Solo con planes Team o Enterprise |
| `claude-code-action` (Claude en GitHub Actions) | Necesita el token de la suscripción de una persona (va con su cuota) o una API de pago. Más adelante, solo para comentar PR y si el tech lead lo quiere |
| MCP de GitHub | `gh` hace lo mismo sin ocupar contexto |
| Skills de ESP32 de terceros (`giltal`, `Jeffallan`, `EricSun787`) | Pocas estrellas y sin licencia clara. Se leen como referencia para escribir las nuestras |

**Otros equipos de Eurobot** con código abierto: `DIT-ROBOTICS/Eurobot-2026-Main` (estrategia con árboles de comportamiento y un robot rival simulado), `ChampiCircuits/champi_robot_ros` (ROS 2 y simulador), `memristor/mep3` y `VRAC-team/webots_eurobot_example` (Webots con un rival de prueba). Sirven para sacar ideas de estrategia y simulación. Si se reutiliza código, hay que respetar su licencia. Copiar el robot de otro equipo descalifica `[Gen F.2, H.4]`.

## 4. Lo que hay que crear (ideas propias)

### 4.1 La pieza central: `scripts/checkRules.py`

Un único comprobador de `projectRules.md`, usado desde cuatro sitios: el hook tras editar, la skill `rules-check`, el `pre-commit` y la Action. Así la norma se comprueba igual con IA y sin ella.

- **Comprueba lo que se puede medir:** punteros (`*` y `->` en declaraciones, `new` y `malloc`), globales en `.cpp`, más de 6 `#include`, `try`/`catch`, más de 15 funciones por archivo, más de 150 líneas por función, más de 5 parámetros, nombres que no son `camelCase` y clases que no están al principio del archivo.
- **Reutiliza** `listPythonFunctions` y `listCppFunctions` de `.claude/hooks/checkFileLimits.py`; ese hook acaba llamando al script.
- **Salida:** texto para personas, o JSON (`--json`) para la skill y la Action. Código de salida 1 si algo incumple.
- **Excepciones por subproyecto** (por ejemplo, Python en `src/vision/`): las lee de una tabla del propio script, para no tener que interpretar los `CLAUDE.md`.

### 4.2 Skills de equipo (`.claude/skills/`), seis como máximo al principio

| Skill | Qué hace | Detalles |
|---|---|---|
| `commit-prep` | Reparte lo pendiente en commits de 1 archivo y ≤250 líneas, pasa `checkRules.py` a cada uno y redacta el título (con el número de release) y la descripción (`Added:`, `Changed:`, `Deleted:`, con números de línea, y la frase semanal). **Da los comandos; los lanza la persona** | Solo se ejecuta si la llama la persona (`disable-model-invocation: true`). Recibe `git status --short` y `git diff --stat` al empezar (`` !`...` ``, con `|| true` para que no se corte). La frase semanal y la release las pregunta, o las lee de la última etiqueta si el equipo la usa |
| `rules-check` (nueva) | Lo que dice `checkRules.py`, más lo que necesita criterio: nombres que se explican solos, recursión con límite, bloqueos largos, llamadas anidadas más de dos niveles | Sustituye a la descartada. Solo lectura |
| `defend` | Antes de un commit, hace 5 preguntas sobre el cambio que su autor tiene que saber contestar (qué hace, por qué así, qué pasa si falla, cómo se probó, qué norma aplica) y explica las que no sepa | Nace de la norma «cada miembro tiene que poder defender su código». No toca archivos |
| `proposal` | Guía una propuesta: problema, opciones, criterios, coste, riesgos, norma citada y qué pide a otros departamentos | Plantilla en un archivo de la skill, con `src/vision/visionProposal.md` de modelo. Se guarda donde dice `docs/repoStructure.md` (en el subproyecto o en `docs/`) |
| `new-subproject` | Crea `src/<nombre>/` con su `CLAUDE.md` (los 5 puntos, empezando por el contrato) y su `README.md`, y añade la fila a `docs/repoStructure.md` | Solo si la llama la persona |
| `build` | Compila el subproyecto con `arduino-cli`. Si se le pide, sube a la placa y lee el puerto serie | Espera a decidir placa y herramienta. Propuesta: un `sketch.yaml` por sketch, que fija las versiones del core del ESP32 y de las librerías, como el `requirements.txt` de visión **(por comprobar)** |

**Más adelante:** `wiki-update` (borrador de la wiki de cada archivo cambiado y lista de wikis con más de 3 semanas sin revisar), `weekly` (borrador del scrum a partir de `git log` y Notion), `homologation-check` (repasa `[Gen F]` con las medidas del robot: perímetro, altura, seta, cordón, soporte de baliza, hueco para pegatinas) y `match-debrief` (convierte el registro de un partido de prueba en una línea de tiempo con lo que falló).

### 4.3 Subagentes (`.claude/agents/`), todos de solo lectura

| Subagente | Modelo | Qué hace | Detalles |
|---|---|---|---|
| `referee` | `haiku` (si se equivoca, `sonnet`) | ¿Es legal? ¿Cuánto puntúa? Cita la sección (`[2027 E.1]`, `[Gen F.3]`). Si la norma no lo aclara, redacta la pregunta para la FAQ | Lee `docs/gameRules.md` (§4.8) y la FAQ oficial. Con `memory: project` guarda lo que ya respondieron los árbitros en `.claude/agent-memory/referee/`, que viaja por Git |
| `rules-reviewer` | `haiku` | Revisa una rama entera contra las normas antes de la release | Pasa `checkRules.py` a todos los archivos cambiados y resume |
| `concurrency-reviewer` | `opus`, esfuerzo alto | Mutex, interbloqueos, interrupciones, inversión de prioridad y llamadas que bloquean en FreeRTOS | Lo que más cuesta ver a mano y más falla en un partido |
| `hardware-reviewer` | `sonnet` | Cruza el código con un mapa de pines único: pines de arranque y de solo entrada del ESP32, pines repetidos, niveles de tensión | Necesita que electrónica mantenga un `pinMap.h` común (dónde va, por decidir) |
| `strategy-analyst` | `sonnet` | Compara estrategias por puntos y por tiempo (100 s, ataque desde el segundo 85) con `scoreCalc.py` | Para quien no programa |
| `firmware-tester` | `sonnet` | Compila, simula en Wokwi o sube a la placa y comprueba el puerto serie | El único con MCP propio (`mcpServers`): sus herramientas no cargan en las sesiones de los demás. Fase 4 |

### 4.4 Hooks y permisos

| Cambio | Cómo | Para qué |
|---|---|---|
| Norma completa al editar | `checkFileLimits.py` pasa a llamar a `checkRules.py` | Claude corrige antes de entregar |
| Proteger `projectRules.md` y los contratos (`visionTypes.py`) | Regla `ask` en `permissions` | La persona confirma cada edición; no hace falta script |
| Cerrar los huecos de `blockGitWrites.py` | `git branch <nombre>`, `eval "git ..."` | Huecos conocidos desde el 2026-11-15 |
| Aviso al abrir en `main` | `SessionStart`: «estás en `main`; crea tu rama a mano» | Las normas piden una rama por tarea |
| Compilar al terminar | `Stop`: solo si cambió algún `.ino`, `.cpp` o `.h`. Si falla, Claude sigue para arreglarlo, una sola vez (`stop_hook_active` evita el bucle); sin `arduino-cli`, no hace nada | «Compilation of all code before committing is mandatory» |
| Documento vivo | `Stop`: si cambió `src/` y no el documento vivo (nombre por decidir), lo recuerda | La idea de [[docs/vision-codigo\|vision-codigo]] §9 |
| **Arreglar `ensureTeamPlugins.py`** | Hoy falla con dos plugins del mismo marketplace | **Antes** de activar un segundo plugin (Context7) |

**Normas por lenguaje:** `.claude/rules/cpp.md` y `.claude/rules/python.md` con `paths:` (por ejemplo, `"**/*.{ino,cpp,h}"`). Solo se cargan al tocar archivos de ese lenguaje: lo que vale para todo el C++ del robot, sin engordar el `CLAUDE.md` de la raíz. Por ejemplo, referencias en vez de punteros, o evitar `String` de Arduino en bucles porque usa el heap.

### 4.5 MCP del equipo: `.mcp.json`

```json
{
  "mcpServers": {
    "notion": { "type": "http", "url": "https://mcp.notion.com/mcp" }
  }
}
```

Context7 entra como plugin (§3.1), no aquí. El resto (Wokwi, arduino-mcp-server, KiCad, draw.io, build123d) va en el `README.md` como opcional, con el comando `claude mcp add ...` de cada uno. Los tokens personales van en variables de entorno (`${WOKWI_CLI_TOKEN}`), nunca en el repo.

### 4.6 Git y GitHub (valen para todos, usen IA o no)

| Pieza | Qué hace | Notas |
|---|---|---|
| `.githooks/pre-commit` | Rechaza commits de más de 1 archivo o de más de 250 líneas, pasa `checkRules.py` y busca claves o tokens | Se activa una vez por clon: `git config core.hooksPath .githooks`. Busca `python3`, `python` o `py`, como `settings.json` |
| `.githooks/commit-msg` | Comprueba que hay al menos una sección `Added:`, `Changed:` o `Deleted:` y la frase semanal | Se salta con `--no-verify`: es una ayuda, no un muro |
| `.github/workflows/rules.yml` | En cada PR: `checkRules.py` sobre lo cambiado y que cada commit sea de 1 archivo y ≤250 líneas | No se puede saltar |
| `.github/workflows/compile.yml` | Compila los sketches con `arduino/compile-sketches` e informa de la memoria usada | El core del ESP32 tarda en instalarse y puede llenar el disco del runner. Después, un test de Wokwi CI |
| Protección de `main` | Ruleset: PR obligatorio con 1 aprobación y las dos Actions en verde | La configura el dueño del repo; gratis en repos públicos |
| `.github/pull_request_template.md` | Lista: compilado, wiki al día, contrato sin tocar (o acordado), probado en placa o en simulador | Ordena la revisión |

### 4.7 Para estrategia: `scripts/scoreCalc.py`

Calculadora de puntos y tiempos con la tabla de `[2027 E, F]`. Recibe un plan de partido (qué se construye, nivel del Grial, retorno, SIMAs, bolas) y devuelve los puntos y si cabe en 100 s con los tiempos estimados de cada acción. La usa `strategy-analyst`. La misma lógica se puede publicar como página interactiva para mecánica y estrategia, sin instalar nada. Más adelante (fase 6): un simulador 2D sencillo de la mesa para probar estrategias contra un rival de prueba, como el de Webots de VRAC.

### 4.8 Normativa dentro del repo: `docs/gameRules.md`

Resumen en inglés de [[docs/normativa-resumen|la normativa]] con la sección de cada regla y el enlace a los PDF oficiales. Sin él, `referee` y cualquier Claude del equipo citan de memoria. Hoy el `CLAUDE.md` del repo dice que pidan el PDF a la persona; habría que cambiar esa línea.

## 5. Qué le sirve a cada departamento

| Departamento | Con lo de este plan |
|---|---|
| **Programación** | `commit-prep`, `rules-check`, `defend`, `build`, `/code-review`; `concurrency-reviewer`, `firmware-tester` y Wokwi; `clangd-lsp` y Context7 |
| **Electrónica** | `hardware-reviewer` con el `pinMap.h`; KiCad MCP si usan KiCad; `homologation-check` (seta, fusible, batería `[Gen F.4]`) |
| **Mecánica y diseño** | `referee` (medidas y envolvente `[Gen F.3]`); `proposal`; CAD por código para piezas sencillas; cálculos de motores y reductoras en el chat |
| **Estrategia** | `referee`, `strategy-analyst`, `scoreCalc.py` y, más adelante, el simulador |
| **Gestión** (PM, Scrum Master) | Notion MCP, `weekly`, skills de documentos para el dossier de patrocinio y el póster |

## 6. Cómo quedaría el repo

```text
BotQueValeUnEuro/
├── .mcp.json                     # Notion
├── .claude/
│   ├── settings.json             # + reglas ask, hooks nuevos, Context7
│   ├── hooks/                    # los 3 de hoy + aviso de rama + comprobaciones al terminar
│   ├── rules/                    # cpp.md, python.md
│   ├── skills/                   # commit-prep, rules-check, defend, proposal, new-subproject, build
│   ├── agents/                   # referee, rules-reviewer, concurrency-reviewer, hardware-reviewer, strategy-analyst, firmware-tester
│   └── agent-memory/referee/     # lo que ya respondió la FAQ (lo escribe el subagente)
├── .githooks/                    # pre-commit, commit-msg
├── .github/                      # workflows/rules.yml, workflows/compile.yml, pull_request_template.md
├── scripts/                      # checkRules.py, scoreCalc.py
└── docs/                         # gameRules.md y el documento vivo (nombre por decidir)
```

Son unos 25 archivos, o sea, 25 commits a mano repartidos en las fases de §7. `scripts/`, `.githooks/`, `.github/` y `.mcp.json` entran en la excepción de [[docs/propuesta-ia|propuesta-ia]] §8 (archivos que no son Arduino ni C++), que tiene que aceptar el tech lead.

## 7. Fases

| Fase | Qué | Depende de |
|---|---|---|
| 0 | Analizar este plan; encuesta al equipo (§8) | Víctor |
| 1 | `checkRules.py` → hook que lo usa → `rules-check` → `commit-prep` → `.githooks/` | Nada: es lo que más trabajo quita |
| 2 | `rules.yml`, `compile.yml`, plantilla de PR, protección de `main` | Tech lead |
| 3 | `docs/gameRules.md`, `referee`, `scoreCalc.py`, `strategy-analyst`, `.mcp.json` con Notion, `proposal`, `defend` | Enlace de Notion |
| 4 | `build`, `sketch.yaml`, `clangd-lsp`, Wokwi, `concurrency-reviewer`, `hardware-reviewer`, `firmware-tester` | Placa y herramienta de compilación |
| 5 | Por departamento: KiCad, draw.io, CAD por código; `wiki-update`, `weekly`, `new-subproject` | Encuesta |
| 6 | Competición: `homologation-check`, `match-debrief`, simulador | Robot montado |

Cada pieza: Claude la prepara cuando Víctor la pide, se prueba en local y Víctor hace el commit.

## 8. Preguntas para el equipo

Bloquean algunas fases, no el plan.

1. ¿Qué usa cada uno (Claude Code de terminal, la extensión de VS Code, Copilot, Cursor, nada)? ¿Quién tiene suscripción?
2. ¿Qué placa y cómo se compila: ESP32 con `arduino-cli`, o PlatformIO? PlatformIO fija versiones y trae tests y análisis estático, pero `projectRules.md` habla de `.ino`.
3. ¿Con qué programa hace electrónica los esquemas y las PCB?
4. ¿Cuál es el enlace del tablero de Notion? ¿Quién puede editarlo desde la IA?
5. ¿Acepta el tech lead `scripts/`, `.githooks/`, `.github/` y `.mcp.json`, y Python en ellos? ¿Protege `main`? ¿Quiere revisión de PR con Claude?
6. ¿Dónde vive la wiki: la de GitHub o `docs/`?
7. ¿Se guardan la frase semanal y el número de release en algún sitio que pueda leer `commit-prep` (una etiqueta de Git, un archivo)?

## 9. Cómo se comprueba cada pieza

- **Script y hooks:** pasarles por la entrada el JSON de una edición con un archivo que incumple (un puntero, 16 funciones) y ver el código de salida 2 y el mensaje. Repetirlo en Windows con Git Bash.
- **Skills y subagentes:** usarlos en una sesión real sobre `prueba_ruedasomni.ino` (rama `victorm`) y sobre `src/vision/`. `/doctor` y `/context` dicen si se cargan y cuánto ocupan.
- **MCP:** `/mcp` muestra Notion conectado después de iniciar sesión; leer una tarea del tablero.
- **Git y CI:** el `pre-commit` tiene que rechazar un commit de 2 archivos, y un PR de prueba con un puntero tiene que poner `rules.yml` en rojo.
- **Un compañero clona el repo y lo prueba:** nada puede depender de la carpeta privada de Víctor.

## 10. Riesgos y lo que falta comprobar

- **Herramientas jóvenes:** arduino-mcp-server (26 estrellas) y platformio.mcp (10) pueden cambiar o abandonarse. Hay que fijar la versión (`npx -y arduino-mcp-server@<versión>`) y que nada importante dependa solo de ellas: la base siempre es `arduino-cli`.
- **Plugins y MCP ejecutan código en el ordenador de cada uno:** solo de marketplaces de confianza, como ya dice `docs/repoStructure.md`.
- **Windows:** los scripts tienen que ir en Python con la misma búsqueda de `python3`, `python` o `py` que ya usa `settings.json`.
- **Por comprobar:** qué librerías nuestras tiene Context7; límites del plan gratis de Wokwi CI; si arduino-mcp-server y platformio.mcp funcionan en Windows; `clangd` con el compilador del ESP32; perfiles de `sketch.yaml` con el core del ESP32; si los hooks saltan en Copilot y Cursor ([[docs/propuesta-ia|propuesta-ia]] §11).

## Fuentes

- Claude Code: [skills](https://code.claude.com/docs/en/skills.md) · [subagentes](https://code.claude.com/docs/en/sub-agents.md) · [hooks](https://code.claude.com/docs/en/hooks.md) · [MCP](https://code.claude.com/docs/en/mcp.md) · [memoria y `.claude/rules/`](https://code.claude.com/docs/en/memory.md) · [plugins de lenguaje](https://code.claude.com/docs/en/plugins/code-intelligence.md) · [marketplaces de Anthropic](https://code.claude.com/docs/en/plugins/anthropic-marketplaces.md) · [qué incluye cada plan](https://code.claude.com/docs/en/feature-availability.md) · [GitHub Actions](https://code.claude.com/docs/en/github-actions.md)
- Catálogo oficial de plugins: [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)
- Firmware: [arduino-mcp-server](https://github.com/hardware-mcp/arduino-mcp-server) · [platformio.mcp](https://github.com/powerdragonfire/platformio.mcp) · [Wokwi MCP](https://docs.wokwi.com/wokwi-ci/mcp-support) · [Wokwi CI](https://docs.wokwi.com/wokwi-ci/getting-started) · [arduino/compile-sketches](https://github.com/arduino/compile-sketches) · [arduino-lint-action](https://github.com/arduino/arduino-lint-action)
- Gestión y documentación: [Notion MCP](https://developers.notion.com/docs/get-started-with-mcp) · [GitHub MCP](https://github.com/github/github-mcp-server) · [Context7 en Claude Code](https://context7.com/docs/clients/claude-code) · [draw.io MCP](https://github.com/jgraph/drawio-mcp)
- Electrónica y CAD: [KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) · [kicad-mcp-pro](https://github.com/oaslananka/kicad-mcp-pro) · [SolidworksMCP-python](https://github.com/andrewbartels1/SolidworksMCP-python) · [freecad-mcp](https://github.com/neka-nat/freecad-mcp) · [build123d-mcp](https://github.com/pzfreo/build123d-mcp)
- Skills de referencia: [giltal/claude-skills](https://github.com/giltal/claude-skills) · [Jeffallan, embedded-systems](https://github.com/Jeffallan/claude-skills/blob/main/skills/embedded-systems/SKILL.md) · [superpowers](https://claude.com/marketplace/plugins/superpowers)
- Otros equipos: [DIT-ROBOTICS/Eurobot-2026-Main](https://github.com/DIT-ROBOTICS/Eurobot-2026-Main) · [ChampiCircuits/champi_robot_ros](https://github.com/ChampiCircuits/champi_robot_ros) · [VRAC-team/webots_eurobot_example](https://github.com/VRAC-team/webots_eurobot_example)
