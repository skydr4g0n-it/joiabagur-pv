## Why

El sistema tiene **un solo índice**. `ai.product_document` responde a «enséñame anillos de plata» y no puede responder a «¿este anillo se puede mojar?», porque esa respuesta no vive en ningún producto: vive en el conocimiento comercial general de la joyería, que hoy **no existe en el sistema**. El §5 del diseño ya separó los dos problemas — el catálogo no se trocea, el conocimiento sí, *«y es lo que permite citas verificables»* sin violar la decisión 4 de la revisión, que prohíbe el conocimiento por producto.

C05 dejó creadas `ai.knowledge_document` y `ai.knowledge_chunk` con su forma final, y **ningún código las escribe ni las lee**. C21 dejó el módulo de fusión puro, con un docstring que nombra a C23 como importador futuro. C20 dejó una expansión de consulta cuyos grupos son, precisamente, el vocabulario de materiales y piedras de este corpus. Faltan las dos mitades que nadie ha hecho: **el contenido y el camino de ida y vuelta hasta él**. Sin ellas, C30 no tiene nada que citar, y con él se queda parada toda la rama de generación `C30 → C31 → C32 → C38 → C39`.

## What Changes

- **Corpus de conocimiento**: 32 documentos Markdown versionados en `data/knowledge/`, ~161 secciones, redactados con asistencia de un LLM y revisados a mano. Cubre materiales (una ficha por término canónico del vocabulario de enriquecimiento), combinaciones y marcajes, piedras, medidas y tallas, uso y entorno, piel y seguridad, servicio, regalo, glosario, y el origen menorquín de las colecciones.
- **`claim_scope` obligatorio por sección**, con dos valores: `general` (comprobable fuera de la joyería) y `establecimiento` (compromiso de la casa, hoy ilustrativo). Viaja con cada fragmento recuperado y gobierna cómo se presenta la cita.
- **Cero documentos `guion_venta`**, de los cinco tipos que el esquema admite. No es un corte de alcance: un guion es texto imperativo, y un chunk imperativo dentro de un prompt es indistinguible de una instrucción — haría del propio corpus una superficie de inyección. El tono comercial se lleva al prompt versionado.
- **Troceado por secciones**: una sección `##` = un chunk, sin solape, con el título del documento y el de la sección dentro del contenido indexado. Una sección que pasa del tope **falla la ingesta** en lugar de trocearse sola.
- **Identidad determinista del chunk**, derivada del par documento-sección, más un identificador de cita legible. La cita resuelve, localiza y abre el fichero del repositorio; reindexar no la rompe.
- **Indexación idempotente** en las dos tablas existentes, reutilizando el cliente de embeddings de C11 **sin modificarlo**, sin re-embeber lo que no cambió, y borrando los fragmentos que el corpus ya no produce.
- **Búsqueda de conocimiento** como función de librería —sin ruta HTTP—, con rama vectorial y rama léxica fusionadas por RRF **importando** el módulo de C21, y umbral de abstención propio.
- **CLI** de sincronización, junto a las dos que ya existen.
- **Mini-medición propia** de ~32 preguntas más un grupo fuera de dominio, sin usar las tablas de evaluación que crea C24.
- **Ocho prompts versionados**, uno por bloque de generación del corpus.
- **Sin cambios que rompan nada**: ninguna migración, ninguna ruta nueva, `openapi.json` sin diff, ningún contrato REST afectado.

## Capabilities

### New Capabilities
- `knowledge-corpus`: el segundo índice del sistema — forma y validación del corpus de conocimiento general, troceado por secciones con identidad determinista, alcance de cada afirmación declarado por sección, indexación idempotente con reutilización del cliente de embeddings existente, y búsqueda híbrida que devuelve fragmentos con citas resolubles y con abstención propia.

### Modified Capabilities
Ninguna.

`ai-vector-schema` **no** cambia y no necesita delta: ya especifica el esquema y los índices de `ai.knowledge_document` y `ai.knowledge_chunk` —cascada al borrar, unicidad de `(document_id, chunk_index)`, HNSW con clase de operador coseno, GIN sobre el vector de texto completo y sobre el documento de metadatos, columna generada en español, y la prohibición de acotar el conocimiento a un producto—, y este change **consume** esas garantías sin alterarlas. `hybrid-fusion` y `query-expansion` se importan tal cual: sus requisitos ya declaran que la fusión es pura y sin dominio y que la expansión devuelve grupos, no una consulta reescrita, así que un segundo consumidor no mueve ninguno de sus MUST.

## Impact

- **Nuevo**: `data/knowledge/` (corpus y su guía de autoría), `ai-service/src/jbg_ai/knowledge/` (paquete propio), `ai-service/prompts/knowledge/`, `ai-service/tests/knowledge/`, fixture de la mini-medición.
- **Modificado**: `ai-service/src/jbg_ai/indexing/cli.py` (un subcomando), `ai-service/src/jbg_ai/config/settings.py` (dos ajustes con default), `ai-service/README.md`, `Documentos/epicas.md`.
- **Consumido sin tocar**: `retrieval/fusion.py` (C21), `retrieval/synonyms.py` (C20), `indexing/embeddings.py` (C11, **congelado**: su propio docstring se lo prohíbe a este change), y las dos tablas de C05.
- **Sin impacto**: `backend/`, `frontend/`, `terraform/`, `.github/workflows/`, `ai-service/openapi.json`, migraciones de Alembic y de EF Core.
- **Desbloquea**: C30, y con él la rama de generación completa. **No** está en la cadena crítica `C21 → C24 → C25 → C26 → C34 → C36`.
- **Riesgo declarado**: el corpus es sintético —los textos comerciales que el §8.1 daba como «a pedir al negocio» nunca llegaron—, y la verificación de citas es estructural, no semántica. Se mitiga con `claim_scope` por sección y con una limitación explícita en el README; no desaparece.
