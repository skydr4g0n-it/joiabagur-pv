## Why

C25 corrige la fusión híbrida y, para poder demostrar que la corrige, **conserva la fusión plana
como modo seleccionable**: sin ella la fila `v2-hibrido` de la tabla de ablations deja de ser
reproducible y el change pierde la referencia contra la que se leen todas las demás filas. Es una
decisión de medición, no de producto, y su propio `design.md` la declara temporal.

Una vez la tabla está publicada y la configuración ganadora congelada, ese modo pasa a ser lo
contrario de lo que era: **un camino muerto que nadie ejecuta y que cualquiera puede activar por
error**, con pesos por lista que ya no existen en ninguna otra parte del sistema y una aritmética
que el propio proyecto midió como defectuosa —los 60 documentos léxicos ganando al mejor candidato
vectorial en toda consulta—. Mantener vivo un camino que se demostró roto es la forma más callada
de que vuelva.

Lo mismo vale para la variante de ponderación adaptativa que pierda el barrido de C25, y para las
perillas que quedan sin lectores cuando la decisión se fija.

## What Changes

- **Se retira la fusión plana de tres listas.** Deja de ser seleccionable y su código desaparece,
  junto con los pesos por lista que sólo ella consumía.
- **Se retira la variante de ponderación adaptativa que perdió el barrido** de C25 —la continua o
  la binaria con `α`—, para que no queden dos mecanismos vivos donde la medición eligió uno.
- **Se retiran las perillas sin lector** que la decisión de C25 deja fijadas, y sus valores pasan
  a constantes documentadas donde siga habiendo motivo para nombrarlos.
- **BREAKING (interno):** la configuración de evaluación `v2-hibrido` deja de poder ejecutarse.
  Sus cifras se conservan como artefacto —el JSONL por consulta y el informe están versionados en
  git— pero la fila deja de poder **re-medirse**, y eso se declara en lugar de disimularse.
- **Se sustituye el requisito de reproducibilidad de la línea base por uno de conservación**: lo
  que el proyecto garantiza a partir de aquí es que las cifras de la línea base están archivadas y
  citables, no que su código siga ejecutable.

## Capabilities

### New Capabilities

Ninguna. Es un change de limpieza: retira comportamiento y no introduce ninguno.

### Modified Capabilities

- `hybrid-fusion`: se elimina el requisito que obliga a mantener seleccionable la fusión de una
  sola etapa, y el que admite dos formas de ponderación adaptativa queda reducido a la que la
  medición eligió.
- `retrieval-evaluation`: el requisito de que la configuración de la línea base siga siendo
  seleccionable se sustituye por el de que sus cifras y su procedencia queden archivadas y
  citables, con la pérdida de re-ejecución declarada.

## Impact

- **`ai-service/` es el único componente afectado**, y sólo por borrado:
  - `src/jbg_ai/retrieval/orchestrator.py` — desaparece la rama del modo plano
  - `src/jbg_ai/config/settings.py` — desaparecen los pesos por lista y las perillas sin lector
  - `src/jbg_ai/evals/configs.py` y `evals/configs/v2-hibrido.yaml` — la fila deja de ser ejecutable
  - `tests/retrieval/`, `tests/evals/` — caen los tests que protegían el modo retirado
- **Sin migración, sin cambio de contrato, sin reindexar.** `openapi.json` no se mueve.
- **Sin diff en `backend/`, `frontend/`, `terraform/` ni `.github/workflows/`.**
- **Aguas arriba:** depende por completo de C25. **No puede abrirse antes de que C25 esté
  archivado y su tabla publicada**, porque su único propósito es retirar el andamio que aquél
  necesita en pie.
- **Riesgo que el change acepta a propósito:** se pierde la capacidad de re-ejecutar la línea base.
  Es el precio de no dejar vivo un camino medido como defectuoso, y se declara en el README.
