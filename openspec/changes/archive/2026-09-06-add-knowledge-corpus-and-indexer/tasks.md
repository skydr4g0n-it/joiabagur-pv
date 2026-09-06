## 1. Formato de autoría y andamiaje del corpus

- [x] 1.1 Crear `data/knowledge/` y comprobar con `git check-ignore` que sus ficheros **no** quedan ignorados; no tocar `.gitignore` si no hace falta
- [x] 1.2 Escribir `data/knowledge/README.md` con las siete reglas de autoría: un `# Título` y solo secciones `##`, nada de texto antes de la primera sección, 80-250 palabras por sección con tope duro de 1.200 caracteres, `claim_scope` obligatorio en comentario HTML bajo el encabezado, modo descriptivo y nunca imperativo, prohibición de SKU / producto / precio, y una pregunta de evaluación por documento
- [x] 1.3 Redactar a mano **un documento piloto** (`material-plata`) que sirva de patrón a los ocho prompts, y validarlo contra el chunker en cuanto exista

## 2. Prompts versionados de generación

- [x] 2.1 Crear `ai-service/prompts/knowledge/v1/` siguiendo el patrón de `catalog-synth/` y `enrichment/`
- [x] 2.2 Escribir los ocho prompts de bloque, **uno por bloque y no por documento**, cada uno con: esqueleto exacto de secciones con su `claim_scope`, las siete reglas de autoría **completas y no resumidas**, la evidencia medida que justifica ese bloque, la prohibición de SKU / producto / precio, y la instrucción de devolver **solo ficheros Markdown**
- [x] 2.3 Fijar el reparto de los ocho encargos: (1) materiales frecuentes `plata`/`oro`/`baño de oro`/`latón`/`hilo`; (2) materiales residuales `perla`/`resina`/`acero`/`cuero` + combinaciones y marcajes; (3) piedras; (4) medidas y tallas; (5) uso y entorno; (6) piel y seguridad + regalo; (7) servicio; (8) glosario + Menorca

## 3. Generación y revisión del corpus

- [x] 3.1 Ejecutar el encargo 1 en **subagente o ventana de chat nueva** y revisar los 5 documentos antes de seguir
- [x] 3.2 Encargo 2 (6 documentos), en ventana nueva, revisado al recibirlo
- [x] 3.3 Encargo 3 (3 documentos de piedras: materia orgánica, cuarzos y gemas facetadas, opacas porosas y tratadas), en ventana nueva
- [x] 3.4 Encargo 4 (4 documentos de medidas y tallas), en ventana nueva. Su prompt lleva **la tabla de equivalencia de D16 literal, sin margen para reinterpretarla**: tres tallas españolas enteras por letra, `XXS` 4-6 · `XS` 7-9 · `S` 10-12 · `M` 13-15 · `L` 16-18 · `XL` 19-21 · `XXL` 22-24, con `XXS` y `XXL` marcadas **por encargo**; la regla `circunferencia = talla + 40` como sección `general` y la asignación de letras como sección `establecimiento`; las cuatro reglas de oficio (banda ancha, nudillo, medir al final del día y en verano subir); y la lista de qué aro se puede ajustar y cuál no
- [x] 3.5 Encargo 5 (4 documentos de uso y entorno), en ventana nueva
- [x] 3.6 Encargo 6 (4 documentos de piel, seguridad y regalo), en ventana nueva
- [x] 3.7 Encargo 7 (4 documentos de servicio, **todos `establecimiento`**), en ventana nueva
- [x] 3.8 Encargo 8 (glosario y Menorca), en ventana nueva
- [x] 3.9 Comprobar el recuento final: **32 documentos, ~161 secciones**, `material` 14 · `talla` 4 · `faq` 10 · `politica` 4 · `guion_venta` **0**
- [x] 3.10 Escribir el sidecar `.meta.json` con `generator_version`, `model`, `prompt_version`, `generated_at` y los recuentos por `doc_type` y por `claim_scope`

## 4. Paquete `knowledge/` — carga y troceado

- [x] 4.1 Crear `ai-service/src/jbg_ai/knowledge/` con `__init__.py` y `errors.py` (`KnowledgeCorpusError` que nombra fichero y sección)
- [x] 4.2 `corpus.py`: descubrimiento de ficheros, parseo de título, secciones y marcas, y modelo de datos del documento cargado
- [x] 4.3 `corpus.py`: validaciones — tipo de documento en el vocabulario cerrado, `claim_scope` obligatorio por sección, tope de 1.200 caracteres, rechazo de texto antes de la primera sección, prohibición de SKU / producto / precio, y ausencia de documentos `guion_venta`
- [x] 4.4 `corpus.py`: invariante de cobertura — una ficha por término canónico de `materials` en `vocabularies.yaml`, leído **sin modificar** ese fichero
- [x] 4.5 `chunking.py`: una sección `##` = un chunk, sin solape, `content` con los dos títulos, marca de `claim_scope` retirada antes de componer, y `metadata` con `citation_id`, slugs, títulos, `claim_scope`, `content_hash` y `source_ref` opcional. Función pura: sin sesión, sin proveedor, sin socket

## 5. Paquete `knowledge/` — indexación

- [x] 5.1 `indexer.py`: identidad determinista `uuid5` para documento y para chunk a partir de los slugs; `chunk_index` se escribe pero **no** es identidad de cita
- [x] 5.2 `indexer.py`: clave de versión propia `knowledge/v1`, calculada **en este paquete** y escrita en `embedding_version`. No importar `document_version_key` de C11, que sella `source-text/v1`
- [x] 5.3 `indexer.py`: upsert por documento, borrado de los chunks que la ejecución no produce, y omisión del embedding cuando `content_hash` y `embedding_version` coinciden
- [x] 5.4 `indexer.py`: cliente de embeddings **inyectable**, reutilizando `EmbeddingClient` de C11 sin tocar `indexing/embeddings.py`
- [x] 5.5 Comprobar que ninguna sentencia crea, altera o borra tabla, columna o índice

## 6. Paquete `knowledge/` — búsqueda

- [x] 6.1 `search.py`: rama vectorial k-NN coseno sobre `ai.knowledge_chunk.embedding`, con `<=>` para no desalinear el índice HNSW
- [x] 6.2 `search.py`: rama léxica sobre `knowledge_chunk.tsv`, con la `tsquery` compuesta desde los grupos de `expand_query` de C20, parámetros ligados y sin adyacencia posicional. SQL propio: no tocar `retrieval/search.py`
- [x] 6.3 `search.py`: fusión **importando** `retrieval/fusion.py`, sin reescribir nada y sin leer puntuaciones crudas
- [x] 6.4 `search.py`: umbral de abstención propio — por debajo, cero fragmentos — y filtro por `doc_type` **solo** si el llamante lo pide
- [x] 6.5 `search.py`: resultado con `citation_id`, `claim_scope`, título de documento y de sección, texto y puntuación. Firma con forma de tool, para que C30 la use como `consultar_conocimiento`
- [x] 6.6 Logs `stage=knowledge` con `trace_id`, junto a los ya existentes

## 7. Configuración y CLI

- [x] 7.1 `JPV_KNOWLEDGE_DISTANCE_THRESHOLD` y `JPV_KNOWLEDGE_HYBRID_ENABLED` en `Settings`, con default y con el valor efectivo viajando como **parámetro de la llamada**
- [x] 7.2 Subcomando `python -m jbg_ai.indexing sync-knowledge [--full]` en `indexing/cli.py`, con la misma carga de entorno que `sync` y `sync-pos`
- [x] 7.3 Documentar el comando y los dos ajustes en `ai-service/README.md`
- [x] 7.4 Verificar que `ai-service/openapi.json` queda **sin diff** y que no se ha tocado `canonical_openapi_settings` si los ajustes no entran en el contrato

## 8. Tests

- [x] 8.1 Crear `ai-service/tests/knowledge/`, espejo de `src/jbg_ai/knowledge`, íntegramente *offline*
- [x] 8.2 Chunker: `test_chunker_preserves_section_titles_in_metadata`, marca retirada del contenido, ausencia de solape
- [x] 8.3 Trazabilidad: `test_every_chunk_has_traceable_document_id`, `test_citation_id_resolves_to_a_file_and_a_heading_in_the_corpus`
- [x] 8.4 Identidad: `test_chunk_identity_is_stable_across_reindexing`, `test_inserting_a_section_does_not_repoint_existing_citations`
- [x] 8.5 Validaciones: `test_section_over_the_size_limit_fails_ingestion`, `test_document_with_text_before_first_section_is_rejected`, `test_section_without_claim_scope_is_rejected`, `test_corpus_contains_no_sku_product_or_price`, `test_corpus_contains_no_sales_script_document`
- [x] 8.6 Cobertura y alcance: `test_every_canonical_material_has_exactly_one_sheet`, `test_material_sheet_is_not_product_scoped`, `test_claim_scope_travels_with_the_returned_chunk`
- [x] 8.6b Convención de talla (D16): `test_ring_size_table_is_arithmetically_consistent` (tallas enteras, tramos contiguos y sin solape, `circunferencia = talla + 40` en cada fila), `test_ring_size_table_covers_the_size_vocabulary` (las siete letras, con `XXS` y `XXL` marcadas por encargo), `test_motif_scale_words_are_never_a_ring_fit_label`, y `test_resizing_limits_agree_across_documents` (lo que excluye `tallas-anillos` coincide con las fichas de `baño de oro`, `latón` y `acero` y con `politica-reparaciones-y-ajustes`)
- [x] 8.7 Indexación: `test_reindexing_removes_chunks_no_longer_produced`, `test_unchanged_section_is_not_re_embedded`, y versión de preprocesado propia distinta de la de producto
- [x] 8.8 Búsqueda: `test_knowledge_search_returns_chunk_with_citation_id`, `test_out_of_domain_question_returns_no_citation`, `test_hybrid_disabled_falls_back_to_vector_only`, `test_knowledge_search_makes_no_provider_call_with_injected_fake`
- [x] 8.9 Guardia de congelación: `test_embeddings_module_is_untouched`
- [x] 8.10 `uv run pytest` en verde, sin llamadas reales a LLM, embeddings ni RDS; los tests de base con testcontainers y pgvector

## 9. Medición y cierre

- [x] 9.1 Fixture de ~32 preguntas (una por documento) más 4-5 fuera de dominio con resultado esperado «ninguna cita»
- [x] 9.2 Comando que imprime Recall@3, MRR y tasa de abstención sobre el fixture, **sin usar `ai.eval_run` / `eval_case` / `eval_result`**
- [x] 9.3 Correr vectorial-solo frente a híbrido y **decidir con el número** si la rama léxica se queda; si no mueve nada, retirarla y declararlo
- [x] 9.4 Calibrar `JPV_KNOWLEDGE_DISTANCE_THRESHOLD`: el valor más estricto que mantiene en cero las fuera de dominio sin perder ninguna con respuesta. Sustituir el provisional y anotarlo en `design.md`
- [x] 9.5 Medir la latencia de una consulta de conocimiento en caliente y anotarla para que C30 la herede
- [x] 9.6 Re-medir contra `ai.product_document` con la base levantada y corregir el §2 del informe de exploración donde el proxy de texto se desvíe (`oro`, `perla`, `pequeño`/`grande`/`mediano`)
- [x] 9.7 Informe versionado en `Documentos/Proyecto Final AIEng/informes/` con la mini-medición, la decisión sobre la rama léxica y el umbral calibrado
- [x] 9.8 Enlazar la HU en `Documentos/epicas.md` (EP12) y dejar redactada la limitación del README: corpus sintético, ~16 % de secciones `establecimiento` ilustrativas, verificación de citas estructural y no semántica
- [x] 9.9 Comprobar el diff: sin migración, `openapi.json` sin cambios, y `indexing/embeddings.py`, `enrichment/vocabularies.yaml`, `retrieval/orchestrator.py`, `retrieval/search.py` y `frontend/` intactos
- [x] 9.10 Anotar como verificación posterior —**no bloqueante**— confirmar con el negocio la tabla de tallas de D16 antes de grabar el vídeo de la demo. Si sus tramos son otros, cambia **una** sección de **un** documento, y su marca `establecimiento` ya la señala
- [x] 9.11 `openspec validate --all --strict` en `0 failed`
