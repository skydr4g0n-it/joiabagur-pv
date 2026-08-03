# HU-AIENG-001: Esqueleto ejecutable del servicio de IA (`jbg-ai`)

## Formato estándar

Como **desarrollador del proyecto**, quiero **disponer de un microservicio Python `jbg-ai` vacío pero ejecutable** (configuración, salud, logging, contenedor y compose) **para** **poder construir en paralelo contratos, esquema vectorial y corpus sin esperar infraestructura ad hoc**.

---

## Descripción

Primera pieza del Proyecto Final de IA (change OpenSpec `init-ai-service-skeleton` / C01). Entrega el cimiento del servicio RAG en Python sobre FastAPI, alineado con el diseño: frontera estrecha (Python solo vectorial/LLM; .NET conserva negocio), misma base PostgreSQL en producción con esquemas `public` + `ai`, y desarrollo local desacoplado de RDS.

**Alcance de esta historia (sí):**

- Proyecto `ai-service/` con `uv`, paquete `jbg_ai`, FastAPI y `GET /health` con versión.
- Configuración por entorno con pydantic-settings y fail-fast solo de variables mínimas.
- Logging estructurado con `trace_id` (header o generación; sin JWT aún).
- `Dockerfile` y servicio en `backend/docker-compose.yml` (red `jpv-network`).
- Imagen local de Postgres con extensión pgvector disponible (`pgvector/pgvector:pg15` o equivalente), sin crear aún el esquema `ai` ni tablas.
- Tests unitarios/smoke con `TestClient` (sin llamadas a LLM ni a RDS).

**Fuera de alcance (no):**

- Autenticación JWT interna, routers de dominio ni OpenAPI congelado → HU posteriores / C02.
- `CREATE EXTENSION vector`, esquema `ai`, rol dedicado, Alembic y tablas → C05.
- Escritura en `public`, enriquecimiento, feeds ni indexación → C08/C09/C12/C13.
- Despliegue a ECR/EC2, nginx, SSM ni health enriquecido (BD/proveedor/índice) → C17.
- Conexión del portátil a RDS de producción.

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Base de datos en prod | Misma RDS PostgreSQL 15.17 / DB `jpv`; esquemas `public` (.NET) y `ai` (Python). No segunda instancia. |
| Extensión vectorial | Proyecto **pgvector**; SQL: `CREATE EXTENSION vector` (en C05, no en esta HU). |
| Permisos Python | El rol del servicio IA **no escribe ni lee `public` por SQL**. |
| Compose | Extender `backend/docker-compose.yml`; puerto publicado solo en local; en prod sin exposición en nginx (C17). |
| Settings required en C01 | Solo `APP_ENV`, `SERVICE_VERSION` y `LOG_LEVEL` (este último puede tener default). `DATABASE_URL`, JWT y claves LLM entran en changes posteriores. |
| Layout | `ai-service/src/jbg_ai/config/settings.py` (settings dentro del paquete). |

**Referencias:** [proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6, §12), [proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (C01).

---

## Criterios de Aceptación

### Escenario 1: Health responde con versión
**Dado que** el servicio `jbg-ai` está arrancado con las variables mínimas configuradas  
**Cuando** se invoca `GET /health`  
**Entonces** la respuesta es HTTP 200  
**Y** el cuerpo incluye estado OK y la versión del servicio (`SERVICE_VERSION`)  
**Y** el endpoint es público (no exige autenticación)

### Escenario 2: Fail-fast si falta configuración obligatoria
**Dado que** falta una variable de entorno requerida (`APP_ENV` o `SERVICE_VERSION`)  
**Cuando** se intenta cargar la configuración / arrancar la aplicación  
**Entonces** el proceso falla de inmediato con error claro  
**Y** no queda un servicio “a medias” escuchando peticiones

### Escenario 3: Logging con `trace_id`
**Dado que** el servicio está arrancado  
**Cuando** se realiza una petición a `/health` con header de correlación (p. ej. `X-Trace-Id`)  
**Entonces** los logs estructurados de esa petición incluyen el mismo `trace_id`  
**Y** si no se envía header, el servicio genera un `trace_id` y lo propaga en logs (y preferiblemente en la respuesta)

### Escenario 4: Contenedor en red interna de compose (local)
**Dado que** existe `backend/docker-compose.yml` con la red `jpv-network`  
**Cuando** se añade el servicio `jbg-ai` y se levanta el compose de desarrollo  
**Entonces** el contenedor arranca y `/health` es alcanzable en el puerto publicado solo para desarrollo  
**Y** el servicio comparte red con Postgres (preparado para C05)  
**Y** no se configura exposición vía nginx ni publicación pensada para producción

### Escenario 5: Postgres local listo para pgvector (sin esquema `ai` aún)
**Dado que** el compose de desarrollo usa imagen Postgres con pgvector (major 15)  
**Cuando** un cliente SQL se conecta a la instancia local  
**Entonces** la extensión `vector` aparece en `pg_available_extensions` (o equivalente)  
**Y** esta historia **no** exige haber ejecutado `CREATE EXTENSION vector` ni creado el esquema `ai`

### Escenario 6: Smoke automatizado sin dependencias externas
**Dado que** el entorno de tests del paquete está configurado (`uv` + pytest)  
**Cuando** se ejecutan los tests de esta historia  
**Entonces** pasan `test_health_returns_ok_with_version` y `test_settings_fail_fast_when_required_env_missing`  
**Y** el smoke usa `TestClient` sin llamar a LLM, embeddings ni RDS de producción

### Escenario 7: Fuera de alcance explícito
**Dado que** esta historia está implementada  
**Cuando** se revisa el entregable  
**Entonces** no existen routers de retrieval/assist/inventory/index/enrich reales ni stubs de contrato congelado  
**Y** no hay migraciones Alembic ni tablas en `ai.*`  
**Y** el servicio no escribe en el esquema `public`

---

## Notas adicionales

- **Actor:** historia de plataforma/infra para el equipo; no hay pantalla de usuario final.
- **Cambio de imagen Postgres local:** al pasar de `postgres:15` a imagen con pgvector puede ser necesario recrear el volumen de desarrollo (`docker compose down -v`); aceptable en O0 sin catálogo real.
- **Verificación RDS prod (15.17):** documentada como admisible para pgvector; el `CREATE EXTENSION` operativo queda en C05. Opcional cerrar con `SELECT ... FROM pg_available_extensions WHERE name = 'vector'` en la instancia real.
- **`trace_id` vs JWT:** en C02 el claim del JWT interno tendrá preferencia; aquí basta header + generación.
- **OpenSpec:** implementar vía change `init-ai-service-skeleton` (proposal → apply → verify → archive) según el plan del PF.
- **Estimación de atributos de priorización:** completar en refinamiento con el equipo (el procedimiento recomienda no fijarlos en el primer borrador).

---

## Tareas

1. Crear `ai-service/` con `pyproject.toml` (`uv`), layout `src/jbg_ai/` y dependencia FastAPI + pydantic-settings.
2. Implementar `jbg_ai.config.settings` con fail-fast de variables mínimas y `GET /health` en `api/main.py`.
3. Añadir middleware/logging estructurado con `trace_id`.
4. Escribir tests: health con versión; settings fail-fast; smoke con `TestClient`.
5. Añadir `Dockerfile` del servicio y entrada `jbg-ai` en `backend/docker-compose.yml` (red interna; puerto solo local).
6. Sustituir imagen Postgres de desarrollo por variante con pgvector (PG 15), sin crear esquema `ai` ni extensión en migraciones.
7. Documentar en README de `ai-service/` cómo arrancar con `uv` / compose y qué variables son obligatorias en C01.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / Valor de negocio:** _Pendiente_ (habilitador de ruta crítica; valor indirecto alto)
- **Urgencia (mercado / feedback):** _Pendiente_ (Ola 0 del PF; desbloquea C02, C05 y C06)
- **Complejidad / Esfuerzo:** _Pendiente_
- **Riesgos y dependencias:**
  - Sin dependencias de otras HU-AIENG (primera de la serie).
  - Desbloquea: contratos/auth (C02), esquema pgvector (C05), corpus híbrido (C06).
  - Riesgo: volumen Docker local incompatible al cambiar imagen Postgres.
  - Riesgo residual bajo: confirmar `vector` en RDS 15.17 antes de C05.
  - No depende de export de catálogo real ni de proveedor LLM.
