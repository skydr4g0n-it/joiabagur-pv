# HU-AIENG-002: Contratos congelados y autenticación de servicio de `jbg-ai`

## Formato estándar

Como **desarrollador del proyecto**, quiero **disponer de los contratos HTTP de `jbg-ai` congelados (modelos Pydantic, stubs deterministas, JWT interno HS256 y snapshot OpenAPI versionado)** **para** **que .NET y Python avancen en paralelo sin esperar a la lógica real de recuperación, enriquecimiento o indexación**.

---

## Descripción

Segunda pieza de la Ola 0 del Proyecto Final de IA (change OpenSpec `add-ai-service-contracts-and-auth` / C02). Sobre el esqueleto entregado en [HU-AIENG-001](HU-AIENG-001.md), congela la frontera Python ↔ .NET: routers de dominio bajo `/v1/`, modelos de request/response completos, stubs tras `STUB_MODE`, validación del JWT interno y `ai-service/openapi.json` versionado con test de snapshot.

El valor no es de usuario final —esta historia no entrega pantalla— sino de **desbloqueo**: sin contrato congelado, el cliente tipado .NET (C03) y el slice vertical (C14–C16) no pueden avanzar, y las dos personas del PF se bloquean mutuamente durante semanas. La regla de frontera que se materializa aquí es la del diseño: *Python calcula parecidos y redacta; .NET calcula números y decide* (diseño v3 §6.2).

**Alcance de esta historia (sí):**

- Routers `retrieval`, `assist`, `inventory`, `index`, `enrich` y `evals`, con request/response Pydantic completos.
- Campos de contrato v3: `materials[]` como lista, `family_id` / `variant_label`, y sobre-recuperación (`top_k` frente a `candidates_returned`).
- Endpoints congelados (todos internos; JWT salvo `/health`):
  `POST /v1/retrieval/products`, `POST /v1/retrieval/substitutes`,
  `POST /v1/assist/sale`, `POST /v1/inventory/propose`,
  `POST /v1/enrich/products`, `POST /v1/index/sync`, `GET /v1/index/status`,
  `GET /v1/evals/runs` (solo perfil de desarrollo).
- Stubs deterministas cuando `STUB_MODE=true`, sin LLM, sin embeddings y sin base de datos.
- Dependencia FastAPI que valida el JWT HS256 y extrae `user_id` / `role` / `pos_id` / `trace_id`; **el body no manda** sobre el token.
- `GET /health` sigue público y sin cambios de contrato respecto a C01.
- OpenAPI exportado a `ai-service/openapi.json` con test de snapshot que rompe ante deriva de contrato.
- Tests unitarios y de smoke con `TestClient`, sin llamadas a LLM ni a RDS.

**Fuera de alcance (no):**

- Lógica real de recuperación, enriquecimiento, indexación o bucles agénticos (C09, C13, C14, C30…). Los stubs se retiran ruta a ruta en changes posteriores.
- Emisión y firma del JWT desde .NET y cliente tipado con Polly → C03.
- `POST /v1/retrieval/complementary` y `POST /v1/families/suggest` → negociación de OpenAPI en changes posteriores.
- Esquema `ai`, extensión `vector`, Alembic y acceso a base de datos → C05.
- Escritura o lectura SQL sobre el esquema `public` (prohibida por diseño para el rol de Python).
- Despliegue a producción, SSM, nginx y health enriquecido → C17.

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Fuente del contrato | Reconstruir desde 3devs §6.8 más los deltas v3 (`materials[]`, familias, sobre-recuperación, `inventory/propose`). El plan C02 cita un "§6.8" que en el diseño v3 no existe: v3 termina en §6.4. |
| Autoridad del contrato | El snapshot `openapi.json` y la spec del change mandan sobre la prosa del diseño mientras no se sincronice el documento. |
| Autenticación | JWT interno HS256 con `PyJWT`; secreto en settings y en Compose para local; claims `user_id`, `role`, `pos_id`, `trace_id`. |
| Scope | El `pos_id` y el `role` del token prevalecen siempre sobre el body. El `pos_id` opcional del request se acepta por compatibilidad de OpenAPI pero se ignora. |
| `trace_id` | Se prefiere el claim del JWT; si no viene, se mantiene el comportamiento del `TraceIdMiddleware` de C01 (header `X-Trace-Id` o generación). |
| Sobre-recuperación | Stub de `retrieval/products`: `min(top_k × 3, 60)` candidatos, expuestos en `candidates_returned`. `top_k` sigue siendo el tamaño de página que .NET quiere **después** de hidratar. |
| Stubs | `STUB_MODE` por defecto `true` en local y test. Si es `false` y no hay implementación real todavía, el endpoint responde HTTP 501. |
| Endpoint de evals | `GET /v1/evals/runs` se monta solo con perfil de desarrollo. El snapshot OpenAPI se genera con ese perfil canónico, documentado en el README, para que sea determinista. |
| Cifras en el texto generado | El `pitch` del stub emite `{{price}}` y `{{stock}}` como placeholders; Python nunca inventa precio ni stock (diseño v3 §7.7). |
| Librería JWT | `PyJWT`, descartado `python-jose` por mantenimiento más débil. |

**Referencias:**
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.1–6.4 frontera y seguridad, §7.6 sobre-recuperación, §7.7 generación y placeholders),
[proyecto-final-diseno-rag-joiabagur-3devs.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur-3devs.md) (§6.8 tabla de contratos),
[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C02),
[HU-AIENG-001.md](HU-AIENG-001.md),
change OpenSpec `openspec/changes/add-ai-service-contracts-and-auth/` y su ticket técnico.

---

## Criterios de Aceptación

### Escenario 1: El stub de recuperación cumple el schema publicado
**Dado que** `STUB_MODE` está activo y el cliente presenta un JWT válido  
**Cuando** se invoca `POST /v1/retrieval/products` con un body válido (`query`, `top_k`, `filters`)  
**Entonces** la respuesta es HTTP 200  
**Y** el cuerpo valida contra el schema de respuesta de recuperación  
**Y** cada resultado incluye `materials` como lista, más `family_id` y `variant_label` (nulos cuando se desconocen)  
**Y** no se realiza ninguna llamada a LLM, a embeddings ni a base de datos  

### Escenario 2: La sobre-recuperación es observable
**Dado que** `STUB_MODE` está activo  
**Cuando** se invoca `POST /v1/retrieval/products` con `top_k = 5`  
**Entonces** `candidates_returned` es 15  
**Y** la lista `results` tiene longitud 15  

### Escenario 3: La sobre-recuperación respeta el tope de 60
**Dado que** `STUB_MODE` está activo  
**Cuando** se invoca `POST /v1/retrieval/products` con `top_k = 30`  
**Entonces** `candidates_returned` es 60  
**Y** la lista `results` tiene longitud 60  

### Escenario 4: La asistencia de venta agrupa por familia
**Dado que** `STUB_MODE` está activo y el cliente está autenticado  
**Cuando** se invoca `POST /v1/assist/sale` con un body válido  
**Entonces** la respuesta incluye `groups[]`, cada uno asociado a un `family_id`  
**Y** los miembros de cada grupo exponen `variant_label`  
**Y** el `pitch` devuelto contiene los placeholders `{{price}}` y `{{stock}}` sin resolver  

### Escenario 5: Sin token se rechaza
**Dado que** el servicio está arrancado  
**Cuando** se invoca cualquier endpoint `/v1/*` sin cabecera `Authorization: Bearer`  
**Entonces** la respuesta es HTTP 401  

### Escenario 6: Token inválido se rechaza
**Dado que** el servicio está arrancado  
**Cuando** se invoca un endpoint `/v1/*` con un token mal firmado, caducado o con claims obligatorios ausentes  
**Entonces** la respuesta es HTTP 401  
**Y** el cuerpo no revela detalle del secreto ni de la causa exacta del fallo  

### Escenario 7: El `pos_id` del token manda sobre el body
**Dado que** el JWT lleva `pos_id = B` y el body envía `pos_id = A`, con A ≠ B  
**Cuando** se invoca `POST /v1/retrieval/products`  
**Entonces** el scope efectivo aplicado por el handler es B  
**Y** la petición no falla por el valor enviado en el body  

### Escenario 8: Health sigue público
**Dado que** el servicio está arrancado  
**Cuando** se invoca `GET /health` sin token  
**Entonces** la respuesta es HTTP 200 con estado OK y la versión del servicio  

### Escenario 9: El snapshot de OpenAPI es estable y detecta deriva
**Dado que** existe `ai-service/openapi.json` versionado en el repositorio  
**Cuando** se ejecuta `test_openapi_snapshot_is_stable`  
**Entonces** el OpenAPI vivo coincide con el fichero committeado  
**Y** si se modifica un modelo Pydantic o la firma de una ruta sin regenerar el snapshot, el test falla  

### Escenario 10: Falta el secreto de firma y el arranque falla de inmediato
**Dado que** la aplicación monta los routers de dominio  
**Cuando** `JWT_SECRET` falta o está vacío  
**Entonces** la carga de configuración falla con un error que identifica la variable ausente  
**Y** no queda un servicio "a medias" aceptando peticiones  

### Escenario 11: Con los stubs desactivados y sin implementación real se responde 501
**Dado que** `STUB_MODE` es `false`  
**Cuando** se invoca un endpoint `/v1/*` cuya lógica real aún no existe  
**Entonces** la respuesta es HTTP 501  
**Y** el mensaje indica que la implementación llega en un change posterior  

### Escenario 12: El endpoint de evaluación solo existe en desarrollo
**Dado que** la aplicación se construye con un perfil de producción  
**Cuando** se invoca `GET /v1/evals/runs` con un token válido  
**Entonces** la ruta no está montada  
**Y** con perfil de desarrollo la misma ruta responde HTTP 200 con una lista determinista de ejecuciones  

### Escenario 13: Fuera de alcance explícito
**Dado que** esta historia está implementada  
**Cuando** se revisa el entregable  
**Entonces** no hay búsqueda vectorial real, ni enriquecimiento, ni indexación reales  
**Y** no hay cliente .NET ni emisión de JWT desde la API ASP.NET (eso es C03)  
**Y** no hay migraciones Alembic ni tablas `ai.*`  
**Y** el servicio no lee ni escribe el esquema `public` por SQL  

---

## Notas adicionales

- **Actor:** historia de plataforma y contratos para el equipo del PF. No hay pantalla de usuario final; el beneficiario directo es el desarrollador que implementa C03.
- **Origen del "§6.8":** el plan C02 cita una sección que el diseño v3 no tiene (termina en §6.4). La tabla de contratos vive en el documento 3devs §6.8. Esta HU y el ticket documentan la reconstrucción; sincronizar el documento de diseño es trabajo editorial posterior y no bloquea.
- **Retirada de stubs:** cada change posterior (C09, C13, C14…) sustituye handlers concretos. No es trabajo de esta historia, pero el contrato que se congela aquí es el que deberán respetar.
- **Determinismo:** los stubs deben ser reproducibles para el mismo input, porque C03 construirá sus tests de mapeo contra ellos.
- **Riesgo de contrato fino:** se incluyen ya campos opcionales (`debug`, `usage`, `match_reasons`, `similarity_signals`) aunque los stubs los rellenen de forma mínima, para reducir la probabilidad de reabrir el contrato en la Ola 4.
- **Documentación de arquitectura:** `Documentos/modelo-c4.md`, `Documentos/arquitectura.md` y `Documentos/epicas.md` ya incorporan el contenedor `jbg-ai`, la frontera Python ↔ .NET y el bloque EP11–EP17 / serie `HU-AIENG-*`. Esta historia no vuelve a tocar esos documentos salvo si el apply introduce un detalle nuevo que deba reflejarse.
- **OpenSpec:** se implementa vía el change `add-ai-service-contracts-and-auth` (proposal → apply → verify → archive). Los artefactos del change se regeneran a partir de esta HU y del ticket.

---

## Tareas

1. Extender `Settings` con `jwt_secret` (obligatorio, no vacío), `jwt_ttl_seconds` (default `300`) y `stub_mode` (default `true`); añadir `PyJWT` y sincronizar el lockfile con `uv`.
2. Actualizar el servicio `jbg-ai` de `backend/docker-compose.yml` con `JWT_SECRET` y `STUB_MODE`, y la tabla de variables obligatorias de `ai-service/README.md`.
3. Implementar la validación HS256 y el `ServicePrincipal`, más la dependencia FastAPI que rechaza con 401 y da preferencia al claim `trace_id`. Claims del JWT en `snake_case` (`user_id`, `role`, `pos_id`, `trace_id`); C03 mapea desde el lado .NET.
4. Definir los schemas Pydantic de recuperación, asistencia, inventario, enriquecimiento, indexación y evals, con `materials[]`, `family_id`, `variant_label`, `top_k` y `candidates_returned`.
5. Implementar los stubs deterministas y montar los routers `/v1/*`, aplicando la regla de sobre-recuperación y el 501 cuando `STUB_MODE` es `false`.
6. Montar `GET /v1/evals/runs` solo cuando `ENABLE_DEV_ENDPOINTS` es `true` (derivado de `APP_ENV`) y documentar el perfil canónico con el que se genera el snapshot.
7. Exportar y versionar `ai-service/openapi.json`, y añadir el test de snapshot. Regeneración manual documentada en el README (sin script dedicado en este change).
8. Escribir los tests del plan C02 más los de token inválido, fail-fast de `JWT_SECRET`, 501 con stubs desactivados y ausencia de la ruta de evals en perfil de producción.
9. Verificar `uv run pytest` en verde sin llamadas a LLM ni a RDS.

---

## Estimaciones y atributos de priorización

> Valores propuestos por el Product Owner a partir de la guía de estimación de [Procedimiento-TicketsTrabajo.md](../../Procedimientos/Procedimiento-TicketsTrabajo.md) (§4.6). **Pendientes de validar** en la sesión de refinamiento del equipo.

- **Puntos de historia:** **8** — amplitud alta (ocho endpoints con modelos de ida y vuelta), capa de autenticación nueva e infraestructura de snapshot. No llega a 13 porque no hay lógica real, ni base de datos, ni proveedor LLM: todo son stubs deterministas.
- **Impacto en usuario / Valor de negocio:** **3** — nulo de forma directa (no hay pantalla), alto de forma indirecta: es la pieza que permite trabajar en paralelo y sin la cual no existe el slice vertical.
- **Urgencia (mercado / feedback):** **5** — Ola 0, ruta crítica 🔴. Cada día de retraso lo heredan C03 y toda la cadena posterior.
- **Complejidad / Esfuerzo:** **4** — la dificultad no está en el algoritmo sino en acertar el contrato a la primera y en la disciplina del snapshot; equivocarse aquí se paga en la Ola 4.
- **Riesgos y dependencias:**
  - Depende de HU-AIENG-001 / C01 (esqueleto ejecutable) — **hecho y archivado**.
  - Desbloquea C03 (cliente .NET tipado) y habilita el trabajo en paralelo hasta C14/C15.
  - **Riesgo:** contrato demasiado fino que haya que reabrir en la Ola 4, rompiendo C03, C15 y C16 → mitigado incluyendo ya los campos opcionales y forzando la negociación con el snapshot.
  - **Riesgo:** desalineación de nombres de claims con .NET (`pos_id` frente a `pointOfSaleId`) → Python congela `snake_case` y C03 mapea.
  - **Riesgo:** ambigüedad entre versiones del diseño sobre "§6.8" → la spec del change y el `openapi.json` son la autoridad.
  - **Riesgo:** falta del `JWT_SECRET` en el Compose local → mitigado con fail-fast y secreto local en el fichero de Compose, nunca reutilizable en producción.
  - No depende del export del catálogo real ni de la elección de proveedor LLM.
