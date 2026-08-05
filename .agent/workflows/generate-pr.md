---
name: "PR: Generate"
description: Genera el cuerpo de una Pull Request analizando el diff de la rama actual contra la base, troceado por dominios y sin alucinar
category: Workflow
tags: [pull-request, git, review, automation]
---

Genera el cuerpo de una Pull Request para la rama actual.

**Entrada** (`$ARGUMENTS`): rama base contra la que comparar.

**Si se omite, PREGUNTA primero.** La base no se da por sentada nunca. Antes de
ejecutar nada, plantea al usuario contra qué rama quiere abrir la PR, dándole:

- la rama actual (`git rev-parse --abbrev-ref HEAD`), que será el origen;
- la base sugerida por el repo (`git rev-parse --abbrev-ref origin/HEAD`),
  como sugerencia y no como decisión tomada;
- las demás candidatas (`git branch -r`).

Espera su respuesta antes de continuar.

## Qué hacer

Invoca la skill **`generate-pr`** y sigue su `SKILL.md` de principio a fin.

- En Claude Code: la skill se activa por su descripción; si no, cárgala
  explícitamente.
- En otro entorno: lee y ejecuta paso a paso el `SKILL.md` de la copia de tu
  harness — la skill está replicada en `.agent/`, `.claude/`, `.codex/`,
  `.cursor/` y `.opencode/skills/generate-pr/`.

Pasa la rama base confirmada como `-BaseBranch` al script `pr-context.ps1`. El
script se detiene con código 2 si no la recibe: es una red de seguridad, no una
forma de descubrirla.

## Resultado esperado

Todo bajo `.pr/<rama>/` (una subcarpeta por rama; campo `outDir` del manifest):

1. `manifest.json`, `summary.md` y `chunks/*.diff` — contexto troceado.
2. `PR_body_tmp.md` — cuerpo de la PR redactado, listo para revisión humana.
3. Un resumen en el chat: título propuesto, dominios cubiertos, breaking changes y
   riesgos detectados.
4. Oferta opcional de crear la PR con
   `gh pr create --assignee @me --body-file <outDir>/PR_body_tmp.md` — solo si el
   usuario lo confirma.

## Guardarraíles

- No asumas la rama base. Sin indicación explícita del usuario, pregunta.
- No describas nada que no esté en el diff troceado. Ver la regla
  `pr-generation-standards.mdc`.
- No publiques la PR sin confirmación explícita.
- Si no hay diferencias con la base, informa y detente: no hay PR que redactar.
