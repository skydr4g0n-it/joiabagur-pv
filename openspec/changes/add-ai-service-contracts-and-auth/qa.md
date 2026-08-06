# QA — C02 `add-ai-service-contracts-and-auth`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-06 · **Rama:** `c02-add-ai-service-contracts-and-auth` · **Commit de implementación:** `6ba8094`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11.15 |
| uv | 0.11.7 |
| PyJWT | 2.13.0 (resuelto y fijado en `uv.lock`) |
| Docker | Server 29.6.2 |
| Comando de test | `uv run --system-certs pytest` desde `ai-service/` |

`--system-certs` es necesario en esta máquina: sin él, `uv` falla al resolver PyPI con `invalid peer certificate: UnknownIssuer`. Ya estaba documentado en el README desde C01.

---

## 1. Suite automática

**Resultado: 74 tests, 74 en verde, 0 fallos, ~1,3 s.**

| Fichero | Tests | Cubre |
|---|---|---|
| `tests/test_auth.py` | 21 | 401 sin token en los ocho endpoints, siete variantes de token inválido, cabecera mal formada, `alg=none`, token válido, `pos_id` del token, `trace_id` del claim |
| `tests/test_contracts.py` | 12 | Los ocho endpoints validan contra su modelo declarado; inventory priorizado; enrich con confianza por campo; index counters y drift; eco de scope |
| `tests/test_stub_mode.py` | 10 | 501 en los ocho endpoints con `STUB_MODE=false`, mensaje con el change entregador, auth antes que el guard |
| `tests/test_retrieval_stub.py` | 9 | Schema de recuperación, sobre-recuperación en seis puntos, determinismo, substitutes con `similarity_signals`, 422 por `top_k` fuera de rango |
| `tests/test_settings.py` | 7 | Fail-fast de `APP_ENV` / `SERVICE_VERSION` / `JWT_SECRET` (ausente y en blanco), defaults, derivación de `ENABLE_DEV_ENDPOINTS` |
| `tests/test_openapi_snapshot.py` | 4 | Igualdad estricta con el fichero committeado, detección de deriva, superficie congelada, docs deshabilitadas |
| `tests/test_assist_stub.py` | 4 | Agrupación por familia, placeholders sin resolver, ausencia de cifras, determinismo |
| `tests/test_health.py` | 4 | Health público con versión y correlación (C01 + `test_health_is_public`) |
| `tests/test_evals_gating.py` | 3 | Evals en perfil dev, ausente en perfil prod, resto de `/v1` intacto en prod |

### Los once tests exigidos por el ticket

| Test del ticket | Estado |
|---|---|
| `test_retrieval_stub_matches_response_schema` | ✅ verde |
| `test_over_retrieval_returns_capped_candidates` | ✅ verde (`5 → 15`, `30 → 60`) |
| `test_assist_sale_groups_by_family` | ✅ verde |
| `test_request_without_token_is_rejected` | ✅ verde (parametrizado sobre los ocho endpoints) |
| `test_invalid_token_is_rejected` | ✅ verde (firma, caducidad, cuatro claims ausentes, claim en blanco) |
| `test_pos_id_from_token_overrides_body_value` | ✅ verde |
| `test_health_is_public` | ✅ verde |
| `test_unimplemented_route_returns_501_when_stub_mode_off` | ✅ verde (parametrizado sobre los ocho endpoints) |
| `test_openapi_snapshot_is_stable` | ✅ verde |
| `test_settings_fail_fast_when_jwt_secret_missing` | ✅ verde (+ `..._blank` para el secreto vacío) |
| `test_dev_only_evals_route_absent_in_prod_profile` | ✅ verde |

---

## 2. Criterios de aceptación de la HU

| Escenario HU-AIENG-002 | Cómo se comprueba | Estado |
|---|---|---|
| 1 · Stub de recuperación cumple el schema | `test_retrieval_stub_matches_response_schema`, con la fixture `forbid_network` activa | ✅ |
| 2 · Sobre-recuperación observable (`top_k=5 → 15`) | `test_over_retrieval_returns_capped_candidates` | ✅ |
| 3 · Tope de 60 (`top_k=30 → 60`) | mismo test + `test_over_retrieval_rule_holds_across_the_range` (`1→3`, `10→30`, `20→60`, `50→60`) | ✅ |
| 4 · Assist agrupa por familia y deja placeholders | `test_assist_sale_groups_by_family` + `test_pitch_never_resolves_price_or_stock` | ✅ |
| 5 · Sin token se rechaza | `test_request_without_token_is_rejected` sobre los ocho endpoints | ✅ |
| 6 · Token inválido se rechaza sin revelar la causa | `test_invalid_token_is_rejected` asserta que el cuerpo no contiene el secreto ni las palabras «signature» / «expired» | ✅ |
| 7 · El `pos_id` del token manda | `test_pos_id_from_token_overrides_body_value` (token `POS-B` frente a body `POS-A`) y `test_scoped_responses_echo_the_token_scope` | ✅ |
| 8 · Health sigue público | `test_health_is_public` + smoke en Compose | ✅ |
| 9 · Snapshot estable y detecta deriva | `test_openapi_snapshot_is_stable`, `test_snapshot_comparison_detects_drift` y la prueba manual de la sección 4 | ✅ |
| 10 · Falta `JWT_SECRET` y el arranque falla | `test_settings_fail_fast_when_jwt_secret_missing` / `..._blank`; el error nombra `jwt_secret` | ✅ |
| 11 · `STUB_MODE=false` responde 501 | `test_unimplemented_route_returns_501_when_stub_mode_off` | ✅ |
| 12 · Evals solo en desarrollo | `test_evals_route_returns_runs_in_dev_profile`, `test_dev_only_evals_route_absent_in_prod_profile` (404 genérico + ausencia en el OpenAPI de prod) | ✅ |
| 13 · Fuera de alcance respetado | **Por inspección**, no por test automático: sin driver de base de datos ni SDK de LLM en `pyproject.toml`, sin Alembic, sin SQL en el árbol, sin código .NET tocado. Refuerzo automático: `forbid_network` | ✅ con matiz |

---

## 3. Smoke end-to-end con Docker Compose

`docker compose up -d --build jbg-ai` desde `backend/`. Imagen construida y contenedor `jpv-pv-jbg-ai` arrancado con el entorno del Compose (`JWT_SECRET`, `STUB_MODE`).

| Comprobación | Resultado observado |
|---|---|
| `GET /health` sin token | `200` · `{"status":"OK","version":"0.1.0"}` |
| `POST /v1/retrieval/products` sin token | `401` |
| `POST /v1/retrieval/products` con token firmado con el secreto del Compose | `200` |
| Sobre-recuperación con `top_k=5` | `candidates_returned: 15`, `results: 15` |
| Body con `pos_id: POS-FROM-BODY`, token con `pos_id: POS-COMPOSE` | `effective_pos_id: POS-COMPOSE` — el token manda, y la petición no falla |
| `trace_id` del claim | `trace_id: smoke-trace` en el cuerpo (el header `X-Trace-Id` no se envió) |

El contenedor se detuvo al terminar (`docker compose stop jbg-ai`); no queda nada corriendo por esta verificación.

---

## 4. Verificación manual de la detección de deriva

El valor del snapshot es que **rompa** cuando el contrato se mueve, así que se comprobó de verdad y no solo por lectura:

1. Se añadió un campo `drift_probe: str | None = None` a `RetrievalResult`.
2. `uv run pytest tests/test_openapi_snapshot.py::test_openapi_snapshot_is_stable` → **1 failed** (`AssertionError`).
3. Se revirtió el campo y la suite volvió a 74 en verde.

El perfil canónico vive en `canonical_openapi_settings()`, invocado tanto por el test como por el one-liner de regeneración del README: es lo que impide que ambos construyan la app con perfiles distintos.

---

## 5. Comprobaciones de disciplina

| Comprobación | Resultado |
|---|---|
| `openspec validate add-ai-service-contracts-and-auth --strict` | `Change ... is valid` |
| Artefactos del change | 4/4 completos (proposal, design, specs, tasks) |
| `TODO` / `FIXME` / `XXX` / `HACK` en `ai-service/**/*.py` | Sin coincidencias |
| Rutas montadas en perfil dev | `/health` + los ocho `/v1` |
| Rutas montadas en perfil prod | `/health` + siete `/v1`; `/v1/evals/runs` ausente del router y del OpenAPI |
| Schemas publicados en el snapshot | 35 |
| `docs_url` / `redoc_url` | `None`, comprobado por test |

---

## 6. Cómo se comprueba «sin LLM, sin embeddings y sin base de datos»

No basta con no escribir la llamada, así que hay dos capas:

1. **Fixture `forbid_network`** (`tests/conftest.py`): parchea `socket.socket.connect` y `socket.create_connection` para que cualquier conexión levante `AssertionError`. Se aplica en los tests de contrato y de stubs. `TestClient` funciona en proceso, así que un socket abierto solo podría venir del código de producción.
2. **Dependencias**: `pyproject.toml` no incluye driver de base de datos, cliente de embeddings ni SDK de proveedor LLM. Las únicas dependencias de runtime son `fastapi`, `pydantic-settings`, `pyjwt` y `uvicorn`.

Los stubs además no llaman al reloj: las fechas de `index/status` y `evals/runs` son constantes, precisamente para que el determinismo sea comprobable.

---

## 7. Lo que **no** se ha comprobado

Se deja explícito para que nadie lo dé por hecho:

- **Nada del lado .NET.** No hay emisión ni firma de JWT desde ASP.NET, ni cliente tipado, ni Polly: es C03. El token del smoke se firmó con un script Python auxiliar, no con el emisor real.
- **Rendimiento y latencia.** Los objetivos de p95 del diseño pertenecen a los changes de implementación real; aquí los stubs son O(1) y no se ha medido nada.
- **Despliegue.** No se ha probado ECR, EC2, nginx ni SSM (C17). El smoke es Compose local.
- **Linter y type-checker.** El proyecto no tiene `ruff` ni `mypy` configurados en `ai-service/`; no se ha ejecutado análisis estático más allá de los diagnósticos del IDE.
- **Base de datos.** No se ha levantado Postgres ni comprobado pgvector: C02 no abre conexión (eso es C05).
- **Concurrencia y carga.** Ningún test concurrente.

---

## 8. Riesgos vivos tras la verificación

| Riesgo | Estado |
|---|---|
| **Secreto local committeado.** `backend/docker-compose.yml` contiene `JWT_SECRET: local-dev-jwt-secret-0123456789abcdef` en claro | Aceptado y marcado con comentario en el fichero: es placeholder de desarrollo. Producción lo toma de SSM `/jpv/prod/*` en C17 y **no** debe reutilizar este valor |
| **`results` tiene `candidates_returned` elementos, no `top_k`.** Es la semántica congelada, pero es el campo más fácil de malinterpretar al escribir el cliente .NET | Documentado en el README, en la spec y en dos tests frontera. A vigilar en la revisión de C03 |
| **El snapshot de repo incluye `/v1/evals/runs`, que producción no sirve** | Trade-off deliberado del design (decisión 9), fijado por dos tests |
| **Warning de deprecación de `httpx` en `TestClient`** (`install httpx2`) | Ruido de Starlette, no afecta a los resultados; no se ha tocado la dependencia en este change |

---

## Veredicto

La implementación cumple los trece escenarios de la HU y los siete criterios de aceptación del ticket, con la salvedad de que el escenario 13 se verifica por inspección de dependencias y por bloqueo de red, no por un test que asserte la ausencia de SQL. La suite está en verde, el snapshot detecta deriva de verdad, y el smoke con Compose confirma el comportamiento de frontera extremo a extremo.
