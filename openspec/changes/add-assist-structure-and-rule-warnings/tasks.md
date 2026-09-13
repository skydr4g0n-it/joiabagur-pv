## 1. Puerta de entrada y línea base

- [ ] 1.1 Medir la línea base de `uv run pytest` en `ai-service/` sobre el árbol limpio (`git stash push -u`, correr, `git stash pop`) y **guardar los nombres de los tests que fallan**, no el recuento. Validación: el fichero de nombres existe y la duración de la pasada queda anotada, porque una pasada corta puede significar que los contenedores no arrancaron.
- [ ] 1.2 Ejecutar `openspec validate --all --strict` y confirmar `0 failed` antes de tocar código. Validación: la salida dice `0 failed`.
- [ ] 1.3 Anotar el `git_sha` de partida y el estado de `ai-service/openapi.json` (hash del fichero) para poder diffear el snapshot después. Validación: los dos valores quedan en el borrador del informe de implementación.

## 2. Los tres spikes, antes de decidir nada

- [ ] 2.1 **Spike 1, dos brazos**: pasar las 72 consultas de `evals/golden/queries.jsonl` por `search_knowledge`, con y sin el filtro de exclusión por documento, contando citas devueltas y abstenciones en cada brazo. Validación: tabla con las dos columnas y el recuento de citas espurias por categoría, escrita antes de fijar el umbral de M1.
- [ ] 2.2 **Spike 2**: comprobar si el vector de consulta de `retrieve_products` es reutilizable por `search_knowledge` — mismo cliente, misma dimensión, misma `model_version_key`. Validación: una afirmación con la evidencia delante, y la costura identificada si es viable.
- [ ] 2.3 **Spike 3**: medir la cardinalidad máxima de familia en `ai.product_document` y fijar el tope del roster. Validación: la cifra máxima observada y el tope elegido, con su holgura.
- [ ] 2.4 Registrar las tres mediciones en el borrador del informe de implementación. Validación: el fichero existe en `Documentos/Proyecto Final AIEng/informes/` con las tres secciones.

## 3. El bloque de contrato

- [ ] 3.1 Añadir `product_id` a `AssistRequest`, hacer `query` opcional y escribir el `model_validator` de «al menos uno», con el mensaje nombrando ambos campos. Validación: test de que una petición sin ninguno de los dos devuelve error de validación nombrando los dos.
- [ ] 3.2 Hacer `AssistGroup.family_id` nulable. Validación: test de que el modelo acepta `None`.
- [ ] 3.3 Añadir `match_reasons: list[str]` a `AssistGroupMember`, reusando el vocabulario de `RetrievalResult`. Validación: test de que el campo existe y por defecto es lista vacía.
- [ ] 3.4 Reformar `Citation`: añadir `citation_id`, `document_title`, `section_title`, `claim_scope`, `doc_type` y `score`; retirar `source`. Validación: test de que los seis campos nuevos son obligatorios salvo los que el diseño declare opcionales, y que `source` ya no existe.
- [ ] 3.5 Añadir `abstained: bool` y `prompt_version: str | None` a `AssistResponse`. Validación: test de que `abstained` es obligatorio y `prompt_version` admite nulo.
- [ ] 3.6 Declarar el **vocabulario cerrado de códigos de aviso** como constante del paquete de assist, con los dos códigos, y documentar en el campo `warnings` que sólo admite miembros de ese vocabulario. Validación: test de que el vocabulario tiene exactamente dos miembros y ninguno contiene espacios.
- [ ] 3.7 Ajustar `assist_sale_stub` al contrato nuevo, **incluyendo un grupo con `family_id` nulo y un solo miembro**, y citas con sus seis campos. Validación: test de que el fixture es determinista entre dos llamadas y de que al menos un grupo tiene familia nula.
- [ ] 3.8 Regenerar `ai-service/openapi.json` con `canonical_openapi_settings()` y **revisar el diff campo a campo** antes de comprometerlo. Validación: `test_openapi_snapshot_is_stable` en verde y el diff revisado sin cambios no intencionados en las otras nueve rutas.

## 4. El roster de familia en el puerto de búsqueda

- [ ] 4.1 Añadir `family_roster(family_id, …)` al protocolo `ProductSearchPort`, con su docstring explicando que lee sólo el esquema del índice y por qué no reutiliza `search`. Validación: el protocolo declara el método y `mypy`/`ruff` pasan.
- [ ] 4.2 Implementar el método en el adaptador SQL sobre `ai.product_document` únicamente, en **una** sentencia, con el tope del spike 3. Validación: test con Testcontainers de que devuelve los miembros de una familia y de que respeta el tope; el test se omite si Docker no está accesible.
- [ ] 4.3 Añadir el método al fake de búsqueda de los tests. Validación: los tests existentes de retrieval siguen pasando con el protocolo ampliado.
- [ ] 4.4 Verificar que el método **no lee el esquema `public`**. Validación: test o inspección que confirme que la sentencia sólo referencia el esquema del índice.

## 5. El filtro de exclusión en la búsqueda de conocimiento

- [ ] 5.1 Añadir el parámetro de exclusión por documento a `search_knowledge` y al protocolo `KnowledgeSearchIndex`, opcional y con comportamiento idéntico cuando está ausente o vacío. Validación: test de que la misma pregunta con exclusión ausente y con exclusión vacía devuelve los mismos fragmentos en el mismo orden.
- [ ] 5.2 Inyectar la cláusula condicional en `compile_vector_sql` **y** en `compile_lexical_sql`, con la misma forma que `_DOC_TYPE_CLAUSE`, sobre la clave primaria del documento. Validación: test de que un documento excluido no aporta fragmentos **por ninguna de las dos ramas**.
- [ ] 5.3 Construir el conjunto de exclusión con `document_id(material_sheet_slug(term))` para las nueve canónicas que la pieza no declara. Validación: test de que para una pieza de un material se excluyen ocho fichas y ninguna más.
- [ ] 5.4 Verificar que **no** se excluyen `faq`, `politica`, `talla`, las fichas de piedras, `material-piezas-mixtas` ni `material-marcajes-y-punzones`. Validación: test explícito por cada uno de esos grupos.
- [ ] 5.5 Confirmar que no hace falta migración ni columna nueva. Validación: `alembic` sin revisión nueva y el diff no toca `migrations/`.

## 6. El paquete `assist/`

- [ ] 6.1 Crear `ai-service/src/jbg_ai/assist/` con su `__init__.py`, `errors.py` y la resolución de modo a partir de los anclajes de la petición. Validación: test de que los tres modos se resuelven correctamente y que la ausencia de ambos anclajes es un error.
- [ ] 6.2 Implementar `intent` estructural: el valor de pieza anclada en M2 y el de sin clasificar en M1 y M3, **sin heurística de palabras clave**. Validación: test de que dos consultas con redacción distinta y los mismos anclajes dan el mismo `intent`.
- [ ] 6.3 Implementar la agrupación por `family_id` con el invariante *familia nula ⇒ un solo miembro*. Validación: tests de familia presente, familia ausente, y de que ningún grupo con familia nula lleva más de un miembro.
- [ ] 6.4 Implementar las dos reglas de aviso, leyendo `size_label` del candidato interno y el recuento del roster. Validación: test de que el aviso de variantes dispara con un miembro que la recuperación **no** devolvió, y de que una familia de uno no lo dispara.
- [ ] 6.5 Verificar que **no** se emite ningún aviso de stock ni ningún `qty_bucket`. Validación: test con una pieza de bucket cero que comprueba la ausencia de los dos códigos de stock y de cualquier bucket en la respuesta.
- [ ] 6.6 Implementar el direccionamiento determinista de M2: lista blanca de secciones parametrizada, tope de materiales parametrizado, sección de piezas mixtas cuando declara dos o más, y **sólo `claim_scope: general`**. Validación: tests de que se citan las fichas de los materiales declarados, de que no entra ninguna sección `establecimiento`, y de que no se hace ninguna llamada a proveedor.
- [ ] 6.7 Implementar la puerta de abstención: no devolver grupos cuando la regla ha saltado, y declararlo en `abstained`, con el valor efectivo recibido **por parámetro**. Validación: tests de consulta abstenida, de consulta contestable, y de que `abstained` está presente en los tres modos con valor `false` en M2.
- [ ] 6.8 Implementar los tres errores de pieza inservible reutilizando el patrón de `source_document`. Validación: tests de pieza desconocida, inactiva y sin embedding, cada uno con su respuesta distinta, y de que ninguno es un 200 con `abstained`.
- [ ] 6.9 Verificar que el paquete **no importa ningún cliente de proveedor**. Validación: test de introspección de imports del módulo.

## 7. Cableado del router

- [ ] 7.1 Sustituir `require_stub_mode` por el despacho real cuando `STUB_MODE=false`, conservando el fixture cuando está activo, y retirar la constante `DELIVERED_BY`. Validación: test de que con stubs apagados la ruta **no** devuelve 501 y con stubs activos sirve el fixture.
- [ ] 7.2 Confirmar que `pos_id` sale del token y nunca del cuerpo, y que la respuesta devuelve el ámbito aplicado. Validación: test con token y cuerpo discrepantes, y test de 401 sin token.
- [ ] 7.3 Emitir `pitch` vacío, `prompt_version` nulo y `usage` a cero. Validación: test de los tres valores con stubs apagados.
- [ ] 7.4 Añadir el log estructurado del modo resuelto, número de grupos, códigos de aviso, `citation_id` devueltos y decisión de abstención, con el `trace_id`. Validación: test de que la línea de log contiene esos campos y **ningún vector**.
- [ ] 7.5 Comprobar que **ningún campo** de la respuesta lleva precio ni stock, sobre la respuesta completa y no sólo sobre el pitch. Validación: test que recorre la respuesta serializada buscando ambos.

## 8. Verificación

- [ ] 8.1 `uv run pytest` completo y **comparación por nombres** contra la línea base de la tarea 1.1. Validación: el conjunto de nombres que fallan es el mismo o menor; cualquier nombre nuevo se investiga antes de continuar.
- [ ] 8.2 `openspec validate --all --strict` en `0 failed`. Validación: la salida lo dice.
- [ ] 8.3 Revisar que los 19 escenarios de la historia tienen un test que los cubre, y anotar los que no. Validación: tabla escenario → test en el informe.
- [ ] 8.4 Confirmar que el diff **no toca** `backend/`, `frontend/`, `terraform/`, `.github/workflows/`, `migrations/`, `enrichment/` ni `prompts/`. Validación: `git diff --stat` revisado.
- [ ] 8.5 Ejecutar la ruta real contra el Postgres local en los tres modos y guardar una respuesta de cada uno como evidencia. Validación: tres respuestas guardadas, con sus citas resolviendo a fichero y encabezado reales.

## 9. Documentación

- [ ] 9.1 Escribir el informe de implementación con las cifras de los tres spikes y **lo que la implementación refute** de la historia o del diseño. Validación: el informe existe y nombra explícitamente lo refutado, o dice que no refutó nada.
- [ ] 9.2 Actualizar `ai-service/README.md`: la ruta deja de ser stub, el filtro de exclusión, el roster y el vocabulario de avisos. Validación: la sección de C30a existe y el recuento de rutas reales está al día.
- [ ] 9.3 Actualizar `Documentos/epicas.md` y el plan de changes con el estado de C30a. Validación: la Épica 15 refleja el cierre y el §2 del plan mueve C30a de pendiente.
- [ ] 9.4 Revisar si las fichas de C34 y C36 necesitan ajuste por algo que la implementación haya movido. Validación: una afirmación explícita de que se revisaron, con o sin cambios.
- [ ] 9.5 Anotar en `CLAUDE.md` la trampa encontrada al validar: **el validador de OpenSpec lee sólo la primera línea física de la descripción de un requisito**, así que un párrafo con ajuste de ancho cuyo `SHALL` caiga en la segunda línea falla con «must contain SHALL or MUST» aunque lo contenga. Validación: la nota existe y dice que las deltas se escriben con la descripción en una sola línea, como las archivadas.
