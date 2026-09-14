## 1. Puerta de entrada

- [ ] 1.1 Línea base de la suite de `ai-service` por **nombres de test** y no por recuento: `git stash push -u`, `uv run pytest`, guardar los nombres en rojo, `git stash pop`
- [ ] 1.2 `openspec validate --all --strict` en verde antes de tocar nada, y anotar el total de partida
- [ ] 1.3 Comprobar que `evals/routing/cases.yaml` carga y que sus cinco referencias resuelven contra el árbol actual

## 2. Vocabularios y constantes

- [ ] 2.1 Vocabulario cerrado de intención en `assist/constants.py`: los valores de enrutado, más `product_pitch` y `unclassified` intactos
- [ ] 2.2 Vocabulario cerrado de códigos de rechazo, con **códigos distintos** para fuera de dominio y para fuera de catálogo
- [ ] 2.3 Código de aviso nuevo para «el corpus no cubre la pregunta», apilado sobre los dos que ya existen
- [ ] 2.4 `DEFAULT_ROUTER_MODEL`, `ROUTER_TIMEOUT_SECONDS` (2,0, **declarado no calibrado** en el docstring) y `MAX_ROUTER_PROVIDER_CALLS`

## 3. El prompt del clasificador

- [ ] 3.1 Redactar el prompt **desde `enrichment/vocabularies.yaml` y el README del corpus** — los doce tipos de pieza y los nueve materiales
- [ ] 3.2 **Declarar por escrito** en el fichero del prompt que no se han leído los `note` del golden set ni los `why` del fixture para redactarlo
- [ ] 3.3 La consulta viaja en bloque delimitado dentro del mensaje de usuario, nunca concatenada al de sistema

## 4. El clasificador

- [ ] 4.1 Esquema de salida interno (`served`, `index`, `missing_axis`) con `Literal`, de modo que una etiqueta fuera del vocabulario **falle el parseo**
- [ ] 4.2 Cliente del clasificador replicando la costura: temperatura 0, `num_retries: 0`, `response_format`, `complete` inyectable, *timeout* propio
- [ ] 4.3 **Una llamada, sin reparación**: un fallo de parseo es degradación y no violación
- [ ] 4.4 Tres ajustes en `config/settings.py` con la cadena de repliegue de credencial **router → assist → rag**
- [ ] 4.5 Línea de log `stage=router_client` con modelo, *timeout* y `credential=…`, **sin la consulta y sin ninguna clave**
- [ ] 4.6 Fijar los tres ajustes en `canonical_openapi_settings()` para que un valor exportado no se filtre al snapshot

## 5. Cableado en el orquestador

- [ ] 5.1 El enrutador corre **sólo en M1**, y corta **antes** de `retrieve_products`
- [ ] 5.2 M2 no invoca al clasificador — test por introspección, no por lectura
- [ ] 5.3 M3 se marca `both` por construcción y tampoco invoca al clasificador
- [ ] 5.4 Rechazo cortés: sin grupos, `intent` con el veredicto, código de motivo en `warnings[]`, `abstained` en **false**
- [ ] 5.5 *Fail-open* como **rama con test**, nunca un `except` mudo, con su causa en el log
- [ ] 5.6 Techo de **3** llamadas al proveedor comprobado por introspección, y `usage` acumulando las tres

## 6. Repregunta

- [ ] 6.1 Catálogo cerrado de plantillas es-ES en Python, una por eje ausente: tipo de pieza, material, ocasión, precio
- [ ] 6.2 Selección por código desde `missing_axis`, con test de **determinismo** (dos ejecuciones, texto idéntico)
- [ ] 6.3 Sin llamada de generación cuando se emite repregunta

## 7. Guardarraíl determinista de M3

- [ ] 7.1 Cero citas tras el umbral ⇒ código de aviso, leído del resultado ya calculado y **sin llamada adicional**
- [ ] 7.2 Sección de tarea degradada: el argumentario describe la pieza y **no afirma** haber contestado

## 8. Argumentario de la consulta libre

> **Línea de corte declarada.** Si la sesión se desborda, este grupo es lo que sale: M1 vuelve a
> devolver `pitch` vacío —comportamiento actual y con test— y el corte se declara en el informe.

- [ ] 8.1 Forma de *payload* para varios candidatos, distinta de la de una pieza
- [ ] 8.2 Lista blanca numérica sobre ese *payload*, **excluyendo** identificadores internos y *scores* de recuperación
- [ ] 8.3 `prompts/assist/v2.md` con una sección de tarea por ruta, **conservando `v1.md` sin tocar**
- [ ] 8.4 Test fichero↔constante de la versión nueva, y comprobación de que `v1.md` sigue presente e intacto
- [ ] 8.5 Generación en M1 según la ruta decidida, con `prompt_version` reportado

## 9. Contrato

- [ ] 9.1 Descripciones de `intent`, `warnings[]` y `clarification_question` en `api/schemas/assist.py`
- [ ] 9.2 Regenerar `openapi.json` con el perfil canónico
- [ ] 9.3 Verificar el diff **hoja a hoja** aplanando los dos documentos: ningún campo añadido, retirado ni con el tipo cambiado

## 10. Evaluación

- [ ] 10.1 Carga del manifiesto `evals/routing/cases.yaml`, que **falla** si los recuentos declarados no cuadran con los reales — como hace el golden set
- [ ] 10.2 Runner de la matriz de confusión sobre las seis clases
- [ ] 10.3 Publicar las **dos cifras separadas** —rechazo del enrutador y abstención del retriever— con la nota de que no son sumables
- [ ] 10.4 Publicar el **falso positivo sobre `catalog`** como cifra propia, y aplicar el veto: una sola `descripcion-sin-anclaje` silenciada tumba la configuración
- [ ] 10.5 Tasa de rechazo de la puerta numérica en M1 publicada **aparte** de la de M2/M3: no son la misma puerta
- [ ] 10.6 Contraste enrutador ↔ umbral `0,51` sobre las 32 + 5 preguntas, y publicar las discrepancias como hallazgo
- [ ] 10.7 Resultados atados a `run_id`, `git_sha` y versión del prompt, en `evals/results/`

## 11. Cierre

- [ ] 11.1 Comparar la suite **por nombres** contra la línea base de 1.1 — el recuento no vale
- [ ] 11.2 `openspec validate --all --strict` en **0 failed**
- [ ] 11.3 Entrada en `openspec/DEFERRED_TASKS.md` con los cuatro pasos de despliegue, dejando `JPV_ROUTER_TIMEOUT_SECONDS` **fuera** hasta medir el despliegue
- [ ] 11.4 Informe de implementación con las cifras y con **lo que la implementación refute** de estos artefactos
- [ ] 11.5 Documentación: `Documentos/epicas.md`, plan de changes, `ai-service/README.md`, `openspec/config.yaml`
- [ ] 11.6 Anotar en las fichas de C32, C34, C36 y C38 lo que este change les deje escrito
