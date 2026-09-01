# Línea base de las suites, medida antes de tocar código

Medida el 2026-08-31 sobre `ai-eng` en `6ffd390`, con el árbol de trabajo sin un solo
cambio de código. Existe para que la tarea 10.5 compare **nombres** y nunca recuentos,
que es la regla del proyecto.

| Suite | Fallos en la línea base | Total | Alcance |
|---|---|---|---|
| `dotnet test` | **47** | 920 | 17 clases |
| `vitest run` | **113** | 533 | 14 ficheros |
| `uv run pytest` | ~~2~~ → **0** | 466 | *arreglados en este change* |

**Ninguna de las clases del backend toca familias**, ni `ProductFamiliesController`, ni
`AiCatalogController`, ni `FamilySuggestionControllerTests`. La superficie que C18b
modifica está limpia en la línea base, así que cualquier fallo nuevo ahí es de este change.

## La suite de Python no estaba «rota de base»: estaba rota, y se arregló

Los dos fallos que esta línea base registró al principio —`test_malformed_exclusions_are_ignored`
y `test_trace_id_appears_in_stage_logs`— **no eran deuda heredada tolerable**. Eran un
defecto real introducido con **C14** (`b552a99`, archivado el 27 de agosto), que añadió el
logger de `retrieval` y sus dos tests sin que nadie ejecutara la suite completa después.

**Causa.** `migrations/env.py` configura el logging desde `alembic.ini` con `fileConfig`,
cuyo valor por defecto es `disable_existing_loggers=True`. Bajo el CLI de Alembic da igual
—el proceso termina justo después—; **en proceso no**: los tests de migración ejecutan
Alembic en el mismo intérprete que el resto de la suite, así que dejaban **todos los
loggers de `jbg_ai` desactivados** para lo que corriera después.

**Arreglo.** `fileConfig(..., disable_existing_loggers=False)`, y
`tests/migrations/test_alembic_logging_isolation.py` para que no vuelva en silencio.

**Por qué costó cuatro días en verse, que es lo que merece quedar escrito.** Los dos
tests afirman sobre salida de log, así que fallaban con una captura vacía en lugar de con
un error. Y **pasaban al ejecutar su propio fichero**, de modo que la comprobación obvia
decía que el código estaba bien y la conclusión obvia era «dependencia de orden, como en
la suite .NET». Durante este apply llegué a escribir justamente eso aquí. Era falso: la
suite de Python **no tiene fallos de línea base**, y la comprobación válida siempre fue la
suite completa contra la suite completa.

---

## Medido el 2026-08-31: en el backend, ni los nombres son estables

`CLAUDE.md` dice —con razón— que en la suite .NET se comparan **nombres** y nunca recuentos, porque
«un puñado de estos fallos son genuinamente dependientes del orden». Al cerrar C18b se midió cuánto
es ese puñado, ejecutando **la suite completa dos veces sobre el mismo commit**:

| | pasada 1 | pasada 2 |
|---|---|---|
| Fallos | **48** | **54** |
| Nombres sólo en esa pasada | 6 | 12 |
| **Clases con fallos** | **17** | **17 — las mismas** |

**Dieciocho nombres se mueven entre dos ejecuciones de código idéntico**, casi todos dentro de
`InventoryIntegrationTests`. Así que comparar por nombre tampoco decide: sobre esta suite, la unidad
estable es la **clase**.

**La regla útil, entonces:** comparar el **conjunto de clases** con fallos, y sólo mirar nombres
dentro de una clase que no estuviera en la línea base. Para C18b el resultado fue inequívoco —
**ninguna clase de familia falla en ninguna de las dos pasadas**: ni `FamilyReviewControllerTests`,
ni `FamilyReviewVerdictSchemaTests`, ni `ProductFamiliesControllerTests`, ni
`FamilySuggestionControllerTests`, ni `ProductFamilySchemaTests`, ni `AiCatalogControllerTests`.

Ejecutadas en aislamiento, esas seis clases dan **77/77** y **48/48** en verde.
