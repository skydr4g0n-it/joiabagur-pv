## 1. Puerta de entrada

- [x] 1.1 Verificar que **C22 y C25 están archivados**. Si no lo están, parar: sin la proyección por punto de venta y sin `business_score` calibrado, la mitad del orden no existe
- [x] 1.2 Registrar la **huella del conjunto indexado** y la **versión del golden set** antes de tocar nada, para que la rebanada de evaluación declare contra qué corpus se midió
- [x] 1.3 Medir la **línea base de la suite**: `uv run --system-certs pytest`, guardando los **nombres** de los tests que fallan y **nunca** su recuento (`CLAUDE.md`)
- [x] 1.4 Confirmar sobre el árbol que `ai-service/openapi.json` ya contiene `/v1/retrieval/substitutes` con `SubstitutesRequest`, `SubstituteResult`, `SimilaritySignals` y `SubstitutesResponse`. **Si no los contiene, parar**: el change se apoya en que el contrato no se mueve
- [x] 1.5 Comprobar que todos los documentos activos tienen `embedding` poblado. Si alguno no lo tiene, es un caso del error explícito de la tarea 3.6 y no un fallo del change

## 2. Puerto y consulta

- [x] 2.1 `retrieval/ports.py` — método nuevo para **leer el documento origen**: `piece_type`, `size_label`, `materials`, `style_tags`, `family_id`, `price_band` y si tiene `embedding`. Devuelve la ausencia como resultado y no como excepción, para que el router decida el error
- [x] 2.2 `retrieval/ports.py` — método nuevo para **vecinos por embedding almacenado**, con el filtro duro por `piece_type`, la exclusión de la pieza origen y de `exclude_product_ids`, y el punto de venta entrando **sólo** como `signal_pos_id`. Documentar en el docstring que aquí **no existe** el parámetro que restringe: en sustitutos la disponibilidad nunca elimina
- [x] 2.3 `retrieval/search.py` — sentencia nueva: k-NN contra el embedding de una fila, reutilizando `_SCOPE_CTE` y **`_SIGNAL_JOIN`** (`LEFT JOIN`), nunca `_SCOPE_JOIN`. Conservar el desempate determinista que C24 introdujo, sin el cual dos corridas idénticas difieren
- [x] 2.4 Verificar que la sentencia **no lee el esquema `public`** y que abre **una sola** conexión por petición: el pool está limitado a 5 sin overflow

## 3. Módulo `substitutes.py`

- [x] 3.1 `retrieval/substitutes.py` — **nuevo**. Orquestación de la petición: resolver alcance con `projection.resolve_scope`, leer el documento origen, pedir vecinos, componer el orden y construir la respuesta
- [x] 3.2 Composición del orden: `sim − w_size·[talla distinta] − w_availability·[agotado]`, **todos los términos continuos**. Escribir en el docstring por qué **no se reutiliza `demotion_rank`** — su bloque entero de talla particiona, que es el fallo que C25 midió con la rotación
- [x] 3.3 Término de talla **inerte cuando alguna de las dos piezas no declara talla**, con el comentario que lo justifica: ausencia no es desajuste, y el 54 % de los anillos no tiene `size_label`
- [x] 3.4 Término de disponibilidad **reutilizando `business_score` y `OUT_OF_STOCK_BUCKET`** de `filters.py`, para que la semántica de agotado siga viviendo en un solo sitio
- [x] 3.5 Sobre-recuperación con la misma ventana que `retrieve_products`, y `candidates_returned` declarando lo producido — el contrato dice que `top_k` es la página que .NET quiere **después** de filtrar
- [x] 3.6 Errores: producto origen inexistente, inactivo o sin embedding → **error explícito que nombra la causa**, nunca 200 con lista vacía
- [x] 3.7 `low_confidence` **siempre falso**, con el comentario que remite a la distribución de vecinos más próximos medida en la exploración

## 4. Señales y motivos

- [x] 4.1 `material_overlap` como Jaccard de `materials`; cero cuando alguno de los dos conjuntos está vacío
- [x] 4.2 `style_similarity` como Jaccard de `style_tags`. **Prohibido derivarlo del embedding**: sería una copia de `score` y la segunda definición que diverge
- [x] 4.3 `family_match` verdadero sólo con `family_id` no nulo e igual; `visual_similarity` **null** por diseño, con el comentario que remite al §15.7 del documento de diseño
- [x] 4.4 `match_reasons` — construir la lista legible: relación de talla con el origen (coincide / difiere, nombrando ambas), materiales compartidos, pertenencia a familia, y **la declaración explícita de que no había etiquetas de estilo que comparar** cuando ninguno de los dos las tiene
- [x] 4.5 Comprobar que `match_reasons` no transporta ninguna cifra de precio ni de stock: la autoridad es .NET y el validador del §11.3 rechaza lo contrario

## 5. Ruta y configuración

- [x] 5.1 `api/routers/retrieval.py` — conectar la implementación real y retirar `require_stub_mode` **de esa ruta**, conservando el stub cuando `STUB_MODE` está activo para que los tests de contrato de C02 sigan en verde
- [x] 5.2 Retirar la constante `SUBSTITUTES_DELIVERED_BY` si deja de tener lector; comprobar por búsqueda y no por memoria
- [x] 5.3 `config/settings.py` — añadir el peso de talla como campo **opcional al arranque**, con su valor por defecto y su documentación, y sin tocar `extra="ignore"`
- [x] 5.4 `retrieval/fusion.py` — corregir el docstring que predice *«C26 (substitutes) is the next caller»*: con una sola lista no hay nada que fusionar, y una predicción falsa en el código es deuda

## 6. Evaluación

- [x] 6.1 `evals/golden/queries.jsonl` — añadir `source_product_id` a `q49`–`q52` con sus orígenes resueltos: `SKU13`, `SKU77`, `SKU106` y `SKU159`
- [x] 6.2 Añadir la **quinta consulta, sin familia**, anclada en `SKU102 Anillo caracola`, y retirar su marca de no juzgada junto con la de las cuatro anteriores
- [x] 6.3 Etiquetar las cinco por *pooling*, reutilizando `criterion.md` **sin cambios** —su grado 1 ya está redactado en términos de sustituto— y registrar el criterio aplicado
- [x] 6.4 Camino de ejecución en `evals/` que llame a la tubería de sustitutos **en proceso**, como `execute.py` ya hace con `retrieve_products`
- [x] 6.5 **Barrer el peso de talla** sobre las cinco consultas y publicar el recorrido, no sólo el ganador. Si la diferencia queda bajo el ruido, adoptar `0,05` y decirlo
- [x] 6.6 Informe de la rebanada en `ai-service/evals/results/`, con procedencia completa y la declaración de que mide la calidad del sustituto **dado el producto origen correcto**
- [x] 6.7 Verificar que la **tabla de ablations publicada de C24/C25 no cambia ni una cifra**, ni sus configuraciones ni sus juicios previos

## 7. Tests

- [x] 7.1 `test_never_returns_a_different_piece_type` — con un caso donde el vector puro coloca otro tipo por delante
- [x] 7.2 `test_source_product_never_returned_as_own_substitute`
- [x] 7.3 `test_explicitly_excluded_products_are_not_returned`
- [x] 7.4 `test_no_live_family_member_is_dropped_from_the_result`
- [x] 7.5 `test_family_membership_does_not_force_the_first_position`
- [x] 7.6 `test_same_size_candidate_outranks_same_family_different_size` — caso real `SKU13`
- [x] 7.7 `test_different_size_sibling_stays_inside_the_visible_window` — **el test que impide el atajo**: comprueba que la degradación es suave y no un destierro
- [x] 7.8 `test_size_term_is_inert_when_either_side_declares_no_size`
- [x] 7.9 `test_size_weight_of_zero_reproduces_the_ordering_without_the_term`
- [x] 7.10 `test_material_overlap_increases_similarity_score`
- [x] 7.11 `test_out_of_stock_candidate_is_demoted_and_never_removed`
- [x] 7.12 `test_absent_projection_row_is_not_read_as_zero_stock`
- [x] 7.13 `test_style_similarity_absence_is_declared_in_match_reasons`
- [x] 7.14 `test_visual_similarity_is_null_by_design`
- [x] 7.15 `test_substitutes_never_abstains_and_says_so`
- [x] 7.16 `test_unknown_or_unindexed_source_product_is_an_explicit_error`
- [x] 7.17 `test_no_embedding_provider_call_is_made` — con un doble que levanta al ser invocado
- [x] 7.18 `test_stub_mode_still_serves_the_c02_substitutes_fixture`

## 8. Perímetro y verificación

- [x] 8.1 Ejecutar la suite y comparar los **nombres** de los tests en rojo contra la línea base de 1.3
- [x] 8.2 `test_openapi_snapshot_is_stable` en verde y `ai-service/openapi.json` **sin diff**
- [x] 8.3 Comprobar que **no hay migración** de Alembic ni de EF Core
- [x] 8.4 Comprobar el diff completo contra el punto de nacimiento de la rama: **sin cambios** en `backend/`, `frontend/`, `terraform/` ni `.github/workflows/`
- [x] 8.5 Comprobar que no se ha movido ningún peso calibrado por C25 ni ninguna configuración de evaluación superviviente
- [x] 8.6 `openspec validate --all --strict` con **0 failed**

## 9. Documentación

- [x] 9.1 `ai-service/README.md` — la capacidad nueva, el ajuste nuevo y la declaración de que **no se llama al proveedor**
- [x] 9.2 `ai-service/tests/README.md` — los escenarios nuevos y dónde viven
- [x] 9.3 Informe de implementación en `Documentos/Proyecto Final AIEng/informes/c26-implementation-measurements.md`, con las cifras del barrido y de la rebanada delante
- [x] 9.4 Declarar en el README las **dos limitaciones medidas**: `style_similarity` es prácticamente cero sobre catálogo real (1 de 404), y la medición aísla la calidad del sustituto dado el producto origen correcto
- [x] 9.5 Actualizar la ficha C26 del plan y `Documentos/epicas.md` con lo realmente entregado, incluida cualquier desviación respecto de este `tasks.md`
- [x] 9.6 Anotar en la ficha de **C34** que la exclusión por stock le corresponde, para que quien la implemente no la busque aquí
