# Línea base de las tres suites, medida antes de tocar código

Medida el 2026-08-31 sobre `ai-eng` en `6ffd390`, con el árbol de trabajo sin un solo
cambio de código. Existe para que la tarea 10.5 compare **nombres** y nunca recuentos,
que es la regla del proyecto.

| Suite | Fallos | Total | Alcance |
|---|---|---|---|
| `dotnet test` | **47** | 920 | 17 clases |
| `vitest run` | **113** | 533 | 14 ficheros |
| `uv run pytest` | **2** | 444 | 1 fichero |

**Ninguna de las clases del backend toca familias**, ni `ProductFamiliesController`, ni
`AiCatalogController`, ni `FamilySuggestionControllerTests`. La superficie que C18b
modifica está limpia en la línea base, así que cualquier fallo nuevo ahí es de este change.

## Los dos fallos de Python son dependientes del orden, y engañan

`test_malformed_exclusions_are_ignored` y `test_trace_id_appears_in_stage_logs` **pasan
al ejecutar su fichero solo** y fallan en la suite completa: algo reconfigura el logging
antes de llegar a ellos y `caplog` deja de capturar. Comprobarlos por fichero suelto da
un falso «lo has roto tú», y así ocurrió una vez durante este apply.

Es la misma trampa que `CLAUDE.md` documenta para el backend —*«un puñado de estos fallos
son genuinamente dependientes del orden, así que dos ejecuciones del mismo código
discrepan»*— y conviene saber que **también aplica a la suite de Python**, donde la
documentación no lo advertía.

**La comprobación válida es la suite completa contra la suite completa.**
