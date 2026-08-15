> **Línea de corte.** Los grupos 1 a 5 forman una mitad completa y archivable por sí sola —andamiaje, preparación previa, migración, índices y los cuatro detectores—, que es lo único que C11 necesita para arrancar. Los grupos 6 a 8 son la segunda mitad: motor, configuración, contenedor y documentación. Si la sesión se desborda (regla 5 del plan), el corte es aquí y es mecánico.

> **Guardarraíl del arnés.** En el grupo 5 se construyen **únicamente** las aserciones que estos cuatro tests necesitan hoy. Ningún ayudante «por si acaso»: es literalmente el enunciado que produce un DSL de aserciones que nadie pidió y que se come la sesión, tal como C04 dejó anotado para su propio arnés.

> **Guardarraíl de alcance.** Este change **no toca** routers, modelos Pydantic ni `ai-service/openapi.json`. Si `test_openapi_snapshot_is_stable` se pone rojo en cualquier momento, la causa es que el trabajo se ha salido del alcance, no que el contrato deba regenerarse.

## 1. Dependencias y andamiaje de Alembic

- [x] 1.1 Añadir a `ai-service/pyproject.toml` las dependencias de runtime (`sqlalchemy[asyncio]`, `psycopg[binary,pool]`, `pgvector`, `alembic`) y la de desarrollo (`testcontainers[postgres]`), y regenerar `uv.lock`. **Validación:** `uv sync --system-certs` completa y `uv run pytest` sigue en verde sin cambios en los tests existentes
- [x] 1.2 Crear `ai-service/alembic.ini` apuntando a `migrations/`, sin cadena de conexión escrita en el fichero: se lee del entorno. **Validación:** `uv run alembic current` responde sin error de configuración
- [x] 1.3 Escribir `migrations/env.py` con `version_table_schema` en `ai`, y con la creación idempotente del esquema y la extensión **antes** de ceder el control a las revisiones — sin esto, Alembic intenta materializar su tabla de versiones en un esquema que todavía no existe. **Validación:** `uv run alembic upgrade head` sobre base limpia no falla en la tabla de versiones
- [x] 1.4 Fijar el driver `psycopg` en la forma de la URL, de modo que la misma cadena sirva para Alembic (síncrono) y para la aplicación (asíncrono). **Validación:** la misma variable de entorno funciona en los dos caminos. *Verificado con la misma `DATABASE_URL` en ambos. **Hallazgo al aplicar:** psycopg asíncrono no funciona con el `ProactorEventLoop`, que es el event loop por defecto de Python en Windows; exige `WindowsSelectorEventLoopPolicy`. No afecta a producción (contenedor Linux) ni a los tests (Alembic es síncrono), pero sí a ejecutar el servicio con uvicorn directamente en Windows. Se documenta en 8.1*

## 2. Preparación previa fuera de Alembic

- [x] 2.1 Escribir `migrations/bootstrap.sql` con la extensión, el esquema, el rol dedicado y sus permisos: uso y creación sobre `ai`, y sobre `public` **solo** lo necesario para resolver el tipo `vector`, sin `SELECT` sobre ninguna tabla. **Validación:** ejecutado como superusuario sobre el PostgreSQL de Compose, deja el rol capaz de crear en `ai` e incapaz de leer `public`
- [x] 2.2 Documentar en `ai-service/README.md` que se ejecuta **una sola vez y con privilegios de administrador**, y que en producción es alcance de C17 contra RDS. **Validación:** un lector que sigue el README desde cero llega a una migración aplicada. *Se aprovechó para dejar el README entero al día —variables nuevas, sección de base de datos, tests de migración, no-objetivos y layout—, así que 8.1 solo tendrá que verificarlo*

## 3. Migración inicial — tablas

- [x] 3.1 Crear la revisión única del change y declarar en ella el esquema y la extensión de forma idempotente, para que el SQL sea autodescriptivo sin depender del entorno de migración. **Validación:** aplicar dos veces seguidas no produce error
- [x] 3.2 Declarar `ai.product_document`: clave por identificador de producto, materiales como array, texto canónico y hash, embedding **nulable**, marca de actividad, origen del dato y metadatos de modelo. Vocabularios cerrados con `CHECK`, **nunca** con tipo enumerado. **Validación:** insertar un origen fuera del vocabulario es rechazado; insertar sin embedding es aceptado
- [x] 3.3 Declarar `ai.knowledge_document` y `ai.knowledge_chunk`, con clave foránea **intra-esquema** y borrado en cascada, y unicidad del par documento/índice de fragmento. **Validación:** borrar un documento borra sus fragmentos; repetir el índice de fragmento es rechazado
- [x] 3.4 Declarar `ai.pos_projection` con clave compuesta y disponibilidad como **bucket con `CHECK`**, nunca cantidad exacta. **Validación:** un valor fuera del vocabulario de buckets es rechazado
- [x] 3.5 Declarar `ai.co_occurrence` con clave por el par y **`CHECK` de orientación** (primero estrictamente menor que segundo). **Validación:** el par en orden descendente es rechazado, y el mismo par no puede almacenarse dos veces
- [x] 3.6 Declarar `ai.sync_failure` con feed, cursor, payload, error, intentos e instante del próximo reintento. **Validación:** la fila conserva contexto suficiente para reintentar el lote
- [x] 3.7 Declarar las columnas de texto completo como **generadas y almacenadas**, con la configuración `'spanish'` nombrada explícitamente — la forma de dos argumentos, que es la inmutable y por tanto la única legal aquí. **Validación:** el catálogo muestra columna generada y la expresión nombra la configuración española
- [x] 3.8 Revisar que **ninguna columna que referencia entidades de .NET lleva clave foránea** hacia `public`. **Validación:** la consulta de restricciones del esquema `ai` no devuelve ninguna que apunte a `public`

## 4. Índices y reversión

- [x] 4.1 Declarar los dos índices HNSW con **`vector_cosine_ops`** y parámetros explícitos (`m = 16`, `ef_construction = 128`, según S8 y no los valores por defecto del motor). **Validación:** el catálogo devuelve método `hnsw` y clase de operadores de coseno para ambos
- [x] 4.2 Declarar los índices GIN sobre las dos columnas de texto completo, sobre el array de materiales y sobre el documento de metadatos de los fragmentos. **Validación:** el catálogo los devuelve como GIN
- [x] 4.3 Declarar los índices B-tree sobre familia, tipo de pieza, banda de precio y origen del dato, más el de búsqueda inversa de la proyección y el de la cola de reintentos. **Validación:** catorce índices declarados en total, además de las seis claves primarias
- [x] 4.4 Escribir la reversión: borra **las seis tablas y nada más**; el esquema y la extensión se quedan, porque la extensión es un objeto compartido de la base de datos y el esquema alberga la propia tabla de versiones. **Validación:** tras revertir, las tablas no existen y esquema y extensión sí

## 5. Arnés de test y los cuatro detectores

- [x] 5.1 Escribir `ai-service/tests/migrations/conftest.py` con contenedor efímero pgvector de ámbito de sesión, **una base de datos nueva por test** y omisión con motivo legible si Docker no responde. Resolver rutas desde `support/paths.py`, nunca con `Path(__file__).parents[N]`. **Validación:** los tests corren aislados y en cualquier orden; sin Docker, la suite completa sigue verde
- [x] 5.2 `test_migration_creates_vector_extension_and_ai_schema`: extensión instalada, esquema presente, las seis tablas dentro, y **tabla de versiones en `ai` y no en `public`**. **Validación:** pasa sobre base limpia
- [x] 5.3 `test_hnsw_index_uses_cosine_operator_class`: **join al catálogo** (índice → clase de operadores → método de acceso), no búsqueda de cadena en el texto del índice. **Validación:** afirma clase de coseno y método HNSW para los dos embeddings
- [x] 5.4 `test_gin_index_exists_on_materials`: índice GIN sobre el array de materiales, que es lo que sostiene los filtros de solape y contención del diseño §7.3. **Validación:** pasa, y también las aserciones hermanas sobre texto completo y metadatos
- [x] 5.5 `test_upgrade_downgrade_is_reversible` con **las tres piernas**: aplicar, revertir, **volver a aplicar**. Sin la tercera el test no detecta objetos huérfanos, que es su único motivo de existir. **Validación:** pasa completo
- [x] 5.6 Romper a propósito lo que cada detector vigila —empezando por sustituir la clase de operadores por la euclídea—, comprobar que **el test falla**, y revertir la rotura. **Validación:** los cuatro fallan cuando deben y vuelven a verde tras revertir

## 6. Motor de base de datos y configuración

- [x] 6.1 Añadir a `config/settings.py` la cadena de conexión y el tamaño de pool como **opcionales**, sin valor por defecto la primera y con 5 el segundo. **Validación:** `test_settings_fail_fast_when_required_env_missing` sigue en verde y cargar sin ellas funciona
- [x] 6.2 Implementar el motor asíncrono en `src/jbg_ai/db/`, con pool acotado sin desbordamiento, espera por conexión muy por debajo del presupuesto de 0,8 s que .NET concede a la recuperación, y comprobación previa de conexión. **Validación:** el tope efectivo es 5 y no hay conexiones adicionales
- [x] 6.3 Hacer la creación **perezosa**: importar el módulo no construye motor ni abre conexión, y pedir sesión sin configuración falla con un error que nombra lo que falta. **Validación:** importar el módulo no abre sockets; el fallo ocurre al pedir sesión, no al arrancar
- [x] 6.4 Comprobar que el servicio arranca y sirve `/health` y las rutas `/v1` **sin cadena de conexión definida**. **Validación:** escenario de la spec de runtime en verde

## 7. Contenedor y Compose

- [x] 7.1 Añadir `alembic.ini` y `migrations/` al `Dockerfile`, que hoy copia solo `src` — **sin esto C17 no puede migrar en producción, y lo descubriría el 19 de agosto**. **Validación:** `alembic upgrade head` se ejecuta desde dentro de la imagen construida
- [x] 7.2 Añadir la cadena de conexión al servicio `jbg-ai` de `backend/docker-compose.yml`, resolviendo el servicio `postgres` por nombre de red y **puerto interno**, no por el puerto publicado en el host, y sin `depends_on` porque el motor es perezoso. **Validación:** `docker compose up jbg-ai` arranca sin configuración extra y aunque la base no esté preparada

## 8. Documentación y verificación final

- [x] 8.1 Actualizar `ai-service/README.md`: variables nuevas y su opcionalidad, preparación previa, cómo migrar, cómo ejecutar los tests de base de datos y por qué se omiten sin Docker. **Validación:** un lector reproduce el flujo completo desde cero
- [x] 8.2 Actualizar `Documentos/modelo-de-datos.md` con el esquema `ai` y `Documentos/epicas.md` (EP11) con la historia entregada. **Validación:** el esquema documentado coincide con la migración aplicada
- [x] 8.3 Verificar la suite completa y el contrato: `uv run pytest` en verde y `ai-service/openapi.json` **sin cambios**. **Validación:** `test_openapi_snapshot_is_stable` en verde y `git diff` no toca el snapshot
- [x] 8.4 Ejecutar **`openspec validate --all --strict`** y comprobar `0 failed` — el gate del proyecto, no la forma de un solo change. **Validación:** la salida reporta cero fallos
