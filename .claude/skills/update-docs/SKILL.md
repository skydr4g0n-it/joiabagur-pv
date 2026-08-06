---
name: update-docs
description: Revisa los últimos cambios del repo (commiteados y sin commitear, con foco en los changes de OpenSpec en curso o recién archivados), determina qué documentación de contexto de largo plazo ha quedado desactualizada — los README de raíz, backend, ai-service, frontend y terraform, y los documentos de Documentos/ y openspec/ — y la actualiza tras confirmación. Úsala cuando el usuario pida actualizar la documentación, sincronizar los docs con el código, o invoque el comando /update-docs.
license: MIT
compatibility: Requiere Git y PowerShell 7+.
metadata:
  author: joiabagur-pv
  version: "1.0"
---

# update-docs — Sincronizador de la documentación de contexto

Mantiene alineada la **memoria de largo plazo** del repo con lo que realmente
hay en el código. El flujo separa recolección, análisis y escritura para que
ninguna frase acabe en un documento sin evidencia detrás:

| Fase | Responsable | Qué hace |
|---|---|---|
| **0 · Alcance** | **el usuario** | Decide qué ventana de cambios se analiza. La rama base nunca se asume. |
| **A · Recopilación** | `scripts/docs-context.ps1` (determinista, sin IA) | Cambios commiteados + sin commitear, changes de OpenSpec activos y recién archivados, y **documentos candidatos** según `config/doc-impact.json`. |
| **B · Análisis** | tú, documento a documento | Contrastas cada documento candidato con el código real y anotas qué frase concreta ha quedado obsoleta. |
| **C · Plan** | tú, con el usuario | Escribes `<outDir>/plan.md`, lo enseñas y **esperas confirmación**. |
| **D · Aplicación** | tú | Editas **solo** lo aprobado, con ediciones quirúrgicas, y cierras el informe. |

> `<outDir>` es `.docs-update/<rama>/` (campo `outDir` del `manifest.json`).
> Esa carpeta es scratch: está en `.gitignore`, no se commitea.

> **Regla de oro:** un documento solo se toca si **el código lo contradice**.
> Si no puedes verificar una afirmación en el repo, no la escribas: anótala como
> pendiente en el plan. Nunca reescribas un documento entero para "mejorarlo".

Los archivos de apoyo están **junto a este SKILL.md**: `scripts/`, `config/`,
`references/`, `templates/`. Carga los `references/` **solo cuando los
necesites** (divulgación progresiva) — no los leas todos de golpe.

---

## Paso 0 — Contexto del repo

`joiabagur-pv` es un **monorepo**: `backend/` (.NET 10 / EF Core / PostgreSQL),
`frontend/` (React 19 + Vite + Metronic), `ai-service/` (microservicio Python
`jbg_ai`, FastAPI), `terraform/` y `.github/workflows/`.

Su memoria de largo plazo son tres árboles, y los tres entran en el alcance de
esta skill:

- **README de componente** — `README.md` (raíz), `backend/README.md`,
  `ai-service/README.md`, `frontend/README.md`, `terraform/README.md`.
- **`Documentos/`** — arquitectura, modelo C4, modelo de datos, épicas, guías,
  testing, historias y Proyecto Final de IA.
- **`openspec/`** — `project.md` y `config.yaml` (contexto), `specs/` (specs
  vivas, **fuera del alcance de escritura**) y `changes/`.

`CLAUDE.md` documenta las reglas operativas del repo para agentes (formas de
`openspec validate`, spec viva vs spec delta, particularidades de `ai-service`):
úsalo como contexto, pero **no lo actualices desde aquí** — no es documentación
funcional. `AGENTS.md` sigue vacío.

## Paso 1 — Confirmar el alcance (obligatorio, antes de ejecutar nada)

**La ventana de cambios nunca se da por sentada.** El modo por defecto es
*rama actual vs rama base + working tree*, y la base la decide el usuario.

Si no la ha indicado (argumento del comando o petición en el chat),
**pregúntasela antes de ejecutar el script**, dándole el contexto para decidir:

- la **rama actual** (`git rev-parse --abbrev-ref HEAD`);
- la **base sugerida** por el repo (`git rev-parse --abbrev-ref origin/HEAD`),
  como sugerencia, no como decisión tomada;
- las **candidatas** (`git branch -r`), excluyendo la actual.

El argumento admite tres formas: nombre de rama base (`master`), rango git
(`HEAD~10..HEAD` → `-Range`) o nombre de un change de OpenSpec (en ese caso
pregunta igualmente la base y usa el change para **priorizar** el análisis).

No continúes hasta tener respuesta.

## Paso 2 — Fase A: recopilar contexto (script)

Ejecuta el script de esta skill desde la raíz del repo:

```powershell
pwsh <skill-dir>/scripts/docs-context.ps1 -BaseBranch <rama>
```

`<skill-dir>` es la carpeta que contiene este SKILL.md. La skill está replicada
en los cinco harnesses del repo (`.agent/`, `.claude/`, `.codex/`, `.cursor/` y
`.opencode/skills/update-docs/`); usa la copia de tu entorno.

Flags útiles: `-Range HEAD~10..HEAD` (ventana explícita, sin base),
`-NoUncommitted` (ignora el working tree), `-NoFetch` (offline),
`-RecentArchiveDays N` (ventana de changes archivados; por defecto 45).

Sin `-BaseBranch` ni `-Range` el script se detiene con código 2 y lista las
candidatas: eso significa que te has saltado el Paso 1. `-AutoBase` existe solo
para uso desatendido — **no lo uses en una sesión interactiva**.

Lee después `<outDir>/manifest.json` y `<outDir>/summary.md`. Casos límite:

- `empty: true` → no hay cambios en el rango. Infórmalo y **detente**.
- `missingDocs` no vacío → esos documentos no existen. Trátalos como
  **propuesta de creación** en el plan, nunca los des por escritos.
- `unclassifiedFiles` no vacío → ficheros que la matriz no cubre. Revísalos a
  mano y, si el patrón es recurrente, propón añadir el glob a
  `config/doc-impact.json`.

## Paso 3 — Fase B: analizar documento a documento

El manifiesto trae `docs[]` ya priorizado. Recórrelo **de uno en uno**:

1. Lee el `reference` que indica cada entrada — y solo ese:
   - `references/readmes.md` → los cinco README.
   - `references/documentos-funcionales.md` → todo `Documentos/`.
   - `references/openspec-context.md` → `openspec/project.md` y `config.yaml`.
2. Lee **las secciones afectadas** del documento, no el documento entero.
3. **Verifica contra el código** antes de decidir nada: carga
   `references/verification.md` y comprueba en el repo real (entidades,
   controladores, `package.json`, `.tf`, settings de `jbg_ai`…) qué dice hoy la
   fuente de verdad.
4. Anota, por documento: sección, frase o tabla concreta que ha quedado
   obsoleta, texto propuesto, y **evidencia** (`ruta:línea` o el fichero del
   manifiesto que lo dispara).

**Los cinco README se revisan siempre**, aunque la matriz no los haya marcado:
vienen con `alwaysReview: true` y en el plan debe aparecer un veredicto
explícito para cada uno — `actualizar`, `sin cambios` o `no aplica`.

Además, cruza siempre el estado de `openspecChanges[]`:

- change **activo** con tareas pendientes → documenta solo lo ya implementado;
  lo demás va al plan como «pendiente hasta que cierre el change».
- change **recién archivado** → es el disparador típico: sus `specs/` describen
  comportamiento que ya debería estar en `Documentos/` y en los README.

## Paso 4 — Fase C: plan y confirmación (parada obligatoria)

1. Rellena `templates/docs-update-report.md` y escríbelo en `<outDir>/plan.md`.
2. Muestra en el chat la tabla resumen: documento · qué cambia · por qué ·
   evidencia · riesgo.
3. **Pregunta al usuario qué entradas aplicar.** Ofrece aceptar todo, un
   subconjunto, o nada. No edites ningún fichero antes de la respuesta.

Marca aparte, y no las apliques sin mención expresa:

- creación de documentos que no existen;
- secciones congeladas del README raíz (ver `references/readmes.md`);
- cualquier entrada cuya evidencia sea indirecta.

## Paso 5 — Fase D: aplicar

Solo lo aprobado, y con estas reglas:

- **Ediciones quirúrgicas**: cambia la frase, la fila de tabla o el bloque
  afectado. No reordenes, no reformatees, no traduzcas lo que ya estaba.
- **Idioma del documento**: se respeta el que tenga (`language` en el
  manifiesto). Los identificadores técnicos, siempre en inglés.
- **Coherencia interna**: si cambias un encabezado, actualiza el índice del
  documento; si cambias una ruta, revisa los enlaces relativos que apuntan a ella.
- **Diagramas**: los ER y C4 son Mermaid; si añades una entidad o componente,
  actualiza también el diagrama, no solo la tabla.

## Paso 6 — Cierre

1. Actualiza `<outDir>/plan.md` marcando cada entrada como `aplicado`,
   `descartado` o `pendiente`.
2. Resume en el chat: documentos modificados, creados, descartados y pendientes.
3. Señala lo que queda fuera de esta skill y a quién le toca:
   - HU nuevas o desalineadas → comando `enrich-us`.
   - `openspec/specs/**` desincronizado → `opsx:sync` / `opsx:archive`.
   - Cuerpo de PR → skill `generate-pr`.
4. **No hagas commit ni push** salvo petición explícita del usuario.

---

## Guardarraíles

- **El alcance nunca se asume**: sin base o rango indicado por el usuario, se
  pregunta. Nada de `-AutoBase` en sesión interactiva.
- **Nada sin evidencia**: cada línea escrita apunta a un fichero del manifiesto
  o a una ruta verificada del repo. Lo no verificable se anota como pendiente.
- **Parada obligatoria antes de escribir**: el plan se confirma siempre.
- **No inventes documentos**: si falta uno, se propone crearlo, no se referencia
  como existente.
- **No toques `openspec/specs/**`**: esas specs las sincroniza el flujo OpenSpec.
  Aquí solo se señala la desincronización.
- **No crees ni reescribas historias de usuario**: eso es `enrich-us`.
- **Registro histórico intocable**: `Documentos/prompts.md`,
  `Documentos/Sesiones Master AIEng/**` y `Documentos/Propuestas/**` son
  documentos fechados; no se actualizan retroactivamente.
- **README raíz**: es el entregable del máster. Solo se editan las secciones
  técnicas listadas en `references/readmes.md`; el resto se reporta.
- **Especificado no es implementado**: un cambio en `openspec/changes/**` o en
  `Documentos/**` es documentación, no código. No documentes como existente lo
  que solo está propuesto.
- Idioma de la interacción y del plan: **español**.
