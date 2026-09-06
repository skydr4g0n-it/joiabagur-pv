## 1. Precondiciones de entorno — verificar y parar si falla

- [ ] 1.1 Comprobar que el contenedor `jpv-pv-postgres` responde en el 5433 y que `SELECT count(*) FROM ai.product_document WHERE is_active` devuelve 1.168. **Si no, parar y levantarlo antes de seguir.**
- [ ] 1.2 Comprobar que `JPV_EMBEDDING_API_KEY` está operativa con una llamada de prueba al proveedor. **Si no, parar y configurarla.**
- [ ] 1.3 Comprobar que `SSL_CERT_FILE` apunta al PEM de raíces de Windows concatenado con el bundle de `certifi`; sin él el proveedor falla por TLS interceptado. **Si no, parar y configurarlo.**
- [ ] 1.4 Medir la **línea base de la suite** antes de tocar nada (`git stash push -u`, `uv run pytest`, `git stash pop`) y guardar los **nombres** de los tests que fallan, no el recuento.
- [ ] 1.5 Registrar `index_set_hash`, `model_version_key` vivo y `git_sha` de partida, que son tres de los cinco elementos de la tupla de procedencia.

## 2. Desempate determinista en la ruta viva

- [ ] 2.1 Añadir `, d.product_id` como última clave del `ORDER BY` de la sentencia vectorial en `retrieval/search.py`.
- [ ] 2.2 Añadir `, d.product_id` como última clave del `ORDER BY` de la sentencia léxica en `retrieval/search.py`.
- [ ] 2.3 Test que demuestra que dos documentos con la misma `ts_rank` y la misma `coordination` sobreviven al corte siempre en el mismo orden.
- [ ] 2.4 Test que demuestra que el desempate **no** reordena candidatos cuyas distancias o rangos difieren.
- [ ] 2.5 Confirmar que `openapi.json` sigue byte a byte idéntico y que la suite no gana fallos nuevos por nombre.

## 3. Migración y esquema

- [ ] 3.1 Revisión de Alembic con `ai.eval_run` (`run_id` uuid PK, `config_id`, `golden_set_version`, `index_set_hash`, `embedding_model_version_key`, `git_sha`, `started_at`, `finished_at`, `status`, `metrics jsonb`, `documents_omitted`, `notes`).
- [ ] 3.2 `ai.eval_case` (FK a `eval_run`, `query_id`, `category`, `in_tuning_set`, `data_origin_bucket`, `judged_depth`, métricas por consulta en `jsonb`).
- [ ] 3.3 `ai.eval_result` (FK a `eval_run`, `query_id`, `product_id`, `rank`, `score`, `grade` nullable, `unjudged`).
- [ ] 3.4 Índices: `config_id` y `started_at` sobre `eval_run`; `(run_id, query_id)` sobre `eval_case`; `(run_id, query_id, rank)` sobre `eval_result`.
- [ ] 3.5 Verificar `upgrade` y `downgrade` contra la base local; el `downgrade` no debe dejar rastro.

## 4. Criterio de anotación y consultas

- [ ] 4.1 Escribir `ai-service/evals/golden/criterion.md` con las tres anclas de grado, **antes** de registrar ningún juicio.
- [ ] 4.2 Redactar las **12** consultas de descripción natural **sin anclaje léxico**, comprobando que su respuesta esperada no comparte término con la consulta tras `expand_query`.
- [ ] 4.3 Redactar las **7** de variante/talla y las **5** de materiales, incluyendo al menos una multi-material.
- [ ] 4.4 Redactar las **4** de piedra que aíslan `stone_type` (`ónix` 124, `coral` 23, `perla` 34 en texto pero 0 en `materials`).
- [ ] 4.5 Redactar las **5** subjetivas (ocasión/estilo/regalo) y las **4** de léxico exacto (SKU y nombre literal).
- [ ] 4.6 Redactar las **6** de sinónimos, dos por cada tipo: artefacto del stemmer, sinónimo comercial y puente direccional.
- [ ] 4.7 Redactar las **5** fuera de dominio **plausibles** — nunca texto sin sentido, que haría abstener a todas las configuraciones por igual.
- [ ] 4.8 Redactar las **8** declaradas sin juicios (4 de sustituto para C26, 4 de ambigua para C30) con `pooled_in: []`.
- [ ] 4.9 Marcar `in_tuning_set: true` en las consultas heredadas de C20 y C21, y comprobar el anclaje a productos reales **por categoría**.

## 5. Carga y validación del golden set

- [ ] 5.1 `evals/golden.py`: modelo de `queries.jsonl` y `judgements.jsonl`, con versión del conjunto.
- [ ] 5.2 Validación de la matriz de trazabilidad: la carga **falla** si no se cumplen los seis mínimos por pleito.
- [ ] 5.3 Validación de que ninguna categoría queda íntegramente sintética.
- [ ] 5.4 Un test por cada requisito de la matriz, con un golden set de fixture que lo incumple.

## 6. Configuraciones y líneas base

- [ ] 6.1 `evals/configs.py` con el modelo declarativo y las cinco configuraciones en `evals/configs/`.
- [ ] 6.2 `v0-nombre`: réplica de `ProductService.SearchProductsAsync` — subcadena sobre `name` más SKU exacto, orden alfabético.
- [ ] 6.3 `v0-fts`: réplica de `AssistedSearchRepository.SearchLexicalAsync` recomponiendo `name ‖ sku ‖ <línea Descripción de doc_text>`, con `websearch_to_tsquery` y términos OR.
- [ ] 6.4 Test que fija el prefijo `Descripción: ` como contrato del renderizador, para que un cambio en `build_source_text` rompa el test y no la fidelidad en silencio.
- [ ] 6.5 `v1-vectorial` y `v2-hibrido` como parámetros del orquestador existente, **sin duplicar pipeline**.
- [ ] 6.6 Test que confirma que las dos líneas base registran coste **cero**, no ausente.

## 7. Línea base sin recuperación (`v0-cag`)

- [ ] 7.1 Compactador del catálogo a `sku · nombre · tipo · materiales`, una línea por producto, **sin precio**.
- [ ] 7.2 Recuento de tokens del catálogo completo y proyección de escala a 2.500 y 5.000 productos.
- [ ] 7.3 Truncado determinista por `product_id` cuando se excede el presupuesto, registrando `documents_omitted`.
- [ ] 7.4 Test que verifica el truncado determinista y el registro de omitidos con un corpus mayor que el presupuesto — **no que «cabe»**.
- [ ] 7.5 Ejecución sobre el subconjunto de 12 consultas sin anclaje, con `gpt-4o-mini` vía `JPV_RAG_LLM_*` a temperatura 0, registrando modelo y fecha.
- [ ] 7.6 Test que verifica que ningún precio aparece en el contexto construido.

## 8. Vectores congelados y procedencia

- [ ] 8.1 Congelar los vectores de las 48 consultas contra el proveedor real, a seis decimales, en `golden/query_vectors.jsonl` indexados por `model_version_key`.
- [ ] 8.2 Tupla de procedencia por ejecución y marcado de ejecuciones no comparables cuando difiere.
- [ ] 8.3 Test de reproducibilidad: dos ejecuciones con la misma procedencia dan métricas idénticas.
- [ ] 8.4 Test de que una huella de índice distinta marca la comparación como no válida en lugar de compararla.

## 9. Pooling y etiquetado

- [ ] 9.1 `evals/pooling.py`: unión sin repetición, base 20, bloques de 10 mientras aparezcan relevantes, tope 60, `judged_depth` por consulta.
- [ ] 9.2 Juicios apendables por `(query_id, product_id)`, con `pooled_in`, `judged_at` y `source_hash` del momento de etiquetar.
- [ ] 9.3 Construir el *pool* ejecutando las cuatro configuraciones indexadas contra el índice real, **en serie** (el pool de conexiones está capado a 5 y lo comparte la ruta viva).
- [ ] 9.4 **Sesión de etiquetado 1** (~1 h): descripción natural sin anclaje y variante/talla.
- [ ] 9.5 **Sesión de etiquetado 2** (~1 h): materiales, piedra y subjetivas.
- [ ] 9.6 **Sesión de etiquetado 3** (~1 h): sinónimos, léxico exacto y fuera de dominio.
- [ ] 9.7 **Relectura diferida** de las consultas etiquetadas con dudas, que es lo que sustituye a la conciliación entre anotadores.
- [ ] 9.8 Test de que un juicio nuevo sobre un documento no agrupado antes no altera los existentes.

## 10. Métricas

- [ ] 10.1 `evals/metrics.py`: nDCG@5 con grados, y Recall@5, P@3 y MRR en las dos lecturas (graduada y binaria `grado ≥ 1`).
- [ ] 10.2 Test de nDCG contra un valor calculado a mano sobre fixture.
- [ ] 10.3 Desglose por origen: recuperación **siempre sobre los 1.168**, agrupación por consulta, recuento por juicio.
- [ ] 10.4 Test de que no existe configuración que restrinja el corpus por `data_origin`.
- [ ] 10.5 `desplazamiento_sintetico@5` y `unjudged@5`, con sus tests.
- [ ] 10.6 Tasa de abstención y **distribución de distancias por grado** (relevantes frente a irrelevantes), con la comprobación de si son separables por un valor único.
- [ ] 10.7 Recuento de juicios cuyo `source_hash` ya no coincide, publicado junto a las métricas.
- [ ] 10.8 Las tres lecturas de la partición de ajuste: global, sólo ajuste, sólo nuevas.

## 11. Latencia y coste

- [ ] 11.1 Recogida de `latency_ms` por etapa desde los logs del orquestador y composición de `p50`/`p95` de recuperación y extremo a extremo.
- [ ] 11.2 Descarte de la primera ejecución y repetición de 3 por consulta.
- [ ] 11.3 Medir la **latencia de la rama léxica dentro del orquestador** y el **efecto del singleton del cliente de embeddings sobre el p95 en frío y en caliente** — los dos pendientes que C21 §12 dejó sin dueño.
- [ ] 11.4 `golden/pricing.yaml` con `as_of` y `source` verificados contra la fuente el día de la corrida; si no es accesible, `as_of: unknown` y coste declarado **no verificado**.
- [ ] 11.5 Coste por consulta por configuración, con cero como valor registrado.

## 12. Runner, informe y persistencia

- [ ] 12.1 `evals/runner.py`: orquesta las configuraciones **en serie** y construye el `Report`, sin importar la persistencia.
- [ ] 12.2 `evals/report.py`: `Report` → Markdown en `evals/results/` y detalle por consulta en `evals/results/runs/<run_id>.jsonl`.
- [ ] 12.3 `evals/repository.py`: sumidero opcional hacia las tres tablas, sólo con `--persist`, incluidas las líneas base sin coste.
- [ ] 12.4 `evals/cli.py`: `uv run evals run --config vX [--persist] [--repeat 3]`.
- [ ] 12.5 Test de que el arnés produce su informe sin base de datos y sin escribir ninguna tabla.
- [ ] 12.6 `api/routers/evals.py` deja de ser stub: sirve desde `ai.eval_run`, orden más reciente primero, lista vacía con 200 si no hay ejecuciones.
- [ ] 12.7 Test de que `openapi.json` sigue byte a byte idéntico tras el cambio del router.

## 13. Medición, veredicto y defaults

- [ ] 13.1 Ejecutar las cinco configuraciones y producir la tabla de ablations v0→v2.
- [ ] 13.2 Barrido **direccional** del peso de la rama vectorial (`wC ≥ 0,33`) y de la profundidad de rama.
- [ ] 13.3 Aplicar la regla de cambio de defaults: delta de nDCG@5 > 0,05, mismo signo en las tres lecturas, ninguna categoría empeorada más de 0,05. **Documentar el resultado se muevan o no.**
- [ ] 13.4 Si algún default se mueve, actualizar `config/settings.py`, la fila del README y añadir el delta `MODIFIED` correspondiente a `hybrid-fusion` sobre el requisito que fija los pesos medidos.
- [ ] 13.5 Comprobar si la distribución de distancias del corpus de productos tiene hueco limpio entre grados, y escribirlo como resultado en cualquiera de los dos sentidos.
- [ ] 13.6 Registrar el número de consultas cuyo grado 2 está en el top-20 pero fuera del top-5, que es el dato que haría decidible el reranking.

## 14. Documentación y cierre

- [ ] 14.1 Informe versionado `evals/results/c24-baselines-<fecha>.md` con la tabla v0→v2, las tres lecturas, la distribución por grado, la curva de escala de CAG y las dos columnas de latencia.
- [ ] 14.2 Informe de implementación en `Documentos/Proyecto Final AIEng/informes/c24-implementation-measurements.md`, con lo que se movió respecto a la exploración.
- [ ] 14.3 `ai-service/README.md`: comando de la CLI, filas de entorno y las **cuatro limitaciones** — sin acuerdo entre anotadores, el etiquetador escribió parte del corpus, conjunto pequeño con ±0,13 sobre la porción real, y coste del prefiltro sin medir.
- [ ] 14.4 Enlazar la HU en `Documentos/epicas.md` (EP17) y marcar C24 como hecho al archivar.
- [ ] 14.5 Suite completa comparada **por nombre de test** contra la línea base de 1.4.
- [ ] 14.6 `openspec validate --all --strict` en `0 failed` antes de archivar.
