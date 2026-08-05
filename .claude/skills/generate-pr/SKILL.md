---
name: generate-pr
description: Genera el cuerpo (body) de una Pull Request analizando el diff de la rama actual contra la base, troceado por dominios y sin alucinar. Úsala cuando el usuario pida crear, redactar o preparar una PR / pull request, generar el texto de un PR, o invoque el comando /generate-pr.
license: MIT
compatibility: Requiere Git y PowerShell 7+. La integración opcional con GitHub usa la CLI `gh`.
metadata:
  author: joiabagur-pv
  version: "1.1"
---

# generate-pr — Generador de Pull Requests por chunks

Produce un cuerpo de PR **preciso, técnico y verificable** a partir del diff real
de la rama. La arquitectura separa tres fases para minimizar alucinaciones y
consumo de contexto, precedidas de una decisión que toma siempre el usuario:

| Fase | Responsable | Qué hace |
|---|---|---|
| **0 · Base de la PR** | **el usuario** | Decide contra qué rama se compara. Nunca se asume: si no la ha indicado, se le pregunta. |
| **A · Recopilación** | `scripts/pr-context.ps1` (determinista, sin IA) | Refresca la base, calcula ramas/commits/stats y **trocea el diff por dominios** en `.pr/<rama>/`. |
| **B · Análisis** | tú, chunk a chunk | Lees `manifest.json` y analizas **cada chunk por separado**. |
| **C · Redacción** | tú, con la plantilla del repo | Rellenas la plantilla y escribes `<outDir>/PR_body_tmp.md`. |

> Cada rama tiene su carpeta `.pr/<rama>/` (campo `outDir` del `manifest.json`).
> En este SKILL `<outDir>` se refiere a esa ruta — no a `.pr/` a secas.

> **Regla de oro:** describe **solo** lo que aparece en los chunks. Nunca inventes
> cambios, archivos ni efectos. Si algo no se puede verificar en el diff, márcalo
> como `UNKNOWN` o deja el ítem del checklist sin marcar. Ver
> `references/pr-standards.md`.

Los archivos de apoyo están **junto a este SKILL.md**: `scripts/`, `config/`,
`templates/`, `references/`. Carga los `references/` **solo cuando los necesites**
(divulgación progresiva) — no los leas todos de golpe.

---

## Paso 0 — Contexto del repo

`joiabagur-pv` es un **monorepo**: `backend/` (.NET 10 / EF Core / PostgreSQL),
`frontend/` (React 19 + Vite + Metronic), `ai-service/` (microservicio Python
`jbg_ai`, FastAPI), `terraform/` y `.github/workflows/`.

Lee `openspec/project.md` para las convenciones (stack, capas, reglas de negocio);
`CLAUDE.md` y `AGENTS.md` están vacíos en este repo, no los uses como contexto.
Si la rama tiene relación con un change OpenSpec, ojea `openspec/changes/<slug>/`
(`proposal.md`, `tasks.md`) para el WHY, y `Documentos/Historias/` si el change
cita una HU. No leas el código completo: el diff es la fuente de verdad de *qué*
cambió.

## Paso 1 — Confirmar la rama base (obligatorio, antes de ejecutar nada)

**La rama base nunca se da por sentada.** Si quien invoca la skill no la ha
indicado explícitamente (argumento del comando o petición en el chat),
**pregúntasela antes de ejecutar el script.**

Para que la pregunta sea útil, dale el contexto que necesita para decidir:

- la **rama actual**, que será el origen de la PR (`git rev-parse --abbrev-ref HEAD`);
- la **base sugerida** por el repo (`git rev-parse --abbrev-ref origin/HEAD`),
  presentada como sugerencia, no como decisión tomada;
- las **candidatas** (`git branch -r`), excluyendo la rama actual.

No continúes hasta tener respuesta. Es la única decisión de la skill que cambia
por completo el contenido de la PR, y no es reversible una vez publicada.

## Paso 2 — Fase A: recopilar contexto (script)

Ejecuta el script de esta skill desde la raíz del repo, **siempre con la base
que te haya confirmado el usuario**:

```powershell
pwsh <skill-dir>/scripts/pr-context.ps1 -BaseBranch <rama>
```

Si lo lanzas sin `-BaseBranch`, el script se detiene con código 2 sin generar
nada y lista las candidatas: eso significa que te has saltado el Paso 1. Vuelve
a él y pregunta. El flag `-AutoBase` existe solo para uso desatendido (CI); **no
lo uses en una sesión interactiva** — equivaldría a decidir por el usuario.

`<skill-dir>` es la carpeta que contiene este SKILL.md. La skill está replicada en
los cinco harnesses del repo (`.agent/`, `.claude/`, `.codex/`, `.cursor/` y
`.opencode/skills/generate-pr/`); usa la copia de tu entorno. Acepta además
`-NoFetch` para uso offline.

Por defecto el script ejecuta `git fetch origin <base>` para comparar contra una
base actualizada (fail-soft: si no hay red, avisa y continúa con la copia local).

El script escribe en `.pr/<rama>/`: `manifest.json`, `summary.md` y
`chunks/NN-<dominio>.diff`, y poda las carpetas de ramas que ya no existen.
**Toma la ruta exacta de su salida en consola (`outDir`)** — la necesitas en las
fases siguientes.

**Manejo de casos límite** (vienen marcados en `manifest.json`):
- `empty: true` → informa el motivo (`reason`) al usuario y **detente**. No hay PR que redactar.
- `hasUncommitted: true` → avisa al usuario: hay cambios sin commitear que **no** entran en la PR.

## Paso 3 — Fase B: analizar los chunks

1. Lee `<outDir>/manifest.json` (su campo `outDir` confirma la ruta): ramas,
   commits, stats, lista de dominios y chunks.
2. Resume los commits → carga `references/summarize-commits.md`.
3. **Para cada chunk** del manifiesto, **uno a uno**:
   - Lee el archivo `.diff` de ese chunk (y solo ese).
   - Aplica `references/analyze-diff.md` para extraer intención, impacto y notas.
   - Si el chunk toca auth, contratos de API, modelos de datos o variables de
     entorno, carga además `references/breaking-and-risk.md`.
   - Si el chunk toca infra, Docker, deps o config, carga
     `references/deployment-impact.md`.
   - Si un chunk viene `truncated: true`, dilo explícitamente: el análisis de ese
     archivo se basa en cabeceras de hunk, no en el diff completo.

Mantén una nota de trabajo por dominio. **No cargues todos los `.diff` a la vez.**

## Paso 4 — Fase C: redactar el cuerpo

1. Usa la plantilla `templates/pr-template.base.md` (única plantilla del repo).
2. Redacta el título → `references/pr-title.md`.
3. Rellena cada sección de la plantilla con tus notas de la Fase B. Reglas en
   `references/pr-standards.md` (lenguaje técnico, sin marketing, con nombres
   reales de archivos/funciones).
4. Marca el checklist **solo** con lo verificable desde el diff.
5. Escribe el resultado en `<outDir>/PR_body_tmp.md`.

## Paso 5 — Awareness entre componentes

Si `manifest.json` lista dominios de **más de un componente** (`backend-*`,
`frontend-*`, `ai-service` / `ai-contracts`, `infra`), carga
`references/cross-component.md`: cubre acoplamiento de contratos, orden de
despliegue y coordinación con el change de OpenSpec.

## Paso 6 — Cierre y GitHub CLI (opcional)

1. Muestra en el chat un resumen: título propuesto, dominios cubiertos, riesgos y
   breaking changes detectados, ruta del archivo.
2. **Pregunta** al usuario si quiere crear la PR. Solo si acepta:
   ```bash
   gh pr create --base <baseBranch> --head <currentBranch> --assignee @me \
     --title "<título>" --body-file <outDir>/PR_body_tmp.md
   ```
   `--assignee @me` da visibilidad de responsable. No se gestionan reviewers: los
   solicita CODEOWNERS por rutas. Si `gh` no está instalado o no hay remoto en
   GitHub, indícalo y deja el archivo para uso manual. **Nunca** crees la PR sin
   confirmación.

---

## Guardarraíles

- **La rama base nunca se asume**: si el usuario no la ha indicado, se pregunta
  antes de ejecutar el script. Tampoco se resuelve con `-AutoBase` en una sesión
  interactiva.
- Cero alucinación: cada afirmación del body apunta a evidencia de un chunk.
- No describas archivos que no estén en `manifest.json`.
- Análisis incremental: un chunk cada vez; no concatenes diffs.
- No marques ítems del checklist que requieran acción humana (tests manuales, QA).
- Idioma del body: **español**; los identificadores de código, en su idioma original.
- No des por implementado lo que solo esté especificado: un cambio en
  `openspec/changes/**` o en `Documentos/**` es documentación, no código.
- No publiques la PR sin que el usuario lo confirme explícitamente.
