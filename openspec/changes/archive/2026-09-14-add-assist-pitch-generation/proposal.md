## Why

C30a dejó `POST /v1/assist/sale` sirviendo estructura real —tres modos, agrupación por familia,
avisos por reglas, citas resolubles con su `claim_scope` y abstención— y dejó el hueco marcado con
un **requisito** y no con una omisión: la capability viva `assist-generation` prohíbe hoy generar
prosa y llamar a un proveedor. Sin esa mitad el Proyecto Final **no tiene capa de generación**, que
es literalmente lo que el rubro nombra, y la garantía anti-alucinación del §11.3 sólo existe en
evaluación: un argumentario que escriba «39,90 €» **literal** no deja ningún placeholder sin
resolver y por tanto **pasa el rechazo de .NET** y llega al operario. Este change entrega el
argumentario y lleva esa garantía **a ejecución**, sobre una base cuya ablación —misma ruta, mismos
candidatos, mismas citas, con prosa y sin ella— sale gratis del propio desdoble.

## What Changes

- **Se invierte el requisito que prohíbe generar.** La capa llama al proveedor en los dos modos
  anclados a pieza y emite argumentario, `prompt_version` y `usage` reales.
- **Prompt versionado** `prompts/assist/v1.md` con `PROMPT_VERSION = "assist/v1"` y test
  fichero↔constante, con reglas invariantes en el mensaje de sistema y bloque de tarea por modo.
- **Salida estructurada con tramo de apoyo**: el modelo declara, por cita usada, el fragmento de su
  propio argumentario que esa cita sostiene. Se verifica en código y **no viaja al cable**.
- **Tres comprobaciones deterministas** —resolución del identificador, correspondencia del tramo, y
  lista blanca numérica **más adyacencia a moneda o existencias**— con **una sola reparación** por
  petición y dos políticas: dura (sin argumentario) y proporcionada (se retira esa cita).
- **No persistencia del argumentario, log incluido.** Se registran trazas, versión, modelo, uso,
  latencia, identificadores de cita, códigos, abstención, longitud y *hash*; **nunca el texto**. La
  excepción declarada es el arnés de evaluación.
- **Degradación en vez de fallo**: proveedor caído, *timeout* o violación dura devuelven la
  respuesta estructurada de C30a con **200**, y la abstención **corta antes** de llamar.
- **BREAKING (comportamiento, no forma):** `citations[]` pasa de ser *lo que la recuperación
  devolvió* a *lo que el argumentario usó* en los modos con prosa. Un consumidor vería menos citas y
  más pertinentes. **No hay consumidor hoy** —`IAiGatewayClient` no tiene método de assist— y por eso
  se hace ahora.
- **El modo de consulta libre no genera**, y queda declarado como alcance de C31 en vez de como
  defecto. `clarification_question` se declara **de C31**, cerrando su orfandad.
- **`openapi.json` se regenera** por **una sola descripción**: `prompt_version` pasa a significar
  «la capa de generación corrió». Ningún campo se añade, se retira ni cambia de tipo.

## Capabilities

### New Capabilities

Ninguna. C30a fijó el nombre `assist-generation` precisamente para que este change **añada
requisitos sobre ella** en vez de crear otra: el nombre cubre el par.

### Modified Capabilities

- `assist-generation`: se invierte *«This capability generates no prose and calls no provider»*; la
  citación pasa a ser *lo que el argumentario usó* con su desenlace degradado; y se añaden la puerta
  numérica, la integridad referencial con su tramo de apoyo, la no persistencia del texto, el prompt
  versionado y la degradación sin fallo.

## Impact

- **`ai-service/src/jbg_ai/assist/`** — módulos nuevos: cliente generativo, esquema de salida
  estructurada, las tres comprobaciones y la política de reparación. Cableado en `orchestrator.py`.
- **`ai-service/prompts/assist/`** — `v1.md` nuevo; la constante vive en `assist/constants.py`.
- **`ai-service/src/jbg_ai/api/schemas/assist.py`** — sólo la **descripción** de `prompt_version`.
- **`ai-service/openapi.json`** — regeneración con el perfil canónico, una descripción de diferencia.
- **`ai-service/evals/`** — runner del barrido de contexto; artefactos en `evals/results/`.
- **`ai-service/tests/`** — `assist/`, `api/` y `evals/`, en árbol espejo.
- **Dependencias**: ninguna nueva. `litellm` y `JPV_RAG_LLM_*` existen desde C09.
- **Datos**: **ninguna migración**, ni Alembic ni EF Core — el argumentario no se persiste, así que
  no necesita tabla.
- **No tocados a propósito**: `backend/`, `frontend/`, `terraform/`, `.github/workflows/`,
  `retrieval/`, `knowledge/` y `enrichment/`.
- **Aguas abajo**: desbloquea **C31** y **C38**. C38 hereda además dos avisos escritos aquí — el
  arnés guarda el objeto de generación completo, y el golden set **no puede evaluar** el argumentario
  porque sus 72 consultas no anclan ninguna pieza.
