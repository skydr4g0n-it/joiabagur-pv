# Reglas para el contexto de OpenSpec

`openspec/` tiene cuatro piezas con dueños distintos. `update-docs` solo escribe
en dos de ellas.

| Ruta | Dueño | Rol de update-docs |
|---|---|---|
| `openspec/project.md` | esta skill | **Editable** |
| `openspec/config.yaml` | esta skill | **Editable** |
| `openspec/specs/**` | flujo OpenSpec (`opsx:sync`, `opsx:archive`) | Solo señalar desincronización |
| `openspec/changes/**` | flujo OpenSpec (`opsx:*`) | Solo lectura, como evidencia |

Ambos ficheros editables están en **inglés**. Son contexto que se inyecta en
cada sesión de agente: cada línea cuesta, así que se actualizan con precisión
quirúrgica, sin engordarlos.

---

## `openspec/project.md`

Secciones sensibles y su disparador:

| Sección | Se actualiza cuando… |
|---|---|
| `## Purpose` / `### MVP Scope (Phase 1)` | Cambia el recuento de épicas o historias — debe cuadrar con `Documentos/epicas.md` |
| `## Tech Stack` | Entra o sale una tecnología, o cambia una versión mayor (`.csproj`, `package.json`, `pyproject.toml`) |
| `### Testing Stack` | Cambian frameworks o versiones de test |
| `## Project Conventions` | Cambian convenciones de código, capas, patrones o estrategia de test |
| `#### Post-Implementation Documentation Update` | Aparece un documento nuevo que hay que mantener, o cambia la regla de cuándo tocarlo |
| `### Key Entities` | Se añade, renombra o retira una entidad del dominio |
| `### Business Rules` | Se añade o modifica una regla de negocio verificable en el código |
| `## Important Constraints` | Cambian límites de free-tier, rendimiento, seguridad o almacenamiento |
| `## External Dependencies` | Cambia un servicio cloud o una librería de terceros relevante |
| `## Key Documentation References` | Se crea, mueve o renombra un documento de `Documentos/` |

Reglas:

- **Key Entities** describe el dominio, no el esquema: una frase por entidad con
  sus campos distintivos. El detalle va en `Documentos/modelo-de-datos.md`.
- **Business Rules** es una lista numerada; añadir al final para no romper
  referencias externas a «regla N».
- Si añades una entrada a `Key Documentation References`, comprueba que la ruta
  existe.

## `openspec/config.yaml`

Un bloque `context: |` en texto plano más un bloque `rules:` por artefacto
(`proposal`, `specs`, `design`, `tasks`).

- El `context` es la versión **condensada** de `project.md`: si actualizas un
  hecho en `project.md` que también aparece aquí (stack, frontera `jbg-ai`,
  infraestructura, épicas, constraints), actualiza los dos o quedarán en
  contradicción.
- Es YAML: respeta la indentación del bloque literal. Un fallo de sangrado
  rompe el arranque de las herramientas OpenSpec.
- `rules:` solo cambia si cambia la política de trabajo, no por un cambio de
  código.
- Recuerda que el bloque `context` ya declara la deprecación de los workflows
  App Runner + CloudFront: mantén esa marca mientras siga siendo cierta.

## `openspec/specs/**` y `openspec/changes/**`

- **No los edites.** Las specs vivas se actualizan con `opsx:sync` al terminar un
  change y con `opsx:archive` al archivarlo.
- Úsalos como **evidencia de comportamiento**: una spec sincronizada describe lo
  que el sistema hace hoy; un change activo describe lo que *hará*.
- Si detectas que una capability implementada no está en `openspec/specs/`, o
  que una spec contradice el código, ponlo en el plan como **nota para
  `opsx:sync` / `opsx:archive`**, no como edición.
- `openspec/DEFERRED_TASKS.md` recoge trabajo aplazado: si un cambio resuelve
  una entrada, indícalo en el plan (la edita quien cierre la tarea).
