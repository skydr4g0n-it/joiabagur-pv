# QA — C05 `add-pgvector-schema-foundation`

> Registro de las comprobaciones **realmente ejecutadas** sobre la implementación del change, con sus resultados.
> **Fecha:** 2026-08-15 · **Rama:** `c05-add-pgvector-schema-foundation` · **Commit previo a la implementación:** `943d611`
> **Idioma:** cuerpo en español, identificadores técnicos en inglés, por coherencia con [ticket.md](ticket.md) y con la HU.

---

## Entorno de verificación

| Pieza | Valor |
|---|---|
| Python | 3.11.15 |
| Gestor | `uv` 0.11.7 — **con `--system-certs` en todas las llamadas**, según `CLAUDE.md` |
| Docker | 29.6.2 (Docker Desktop, Windows 11) |
| PostgreSQL de los tests | `pgvector/pgvector:pg15` en contenedor efímero, **una base de datos nueva por test** |
| PostgreSQL de las pruebas manuales | El de `backend/docker-compose.yml`, misma imagen, puerto 5433 |
| pgvector | 0.8.6 |
| Contrato | `ai-service/openapi.json` — **no se toca**; verificado con `git diff` |

---

## 1. Suite automática

| Ejecución | Total | Fallos |
|---|---|---|
| **Línea base** (tras añadir dependencias, antes de escribir código de C05) | 77 | **0** |
| Tras la implementación, **con Docker** | **112** | **0** |
| Tras la implementación, **sin Docker** (`DOCKER_HOST` inalcanzable) | 93 + 19 omitidos | **0** |

**35 tests nuevos, todos en verde.** La línea base se midió de verdad: la suite se ejecutó justo después de instalar las cinco dependencias y antes de escribir nada más, precisamente para que un fallo de instalación no se confundiera después con un fallo de diseño.

> **Nota sobre la lectura del recuento.** Aquí sí es fiable, a diferencia de la suite de .NET que documenta `CLAUDE.md`: la suite de Python parte de **cero fallos** y no tiene tests dependientes del orden. 77 + 35 = 112, exactamente.

### Desglose de los 35 tests nuevos

| Fichero | Nº | Marcador | Qué cubre |
|---|---|---|---|
| `tests/migrations/test_ai_schema_migration.py` | 13 | `db` | Extensión y esquema, tabla de versiones fuera de `public`, nada fuera de `ai`, *operator class* de los dos índices vectoriales, GIN sobre materiales y sobre las columnas consultables, columnas generadas en español, ausencia de FK cruzadas, reversibilidad de tres piernas |
| `tests/migrations/test_ai_schema_invariants.py` | 6 | `db` | Vocabulario de origen, embedding ausente aceptado, vocabulario de bucket, orientación del par, borrado en cascada, unicidad del índice de fragmento |
| `tests/db/test_engine.py` | 9 | — | Tope del pool sin desbordamiento, tamaño configurable, espera acotada, comprobación previa, ausencia de motor al importar, reutilización de motor y fábrica, fallo con nombre cuando no hay configuración |
| `tests/db/test_boots_without_database.py` | 3 | — | El perfil por defecto no trae cadena de conexión; `/health` y `/v1` responden sin motor y sin socket |
| `tests/config/test_settings.py` (ampliado) | 4 | — | Ausencia de configuración no impide arrancar, configuración aceptada, cadena en blanco tratada como ausente, tamaño de pool no positivo rechazado |

### Los escenarios de las specs, uno a uno

**`ai-vector-schema`** (capability nueva)

| Requisito · escenario | Test | Resultado |
|---|---|---|
| Esquema `ai` es el único que escribe · bookkeeping dentro de `ai` | `test_migration_keeps_alembic_bookkeeping_out_of_public` | ✅ |
| Esquema `ai` es el único que escribe · nada fuera de `ai` | `test_migration_creates_no_table_outside_the_ai_schema` | ✅ |
| Aprovisionamiento previo · sobre base limpia | `test_migration_creates_vector_extension_and_ai_schema` | ✅ |
| Aprovisionamiento previo · idempotencia | §2 y §3 (manual) | ✅ |
| Aprovisionamiento previo · privilegio insuficiente falla identificable | §3 (manual) | ✅ |
| Rol dedicado · puede migrar y operar `ai` | §3 (manual) | ✅ |
| Rol dedicado · no puede leer `public` | §3 (manual) | ✅ |
| Reversibilidad · revierte y conserva objetos compartidos | `test_upgrade_downgrade_is_reversible` | ✅ |
| Reversibilidad · volver a aplicar funciona | ídem, tercera pierna | ✅ |
| *Operator class* de coseno · documento de producto | `test_hnsw_index_uses_cosine_operator_class[ix_product_document_embedding_hnsw]` | ✅ |
| *Operator class* de coseno · fragmento de conocimiento | `test_hnsw_index_uses_cosine_operator_class[ix_knowledge_chunk_embedding_hnsw]` | ✅ |
| *Operator class* de coseno · la euclídea se detecta como defecto | §4, rotura 1 | ✅ |
| GIN · materiales | `test_gin_index_exists_on_materials` | ✅ |
| GIN · texto completo y metadatos | `test_gin_index_exists_on_searchable_column` (3 casos) | ✅ |
| B-tree de filtros estructurales | §5 (catálogo) | ✅ |
| Texto completo generado en español | `test_tsvector_column_is_generated_with_spanish_configuration` (2 casos) | ✅ |
| Documento de producto · vocabulario de origen | `test_product_document_rejects_data_origin_outside_vocabulary` | ✅ |
| Documento de producto · embedding ausente | `test_product_document_accepts_row_without_embedding` | ✅ |
| Documento de producto · sin tipos huérfanos al revertir | `test_upgrade_downgrade_is_reversible` + §5 | ✅ |
| Conocimiento · cascada | `test_deleting_knowledge_document_deletes_its_chunks` | ✅ |
| Conocimiento · índice de fragmento único | `test_knowledge_chunk_index_is_unique_within_its_document` | ✅ |
| Proyección · vocabulario de bucket | `test_pos_projection_rejects_quantity_outside_bucket_vocabulary` | ✅ |
| Proyección · frescura propia | §5 (columna `refreshed_at`) | ✅ |
| Co-ocurrencia · par invertido rechazado | `test_co_occurrence_rejects_reversed_pair` | ✅ |
| Co-ocurrencia · par duplicado rechazado | Clave primaria compuesta, §5 | ✅ |
| Fallos de sincronización · contexto y cola indexada | §5 (`ix_sync_failure_next_retry_at`) | ✅ |
| Sin FK hacia `public` | `test_ai_schema_declares_no_foreign_key_into_public` | ✅ |
| Integridad intra-esquema preservada | ídem (afirma la FK hacia `ai.knowledge_document`) | ✅ |
| Pool · tope efectivo | `test_pool_is_capped_at_configured_size_without_overflow` | ✅ |
| Pool · no se crea al importar | `test_importing_the_module_creates_no_engine` | ✅ |
| Pool · sesión sin configuración falla claro | `test_engine_without_database_url_fails_naming_the_missing_setting` | ✅ |

**`ai-service-runtime`** (modificada)

| Escenario | Test | Resultado |
|---|---|---|
| Configuración de base de datos ausente no bloquea el arranque | `test_settings_load_without_database_url` · `test_health_answers_without_a_database` | ✅ |
| Configuración aceptada cuando se aporta | `test_settings_accept_database_url_when_supplied` | ✅ |
| Los tres escenarios preexistentes de fallo temprano | Sin cambios, siguen en verde | ✅ |

**`ai-service-dev-compose`** (modificada)

| Escenario | Comprobación | Resultado |
|---|---|---|
| Compose aporta una URL local | §6 (manual) | ✅ |
| Arranque de Compose no aprovisiona extensión ni esquema | §6 (manual) | ✅ |
| Configuración local no apunta a producción | Revisión del fichero: `postgres:5432` de red interna | ✅ |

---

## 2. La migración, ejecutada de verdad

No se dio por buena por aplicar: se aplicó, se revirtió y se volvió a aplicar, y se inspeccionó el catálogo entre medias.

```
alembic upgrade head      → Running upgrade  -> f46c55c056e2, ai schema foundation
alembic downgrade base    → Running downgrade f46c55c056e2 ->
alembic upgrade head      → Running upgrade  -> f46c55c056e2, ai schema foundation
```

Estado tras revertir, consultado directamente:

| Comprobación | Resultado |
|---|---|
| Tablas restantes en `ai` | `alembic_version` — las seis del índice desaparecen |
| Esquema `ai` | Sigue existiendo |
| Extensión `vector` | Sigue instalada, 0.8.6 |
| Tipos enumerados huérfanos | **0** — consecuencia directa de haber elegido `text` + `CHECK` |

Tras volver a aplicar: **7 tablas y 21 índices**, idéntico al primer estado.

---

## 3. El rol dedicado y la frontera, comprobados contra el motor

La frontera `ai` / `public` no se verificó leyendo el código, sino pidiéndole a PostgreSQL que la rompiera:

| Intento como `jbg_ai` | Resultado |
|---|---|
| `CREATE TABLE` en `ai` | `CREATE TABLE` — permitido |
| `SELECT` sobre `public."Products"` | **`ERROR: permission denied for table Products`** |
| `CREATE TABLE` en `public` | **`ERROR: permission denied for schema public`** |
| Aplicar la migración completa | **Correcta** — sin privilegio para instalar extensiones |

La última fila es la que importa: **es el camino de RDS**, donde el administrador aprovisiona y el rol de servicio solo migra. Verificarlo fue lo que sacó a la luz el defecto de la §7.

Idempotencia del script de preparación: la segunda ejecución responde `role jbg_ai already exists, password left untouched`, que es el comportamiento buscado — **volver a ejecutarlo no puede rotar en silencio una credencial de producción**.

---

## 4. Los detectores, verificados rompiendo lo que vigilan

Un detector de fallos mudos que nadie ha visto fallar es él mismo un fallo mudo. Se rompió cada uno a propósito, se comprobó el fallo y se revirtió la rotura.

| # | Rotura introducida | Resultado |
|---|---|---|
| 1 | `vector_cosine_ops` → `vector_l2_ops` | **2 failed** — `ix_..._embedding_hnsw is built with 'vector_l2_ops'; queries use the cosine operator ``<=>``, so this index would never be used and nothing would say so` |
| 2 | GIN sobre materiales → B-tree | **1 failed** |
| 3 | `version_table_schema` → `public` | **1 failed** |
| 4 | La reversión deja `product_document` sin borrar | **1 failed**, en la **tercera pierna** |

La rotura 1 es la demostración del argumento del change: **`CREATE INDEX` no emitió ni un aviso**. La migración construyó felizmente un índice que ninguna consulta habría usado jamás, y solo la aserción contra el catálogo lo dijo.

Tras revertir las cuatro: **112 passed**.

---

## 5. Inspección del catálogo tras la migración

Lo que quedó, leído del catálogo y no del código que lo escribió:

| Comprobación | Resultado |
|---|---|
| Tablas en `ai` | `product_document`, `knowledge_document`, `knowledge_chunk`, `pos_projection`, `co_occurrence`, `sync_failure` + `alembic_version` |
| Índices en `ai` | 21 (14 declarados + 6 claves primarias + la de `alembic_version`) |
| Índices vectoriales | `hnsw` / `vector_cosine_ops` en los **dos** |
| Parámetros HNSW | `m=16,ef_construction=128` en ambos — **explícitos**, no los del motor (`ef_construction` por defecto es 64) |
| GIN | `array_ops` sobre materiales · `tsvector_ops` sobre ambas `tsv` · `jsonb_ops` sobre metadatos |
| Columnas generadas | `to_tsvector('spanish'::regconfig, doc_text)` y `to_tsvector('spanish'::regconfig, content)` |
| Restricciones de comprobación | 5: origen, banda de precio, tipo de documento, bucket, orientación del par |
| Claves foráneas | **1 sola**, `knowledge_chunk → ai.knowledge_document`. Ninguna hacia `public` |
| `embedding` nulable | `YES` |

---

## 6. Contenedor y Compose

| Comprobación | Resultado |
|---|---|
| `docker compose build jbg-ai` | Construye |
| `docker compose up -d jbg-ai` + `GET /health` | `{"status":"OK","version":"0.1.0"}` |
| `alembic current` **dentro del contenedor** | `f46c55c056e2 (head)` |
| Ciclo `downgrade base` → `upgrade head` **dentro del contenedor** | Completo, 7 tablas y 21 índices reconstruidos |

Esta última fila es la que cierra el riesgo nombrado en el ticket: el `Dockerfile` copiaba **solo** `src`, de modo que sin la corrección **C17 habría descubierto el 19 de agosto que no podía migrar en producción**.

---

## 7. Defectos encontrados durante la implementación

Tres, y ninguno se descubrió leyendo código: los tres aparecieron al ejecutar.

### 7.1 · `CREATE SCHEMA IF NOT EXISTS` sí comprueba el privilegio — corrige el diseño

El `design.md` afirmaba que `IF NOT EXISTS` hacía del aprovisionamiento un no-op inocuo para un rol sin privilegios, que es **exactamente el camino de RDS** que la decisión 4 pretendía habilitar. Es falso: PostgreSQL evalúa el privilegio **antes** del cortocircuito, así que la sentencia falla con `permission denied for database` **aunque el esquema ya exista**.

Apareció al migrar por primera vez como `jbg_ai` en lugar de como superusuario — una prueba que se hizo precisamente por desconfianza de la afirmación.

**Corrección:** el entorno de migración y la revisión **comprueban primero y crean después** (`pg_namespace` / `pg_extension`), de modo que el caso ya aprovisionado no intenta ningún DDL y no exige ningún privilegio. La decisión no cambia; cambia su mecanismo. Registrado con fecha en `design.md`. Los requisitos de la spec no cambian: seguían siendo ciertos, era el mecanismo el que estaba mal descrito.

### 7.2 · La precedencia de la cadena de conexión podía apuntar los tests a la base del desarrollador

`env.py` prefería `DATABASE_URL` del entorno sobre la configuración explícita de Alembic. Como el arnés fija la URL en la configuración para dar a cada test su base desechable, un desarrollador con `DATABASE_URL` exportada habría visto los tests **migrar y borrar contra su base de desarrollo**.

**Corrección:** la configuración explícita gana; el entorno es el segundo. En operación normal no cambia nada, porque `alembic.ini` no lleva cadena. Por el mismo motivo, `build_settings()` fija ahora `database_url=None`: sin ese anclaje, los casos que afirman «sin base de datos configurada» dejarían de fallar cuando deben en la máquina de quien tenga la variable puesta.

### 7.3 · `pool.timeout` es un método, no una propiedad

El primer test del pool comparaba un método enlazado contra un número y fallaba siempre. Lo detectó el propio test al ejecutarse por primera vez.

**Corrección:** llamarlo. Anotado en el test para el siguiente que lo lea.

---

## 8. Hallazgo de plataforma, sin corrección de código

**psycopg asíncrono no funciona con el `ProactorEventLoop`**, que es el event loop por defecto de Python en Windows: exige `WindowsSelectorEventLoopPolicy`.

No se corrige en código y el motivo está escrito: producción es un contenedor Linux, los tests de migración usan Alembic, que es síncrono, y bajo `STUB_MODE` nadie pide una sesión. Solo afecta a levantar el servicio con uvicorn directamente en un host Windows cuando una ruta llegue a tocar la base de datos — situación que no existe hasta C13/C14. Cambiar el event loop global desde un módulo de librería sería una intromisión peor que el problema. **Documentado en el README** para quien se lo encuentre.

---

## 9. Revisión de alcance

| Fuera de alcance declarado | Comprobación |
|---|---|
| Ninguna fila insertada | Las seis tablas quedan vacías; solo los tests escriben, y sobre bases desechables |
| Ninguna consulta de similitud | No aparece el operador `<=>` en `src/` |
| Sin modelos ORM ni repositorios | `src/jbg_ai/db/` contiene motor y fábrica de sesiones, nada más |
| Sin `ai.eval_*` ni `ai.query_log` | No creadas; `query_log` queda como pregunta abierta 1 |
| Sin `/health` enriquecido | `GET /health` responde igual que antes del change |
| Sin tocar el contrato | `git diff ai-service/openapi.json` **vacío**; `test_openapi_snapshot_is_stable` en verde |
| Sin ejecución contra RDS de producción | Todo contra Compose local y contenedores efímeros |
| Sin tuning de producción | Ni `halfvec`, ni exploración iterativa, ni `CONCURRENTLY`, ni ciclo de mantenimiento |
| Sin migración de EF Core | `backend/` intacto salvo `docker-compose.yml` |

---

## 10. Gate del proyecto

```
openspec validate --all --strict
Totals: 32 passed, 0 failed (32 items)
```

Ejecutado en la forma `--all --strict`, no en la de un solo change: `CLAUDE.md` recoge que un change puede estar verde mientras las specs vivas con las que sincroniza están rotas, y que así es como tres specs malformadas sobrevivieron sin detectar hasta el 6 de agosto.

---

## 11. Estado del entorno al cerrar

Quedan levantados `jpv-pv-postgres` y `jpv-pv-jbg-ai`, con el esquema `ai` migrado sobre la base de desarrollo y un rol `jbg_ai` con contraseña de desarrollo. **Las seis tablas están vacías**, que es el estado que este change entrega. Para devolver el entorno a como estaba: `docker compose down` desde `backend/`.
