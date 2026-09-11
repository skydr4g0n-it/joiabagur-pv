## Why

El recuperador híbrido está completo —expansión (C20), fusión RRF de tres listas (C21), prefiltro por punto de venta (C22)— y **ninguna de sus decisiones se tomó con una métrica de relevancia**. Se tomaron con una rúbrica que cuenta aciertos como «tipo de pieza y material correctos», y que el propio informe de C21 recusa: *«`doc_text` lleva líneas canónicas `Tipo:` y `Materiales:`, y la expansión apunta justo ahí; medir "tipo correcto y material correcto" premia por construcción a quien casa esas líneas»*. Bajo ese juez la rama vectorial saca 67 de 120 frente a 107 de la léxica sola: siete puntos de ciento veinte para justificar el proveedor externo, los 170-1707 ms por consulta y el índice HNSW. Los cuatro changes archivados que dependen de esa rúbrica escribieron la misma frase — *«C24 lo re-mide»*.

Y el riesgo dejó de ser teórico el 2026-09-06: en el corpus de conocimiento, el sustituto *offline* de C23 midió que la rama léxica ganaba +6,2 pp de recall y, contra el proveedor real, **el veredicto se invirtió** —93,8 % en las dos configuraciones, sólo mejora el orden— además de dejar un umbral que citaba cuatro de las cinco preguntas fuera de dominio. Un juez con parentesco con una de las partes ya le dio la razón una vez en este sistema. Este change construye el juez imparcial, sin el cual la pregunta central del proyecto —¿la búsqueda semántica mejora lo que la joyería tenía?— no tiene respuesta, y C25 no tiene contra qué calibrar.

## What Changes

- **Golden set de 48 consultas juzgadas y 56 escritas**, versionado en git, con relevancia graduada 0-2, criterio de anotación escrito antes de etiquetar, y una **matriz de trazabilidad comprobada por código** que hace fallar la carga si el conjunto no ataca los pleitos que debe arbitrar.
- **Paquete `jbg_ai/evals/`**: carga y validación del golden set, *pooling* de profundidad adaptativa, métricas, configuraciones, runner, informe y persistencia opcional.
- **Cinco líneas base**: `v0-nombre` (el buscador anterior al trabajo de IA), `v0-fts` (la ruta degradada en español), `v0-cag` (acotado: tokens, coste y curva de escala), `v1-vectorial` y `v2-hibrido`.
- **Tablas `ai.eval_run`, `ai.eval_case` y `ai.eval_result`** mediante **una** revisión de Alembic. La migración fundacional nunca las creó.
- **CLI `uv run evals run --config vX [--persist] [--repeat 3]`** e informe versionado en `ai-service/evals/results/` con la tabla de ablations v0→v2.
- **`GET /v1/evals/runs` deja de ser stub** y sirve las ejecuciones persistidas, **sin mover el `openapi.json` congelado**: la ruta ya está publicada y su stub nombra a este change por escrito.
- **Reproducibilidad**: vectores de consulta congelados y una tupla de procedencia por ejecución que sustituye a la semilla aleatoria que la ficha pedía y que no existe en un pipeline determinista.
- **Desempate determinista** en las dos sentencias de recuperación. **Desviación declarada**: la ficha describe C24 como change de evaluación y esto toca ruta viva. Sin ello, dos ejecuciones idénticas difieren y el arnés deja de detectar regresiones, que es su función principal.
- **Cambio condicional de defaults** en `Settings` (peso de la rama vectorial, profundidad de rama) bajo una regla escrita **antes** de medir. Segunda desviación declarada.
- **No** se recalibra el umbral de distancia: se entrega su distribución por grado de relevancia y la re-fijación queda en C25, cuya ficha ya la reclama.

## Capabilities

### New Capabilities

- `retrieval-evaluation`: el golden set como artefacto versionado y sus invariantes de composición; el *pooling* con profundidad adaptativa y juicios apendables; las métricas y su desglose por origen de dato; las configuraciones de línea base y su fidelidad a las semánticas que replican; la reproducibilidad por procedencia; y la separación entre el informe en git —normativo— y la persistencia en base de datos —opcional—.

### Modified Capabilities

- `vector-retrieval`: la rama vectorial trunca a su profundidad de rama sin una clave de desempate, de modo que ante distancias iguales **qué filas sobreviven al corte no está definido**. Se añade el requisito de orden total determinista.
- `hybrid-fusion`: la rama léxica ordena por `coordination` y `ts_rank`, dos magnitudes con empates frecuentes, y también trunca sin desempate. Mismo requisito. Y si la medición mueve los defaults de fusión bajo la regla acordada, el requisito que los fija cambia de valor.
- `ai-service-api-contracts`: `GET /v1/evals/runs` está especificado hoy como una ruta que devuelve *«una lista determinista de ejecuciones de evaluación»*, es decir un fixture. Pasa a servir ejecuciones reales persistidas, conservando el resto del contrato: sólo bajo perfil de desarrollo, autenticada, y **sin cambio alguno en el `openapi.json`**.

## Impact

**Código nuevo**: `ai-service/src/jbg_ai/evals/` (paquete), `ai-service/evals/golden/` (golden set, criterio, vectores congelados, precios), `ai-service/evals/configs/` (cinco configuraciones), `ai-service/tests/evals/`.

**Código modificado**: `ai-service/src/jbg_ai/retrieval/search.py` (dos claves de desempate), `ai-service/src/jbg_ai/api/routers/evals.py` (deja de ser stub), `ai-service/src/jbg_ai/config/settings.py` (sólo si la regla de defaults se dispara), `ai-service/README.md`.

**Base de datos**: una revisión de Alembic aditiva en el esquema `ai`. Ninguna tabla existente se altera. Ninguna migración de EF Core.

**Contratos**: `ai-service/openapi.json` **byte a byte idéntico**. Ningún cambio en `backend/`, `frontend/`, `terraform/` ni `.github/workflows/`.

**Dependencias del entorno, y son duras**: el *pooling* no se puede construir desde un fichero — hay que ejecutar las configuraciones contra el índice real. Requiere la base levantada con los 1.168 documentos, la clave de embeddings operativa y `SSL_CERT_FILE` configurado. La primera tarea del change es verificarlo y **parar si falla**.

**Aguas abajo**: desbloquea C25 (calibración de pesos contra este golden set y re-fijación del umbral con la distribución que aquí se publica) y C38 (validador anti-alucinación, RAGAS y escenarios de agente, integrados en este mismo runner).
