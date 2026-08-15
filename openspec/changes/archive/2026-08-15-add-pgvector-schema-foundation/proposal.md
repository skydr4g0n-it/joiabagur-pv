## Why

El servicio `jbg-ai` arranca, tiene su contrato congelado y el backend .NET sabe hablar con él, pero **no tiene memoria**: no existe ni una dependencia de base de datos, ni una migración, ni un esquema. Todo lo que devuelve hoy sale de fixtures deterministas bajo `STUB_MODE`. Eso convierte a C05 en el cuello de botella real de la Ola 1: la cadena que sostiene el hito del 19 de agosto —C11 texto canónico → C13 indexador → C14 recuperación → C15 endpoint → C16 panel— arranca en C11, y C11 no puede escribir un `source_hash` en ninguna parte mientras `ai.product_document` no exista.

Se hace ahora porque es el único change de la ola que puede empezar sin esperar a nada: su único prerrequisito, C01, está archivado, y C01 dejó la pista preparada a propósito —imagen `pgvector/pgvector:pg15` en Compose con el comentario *«that is C05»*, marcador `db` de pytest ya declarado, carpeta `tests/migrations/` reservada por nombre y la duda sobre RDS ya cerrada en PostgreSQL 15.17.

## What Changes

- **Preparación previa (`bootstrap.sql`), fuera de Alembic**: extensión `vector`, esquema `ai`, **rol de base de datos dedicado** y sus permisos mínimos. Se ejecuta una vez, con privilegios de administrador. Los roles son objetos de clúster, no de base de datos: crearlos desde una migración exigiría privilegio de creación de roles a quien migra y haría fallar la reversión si el rol ya posee objetos.
- **Andamiaje de Alembic** en `ai-service/`, con la tabla de versiones **en el esquema `ai`**. El valor por defecto la crearía en `public` y violaría la frontera del diseño §6.3 —*«Python nunca escribe en `public`»*— en la primerísima migración del lado Python.
- **Una única migración inicial** con seis tablas vacías (`product_document`, `knowledge_document`, `knowledge_chunk`, `pos_projection`, `co_occurrence`, `sync_failure`) y catorce índices declarados: **HNSW con `vector_cosine_ops`** sobre los dos embeddings, **GIN** sobre `tsv`, sobre `materials` y sobre `metadata`, y B-tree sobre `family_id`, `piece_type`, `price_band` y `data_origin`.
- **Vocabularios cerrados con `text` + `CHECK`, nunca `ENUM`**: un tipo enumerado sobrevive al borrado de la tabla y rompe la siguiente aplicación de la migración, semanas después y sin relación aparente con la causa.
- **Columna `tsv` generada** con la configuración española indicada explícitamente, de modo que el idioma del índice léxico sea un hecho de esquema y no una convención que un camino de escritura pueda rodear.
- **Motor asíncrono con pool acotado a 5 conexiones**, sin desbordamiento y de creación perezosa.
- **Cuatro tests que son detectores de fallo mudo**, sobre contenedor efímero con pgvector y base de datos nueva por test.
- Cinco dependencias nuevas en `ai-service` (SQLAlchemy, psycopg 3, pgvector, Alembic y, en desarrollo, testcontainers), rutas de Alembic añadidas al `Dockerfile` para que C17 pueda migrar desde el contenedor, y `DATABASE_URL` en el servicio `jbg-ai` de Compose.

Sin cambios que rompan nada: **ningún router, ningún modelo Pydantic y ninguna modificación de `ai-service/openapi.json`**. Si `test_openapi_snapshot_is_stable` se pone rojo, es la señal de que el change se ha salido de su alcance. Los dos ajustes nuevos son **opcionales** a propósito: la spec viva `ai-service-dev-compose` garantiza que el arranque no requiere base de datos, y hacerlos obligatorios convertiría en falso un escenario ya aceptado y dejaría sin arrancar el contenedor de Compose.

**El principio que ordena el resto: en este change casi ningún error produce un error.** Un test que solo comprueba que la migración aplica es teatro, porque aplicarla ya lo demuestra. El valor está entero en las propiedades que están mal **sin dar ningún aviso**: la *operator class* desalineada con el operador de consulta —que los apuntes del Máster S8 describen como *«el bug operativo más caro y más fácil de cometer en pgvector»*, porque el índice existe, nada protesta y PostgreSQL cae a recorrido secuencial en silencio—, la tabla de versiones en el esquema equivocado, el tipo huérfano tras revertir, y la configuración de texto por defecto en lugar de la española. Sobre los ~1.500 vectores del proyecto ninguno se notaría siquiera en latencia. Cada test de este change se escribe contra uno de esos fallos, nombrado.

## Capabilities

### New Capabilities

- `ai-vector-schema`: capa de persistencia vectorial del servicio `jbg-ai`. Cubre la propiedad del esquema `ai` y la prohibición de escribir en `public`, la instalación de la extensión y el rol dedicado como preparación previa a las migraciones, el ciclo de migración reversible con su tabla de versiones dentro del esquema propio, la forma de las seis tablas del índice y sus invariantes de integridad, las garantías de indexación —*operator class* alineada con el operador de consulta, solape por materiales, configuración léxica española anclada al esquema— y el pool acotado de conexiones.

### Modified Capabilities

- `ai-service-runtime`: el requisito de carga de configuración **enumera** las variables del servicio. Se añaden `DATABASE_URL` y `DB_POOL_SIZE`, ambas **opcionales**, con la garantía explícita de que su ausencia no impide arrancar ni servir las rutas existentes.
- `ai-service-dev-compose`: el requisito de trabajo sin RDS de producción decía que la cadena de conexión *«se omite hasta un change posterior»*; este es ese change, y ahora Compose la aporta apuntando a su propio PostgreSQL. El requisito de disponibilidad de la extensión deja de referirse a *«este change»* —una autorreferencia que en una spec viva ya no tiene antecedente— y pasa a decir quién crea la extensión y quién no: la preparación previa, nunca el arranque de Compose.

## Impact

**Código afectado**

- `ai-service/pyproject.toml` y `uv.lock`: cinco dependencias nuevas. Es la primera adición real desde C02.
- `ai-service/alembic.ini` y `ai-service/migrations/`: **nuevos**, con el entorno de migración, la preparación previa y la única revisión del change.
- `ai-service/src/jbg_ai/db/`: **nuevo**, motor perezoso y fábrica de sesiones.
- `ai-service/src/jbg_ai/config/settings.py`: dos ajustes opcionales.
- `ai-service/tests/migrations/`: **nuevo**, arnés con contenedor efímero y los cuatro detectores. Es la primera carpeta reservada de `tests/README.md` que se materializa.
- `ai-service/Dockerfile`: copia de las rutas de Alembic. Hoy solo copia `src`, así que sin esto **C17 descubriría el 19 de agosto que no puede migrar en producción**.
- `backend/docker-compose.yml`: `DATABASE_URL` en el servicio `jbg-ai`, aditiva y opcional, apuntando al puerto interno del servicio `postgres` y nunca a producción.

**Dependencias**

Cinco paquetes nuevos. Se elige **psycopg 3 como único driver**: `asyncpg` obligaría a dos cadenas de conexión distintas —una para la aplicación y otra para Alembic— y a que alguien recuerde traducir entre ellas. En esta máquina, `uv sync` requiere `--system-certs`.

**Sistemas y contratos**

- No se toca `backend/`, ni el frontend, ni `terraform/`. **No hay migración de EF Core**, así que este change **no compite** por el turno de migración única del plan y puede convivir con C04, C07, C08, C19, C27 o C29.
- `ai-service/openapi.json` no se modifica.
- No se ejecuta nada contra el RDS de producción: eso es C17.

**Fuera de alcance**

Ni una fila insertada (C13, C22, C23); ninguna consulta de similitud ni uso del operador de distancia en código de aplicación (C14); sin modelos ORM ni repositorios —el acceso tipado nace en C11/C13, cuando conozcan su forma—; sin tablas de evaluación (C24); sin `/health` enriquecido ni despliegue (C17); y sin el tuning de producción que S8 documenta —`halfvec`, exploración iterativa con filtros selectivos, construcción concurrente y ciclo de mantenimiento—, que se declara como horizonte con su motivo, no como olvido.

Dos huecos del plan quedan recogidos en lugar de resueltos en silencio: `ai.query_log` aparece en el diseño §7.2 pero **ninguna ficha de change la adjudica**, y el repositorio **no tiene integración continua para Python**. Ninguno entra aquí; ambos van con su opción por defecto en el ticket técnico.
