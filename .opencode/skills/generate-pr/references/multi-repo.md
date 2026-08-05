# Referencia — Awareness multi-repo

Módulo cargado por `generate-pr` en la Fase B/C cuando `manifest.json` reporta un
repo hermano con `branchMatch: true`.

## Contexto

El producto Adresles vive en 3 repos (ver `AI_OPERATING_MODEL.md`):

- `adresles-platform-2.0` — backend FastAPI + frontend React.
- `adresles-woocommerce` — plugin de checkout WooCommerce.
- `adresles-workspace` — Memory Bank, `ai-config/`, scripts (transversal).

Una funcionalidad full-stack se implementa como **dos changes coordinados**, uno
por repo, que comparten slug base. Por tanto, una PR puede tener una **PR hermana**
en el otro repo de código.

## Detección

`pr-context.ps1` revisa los repos hermanos (carpetas hermanas) y, si encuentra una
rama con el **mismo nombre**, lo marca en `manifest.json → siblingRepos[].branchMatch`.

## Qué añadir al body

Si hay una PR hermana probable:

1. En "Motivación y contexto", indica que es parte de un cambio coordinado y nombra
   el repo hermano y la rama.
2. En "Deployment Notes", especifica el **orden de despliegue** si importa
   (regla habitual: el backend que expone un contrato se despliega antes que el
   plugin que lo consume).
3. Señala el **impacto cruzado**: si este cambio altera un contrato de API que el
   plugin consume, dilo explícitamente.
4. Indica el **orden de merge** (ver abajo) en "Notas adicionales" o "Deployment".

No analices el diff del repo hermano: cada PR describe su propio repo. Solo se
deja constancia del enlace y de las dependencias de despliegue.

## Orden de merge en cambios coordinados

Si el cambio toca configuración de IA (`.cursor/`, `.claude/`, `memory-bank/`,
`CLAUDE.md`, `AGENTS.md`), la **PR de `adresles-workspace` debe mergearse primero**:
es la fuente de verdad de la que `sync-ai-config.ps1` genera los artefactos de los
repos de código.

El `drift-check` de CI lo **fuerza**: la PR de `adresles-platform-2.0` o
`adresles-woocommerce` falla el check mientras la rama homónima de
`adresles-workspace` no esté en `main` (compara contra `adresles-workspace@main`).
Es el comportamiento esperado, no un error de la PR. Secuencia correcta:

1. Mergear la PR de `adresles-workspace`.
2. Re-ejecutar el `drift-check` de las PRs de platform/woo → pasan a verde.
3. Mergear las PRs de platform y woo.

Cuando el cuerpo de una PR de platform/woo sea un cambio coordinado, déjalo escrito
explícitamente para quien revisa.
