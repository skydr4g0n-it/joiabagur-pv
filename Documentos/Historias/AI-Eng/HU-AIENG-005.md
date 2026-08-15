# HU-AIENG-005: Cimiento de persistencia vectorial — extensión `vector`, esquema `ai` y migraciones Alembic

## Formato estándar

Como **desarrollador del proyecto**, quiero **un esquema `ai` con pgvector, migraciones Alembic propias del lado Python y las tablas del índice vacías pero con sus índices correctos** **para** **que la indexación, la recuperación y la evaluación puedan construirse a partir de la semana siguiente sobre una capa de datos que ya está probada, en lugar de improvisarla dentro del primer change que la necesite**.

---

## Descripción

Primer change de la Ola 1 del Proyecto Final de IA (change OpenSpec `add-pgvector-schema-foundation` / C05, épica **EP11 — Plataforma del Servicio de IA**). Está en la **ruta crítica** 🔴 y es el **primer change con migración del lado Python**, equivalente para Alembic a lo que C04 fue para EF Core.

El valor no es de usuario final —esta historia no entrega ni pantalla ni endpoint— sino de **cimiento**. C11 construye el texto canónico y el cliente de embeddings, C13 puebla el índice, C14 hace la primera recuperación real y C24 mide: los cuatro escriben o leen en `ai.*`, y ninguno puede empezar mientras esas tablas no existan. Que este change se resuelva mal no se nota en septiembre: se nota en que cada uno de los cuatro siguientes paga un rodeo.

La particularidad de esta historia es que **casi ninguno de sus errores produce un error**. Un `ENUM` que sobrevive al `downgrade`, una tabla de versiones de Alembic creada en `public`, una `tsvector` construida con la configuración por defecto en lugar de la española, o —el caso de libro— un índice HNSW creado con la *operator class* equivocada: los cuatro compilan, migran y arrancan. El último es el más caro y el mejor documentado: los apuntes del Máster S8 lo describen como *«el bug operativo más caro y más fácil de cometer en pgvector»*, porque el índice existe, `CREATE INDEX` no protesta, las consultas devuelven resultados correctos, y lo único que cambia es que PostgreSQL ha caído a *sequential scan* en silencio. Sobre los ~1.500 vectores del proyecto tampoco se notaría en latencia. Por eso los cuatro tests de esta historia no son cobertura: son **detectores de fallo mudo**, y se escriben con ese propósito explícito.

C01 dejó la pista preparada a propósito: la imagen de Compose ya es `pgvector/pgvector:pg15` con el comentario *«Do NOT create schema `ai` or run CREATE EXTENSION here — that is C05»*, el marcador `db` de pytest ya está declarado como *«needs a PostgreSQL instance with pgvector»*, la carpeta `tests/migrations/` ya está reservada por nombre para este change, y la duda sobre si RDS admite la extensión ya se cerró (PostgreSQL 15.17). Esta historia consume esa preparación.

**Alcance de esta historia (sí):**

- Dependencias nuevas de `ai-service`: `sqlalchemy[asyncio]`, `psycopg[binary,pool]`, `pgvector` y `alembic` en runtime; `testcontainers[postgres]` en desarrollo.
- Andamiaje de Alembic en `ai-service/` (`alembic.ini` + `migrations/`), con la tabla de versiones **en el esquema `ai`**, nunca en `public`.
- `bootstrap.sql`: extensión `vector`, esquema `ai`, **rol de base de datos dedicado** y sus permisos, ejecutado una vez por un administrador y documentado.
- **Una única migración inicial** con seis tablas vacías: `ai.product_document`, `ai.knowledge_document`, `ai.knowledge_chunk`, `ai.pos_projection`, `ai.co_occurrence` y `ai.sync_failure`.
- Índices: **HNSW con `vector_cosine_ops`** sobre los dos `embedding`, **GIN** sobre `tsv`, sobre `materials` y sobre `metadata`, y B-tree sobre `family_id`, `piece_type`, `price_band` y `data_origin`.
- Columna `tsv` **generada** con `to_tsvector('spanish', …)`, de modo que la configuración española sea un hecho de esquema y no una convención que alguien pueda rodear.
- Motor SQLAlchemy asíncrono con **pool acotado a 5 conexiones**, creado de forma perezosa.
- Ajustes de configuración: `DATABASE_URL` y `DB_POOL_SIZE`, ambos **opcionales**, y `DATABASE_URL` en el servicio `jbg-ai` de Compose.
- Arnés de test con contenedor efímero pgvector y **base de datos nueva por test**, más los cuatro tests de la ficha.
- Copia de `alembic.ini` y `migrations/` en el `Dockerfile`, para que C17 pueda migrar desde el contenedor.

**Fuera de alcance (no):**

- **Cualquier dato.** Las seis tablas nacen y se quedan vacías: poblarlas es C13 (catálogo), C22 (proyección de POS) y C23 (conocimiento).
- **Cualquier consulta.** No hay `SELECT`, ni búsqueda vectorial, ni `<=>` en código de aplicación → C14.
- **Modelos ORM o repositorios.** La migración se escribe a mano; el acceso tipado nace en C11/C13 cuando sepan su forma.
- Tablas `ai.eval_run` / `ai.eval_case` / `ai.eval_result` → **C24**. `ai.query_log` no se crea: no está adjudicada a ningún change y se recoge como pregunta abierta.
- `GET /health` enriquecido con comprobación de base de datos → **C17**.
- Ejecución de `CREATE EXTENSION vector` sobre RDS de producción y despliegue del contenedor → **C17**.
- `halfvec`, `hnsw.iterative_scan`, `REINDEX CONCURRENTLY` y el resto del tuning de producción de los apuntes S8: se documentan como horizonte, no se aplican.
- Cambios en el contrato: **ningún router, ningún schema Pydantic y ningún cambio en `ai-service/openapi.json`**.
- Cualquier acceso SQL al esquema `public`, en cualquier dirección.

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Principio rector | **Todo error caro de este change es silencioso.** Un test que solo comprueba que la migración aplica es teatro: `alembic upgrade head` ya lo demuestra. El valor está entero en las propiedades que están mal **sin dar ningún error**. Cada test se escribe contra un fallo mudo concreto y nombrado |
| Dónde vive `alembic_version` | **En el esquema `ai`**, vía `version_table_schema`. El diseño §6.3 dice que *«Python nunca escribe en `public`»*, y el valor por defecto de Alembic lo incumpliría en la primera migración |
| Huevo y gallina del esquema | Alembic materializa su tabla de versiones **antes** de ejecutar el primer script, así que `CREATE SCHEMA` dentro de `upgrade()` llega tarde. Lo crea `env.py`; la migración lo declara igualmente con `IF NOT EXISTS`, para que el SQL siga siendo autodescriptivo |
| Esquema de la extensión | **`public`** (el destino por defecto), documentado como excepción explícita. `CREATE EXTENSION vector SCHEMA ai` obligaría a cualificar el tipo como `ai.vector(1536)` y a manipular el `search_path` en cada conexión, para siempre. La regla de propiedad habla de **datos**, no de instalación de extensiones |
| Vocabularios cerrados | **`text` + `CHECK`, nunca `ENUM`.** `sa.Enum` crea un tipo que `drop_table` **no** borra: el `downgrade` deja el tipo huérfano y el siguiente `upgrade` falla con *«type already exists»*. Además los vocabularios aún se están decidiendo (materiales en C09, `doc_type` en C23) |
| Usuario dedicado | **Fuera de Alembic**, en `bootstrap.sql` ejecutado una vez por un administrador. Los roles son de **clúster**, no de base de datos; un `DROP ROLE` en el `downgrade` falla si el rol posee objetos |
| Una sola cadena de conexión | No hacen falta `DATABASE_URL` y `DATABASE_ADMIN_URL`. `CREATE EXTENSION IF NOT EXISTS` es no-op cuando el administrador ya la creó, que es exactamente el camino de RDS, y funciona tal cual en local, donde se migra como superusuario |
| Driver | **psycopg 3**, uno solo. `asyncpg` obligaría a dos URLs (`+asyncpg` para la app, `+psycopg2` para Alembic) y a que alguien recuerde traducir entre ellas. `postgresql+psycopg://` habla sync para Alembic y async para FastAPI |
| Operator class del índice vectorial | **`vector_cosine_ops`** con el operador `<=>`, siguiendo S8. Con embeddings normalizados de OpenAI, `<#>` ordenaría igual y sería algo más barato, pero coseno es la convención de la literatura y **sigue siendo correcto si algún día se cambia a un modelo que no normalice** |
| Parámetros HNSW | **`m = 16`, `ef_construction = 128`**, declarados explícitamente. El `ef_construction` por defecto de pgvector es 64; S8 fija 128 como punto de partida para 1536 dimensiones. `ef_search` es de consulta y no se toca aquí → C14 |
| Índice sobre tabla vacía | **Es legítimo y es el motivo de elegir HNSW.** IVFFlat necesita entrenamiento con k-means y no puede construirse sin datos; HNSW absorbe inserciones de forma incremental. Que las seis tablas nazcan vacías con sus índices puestos es una propiedad del algoritmo, no un atajo |
| Dimensión del vector | **`vector(1536)` fijo**, la de `text-embedding-3-small`. S8 lo pide *hardcodeado deliberadamente*, y el diseño §6.3 ya establece que cambiar de modelo se hace en **columna nueva**, nunca sobrescribiendo |
| `embedding` nulable | **Sí.** Permite que una fila exista antes de que su embedding esté calculado, que es justo el patrón de ingesta que C13 necesita para separar el `upsert` del cálculo |
| `tsv` | **Columna generada** con `to_tsvector('spanish', doc_text)`. La forma de dos argumentos es `IMMUTABLE` y por tanto legal en una columna generada; la de un argumento no lo es. Convierte el `test_tsvector_uses_spanish_configuration` de C13 en un hecho de esquema |
| Claves foráneas hacia `public` | **Ninguna.** `product_id`, `pos_id` y `family_id` son columnas `uuid` planas. Una FK real acoplaría `ai` a las tablas de EF Core, haría fallar migraciones de .NET por dependencia y contradiría la frontera del diseño §6.3 |
| Claves foráneas dentro de `ai` | **Sí**, y con `ON DELETE CASCADE` de `knowledge_chunk` hacia `knowledge_document`: borrar un documento debe llevarse sus fragmentos sin lógica aplicativa, como en el modelo de referencia de S8 |
| Orientación de `co_occurrence` | Clave primaria `(product_a, product_b)` **más `CHECK (product_a < product_b)`**. Sin esa restricción cada par se almacena dos veces y C27 dobla su señal de complementarios |
| `qty_bucket` | **Bucket, nunca cantidad exacta** (diseño §7.2). Guardar el número real invitaría a mostrarlo, y la proyección puede estar desfasada: la cantidad la pone .NET |
| Qué borra el `downgrade` | **Las seis tablas y nada más.** El esquema `ai` y la extensión sobreviven, porque la extensión es un objeto compartido de la base de datos y porque borrar el esquema se llevaría por delante la propia tabla de versiones de Alembic a mitad de operación |
| Forma del test de reversibilidad | **Tres piernas, no dos:** `upgrade` → `downgrade` → **`upgrade` otra vez**. Sin la tercera, un tipo o un índice huérfano pasa desapercibido, que es precisamente el fallo que la decisión de `text`+`CHECK` evita |
| Cómo se afirma la *operator class* | **Join al catálogo** (`pg_index` → `pg_opclass` → `pg_am`), afirmando `opcname = 'vector_cosine_ops'` **y** `amname = 'hnsw'`. La alternativa —buscar la cadena en `pg_indexes.indexdef`— también detecta el fallo, porque PostgreSQL **omite la *operator class* del `indexdef` cuando es la de por defecto**, pero depende de una regla de renderizado en lugar de un hecho |
| Verificación por plan de ejecución | **No aquí.** S8 enseña `EXPLAIN ANALYZE` como reflejo correcto, pero sobre tablas vacías el planificador elegiría *sequential scan* de todos modos y la aserción no significaría nada. Se difiere a C14, que ya tendrá datos |
| Se rompe el test a propósito | Tarea explícita, como en C04: alterar la *operator class* a `vector_l2_ops`, comprobar que el test **falla**, y revertir. Un detector de fallos mudos que nadie ha visto fallar es él mismo un fallo mudo |
| Cómo obtienen los tests su PostgreSQL | **Contenedor efímero `pgvector/pgvector:pg15`** por sesión y **base de datos nueva por test**. El test de reversibilidad muta el esquema; compartir base lo haría dependiente del orden, que es el patrón que `CLAUDE.md` ya documenta como veneno en la suite de .NET |
| Sin Docker disponible | **`skip` elegante, no rojo permanente.** No hay flujo de integración continua para Python en el repositorio, así que la única defensa es que `uv run pytest` siga verde en un portátil sin Docker en marcha. Cuatro rojos fijos enseñan a ignorar el rojo |
| `DATABASE_URL` | **Opcional**, y el motor se crea de forma perezosa. La spec viva `ai-service-dev-compose` afirma que *«el arranque de `jbg-ai` no debe requerir conexión a base de datos»*: hacerla obligatoria convertiría en falso un escenario ya aceptado y dejaría sin arrancar el contenedor de Compose |
| Tamaño del pool | **`pool_size = 5`, `max_overflow = 0`** — «acotado a 5» en su lectura literal, y coherente con la restricción de `openspec/project.md` (*máx. 5-10 conexiones*), que se comparten con .NET sobre el mismo RDS |
| Espera del pool | `pool_timeout` **muy por debajo de los 30 s por defecto**, más `pool_pre_ping`. .NET corta la recuperación a 0,8 s con Polly: esperar 30 s por una conexión es trabajar para un cliente que ya se marchó, y RDS cierra conexiones ociosas |
| Modelos ORM y `autogenerate` | **Ninguno todavía.** `autogenerate` no expresa *operator classes* de HNSW, GIN sobre `text[]` ni columnas generadas: produciría una migración que hay que reescribir y un test de desfase con ruido permanente. Mismo guardarraíl que C04 puso a su arnés: solo lo que este change necesita hoy |
| Contrato con .NET | **Intacto.** Ni routers, ni modelos Pydantic, ni `openapi.json`. Si `test_openapi_snapshot_is_stable` se pone rojo, es la señal de que el change se ha salido de su alcance |

**Referencias:**
[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C05, reglas transversales de testing),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.3 frontera y contrato de sincronización, §7.2 esquema del índice, §7.3 filtro por materiales, §7.6 prefiltro blando),
[Anatomía de un índice vectorial](../../Sesiones%20Master%20AIEng/S8_BBDD_Vectoriales/Anatomia%20de%20un%20Indice%20Vectorial%20HNSW,%20IVFFlat%20y%20el%20horizonte%20DiskANN.md) (parámetros HNSW, por qué no IVFFlat),
[Diseño del esquema y búsqueda semántica](../../Sesiones%20Master%20AIEng/S8_BBDD_Vectoriales/Dise%C3%B1o%20del%20esquema%20y%20busqueda%20semantica.md) (antipatrón de la *operator class*, `vector(1536)`, `embedding` nulable, GIN sobre `metadata`),
[Del prototipo a producción](../../Sesiones%20Master%20AIEng/S8_BBDD_Vectoriales/Del%20prototipo%20a%20produccion%20Tuning,%20Monitorizacion%20y%20techo%20PGVector.md) (sizing, `halfvec`, mantenimiento — horizonte, fuera de alcance),
[epicas.md](../../epicas.md) (EP11),
[modelo-de-datos.md](../../modelo-de-datos.md),
[HU-AIENG-001.md](HU-AIENG-001.md), [HU-AIENG-004.md](HU-AIENG-004.md),
specs vivas `openspec/specs/ai-service-runtime/spec.md` y `openspec/specs/ai-service-dev-compose/spec.md`,
contrato congelado `ai-service/openapi.json`,
change OpenSpec `openspec/changes/add-pgvector-schema-foundation/` y su ticket técnico.

---

## Criterios de Aceptación

### Escenario 1: La migración deja la extensión y el esquema en pie
**Dado que** existe una base de datos PostgreSQL limpia con pgvector disponible pero sin la extensión creada
**Cuando** se ejecuta la migración hasta la última revisión
**Entonces** la extensión `vector` queda instalada y consultable en el catálogo
**Y** el esquema `ai` existe
**Y** las seis tablas del índice existen dentro de ese esquema
**Y** volver a ejecutar la migración sobre la misma base no produce error

### Escenario 2: El índice vectorial usa la *operator class* de coseno, no la de por defecto
**Dado que** la migración se ha aplicado sobre una base de datos limpia
**Cuando** se consulta el catálogo de PostgreSQL por los índices de las columnas de embedding
**Entonces** el método de acceso de cada uno es `hnsw`
**Y** su *operator class* es `vector_cosine_ops`, que es la que corresponde al operador `<=>` con el que C14 consultará
**Y** la comprobación falla si alguien la sustituye por `vector_l2_ops`, aunque `CREATE INDEX` no dé ningún error y las consultas sigan devolviendo resultados

### Escenario 3: El filtro por materiales tiene índice de solape
**Dado que** el diseño §7.3 resuelve el filtro por materiales con solape (`&&`) y contención (`@>`) sobre un `text[]`
**Cuando** se inspeccionan los índices de la tabla de documentos de producto
**Entonces** existe un índice **GIN** sobre la columna `materials`
**Y** existe también un GIN sobre `tsv`, y otro sobre la columna `metadata` de los fragmentos de conocimiento

### Escenario 4: La migración es reversible de verdad
**Dado que** la migración se ha aplicado sobre una base de datos limpia
**Cuando** se revierte hasta el estado inicial
**Entonces** las seis tablas dejan de existir
**Y** el esquema `ai` y la extensión `vector` siguen en pie
**Y al volver a aplicarla**, la migración vuelve a completarse sin error, sin colisionar con ningún tipo ni índice que hubiera quedado huérfano

### Escenario 5: Alembic no escribe en el esquema de .NET
**Dado que** la frontera del diseño §6.3 prohíbe a Python escribir en `public`
**Cuando** se ejecuta la migración sobre una base de datos limpia
**Entonces** la tabla de versiones de Alembic está en el esquema `ai`
**Y** no existe ninguna tabla de versiones en `public`
**Y** la migración no ha creado ninguna otra tabla fuera del esquema `ai`

### Escenario 6: La búsqueda léxica queda anclada al español por construcción
**Dado que** la rama léxica de C21 usa `ts_rank` con configuración española
**Cuando** se inspecciona la definición de la columna `tsv` de documentos de producto y de fragmentos de conocimiento
**Entonces** es una columna generada y almacenada
**Y** su expresión usa `to_tsvector` con la configuración `'spanish'` indicada explícitamente
**Y** ningún camino de escritura puede poblarla con otra configuración

### Escenario 7: El servicio sigue arrancando sin base de datos
**Dado que** la spec viva de Compose garantiza que `jbg-ai` arranca sin conexión a base de datos
**Cuando** se cargan los ajustes sin `DATABASE_URL`
**Entonces** la carga es correcta y el servicio arranca
**Y** `GET /health` responde 200 igual que antes de este change
**Y** las rutas `/v1` siguen respondiendo desde los stubs sin abrir ninguna conexión

### Escenario 8: El pool está acotado y no espera más de lo que el llamante tolera
**Dado que** el presupuesto de conexiones se comparte con .NET sobre el mismo RDS
**Cuando** se construye el motor de base de datos con la configuración por defecto
**Entonces** el número máximo de conexiones simultáneas del pool es 5, sin desbordamiento adicional
**Y** el tiempo de espera por una conexión libre es sensiblemente menor que el que .NET concede a una recuperación
**Y** el motor solo se crea cuando alguien lo pide por primera vez, no al importar el módulo

### Escenario 9: Sin la preparación previa, el fallo es explícito
**Dado que** se intenta migrar contra una base de datos donde nadie ha ejecutado la preparación previa y el rol que conecta no puede instalar extensiones
**Cuando** se ejecuta la migración
**Entonces** falla de forma inmediata y con un mensaje que identifica la causa
**Y** no deja el esquema a medias
**Y** la documentación indica qué ejecutar, con qué privilegios y una sola vez

### Escenario 10: Sin Docker, la suite no miente
**Dado que** un desarrollador ejecuta la suite completa en un equipo sin Docker en marcha
**Cuando** se ejecutan los tests de migración
**Entonces** quedan omitidos con un motivo legible
**Y** el resto de la suite pasa en verde
**Y** ningún test de migración se marca como superado sin haber tocado una base de datos real

### Escenario 11: Fuera de alcance explícito
**Dado que** esta historia está implementada
**Cuando** se revisa el entregable
**Entonces** las seis tablas están vacías: este change no inserta ni una fila
**Y** no existe ninguna consulta de similitud ni ningún uso del operador `<=>` en código de aplicación
**Y** no existen modelos ORM ni repositorios
**Y** `GET /health` no comprueba la base de datos
**Y** el snapshot `ai-service/openapi.json` no ha cambiado, y su test de estabilidad sigue en verde
**Y** no se ha ejecutado nada contra el RDS de producción

---

## Notas adicionales

- **Actor:** historia de plataforma para el equipo del Proyecto Final. No hay pantalla ni endpoint; los beneficiarios directos son C11 (texto canónico y embeddings), C13 (indexador), C14 (recuperación), C22 (proyección de POS), C23 (corpus de conocimiento) y C24 (evaluación).

- **Por qué está en la ruta crítica.** C05 desbloquea C11, y de C11 cuelga la cadena C13 → C14 → C15 → C16 que sostiene el hito del **19 de agosto**: un operador buscando en lenguaje natural desde `pv.joiabagur.com`. Es el único change de la Ola 1 que puede empezar hoy sin esperar a nada más que C01.

- **No compite por el turno de migración de .NET.** La regla 4 del plan limita a **una migración de EF Core activa a la vez** y afecta a C04, C07, C08, C19, C27 y C29. Alembic es un árbol de migraciones independiente, así que C05 puede convivir con cualquiera de ellos. Esa independencia también significa que **una segunda migración Alembic más adelante es barata**, lo que justifica no adelantar tablas que ningún change necesita todavía.

- **El corpus real todavía no existe, y no importa.** Las tablas nacen vacías por diseño, no por falta de datos: HNSW se construye sobre tabla vacía y absorbe inserciones de forma incremental. Con IVFFlat esta historia no habría sido posible sin corpus previo, y ese es exactamente el motivo por el que S8 descarta IVFFlat para RAG con corpus creciente.

- **Volumen esperado:** ~1.200-1.500 vectores de producto y unos pocos centenares de fragmentos de conocimiento. El diseño §7.2 ya lo dice sin rodeos: *«pgvector con HNSW es holgado aquí; la decisión se justifica por operación —una sola base de datos, filtros SQL nativos, cero infraestructura nueva—, no por escala»*. Ningún índice de este change mejora una latencia medible en la entrega; se ponen porque el coste de tenerlos es nulo y el de añadirlos con datos dentro no lo es.

- **Limitaciones declaradas:** no se aplica `halfvec` (que S8 recomienda «desde el día uno» para producción real), ni `hnsw.iterative_scan` para filtros muy selectivos, ni ciclo de mantenimiento (`VACUUM ANALYZE`, `REINDEX CONCURRENTLY`), ni tuning de `shared_buffers` / `maintenance_work_mem`. A la escala del proyecto ninguno cambia una cifra medible, pero conviene que quede escrito para el README de C39: son decisiones tomadas, no olvidos.

- **`ai.query_log` queda sin adjudicar.** Aparece en el diseño §7.2 junto a las tablas de evaluación, pero ninguna ficha del plan la reclama: las de evaluación son de C24 y esta no es de nadie. Se recoge como pregunta abierta en el ticket con su opción por defecto —no crearla— en lugar de colarla en silencio.

- **No existe integración continua para Python.** El repositorio tiene `test-backend.yml` y `test-frontend.yml`, pero ningún flujo que ejecute `uv run pytest`. No entra en esta historia, pero condiciona una decisión suya: los tests de base de datos se omiten con motivo cuando no hay Docker, porque no hay un CI que los ejecute siempre y unos rojos permanentes en local acabarían normalizando el rojo.

- **OpenSpec:** se implementa vía el change `add-pgvector-schema-foundation` (proposal → design → specs → tasks → apply → verify → archive). Este change **sí lleva `design.md`**, aunque la lista del plan §7 no lo incluya: el destino de la tabla de versiones, el esquema de la extensión, `text` frente a `ENUM` y la ubicación del rol dedicado son decisiones con alternativas reales cuyo coste se paga en C11, C13 y C17.

- **Línea de corte prevista.** Si la sesión se desborda (regla 5 del plan), el corte es tras las tareas de esquema y tests: **andamiaje + bootstrap + migración + arnés + los cuatro tests** forman una mitad archivable por sí sola, y el motor con su pool, los ajustes y Compose son la segunda. C11, el único dependiente, necesita el esquema mucho antes que el motor, y además espera a C09.

---

## Tareas

> Ordenadas para que las tareas 1-6 formen una mitad completa y archivable por sí sola (esquema, migración y detectores), y las 7-9 la segunda mitad (motor, configuración y documentación), por si hay que aplicar la línea de corte.

1. Añadir las dependencias de base de datos a `ai-service` y regenerar el bloqueo de versiones, verificando que la suite existente sigue en verde.
2. Montar el andamiaje de Alembic con la tabla de versiones en el esquema `ai`, y la creación previa del esquema y la extensión en el entorno de migración, ambas idempotentes.
3. Escribir `bootstrap.sql` con la extensión, el esquema, el rol dedicado y sus permisos, y documentar que se ejecuta **una vez, con privilegios de administrador**.
4. Escribir a mano la migración inicial con las seis tablas, sus vocabularios como `text` + `CHECK`, las columnas `tsv` generadas en español, la restricción de orientación de co-ocurrencia y **ninguna clave foránea hacia `public`**.
5. Declarar los índices: HNSW con `vector_cosine_ops` y parámetros explícitos sobre los dos embeddings, GIN sobre `tsv`, `materials` y `metadata`, y los B-tree del diseño §7.2. Escribir el `downgrade` que borra solo las tablas.
6. Construir el arnés de test con contenedor efímero y base por test, escribir los cuatro detectores, y **verificar que cada uno falla al romper a propósito lo que vigila**, revirtiendo después.
7. Añadir `DATABASE_URL` y el tamaño de pool a la configuración como **opcionales**, e implementar el motor asíncrono perezoso con el pool acotado y la espera recortada.
8. Añadir `DATABASE_URL` al servicio `jbg-ai` de Compose y las rutas de Alembic al `Dockerfile`, para que C17 pueda migrar desde el contenedor.
9. Actualizar `ai-service/README.md`, `Documentos/modelo-de-datos.md` y las referencias del Proyecto Final; verificar `uv run pytest` en verde y el snapshot OpenAPI intacto.

---

## Estimaciones y atributos de priorización

> Valores propuestos a partir de la guía de estimación de [Procedimiento-TicketsTrabajo.md](../../Procedimientos/Procedimiento-TicketsTrabajo.md) (§4.6). **Pendientes de validar** en la sesión de refinamiento del equipo.

- **Puntos de historia:** **5** — no hay algoritmo ni lógica de negocio, pero es la primera vez que el proyecto instala una capa de datos en Python: cinco dependencias nuevas, andamiaje de migraciones, arnés de test con contenedor y seis tablas con catorce índices declarados, cada uno con una decisión detrás.
- **Impacto en usuario / Valor de negocio:** **2** — nulo de forma directa. El valor es habilitador: sin esta capa, cuatro changes de la ruta crítica no pueden empezar.
- **Urgencia (mercado / feedback):** **5** — 🔴 ruta crítica y primer change desbloqueado de la Ola 1. Retrasarlo retrasa la cadena entera hasta el hito del 19 de agosto.
- **Complejidad / Esfuerzo:** **3** — la dificultad no está en escribir el SQL, sino en que **ninguno de los errores caros avisa**: la *operator class* equivocada, el tipo huérfano tras el `downgrade`, la tabla de versiones en `public` o la `tsvector` en la configuración por defecto compilan, migran y arrancan igual.
- **Riesgos y dependencias:**
  - **Prerrequisito:** C01, ya archivado. Sin prerrequisitos hacia adelante: a diferencia de C04, este change no depende de que nadie recuerde llamarlo — quien necesite las tablas fallará de inmediato si no están.
  - **Riesgo:** el índice HNSW se crea con `vector_l2_ops` (la *operator class* por defecto) mientras C14 consulta con `<=>`; el índice queda desactivado en silencio y sobre 1.500 vectores nadie lo nota nunca → mitigado con la aserción sobre el catálogo del escenario 2 y con la tarea de romperla a propósito.
  - **Riesgo:** la tabla de versiones de Alembic nace en `public` con la configuración por defecto, y la primera migración del proyecto viola la frontera que el diseño declara → mitigado con el escenario 5.
  - **Riesgo:** un `ENUM` sobrevive al `downgrade` y rompe el siguiente `upgrade` semanas después, cuando ya nadie relacione la causa → mitigado eligiendo `text` + `CHECK` y con la tercera pierna del escenario 4.
  - **Riesgo:** `DATABASE_URL` entra como obligatoria y deja sin arrancar el contenedor de Compose, invalidando un escenario ya aceptado de la spec viva `ai-service-dev-compose` → mitigado con el escenario 7.
  - **Riesgo:** el arnés de test se sobredimensiona hasta consumir la sesión, que es el mismo riesgo que C04 identificó para su ayudante de esquema → mitigado con el guardarraíl de escribir solo las aserciones que este change necesita hoy y con la línea de corte predefinida.
  - **Riesgo:** `alembic.ini` y `migrations/` no se copian al contenedor y C17 descubre el 19 de agosto que no puede migrar en producción → mitigado con la tarea 8.
  - **Riesgo:** la dimensión 1536 se fija antes de que C11 elija el modelo de embeddings. Aceptado: es la del modelo del programa, el diseño §6.3 ya obliga a que un cambio de modelo vaya en columna nueva, y S8 pide fijarla en el esquema precisamente para que nadie la cambie por accidente.
  - No depende del export del catálogo real, ni del proveedor de modelos, ni de ningún change de .NET: se implementa y se prueba de forma aislada.
