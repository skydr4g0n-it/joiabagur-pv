# Plan de actualización de documentación — `<rama>`

- **Generado**: `<fecha ISO>`
- **Alcance**: `<rama actual>` vs `<base>` (merge-base `<sha corto>`) · cambios sin commitear: `<sí/no>`
- **Ficheros analizados**: `<n>` · **commits**: `<n>` · **áreas tocadas**: `<lista>`
- **Changes de OpenSpec**: `<nombre (activo, tareas x/y) | nombre (archivado el YYYY-MM-DD)>`

## 1. Qué ha cambiado (resumen por área)

| Área | Ficheros | Qué implica para la documentación |
|---|---|---|
| `<área>` | `<n>` | `<una línea>` |

## 2. Veredicto de los cinco README

Obligatorio: una fila por README, siempre.

| README | Veredicto | Motivo |
|---|---|---|
| `README.md` (raíz) | `<actualizar / sin cambios / no aplica>` | `<motivo en una línea>` |
| `backend/README.md` | | |
| `ai-service/README.md` | | |
| `frontend/README.md` | | |
| `terraform/README.md` | | |

## 3. Cambios propuestos

Una entrada por edición concreta. Sin evidencia verificada, no hay entrada.

### E1 · `<ruta/del/documento.md>` → `<sección>`

- **Qué cambia**: `<descripción en una frase>`
- **Por qué**: `<qué hecho del código lo contradice>`
- **Evidencia**: `<ruta:línea>` · `<ruta:línea>`
- **Riesgo**: `<bajo / medio / alto>` — `<por qué, si no es bajo>`
- **Estado**: `propuesto`

```diff
- <texto actual>
+ <texto propuesto>
```

### E2 · `<...>`

`<misma estructura>`

## 4. Requiere aprobación expresa

Estas entradas **no se aplican** con un «adelante» genérico.

| # | Tipo | Documento | Detalle |
|---|---|---|---|
| `<E-n>` | `<creación de documento / sección congelada del README raíz / evidencia indirecta>` | `<ruta>` | `<detalle>` |

## 5. Notas para otros flujos

| Detección | Responsable |
|---|---|
| `<HU que falta o desalineada>` | comando `enrich-us` |
| `<capability implementada sin spec sincronizada>` | `opsx:sync` / `opsx:archive` |
| `<tarea de openspec/DEFERRED_TASKS.md resuelta>` | quien cierre la tarea |
| `<otro>` | `<responsable>` |

## 6. Pendiente / no verificable

Lo que no se ha podido confirmar en el repo y por tanto **no se ha escrito**.

- `<afirmación>` — falta: `<qué haría falta para confirmarla>`

---

## Cierre (se rellena tras aplicar)

| # | Documento | Estado final |
|---|---|---|
| `<E-n>` | `<ruta>` | `<aplicado / descartado / pendiente>` |

- **Modificados**: `<lista de rutas>`
- **Creados**: `<lista de rutas>`
- **Sin cambios**: `<lista de rutas>`
