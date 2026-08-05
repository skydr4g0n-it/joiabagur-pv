# Referencia — Redacción del título de la PR

Módulo cargado por `generate-pr` en la Fase C.

## Formato

Conventional Commits, en minúscula, sin punto final, ≤ 72 caracteres:

```
<tipo>(<ámbito>): <resumen imperativo>
```

- **tipo**: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `ci`, `build`.
- **ámbito**: el dominio dominante del `manifest.json` (`auth`, `orders`,
  `checkout`, `webhooks`, `frontend`, `infra`...). Omítelo si el cambio es
  transversal.
- **resumen**: qué hace el cambio, en imperativo y en español.
- Si hay un breaking change confirmado, añade `!` tras el ámbito: `feat(api)!: ...`.

## Cómo elegir tipo y ámbito

1. Mira la distribución de dominios y líneas en `manifest.json`: el dominio con
   más peso funcional define el ámbito.
2. El tipo se deriva de la intención agregada (ver `analyze-diff.md`): capacidad
   nueva → `feat`; corrección → `fix`; reestructuración sin cambio de
   comportamiento → `refactor`.
3. Si hay varios commits con un patrón claro, resúmelos; no listes todo.

## Ejemplos

- `feat(auth): añadir refresh tokens con rotación`
- `fix(webhooks): evitar procesamiento duplicado de webhooks de WooCommerce`
- `refactor(checkout): extraer validación de dirección a un helper`
- `chore(deps): actualizar FastAPI a 0.110.1`

Evita títulos genéricos ("varios cambios", "mejoras", "actualización").
