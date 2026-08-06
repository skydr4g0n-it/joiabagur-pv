---
name: "OpenSpec: Archive + Docs"
description: Archiva un change de OpenSpec y, a continuación, actualiza con la skill update-docs la documentación de contexto que ese change haya dejado desactualizada
category: Workflow
tags: [workflow, archive, openspec, documentation, context]
---

Encadena los dos procesos que van siempre juntos al cerrar un change: archivarlo
y poner al día la documentación de contexto de largo plazo que deja obsoleta.

**Entrada** (`$ARGUMENTS`, opcional): nombre del change a archivar. Si se omite,
lo pregunta el propio paso de archivado — no lo adivines.

Este comando **no duplica** ninguno de los dos procesos: los invoca. Si algo de
lo que sigue contradice a un `SKILL.md`, manda el `SKILL.md`.

## Paso 1 — Puerta de validación

Ejecuta `openspec validate --all --strict`. Debe reportar `0 failed`.

Es la única forma que sirve: `openspec validate` a secas no valida nada y sale
con código 1. Si hay fallos, **para aquí** y enséñalos. Un change puede estar en
verde mientras las specs vivas en las que sincroniza están rotas: así
sobrevivieron tres specs malformadas hasta el 2026-08-06. Ver
[CLAUDE.md](../../CLAUDE.md).

## Paso 2 — Archivar el change

Invoca la skill **`openspec-archive-change`** y sigue su `SKILL.md` de principio
a fin: selección del change, estado de artefactos y tareas, evaluación y sync de
las delta specs, y movimiento a `openspec/changes/archive/<AAAA-MM-DD>-<nombre>/`.

- En Claude Code: la skill se activa por su descripción; si no, cárgala
  explícitamente.
- En otro entorno: lee y ejecuta paso a paso el `SKILL.md` de la copia de tu
  harness — está replicada en `.agent/`, `.claude/`, `.codex/`, `.cursor/` y
  `.opencode/skills/openspec-archive-change/`.

**Si el archivado no llega a completarse** —el usuario cancela, faltan artefactos
y decide no seguir, o falla el movimiento del directorio— **no continúes**. Dilo
y para: sin change archivado no hay nada nuevo que documentar.

## Paso 3 — Actualizar la documentación

Invoca la skill **`update-docs`** con el change recién archivado como foco.

- **Alcance**: pasa `-RecentArchiveDays 1` al script `docs-context.ps1` para que
  recoja el change que acabas de archivar.
- **Base de comparación**: la skill la pregunta en su Paso 0 y **eso no se
  salta**. Propón la que corresponda —la rama de integración del trabajo en
  curso— pero espera respuesta.
- El resto es su flujo: `manifest.json`, `plan.md`, parada para confirmar el plan
  y, solo entonces, las ediciones aprobadas.

Anuncia el salto de un proceso al otro. Quien lo ejecuta ha pedido archivar *y*
documentar: no lo dejes adivinando en cuál de los dos está.

## Guardarraíles

- Los dos procesos conservan sus paradas. Este comando encadena, no automatiza a
  ciegas: si `update-docs` pide confirmar el plan, se confirma antes de escribir.
- Si el paso 1 falla no se archiva; si el paso 2 no termina no se documenta.
- No edites `openspec/specs/**` desde el paso 3: esa sincronización es del
  archivado (`opsx:sync` / `opsx:archive`).
- No hagas commit ni push salvo petición explícita.
