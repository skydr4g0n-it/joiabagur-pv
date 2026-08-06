---
name: "Docs: Update"
description: Revisa los últimos cambios del repo (commiteados y sin commitear, con foco en los changes de OpenSpec en curso o recién archivados) y actualiza la documentación de contexto de largo plazo — README de raíz, backend, ai-service, frontend y terraform, más Documentos/ y openspec/
category: Documentation
tags: [documentation, readme, openspec, maintenance, context]
---

Actualiza la documentación de contexto de largo plazo de **JoiaBagur PV** a
partir de los últimos cambios del repositorio.

**Entrada** (`$ARGUMENTS`, opcional): rama base contra la que comparar, un rango
git (`HEAD~10..HEAD`) o el nombre de un change de OpenSpec.

**Si se omite la base, PREGUNTA primero.** El alcance no se da por sentado.
Antes de ejecutar nada, plantea al usuario qué ventana de cambios analizar,
dándole:

- la rama actual (`git rev-parse --abbrev-ref HEAD`);
- la base sugerida por el repo (`git rev-parse --abbrev-ref origin/HEAD`),
  como sugerencia y no como decisión tomada;
- las demás candidatas (`git branch -r`).

Espera su respuesta antes de continuar.

## Qué hacer

Invoca la skill **`update-docs`** y sigue su `SKILL.md` de principio a fin.

- En Claude Code: la skill se activa por su descripción; si no, cárgala
  explícitamente.
- En otro entorno: lee y ejecuta paso a paso el `SKILL.md` de la copia de tu
  harness — la skill está replicada en `.agent/`, `.claude/`, `.codex/`,
  `.cursor/` y `.opencode/skills/update-docs/`.

Pasa la base confirmada como `-BaseBranch` (o el rango como `-Range`) al script
`docs-context.ps1`. El script se detiene con código 2 si no recibe ninguna de
las dos: es una red de seguridad, no una forma de descubrir el alcance.

## Alcance de revisión

Se revisan **siempre** los cinco README del monorepo — raíz, `backend/`,
`ai-service/`, `frontend/` y `terraform/` — con veredicto explícito para cada
uno (`actualizar`, `sin cambios`, `no aplica`). Además, los documentos de
`Documentos/` y el contexto de `openspec/` (`project.md`, `config.yaml`) que la
matriz `config/doc-impact.json` marque como afectados.

## Resultado esperado

Todo bajo `.docs-update/<rama>/` (carpeta scratch, ignorada por git):

1. `manifest.json` y `summary.md` — cambios clasificados por área y documentos
   candidatos, generados sin IA.
2. `plan.md` — plan de actualización con evidencia por entrada.
3. Una **parada para confirmar** el plan en el chat, antes de tocar ficheros.
4. Las ediciones aprobadas aplicadas sobre la documentación real, y el plan
   cerrado con el estado final de cada entrada.

## Guardarraíles

- No asumas el alcance. Sin indicación explícita del usuario, pregunta.
- No escribas nada sin evidencia verificada en el repo: lo no verificable va al
  plan como pendiente.
- No apliques ediciones antes de la confirmación del usuario.
- No toques `openspec/specs/**` (eso es `opsx:sync` / `opsx:archive`) ni crees
  historias de usuario (eso es `/enrich-us`).
- Secciones congeladas del README raíz (0. Ficha, 1.1–1.3, 5. Historias,
  6. Tickets): se reportan, no se editan.
- No hagas commit ni push salvo petición explícita.
