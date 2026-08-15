## Context

La ficha C05 del plan cabe en una línea —*«persistencia lista: extensión `vector`, esquema `ai`, usuario dedicado, Alembic y tablas vacías con índices»*— y esa brevedad esconde media docena de decisiones que se pagan en changes posteriores. El diseño §7.2 dibuja el esquema, pero no dice dónde vive la tabla de versiones de Alembic, en qué esquema se instala la extensión, quién crea el rol, ni qué borra exactamente una reversión.

El estado del repositorio en el momento de diseñar:

| Pieza | Estado |
|---|---|
| `ai-service/migrations/`, `alembic.ini` | Ausentes. No existe ningún árbol de migraciones de Python |
| Dependencias de base de datos en `ai-service` | Ninguna: `fastapi`, `pydantic-settings`, `pyjwt`, `uvicorn` (+ `httpx`, `pytest` en desarrollo) |
| Ajustes de base de datos en `config/settings.py` | Ausentes |
| Marcador `db` de pytest | **Ya declarado** por C01: *«needs a PostgreSQL instance with pgvector»* |
| `ai-service/tests/migrations/` | **Reservada por nombre** y adjudicada a C05 en `tests/README.md`; aún sin crear |
| Regla del fixture de base de datos | Ya escrita: *«a database fixture belongs to `migrations/conftest.py`, not to the global one»* |
| Imagen de Compose | **`pgvector/pgvector:pg15`**, con el comentario *«Do NOT create schema `ai` … that is C05»* |
| `backend/scripts/init.sql` | Existe y está montado, pero solo emite un aviso. Se ejecuta **únicamente sobre volumen nuevo** |
| Extensión en RDS | Disponibilidad resuelta en C01 (PostgreSQL 15.17). La ejecución real es de C17 |
| `ai-service/Dockerfile` | Copia **solo** `pyproject.toml`, `uv.lock`, `README.md` y `src` |
| `openapi.json` | Congelado y protegido por `test_openapi_snapshot_is_stable` |
| `SchemaAssert` de C04 | Existe, pero es C# sobre Testcontainers .NET: **no cruza de lenguaje**. Sí cruza su criterio |
| Integración continua para Python | **Ninguna.** Hay `test-backend.yml` y `test-frontend.yml`; nada ejecuta `uv run pytest` |

Dos hechos del entorno gobiernan el diseño más que ninguna consideración estética. El primero: **la frontera del diseño §6.3** —*«`public.*` es de .NET; `ai.*` es de Python; Python nunca escribe en `public` ni lo lee por SQL»*— deja de ser una declaración y pasa a ser objetos reales precisamente en este change. El segundo: **las tablas nacen vacías y así se quedan**, de modo que ninguna decisión puede validarse observando datos.

## Goals / Non-Goals

**Goals:**

- Que C11, C13, C14, C22, C23 y C24 encuentren una capa de datos ya probada en lugar de improvisarla dentro del primer change que la necesite.
- Que la frontera `ai` / `public` quede **materializada y verificable**, no solo escrita.
- Que cada fallo silencioso conocido de pgvector y de Alembic tenga un detector que lo cace, y que ese detector se haya visto fallar.
- Que el servicio siga arrancando exactamente igual que antes para quien no configure base de datos, sin invalidar ningún escenario ya aceptado.
- Que el presupuesto de conexiones del proyecto (5-10 para todo el sistema) quede respetado por construcción y no por disciplina.

**Non-Goals:**

- Cualquier dato. Poblar es C13, C22 y C23.
- Cualquier consulta. La primera recuperación real es C14.
- Modelos ORM y repositorios: el acceso tipado nace cuando quien lo use sepa qué forma necesita.
- Tuning de producción (`halfvec`, exploración iterativa, construcción concurrente, ciclo de mantenimiento, `shared_buffers`): documentado como horizonte en S8, fuera de alcance aquí.
- Ejecución sobre RDS de producción, despliegue y `/health` enriquecido: C17.

## Decisions

### 1. El principio que ordena el resto: aquí ningún error caro produce un error

C04 se ordenó por la asimetría de reversibilidad. C05 se ordena por otra propiedad:

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Los cuatro fallos caros de este change compilan, migran y arrancan      │
├───────────────────────────────┬──────────────────────────────────────────┤
│  operator class desalineada   │  índice creado, nunca usado, sin aviso   │
│  alembic_version en public    │  frontera violada, todo funciona         │
│  ENUM huérfano tras revertir  │  falla el upgrade siguiente, semanas     │
│                               │  después, sin relación aparente          │
│  tsvector con config por      │  busca en inglés, devuelve algo          │
│  defecto en vez de 'spanish'  │                                          │
└───────────────────────────────┴──────────────────────────────────────────┘
```

De aquí sale la regla operativa del change: **un test que solo comprueba que la migración aplica es teatro**, porque aplicarla ya lo demuestra. Todo test de este change se escribe contra un fallo mudo concreto y nombrado, y se verifica rompiendo a propósito lo que vigila. Es el mismo criterio que C04 dejó escrito para su ayudante de esquema, aplicado a otro lenguaje.

### 2. La tabla de versiones de Alembic vive en `ai`, y eso crea un huevo y gallina

**Decisión:** `version_table_schema` apuntando a `ai`; el esquema se crea en el entorno de migración, antes de ejecutar las revisiones.

**Por qué:** el valor por defecto de Alembic crearía `public.alembic_version`. La primera migración del lado Python violaría la frontera del diseño §6.3 en su primera línea, y lo haría en silencio.

**El obstáculo:** Alembic materializa su tabla de versiones **antes** de ejecutar el primer script, así que crear el esquema dentro de la revisión llega tarde.

```
alembic upgrade head
  │
  ├─ 1. asegurar tabla de versiones  →  ai.alembic_version   ← ✗ el esquema no existe
  └─ 2. ejecutar la revisión         →  CREATE SCHEMA ai       (nunca se alcanza)
```

**Resolución:** el entorno de migración crea esquema y extensión de forma idempotente antes de ceder el control; la revisión los declara igualmente con `IF NOT EXISTS`, para que el SQL siga siendo autodescriptivo sin depender del entorno. Los tests afirman sobre el estado tras aplicar, que es lo que importa, no sobre qué fichero contiene la sentencia.

**Alternativas descartadas:** dejar la tabla de versiones en `public` (viola la frontera); crear el esquema en un script previo obligatorio (añade un paso manual a cada entorno de test, y el arnés crea una base de datos por test).

### 3. La extensión se instala en `public`, y es una excepción declarada

| Opción | Consecuencia |
|---|---|
| **`public`** (destino por defecto) — *elegida* | el tipo `vector` resuelve sin ceremonia; a cambio, Python crea un objeto en `public` |
| `SCHEMA ai` | frontera purista; a cambio, el tipo se cualifica como `ai.vector(1536)` y hay que manipular `search_path` en **cada conexión, para siempre**, incluida cualquier herramienta externa |

**Por qué:** la regla de propiedad del §6.3 habla de **datos** —quién escribe filas, quién es autoridad sobre precio y stock—, no de instalación de extensiones. Pagar fricción de `search_path` en C11, C13, C14, C21, C22, C23 y C26 para preservar una lectura literal de la regla es un mal cambio. Queda como excepción escrita, no como descuido.

### 4. El rol dedicado vive fuera de Alembic, y por eso basta una sola cadena de conexión

**Decisión:** extensión, esquema, rol y permisos van en una preparación previa ejecutada **una vez, con privilegios de administrador**. Alembic solo crea tablas e índices.

**Por qué:** los roles son objetos **de clúster**, no de base de datos. Meterlos en una migración exigiría privilegio de creación de roles a quien migra, y la reversión tendría que borrar un rol que probablemente ya posee objetos —operación que falla—. Una migración que no se puede revertir limpiamente contradice el cuarto test de la ficha.

**El efecto elegante:** con `IF NOT EXISTS` en la extensión, **no hacen falta dos cadenas de conexión**. El mismo comando funciona en los dos entornos:

```
   PREPARACIÓN (admin, una vez)        MIGRACIÓN (rol jbg_ai)      RUNTIME (rol jbg_ai)
   ────────────────────────────        ──────────────────────      ────────────────────
   CREATE EXTENSION vector       ──►   CREATE EXTENSION            motor asíncrono
   CREATE SCHEMA ai                    IF NOT EXISTS → no-op       pool 5, sin overflow
   CREATE ROLE jbg_ai                  CREATE TABLE / INDEX        creación perezosa
   GRANT USAGE, CREATE ON ai
   GRANT USAGE ON public   ← solo para resolver el tipo `vector`; ningún SELECT
```

En local se migra como superusuario y la extensión se crea en el primer intento; en RDS la instala el usuario maestro (C17) y la migración la encuentra hecha. Mismo código, misma variable.

**Alternativas descartadas:** `DATABASE_URL` + `DATABASE_ADMIN_URL` (dos variables, dos secretos y una pregunta más en cada despliegue, para resolver algo que `IF NOT EXISTS` ya resuelve); poner el rol en `backend/scripts/init.sql` (solo se ejecuta sobre volumen nuevo, y ese fichero es territorio de .NET).

### 5. psycopg 3 como único driver

`asyncpg` es más rápido en microbenchmarks, pero obliga a dos formas de URL —una para la aplicación y otra para Alembic, que es síncrono— y a que alguien recuerde traducir entre ellas en cada entorno. psycopg 3 habla síncrono y asíncrono bajo **un mismo esquema de URL**. A la escala de este proyecto la diferencia de rendimiento no es medible; la de operación, sí.

### 6. Vocabularios cerrados con `text` + `CHECK`, nunca `ENUM`

**Decisión:** `data_origin`, `doc_type`, `price_band` y `qty_bucket` son `text` con restricción de comprobación.

**Por qué, y es el cuarto test quien lo dice:** un tipo enumerado creado por la capa ORM **no se borra al borrar la tabla**. La reversión deja el tipo huérfano y la siguiente aplicación falla con *«el tipo ya existe»*, semanas más tarde y sin relación aparente con la causa. Elegir `text` + `CHECK` no es preferencia estética: elimina la clase entera de fallo que `test_upgrade_downgrade_is_reversible` existe para cazar.

**Razón secundaria:** los vocabularios todavía se están decidiendo —materiales en C09, tipos de documento en C23, bandas de precio en C09—. Añadir un valor a un enumerado es una migración con bloqueo; a una comprobación, una sustitución.

### 7. HNSW con `vector_cosine_ops`, y parámetros explícitos

| Parámetro | Valor | Origen |
|---|---|---|
| Método | `hnsw` | S8: el caballo de batalla para RAG con corpus creciente |
| *Operator class* | `vector_cosine_ops` | alineada con el operador `<=>` que usará C14 |
| `m` | `16` | S8: correcto para 1536 dimensiones; subirlo dobla memoria y tiempo de construcción |
| `ef_construction` | **`128`** | S8, **no el 64 por defecto de pgvector**: la comunidad convergió en 128 para alta dimensión |
| `ef_search` | — | es parámetro **de consulta**; se fija en C14, no aquí |

Sobre coseno frente a producto interno: con embeddings normalizados —los de OpenAI lo están— ambos **ordenan idéntico**, y el producto interno es marginalmente más barato porque ahorra dividir por normas que ya valen 1. Se elige coseno igualmente por lo que dice S8: es la convención de la literatura, y **sigue siendo correcto el día que alguien cambie a un modelo que no normalice**. Elegir producto interno «por eficiencia» obliga a recordar para siempre una precondición que nadie documentará.

### 8. Por qué las tablas pueden nacer vacías *con* sus índices

No es un atajo: es una propiedad del algoritmo elegido. IVFFlat necesita entrenamiento k-means sobre datos existentes y **no puede construirse sobre una tabla vacía**; HNSW no necesita entrenamiento y absorbe inserciones de forma incremental. El enunciado literal de la ficha C05 —*«tablas vacías con índices»*— solo es realizable con HNSW.

S8 añade el argumento de operación que cierra la elección: IVFFlat **degrada su recall en silencio** a medida que las inserciones alejan la distribución de los centroides originales, y este corpus crece con cada sincronización. Otro fallo mudo, evitado por elección de algoritmo en lugar de por vigilancia.

### 9. `tsv` como columna generada, con el idioma anclado al esquema

**Decisión:** columna generada y almacenada, con `to_tsvector` y la configuración `'spanish'` indicada explícitamente.

**Por qué es posible:** la forma de dos argumentos de `to_tsvector` es `IMMUTABLE` y por tanto legal en una columna generada. La de un argumento no lo es, porque depende de la configuración de sesión — que es exactamente el mecanismo por el que el idioma podría cambiar sin que nadie se entere.

**Qué compra:** convierte el `test_tsvector_uses_spanish_configuration` de C13 de una aserción sobre un camino de código en un **hecho de esquema**. Ningún camino de escritura, presente o futuro, puede poblarla en otro idioma.

### 10. Ninguna clave foránea cruza hacia `public`; sí las hay dentro de `ai`

`product_id`, `pos_id` y `family_id` son columnas `uuid` planas. Una clave foránea real hacia las tablas de EF Core acoplaría el ciclo de vida de los dos esquemas: una migración de .NET que tocara `Products` fallaría por dependencia, y el índice quedaría atado al calendario del otro desarrollador. Contradice además la frontera del §6.3.

Dentro del esquema, en cambio, la integridad referencial se usa sin reservas: los fragmentos de conocimiento apuntan a su documento **con borrado en cascada**, de modo que eliminar un documento se lleve sus fragmentos sin lógica aplicativa —el modelo de referencia de S8—. Y la co-ocurrencia lleva una **restricción de orientación** (`product_a < product_b`) sin la cual cada par se almacenaría dos veces y C27 doblaría su señal de complementarios.

### 11. Migración escrita a mano, sin modelos ORM ni autogeneración

La autogeneración no expresa *operator classes* de HNSW, ni índices GIN sobre arrays, ni columnas generadas: produciría una revisión que hay que reescribir entera, y además un test de desfase modelo↔migración con ruido permanente, porque la comparación no ve el interior de los índices. Sin modelos tampoco sabemos aún qué necesita C13 para insertar.

Es el mismo guardarraíl que C04 puso a su arnés —*«solo las aserciones que este change necesita hoy»*—, aplicado a la capa de acceso: **el acceso tipado nace en C11/C13**, cuando quien lo use sepa su forma.

### 12. Qué borra la reversión, y la tercera pierna del test

**Decisión:** la reversión borra **las seis tablas y nada más**. El esquema y la extensión sobreviven.

**Por qué:** la extensión es un objeto compartido de la base de datos, y el esquema `ai` alberga la propia tabla de versiones de Alembic — borrarlo dejaría a Alembic sin dónde registrar el resultado de la operación que está ejecutando.

**Forma del test, que es donde está el valor:**

```
  aplicar  ──►  revertir  ──►  aplicar otra vez
     │             │                  │
  6 tablas     0 tablas          6 tablas
               esquema y         ▲
               extensión         └── ESTA es la pierna que caza el objeto huérfano.
               en pie                Sin ella el test no vale nada.
```

### 13. La *operator class* se afirma contra el catálogo, no contra el texto del índice

Las dos vías detectan el fallo. La diferencia está en de qué dependen:

| Vía | Cómo detecta | Depende de |
|---|---|---|
| Buscar la cadena en la definición textual del índice | PostgreSQL **omite la *operator class* cuando es la de por defecto**, así que un índice L2 se renderiza sin ella y la búsqueda falla | una regla de **renderizado** |
| **Join al catálogo** (índice → clase de operadores → método de acceso) — *elegida* | afirma el nombre de la clase y el del método | un **hecho** |

La ficha pide *«consulta a `pg_indexes`»* y esa vía funciona; se elige la del catálogo porque afirma lo que se quiere afirmar en lugar de una consecuencia de ello.

**Por qué no se verifica con plan de ejecución.** S8 enseña `EXPLAIN ANALYZE` como el reflejo correcto, y lo es — pero sobre tablas vacías el planificador elegiría recorrido secuencial de todos modos, así que la aserción no significaría nada. Se difiere a C14, que ya tendrá datos. Anotado también para C17: en producción, un contador de usos del índice a cero es la forma más rápida de detectar este mismo antipatrón.

### 14. El arnés: contenedor efímero, una base de datos por test, omisión elegante sin Docker

**Contenedor efímero con pgvector**, de ámbito de sesión, según la regla transversal del plan (*«Testcontainers (.NET) o contenedor efímero con pgvector (Python)»*).

**Una base de datos nueva por test**, no una compartida: el test de reversibilidad **muta el esquema**, y compartir base lo haría dependiente del orden — el patrón que `CLAUDE.md` documenta como veneno en la suite de .NET, donde ya hay fallos que dan resultados distintos en dos ejecuciones del mismo código.

**Omisión con motivo cuando Docker no responde.** No hay integración continua para Python en el repositorio, así que la única defensa real es que la suite siga verde en el portátil del compañero. Cuatro rojos permanentes no informan de nada: enseñan a ignorar el rojo, que es peor que no tener los tests.

### 15. Los ajustes nuevos son opcionales, y el motor es perezoso

La spec viva `ai-service-dev-compose` afirma que *«el arranque de `jbg-ai` no debe requerir conexión a base de datos»* y que *«las ejecuciones locales no necesitan proveedor de IA ni base de datos»*. Hacer obligatoria la cadena de conexión convertiría en **falso un escenario ya aceptado y archivado**, y dejaría sin arrancar el servicio de Compose, que hoy no la define.

Por eso: cadena de conexión y tamaño de pool **opcionales**, motor creado en el primer uso y no al importar el módulo, y error claro **al pedir sesión** —no al arrancar— si no hay configuración. En `STUB_MODE` nadie pide sesión, así que el contenedor de Compose arranca igual que antes aunque su base de datos no exista.

### 16. El pool: acotado de verdad, y con la espera recortada

| Parámetro | Valor | Motivo |
|---|---|---|
| Tamaño | `5` | «Acotado a 5» en su lectura literal; `project.md` fija 5-10 para **todo el sistema**, compartidos con .NET sobre el mismo RDS |
| Desbordamiento | `0` | Con desbordamiento el tope sería decorativo: el valor por defecto añadiría diez conexiones más |
| Espera por conexión | muy por debajo del valor por defecto (30 s) | **.NET corta la recuperación a 0,8 s con Polly.** Esperar 30 s por una conexión es trabajar para un cliente que se marchó hace veintinueve |
| Comprobación previa | activada | RDS cierra conexiones ociosas |

Que la sexta petición **espere en lugar de fallar** es deliberado: el circuit breaker de C03 ya decide cuándo rendirse, y duplicar esa decisión aquí produciría dos políticas de degradación distintas para el mismo síntoma.

## Risks / Trade-offs

- **[Riesgo] El índice se crea con la *operator class* por defecto mientras C14 consulta con el operador de coseno.** El índice queda desactivado en silencio y, sobre 1.500 vectores, nadie lo nota nunca → *Mitigación:* aserción contra el catálogo, más la tarea explícita de romperla y comprobar que falla.
- **[Riesgo] La tabla de versiones nace en `public` con la configuración por defecto**, y la primera migración de Python viola la frontera que el proyecto declara → *Mitigación:* requisito y escenario propios, que afirman también la **ausencia** de tabla de versiones en `public`.
- **[Riesgo] Un objeto huérfano sobrevive a la reversión** y rompe una aplicación futura → *Mitigación:* `text` + `CHECK` elimina la causa principal, y la tercera pierna del test caza el resto.
- **[Riesgo] La cadena de conexión entra como obligatoria** e invalida un escenario aceptado de la spec de Compose, dejando el contenedor sin arrancar → *Mitigación:* ajustes opcionales, motor perezoso y escenario que lo fija.
- **[Riesgo] Las rutas de Alembic no llegan al contenedor**, porque el `Dockerfile` copia solo `src`, y **C17 lo descubre el 19 de agosto** → *Mitigación:* tarea explícita y comprobación de que la migración se ejecuta desde la imagen.
- **[Riesgo] El arnés de test se sobredimensiona hasta consumir la sesión.** Es el mismo riesgo que C04 identificó: *«construye una herramienta que heredarán cinco changes»* es literalmente el enunciado que produce un DSL que nadie pidió → *Mitigación:* solo las aserciones que estos cuatro tests necesitan, y línea de corte predefinida.
- **[Trade-off] La dimensión del vector se fija antes de que C11 elija el modelo.** Aceptado: es la del modelo del programa, S8 pide fijarla en el esquema *precisamente* para que nadie la cambie por accidente, y el §6.3 ya obliga a que un cambio de modelo vaya en **columna nueva**.
- **[Trade-off] Sin `halfvec`, que S8 recomienda «desde el día uno» para producción.** A 1.500 vectores no cambia ninguna cifra medible, y añadirlo tiene coste de complejidad en la construcción del índice. Se declara como limitación consciente para el README de C39, no como olvido.
- **[Trade-off] Los tests de base de datos pueden omitirse.** Una suite que puede saltarse sus tests más importantes es un riesgo real, pero la alternativa —fallar sin Docker— produce rojos permanentes en un repositorio **sin integración continua para Python**, y eso degrada la señal para todos los demás tests.

## Migration Plan

1. **Preparación previa**, una vez por entorno y con privilegios de administrador: extensión, esquema, rol y permisos. En local, contra el PostgreSQL de Compose; en producción, es alcance de C17 contra RDS.
2. **Aplicar la migración** con el rol dedicado. La extensión ya existe, así que su declaración idempotente es un no-op.
3. **Verificación** con los cuatro detectores sobre base limpia.
4. **Reversión**, si hiciera falta: borra las seis tablas y deja esquema y extensión en pie. Como no hay datos que perder —las tablas nacen y se quedan vacías en este change—, la reversión es **inocua por construcción**, y deja de serlo en cuanto C13 empiece a poblar. Ese es el momento en que la reversión pasa a ser una decisión operativa y no un botón.
5. **Sin rollback de datos ni ventana de mantenimiento**: no hay datos, no hay lectores y ningún componente en producción depende todavía del esquema `ai`.

## Open Questions

| # | Pregunta | Opción por defecto |
|---|---|---|
| 1 | `ai.query_log` aparece en el diseño §7.2 y **ninguna ficha de change la adjudica** | **No se crea.** No hay regla de migración única en Python, así que una segunda revisión es barata; adivinar hoy sus columnas, no. Queda anotada para que no se cuele improvisada en C14 |
| 2 | ¿Índice único sobre el código de artículo en el documento de producto? | **No.** La unicidad es responsabilidad del corpus (C06) y el indexado es por identificador de producto (C13). Añadirlo después es una revisión de una línea |
| 3 | Valores concretos del vocabulario de banda de precio | Comprobación permisiva hasta que C09 fije las bandas al calcularlas, antes que inventar hoy un vocabulario que habrá que migrar |
| 4 | ¿Flujo de integración continua para Python? | **Fuera de alcance**: ninguna ficha lo adjudica. Se recoge como observación, y condiciona la decisión 14 mientras no exista |
| 5 | ¿Preparación previa contra RDS de producción en este change? | **No.** Alcance explícito de C17, junto con los secretos en el almacén de parámetros |
