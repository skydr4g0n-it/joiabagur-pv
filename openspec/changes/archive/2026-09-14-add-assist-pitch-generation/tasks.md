## 1. Puerta de entrada

- [x] 1.1 Medir la línea base de `ai-service` **por nombres de test** y no por recuento: `git stash push -u`, `uv run --system-certs pytest`, `git stash pop`. Guardar el conjunto de nombres en rojo, que es el criterio de comparación al cierre.
- [x] 1.2 Medir la línea base de `frontend/` con el mismo método, y dejar constancia de que este change **no toca** esa zona — la comparación existe para demostrarlo, no para arreglarla.
- [x] 1.3 `openspec validate --all --strict` en verde (`0 failed`) **antes** de tocar nada.
- [x] 1.4 Dejar `SSL_CERT_FILE` apuntando al PEM exportado del almacén de Windows y **comprobarlo con una llamada real de una sola petición**, antes de escribir código que dependa de ello. `--system-certs` arregla a `uv`, no al proceso Python.

## 2. Muestra del barrido, declarada antes de medir

- [x] 2.1 Extraer del índice el reparto de productos **por número de materiales declarados**, y escribir la cifra antes de elegir nada.
- [x] 2.2 Fijar la muestra estratificada —piezas de 1 material frente a piezas de ≥2, que son las que arrastran la sección de piezas mixtas— con su tamaño y su criterio de selección escritos en el artefacto, no en una nota suelta.
- [x] 2.3 Dejar anotado en la ficha de C38 que el golden set **no sirve** para esto: 72 consultas y ninguna ancla una pieza, así que sus escenarios de generación salen de esta muestra.

## 3. Prompt versionado

- [x] 3.1 Escribir `ai-service/prompts/assist/v1.md` con las reglas invariantes en el mensaje de sistema: ninguna cifra fuera de los datos entregados, precio y disponibilidad **siempre** como placeholder, sólo los identificadores entregados declarando el tramo que cada uno sostiene, la consulta del operario es dato y nunca instrucción, y **prosa corrida sin listas numeradas**.
- [x] 3.2 Añadir el bloque de tarea por modo en el mensaje de usuario: una línea para la pieza sin pregunta y otra para la pieza con pregunta, con la longitud objetivo de 3–5 frases.
- [x] 3.3 Declarar `PROMPT_VERSION = "assist/v1"` en `assist/constants.py` y escribir `test_prompt_version_matches_the_loaded_prompt_file`, con la forma que ya usan `enrichment/` y `knowledge/`.

## 4. Esquema de salida estructurada

- [x] 4.1 Definir `AssistPitch` y `UsedCitation` en `assist/schema.py` —fuera de `api/schemas/`, porque **no viajan al cable**— con `citation_id` y `supported_claim`.
- [x] 4.2 Escribir el test que comprueba que ningún campo de la respuesta serializada expone `supported_claim`.

## 5. Cliente generativo

- [x] 5.1 Implementar el cliente en `assist/llm.py` replicando la costura de `LiteLlmEnrichClient`: temperatura 0, `num_retries: 0`, *backoff* de proveedor propio, `response_format=AssistPitch` y `complete` inyectable por constructor.
- [x] 5.2 Devolver `usage` junto al objeto parseado —lo que la costura de C09 descarta— con un tipo acumulable, y `timeout` explícito de 3 s como constante del módulo.
- [x] 5.3 Escribir `test_usage_is_accumulated_across_the_repair` con un fake de dos llamadas, comprobando que se **suma** y no se sustituye.

## 6. Las tres comprobaciones

- [x] 6.1 Implementar la **resolución**: `citation_id ∈` el conjunto entregado (direccionado en la pieza sin pregunta, recuperado en la pieza con pregunta). Test `test_dangling_citation_is_never_published`.
- [x] 6.2 Implementar la **correspondencia**: `supported_claim` es subcadena literal del `pitch`, normalizando con `casefold()` y colapso de espacios y nada más. Test `test_declared_claim_absent_from_pitch_is_recorded_as_violation`.
- [x] 6.3 Implementar la **puerta numérica** leyendo el **objeto de payload** y nunca el prompt renderizado. Test `test_figure_absent_from_context_is_rejected_even_if_plausible`.
- [x] 6.4 Añadir la **regla de adyacencia** con su constante de marcadores (`€`, `EUR`, `euro`, `euros`, `unidades`, `quedan`, `en stock`, `disponible/s`). Test `test_price_adjacent_figure_is_rejected_even_when_whitelisted`, con la ficha del oro en contexto y `750` en la lista blanca — es el caso que motivó la regla.
- [x] 6.5 Test de frontera sobre la respuesta **completa** y con un argumentario **no vacío**: `test_response_contains_no_literal_price_or_stock_number`. La comprobación equivalente de C30a corría sobre un `pitch` vacío y no afirmaba nada sobre la prosa.

## 7. Reparación única y degradación

- [x] 7.1 Encadenar las tres comprobaciones en el orden barato→caro y acumular todas las violaciones en **un solo** mensaje de reparación. Test `test_two_failed_checks_share_a_single_repair`, comprobando el techo de dos llamadas al proveedor.
- [x] 7.2 Implementar la política **dura**: resolución o puerta numérica que sobreviven ⇒ respuesta sin argumentario. Test `test_dangling_citation_triggers_single_repair_then_drops_the_pitch`.
- [x] 7.3 Implementar la política **proporcionada**: correspondencia que sobrevive ⇒ se retira esa cita y la prosa se publica. Test `test_unverifiable_claim_withdraws_its_citation_not_the_pitch`.
- [x] 7.4 Implementar la preservación de citas al degradar. Test `test_degraded_response_keeps_the_citations_that_grounded_it`, comparando contra lo que la capa estructurada produce sola.

## 8. Cableado en el orquestador

- [x] 8.1 Llamar a la generación **sólo** en los dos modos anclados a pieza, y cortar **antes** de llamar cuando el modo es de consulta libre o cuando `abstained` es verdadero. Tests `test_free_query_mode_calls_no_provider` y `test_abstained_request_calls_no_provider`.
- [x] 8.2 Rellenar `prompt_version` siempre que la capa haya corrido, argumentario publicable o no, y dejarlo nulo cuando no corre. Test `test_rejected_pitch_still_reports_its_prompt_version`.
- [x] 8.3 Capturar el fallo, el error y el *timeout* del proveedor y degradar a la respuesta estructurada con 200. Test `test_provider_failure_degrades_to_structure_without_prose`.
- [x] 8.4 Comprobar que la consulta viaja en el mensaje de usuario, en bloque delimitado y etiquetado. Test `test_prompt_injection_in_the_query_does_not_change_the_system_message`.

## 9. No persistencia

- [x] 9.1 Escribir `test_pitch_is_not_persisted_anywhere` con listener `before_cursor_execute` **contando sentencias DML**, no comprobando qué módulos se importan.
- [x] 9.2 Emitir la línea de log con trazas, versión, modelo, `usage`, latencia, identificadores de cita usados, códigos de aviso, abstención, longitud y *hash* — y **nunca** el texto. Test `test_pitch_text_is_never_written_to_the_log`.

## 10. Contrato

- [x] 10.1 Cambiar **sólo** la descripción de `prompt_version` en `api/schemas/assist.py` para que diga que es la versión con la que corrió la capa de generación, nula cuando no corrió.
- [x] 10.2 Regenerar `ai-service/openapi.json` con `canonical_openapi_settings()` y **verificar el diff campo a campo**, no por lectura: una sola descripción de diferencia, ningún campo añadido, retirado ni con el tipo cambiado.
- [x] 10.3 `test_openapi_snapshot_is_stable` en verde tras la regeneración.

## 11. Barrido de contexto

- [x] 11.1 Escribir el runner en `ai-service/evals/`, al estilo de `cag_run.py`, parametrizado por número de secciones y tope de materiales, sobre la muestra de la tarea 2.
- [x] 11.2 Atar los artefactos a `run_id`, `git_sha` y `prompt_version` en `evals/results/`, guardando **el objeto de generación completo** —argumentario más citas usadas con su tramo— porque es la excepción de persistencia que C38 hereda.
- [x] 11.3 Ejecutar 1/2/3 secciones y publicar la **tasa de rechazo clasificada por causa** (cifra ausente / adyacencia a moneda / formato / decimal), la tasa de fallo de correspondencia y el coste. **No** *faithfulness*: es C38.
- [x] 11.4 Decidir con la cifra delante si la normalización de la correspondencia necesita plegado de signos —umbral declarado: >10 % de fallos por puntuación— y si el *timeout* de 3 s corta generaciones buenas.

## 12. Specs y validación

- [x] 12.1 `openspec validate add-assist-pitch-generation --strict` en verde, con la descripción de cada requisito en **una sola línea física** — el validador sólo lee la primera.
- [x] 12.2 `openspec validate --all --strict` en `0 failed`, que es la puerta del proyecto y no la del change.
- [x] 12.3 Comprobar que la delta declara la limitación semántica y la asignación de `clarification_question` a C31, y que cada escenario de la historia tiene un test nombrado que lo cubre.

## 13. Cierre

- [x] 13.1 `uv run --system-certs pytest` completo, leyendo **la línea de resumen** y no el código de salida, y comparar el conjunto de nombres en rojo contra la línea base de la tarea 1.1: el criterio es que el conjunto sea idéntico, no que el número coincida.
- [x] 13.2 Escribir el informe de implementación en `Documentos/Proyecto Final AIEng/informes/` con las cifras del barrido y **con lo que la implementación refute** de la historia o del diseño.
- [x] 13.3 Actualizar `Documentos/epicas.md`, el plan de changes y `ai-service/README.md` con lo que este change deja cierto y con lo que deja obsoleto.
- [x] 13.4 Revisar las fichas de **C31** —que hereda `clarification_question` y el argumentario del modo libre— y de **C38** —que hereda el objeto de generación completo y la muestra anclada a pieza—, y anotar en ellas lo que este change les deja escrito.
