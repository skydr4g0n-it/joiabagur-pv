## Why

`POST /v1/assist/sale` está en el contrato congelado de `jbg-ai` desde C02 y **sirve un fixture**:
el router responde `501` cuando `STUB_MODE=false` y declara en su propio módulo que la entrega es de
C30. Es lo último que separa al proyecto de tener una capa de venta asistida real, y es el **único
change libre que desbloquea algo** — con él arrancan `C34 → C36` y `C30b → C31 → C32 → C38`.

Y hay una razón de coste para hacerlo **ahora y no después**: el contrato congelado **no puede
servir a su propio consumidor**. `AssistGroup.family_id` es obligatorio y no nulable mientras el
~58 % del catálogo no pertenece a ninguna familia, y `AssistRequest` exige una consulta de texto
mientras C34 sólo expone rutas ancladas a pieza. Hoy `IAiGatewayClient` no tiene método de assist y
C34 y C36 no existen: la ruta tiene **cero consumidores** y renegociar el contrato cuesta cero. A
partir de C34 dejará de costarlo.

Este change entrega **la mitad estructurada** de C30. El argumentario en prosa es C30b, y el corte
no es por tamaño: C34 y C36 dependen de la **forma** de la respuesta, no de la prosa.

## What Changes

- **BREAKING** — **El contrato congelado se mueve, en un solo bloque**, y `openapi.json` se regenera
  con el perfil canónico: `product_id` en la petición con validación de «al menos uno» frente a
  `query`; `AssistGroup.family_id` **nulable** con el invariante *sin familia ⇒ exactamente un
  miembro*; `match_reasons` en el miembro del grupo; `Citation` reformada para llevar el
  identificador resoluble y la **marca de alcance de la afirmación**, retirando el campo libre que
  la sustituía; y `abstained` y `prompt_version` en la respuesta. Sin consumidores hoy, el impacto
  real es cero.
- **Tres modos de asistencia** sobre la misma ruta: consulta libre, pieza sin pregunta, y pieza con
  pregunta. La intención se deriva **estructuralmente**, sin heurística de palabras clave, y declara
  «sin clasificar» donde no puede saberlo — clasificarla es C31 entero.
- **Agrupación por familia** con la etiqueta de variante destacada, más un **listado de miembros de
  familia nuevo en el puerto de búsqueda**, que lee únicamente el esquema del índice. Agrupar opera
  sobre lo recuperado; avisar de que existen variantes necesita conocer a los miembros que **no** se
  recuperaron, y son dos consultas distintas.
- **Avisos calculados por reglas, como vocabulario cerrado de códigos** y no como prosa: existen
  variantes en la familia, y falta la etiqueta de talla. El texto en castellano lo escribe el
  frontend, con el precedente literal del panel de búsqueda asistida.
- **Los dos avisos de stock salen de este change** y pasan a la capa .NET, que es la autoridad sobre
  el stock y la única que lo conoce tras hidratar. Es el segundo caso de la misma forma: la
  exclusión por falta de stock ya migró de C26 a C34 por idéntico motivo.
- **Citas verificables sin invocar ningún modelo.** En el modo de pieza sin pregunta, el contexto se
  direcciona **por clave primaria** sobre una lista blanca de secciones y sólo admite afirmaciones
  de alcance general, porque una de las fichas de material lleva una sección que es un **compromiso
  de la casa** y el documento mismo pide confirmarlo en tienda antes de trasladarlo a un cliente. En
  los modos con pregunta, la búsqueda de conocimiento gana un **filtro asimétrico**: excluye las
  fichas de los materiales que la pieza no declara —nueve fichas que el corpus describe como
  estructuralmente idénticas y por tanto confundibles— y deja pasar todo lo demás, porque un filtro
  general por material cortaría 23 de los 32 documentos y produciría falsa abstención en masa.
- **La abstención se honra y se declara.** La regla relativa ya corre; lo que falta es que esta capa
  no genere cuando ha saltado y lo diga en su propio campo. **No se reutiliza el nombre de la señal
  de consenso entre ramas**, cuyo significado medido está anticorrelacionado con lo que aquí hace
  falta.
- **Ninguna llamada a un proveedor.** El argumentario se emite vacío, sin versión de prompt y con el
  consumo a cero. Eso convierte a C30b en una capa cuyo valor se puede **medir contra esta**, que es
  la ablación que la evaluación pide y que ninguna otra fila de su tabla aporta.
- **El fixture se conserva** para el modo de stubs, ajustado al contrato nuevo y **con un grupo sin
  familia**, para que ningún cliente pueda ignorar el caso que es el 58 % del catálogo.

## Capabilities

### New Capabilities

- `assist-generation`: la capa de asistencia a la venta del servicio de IA — resolución de modo,
  agrupación por familia, avisos derivados de reglas con vocabulario cerrado, citas resolubles con
  su marca de alcance, y la declaración de abstención. Nace con el argumentario vacío a propósito:
  C30b añadirá sus requisitos **sobre esta misma capability** en lugar de crear otra.

### Modified Capabilities

- `ai-service-api-contracts`: el requisito que congela la forma de la asistencia a la venta cambia —
  la petición admite el ancla de pieza, el grupo admite familia ausente, el miembro expone sus
  razones de coincidencia, la citación lleva identificador resoluble y marca de alcance, y la
  respuesta declara abstención y versión de prompt. Cambia también el requisito de que la ruta
  responda `501` sin implementación, porque deja de tenerla pendiente.
- `knowledge-corpus`: la búsqueda de conocimiento admite **excluir documentos concretos** por su
  identidad, y se declara el direccionamiento **determinista por fragmento** que el modo de pieza
  usa en lugar de buscar. Ninguna de las dos cosas existía.
- `retrieval-abstention`: la decisión de la regla, que hoy sólo vive en la respuesta de recuperación,
  **se propaga al camino de asistencia y se declara allí**, con el valor efectivo viajando por
  parámetro para que el arnés pueda barrer configuraciones en un proceso.

## Impact

- **`ai-service/src/jbg_ai/assist/`** — paquete nuevo. Es la zona del change y hoy no existe.
- **`ai-service/src/jbg_ai/api/`** — modelos de petición y respuesta, router y fixture.
- **`ai-service/src/jbg_ai/retrieval/`** — un método nuevo en el puerto de búsqueda y su
  implementación sobre el esquema del índice. El orquestador se **consume, no se modifica**.
- **`ai-service/src/jbg_ai/knowledge/`** — un parámetro nuevo en la búsqueda y en su protocolo de
  índice, con la cláusula correspondiente en las dos sentencias.
- **`ai-service/openapi.json`** — se regenera. Es el tercer movimiento del contrato desde que se
  congeló, tras los dos de las rutas de familias.
- **`ai-service/tests/`** — árbol espejo: `assist/` nuevo, más ampliaciones en `api/`, `knowledge/`
  y `retrieval/`.
- **Sin migración**, ni de Alembic ni de EF Core: el listado de miembros lee una tabla existente y
  la exclusión de documentos opera sobre una clave primaria ya derivable.
- **Sin cambios en `backend/` ni en `frontend/`.** La superficie de operario —el parámetro de
  pregunta en la API .NET y la caja en la tarjeta— es de C34 y C36, y queda anotada en sus fichas.
- **Sin claves ni ajustes nuevos**, y sin una sola llamada a proveedor de modelos o de *embeddings*
  que no estuviera ya en la recuperación.
- **Aguas abajo**: desbloquea C30b y C34, y con C34 a C36 y C38. Deja además medio construidas dos
  de las seis herramientas del agente de C32.
