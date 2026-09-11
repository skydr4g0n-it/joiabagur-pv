## 1. Entorno y regla escrita antes de medir

- [ ] 1.1 Verificar el entorno y **parar si falla**: base en el 5433 con los 1.168 documentos vivos, `ai.pos_projection` con los 11 puntos de venta drenados, clave de *embeddings* operativa y `SSL_CERT_FILE` configurado
- [ ] 1.2 Confirmar que `HT-ARTRUTX` sigue con surtido cero y excluirlo de la lista de puntos de venta de validación
- [ ] 1.3 Registrar en `design.md` la **regla de decisión reformulada** (D14) con su fecha, antes de ejecutar cualquier barrido: lectura que decide `new`, `tuning` como diagnóstico, margen 0,05, ninguna categoría por debajo de −0,05
- [ ] 1.4 Registrar el **criterio de selección de la forma de la regla de abstención** (D11) con su fecha, antes de mirar la distribución de M1
- [ ] 1.5 Registrar la **función de ganancia operativa** (D3) y su justificación desde la escala de `criterion.md`, antes de calcular ninguna métrica

## 2. Fase 0 — las cuatro mediciones, sin tocar código de ranking

- [ ] 2.1 **M1** — distribución de `min(distancia)` por consulta, separando las 43 contestables de las 5 de fuera de dominio; publicar y declarar si un solo valor las separa
- [ ] 2.2 **M1 (decisión)** — aplicar el criterio de 1.4 y asignar el trabajo del umbral a la **fase A** (escalar, mueve la ventana) o a la **fase D** (regla relativa, no la mueve)
- [ ] 2.3 **M2** — cobertura por consulta y por categoría con el denominador corregido; confirmar que `materiales`, `sinonimos`, `lexico-exacto` y `piedra` dan cobertura 1,00
- [ ] 2.4 **M3** — hermanas de familia en el top-10 por consulta, cruzando los `ranked` del run `d9222333` con `product_document.family_id`; dejar la penalización de variante refutada con una cifra (D16)
- [ ] 2.5 **M4** — reparto de `1-2` frente a `3+` sobre los 6.050 pares asignados; dejar el binario confirmado con una cifra (D17)
- [ ] 2.6 Volcar las cuatro mediciones en `Documentos/Proyecto Final AIEng/informes/c25-implementation-measurements.md`

## 3. Fusión en dos etapas, con la plana conservada

- [ ] 3.1 Verificar que `retrieval/fusion.py` soporta la composición en dos etapas **sin modificar la fórmula**; añadir su test de composición
- [ ] 3.2 `config/settings.py` — reformular `FUSION_DEFAULTS` a pesos **por rama** (`w_lex`, `w_vec`) más el reparto interno léxico fijo, conservando los valores de C21 bajo el modo plano
- [ ] 3.3 `retrieval/orchestrator.py` — etapa 1 (fusión de las dos listas léxicas) y etapa 2 (fusión entre ramas), con `fusion` como perilla y **modo plano seleccionable**
- [ ] 3.4 Test `test_flat_fusion_mode_reproduces_the_published_baseline`: el modo plano con los pesos de C21 reproduce las cifras del informe de C24 sobre la misma versión del golden set
- [ ] 3.5 Test `test_vector_top_hit_reaches_the_top_five_without_lexical_consensus`, con `q06`, `q08` y `q10` como casos
- [ ] 3.6 Test `test_branch_vote_is_independent_of_how_many_of_its_lists_matched`
- [ ] 3.7 Test `test_multi_list_branch_contributes_no_more_candidates_than_a_single_list_one` (los 60 por rama, no 120)
- [ ] 3.8 Verificar que `low_confidence` sigue comportándose como su requisito exige, ahora que la etapa 2 tiene exactamente dos listas

## 4. Regla adaptativa por cobertura

- [ ] 4.1 `retrieval/lexical.py` — expresión del **denominador** de cobertura con `numnode(<fragmento>) > 0`, en la **misma sentencia** que la coordinación
- [ ] 4.2 `retrieval/search.py` — devolver el denominador junto a la coordinación, sin viaje extra al pool
- [ ] 4.3 `retrieval/orchestrator.py` — leer `coordination` del primer *hit* de la lista expandida y aplicar `w_lex × cobertura`, **sin parámetro configurado**
- [ ] 4.4 Test `test_full_coverage_leaves_the_lexical_weight_untouched` — el gate de la predicción falsable de D7
- [ ] 4.5 Test `test_stopword_group_does_not_lower_coverage`, con `sortija de plata` y `anillo de plata y oro`
- [ ] 4.6 Test `test_partial_coverage_lowers_the_lexical_weight`, con `una bicicleta antigua`
- [ ] 4.7 Test `test_empty_typed_list_does_not_by_itself_lower_the_weight`, con `bano de oro`
- [ ] 4.8 Implementar la variante **binaria con `α`** como configuración alternativa, para que entre como segunda fila del barrido

## 5. Señal de punto de venta separada del alcance

- [ ] 5.1 `retrieval/search.py` — separar `scope_pos_id` (`INNER JOIN`, restringe) de `signal_pos_id` (`LEFT JOIN`, sólo lee); añadir `sales_30d` al `SELECT` del CTE
- [ ] 5.2 `retrieval/ports.py` — `sales_30d` en `SearchHit` y `LexicalHit`, con `None` cuando no hay fila de proyección
- [ ] 5.3 **Retirar** el test guardián `test_the_retrieval_path_cannot_read_the_sales_figures` y sustituirlo por el que prohíbe leer `sales_90d` y `last_sale_at`
- [ ] 5.4 `retrieval/orchestrator.py` — los dos parámetros como argumentos independientes, nunca como campo del cuerpo
- [ ] 5.5 Test `test_signal_join_never_restricts_the_candidate_set` — el conjunto de candidatos con señal es idéntico al de sin nada
- [ ] 5.6 Test `test_absent_projection_row_reports_absent_signals_not_zero`
- [ ] 5.7 Test `test_scope_join_still_restricts_when_supplied` — la garantía de C22 intacta

## 6. Score de negocio en el último bloque

- [ ] 6.1 `config/settings.py` — `BUSINESS_DEFAULTS` con el peso de disponibilidad (calibrable) y el de rotación (**fijo y declarado**, con su rationale en el docstring)
- [ ] 6.2 `retrieval/filters.py` — clave lexicográfica de tres componentes más score continuo en la cola; `demote()` conserva el *early return* y no elimina nada
- [ ] 6.3 Test `test_typed_constraint_outranks_the_business_score`
- [ ] 6.4 Test `test_out_of_stock_product_ranks_below_equivalent_in_stock`, **sin escopar** y con la señal por `LEFT JOIN`
- [ ] 6.5 Test `test_rotation_only_breaks_ties` y `test_rotation_cannot_overturn_availability`
- [ ] 6.6 Test `test_weights_load_from_config_not_hardcoded` y `test_zero_weights_restore_the_previous_ordering`
- [ ] 6.7 Test `test_no_stock_quantity_reaches_the_response`
- [ ] 6.8 Test `test_sales_window_is_read_against_the_row_reference_instant`
- [ ] 6.9 Log `stage=signals` con pesos, alcance de lectura, candidatos reordenados y candidatos con señal ausente; sin cantidades exactas y sin vectores

## 7. Métrica operativa y configuraciones

- [ ] 7.1 `evals/metrics.py` — `nDCG@5 operativo` con la ganancia efectiva de D3, publicado junto a la graduada y la binaria
- [ ] 7.2 Test `test_operational_gain_is_a_declared_function_of_grade_and_availability`
- [ ] 7.3 Test `test_operational_metric_does_not_modify_the_judgements`
- [ ] 7.4 `evals/configs.py` — perillas `fusion`, `signal_pos_id` y los pesos de negocio; validación de claves desconocidas conservada
- [ ] 7.5 `evals/configs/v2b-fusion.yaml` — la fusión por rama con adaptativa, **sin** señales de negocio, con su comentario de propósito
- [ ] 7.6 `evals/configs/v3-senales.yaml` — `v2b` más disponibilidad y rotación, con el punto de venta de referencia declarado
- [ ] 7.7 Test `test_baseline_row_is_still_selectable_and_reproducible`

## 8. Barrido en dos fases

- [ ] 8.1 `evals/sweep.py` — rejilla de `ρ` de **una dimensión** en `{0,6 · 0,8 · 0,9 · 0,95 · 1,0 · 1,05 · 1,1 · 1,25}`, con `k` y `depth` barridos juntos
- [ ] 8.2 `evals/sweep.py` — fase `capture`: una recuperación por consulta, persistiendo la ventana de 60 con `qty_bucket`, `sales_30d`, `family_id`, score fusionado, ramas **y la configuración de fusión con la que se capturó**
- [ ] 8.3 `evals/sweep.py` — fase `rescore`: re-puntuado en memoria, que **rechaza** ventanas cuya fusión no coincide con la calibrada
- [ ] 8.4 `evals/sweep.py` — regla de decisión reformulada de D14, leyendo la regla registrada en 1.3
- [ ] 8.5 `evals/cli.py` — subcomandos de las dos fases, documentados en `ai-service/README.md`
- [ ] 8.6 Test `test_rescore_phase_reaches_no_provider_and_no_database`
- [ ] 8.7 Test `test_calibration_sweep_is_reproducible` — ahora estructural
- [ ] 8.8 Test `test_window_captured_under_a_different_fusion_is_refused`
- [ ] 8.9 Test `test_a_weight_that_costs_more_than_the_margin_is_rejected` y `test_a_contaminated_reading_does_not_block_a_change`

## 9. Fase A — fijar la fusión

- [ ] 9.1 Ejecutar el barrido de fusión sobre la rejilla de 8.1, con las variantes adaptativa **continua** y **binaria**
- [ ] 9.2 Aplicar la regla de 1.3 y documentar el veredicto **se mueva o no** el default
- [ ] 9.3 Si M1 situó el umbral aquí, re-fijarlo y registrar que **altera el conjunto de candidatos**
- [ ] 9.4 **Congelar `v2b-fusion`** y registrar su configuración

## 10. Fase B y C — capturar y fijar las señales

- [ ] 10.1 Ejecutar la fase `capture` con la fusión de 9.4 congelada
- [ ] 10.2 Ejecutar la fase `rescore` sobre la rejilla de pesos de negocio, con el objetivo operativo y el guardarraíl de relevancia pura
- [ ] 10.3 Validar los pesos ganadores en **FORNELLS** y **HT-GALDANA**, además de calibrarlos en **MAO-AIR**
- [ ] 10.4 **Congelar `v3-senales`** y registrar su configuración

## 11. Fase D — abstención

- [ ] 11.1 Implementar la forma de regla que M1 seleccionó, en el módulo que le corresponda según su fase
- [ ] 11.2 Test `test_abstention_does_not_fire_on_answerable_queries`
- [ ] 11.3 Test `test_dependency_failure_is_not_disguised_as_an_abstention` y `test_empty_projection_is_not_an_abstention`
- [ ] 11.4 Log `stage=abstain` con la regla, la mejor distancia observada y la decisión; sin vectores
- [ ] 11.5 Publicar, por cada regla candidata, la tasa sobre fuera de dominio **y** el número de contestables que silenció

## 12. Fase E — golden set, re-corrida y publicación

- [ ] 12.1 Ampliar `fuera-de-dominio` de 5 a **15-20** consultas plausibles e imposibles, sin juicios documento a documento
- [ ] 12.2 **Declarar la contaminación que este change crea**: el barrido corre sobre las 48, así que al fijar `ρ` las 40 hoy limpias dejan de serlo para cualquier change posterior. Re-marcar el golden set en consecuencia y registrar en el informe qué lectura queda sin contaminar
- [ ] 12.2b Dejar **al menos una lectura limpia** para C26 y C38: las consultas nuevas de 12.1 no entran en ningún barrido de este change, así que nacen y se conservan como partición no contaminada. Anotar explícitamente que la marca `in_tuning_set` es un hecho histórico y **nunca** una elección — marcar como contaminada una consulta limpia sería falsear la única defensa contra el sobreajuste que este conjunto tiene
- [ ] 12.3 Validación de composición: la carga falla si `fuera-de-dominio` baja del mínimo declarado
- [ ] 12.4 *Pooling* de lo que `v2b` y `v3` promuevan; **juzgar sólo lo nuevo**, agrupando por categoría y con relectura diferida de las dudosas
- [ ] 12.5 Corregir el desfase de un día en `judged_at` que C24 dejó a propósito
- [ ] 12.6 Re-correr **las seis filas** bajo la versión nueva, `v0-cag` incluida, para que la tabla comparte una sola procedencia
- [ ] 12.7 **Re-confirmar** los ganadores de 9.4 y 10.4 contra el titular en la versión nueva — un punto de rejilla, no la rejilla
- [ ] 12.8 Informe versionado en `ai-service/evals/results/` con la tabla v0→v3 de seis filas, las lecturas de D14 con su recuento de saturación, la distribución de D11 y el antes/después de las consultas sin anclaje
- [ ] 12.9 Aplicar el criterio **relativo** de D2 y declarar la brecha contra el absoluto del §11.2 con sus cifras medidas

## 13. Documentación, contrato y cierre

- [ ] 13.1 Verificar que `ai-service/openapi.json` queda **sin diff** y que no hay migración de Alembic
- [ ] 13.2 Verificar que `backend/`, `frontend/`, `terraform/` y `.github/workflows/` quedan **sin diff**
- [ ] 13.3 `ai-service/README.md` — pesos por rama, cobertura, señales, abstención, las dos fases del barrido y las **cuatro limitaciones** a declarar
- [ ] 13.4 `ai-service/tests/README.md` — los tests nuevos y la retirada del guardián de ventas
- [ ] 13.5 Renombrar en comentarios de código las referencias a C25 que lo nombran como sucesor: `retrieval/filters.py`, `retrieval/fusion.py`, `tests/retrieval/test_fusion.py`, `tests/retrieval/test_pos_scope.py`
- [ ] 13.6 Actualizar la **ficha C25** y añadir la entrada fechada del §0 en `Documentos/Proyecto Final AIEng/proyecto-final-plan-changes-openspec.md`, con el renombrado y las dos refutaciones
- [ ] 13.7 Actualizar el **§11.2 del diseño RAG**: `v3-señales` pasa a dos filas y el criterio a relativo
- [ ] 13.8 Actualizar `Documentos/epicas.md` al cerrar (estado de C25 y recuento)
- [ ] 13.9 `uv run pytest` en verde, sin llamadas reales a proveedor ni a RDS
- [ ] 13.10 `openspec validate --all --strict` en **`0 failed`**
- [ ] 13.11 `/opsx:verify` antes de archivar, con atención a las dos refutaciones y al orden de fases
