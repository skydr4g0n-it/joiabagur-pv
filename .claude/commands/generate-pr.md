---
name: "PR: Generate"
description: Genera el cuerpo de una Pull Request analizando el diff de la rama actual contra la base, troceado por dominios y sin alucinar
category: Workflow
tags: [pull-request, git, review, automation]
---

Genera el cuerpo de una Pull Request para la rama actual.

**Entrada** (`$ARGUMENTS`, opcional): rama base contra la que comparar. Si se
omite, se detecta automáticamente (`origin/HEAD`, con fallback a `main`/`master`).

## Qué hacer

Invoca la skill **`generate-pr`** y sigue su `SKILL.md` de principio a fin.

- En Claude Code: la skill se activa por su descripción; si no, cárgala
  explícitamente.
- En Cursor u otro entorno: lee y ejecuta
  `.cursor/skills/generate-pr/SKILL.md` (o `.claude/skills/generate-pr/SKILL.md`)
  paso a paso.

Pasa `$ARGUMENTS` como rama base (`-BaseBranch`) al script `pr-context.ps1` si el
usuario indicó una.

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

- No describas nada que no esté en el diff troceado. Ver la regla
  `pr-generation-standards.mdc`.
- No publiques la PR sin confirmación explícita.
- Si no hay diferencias con la base, informa y detente: no hay PR que redactar.
