# Reindexación y versionado de embeddings

Creada: 27 de junio de 2026 12:38
Módulo: M4. Arquitectura RAG (https://app.notion.com/p/M4-Arquitectura-RAG-345ea9ca03c4804b8038eb0f1527b718?pvs=21)
Sesión: S11. RAG Avanzado - Generación y Calidad (https://app.notion.com/p/S11-RAG-Avanzado-Generaci-n-y-Calidad-38cea9ca03c48049a493d33b89499a1d?pvs=21)

El sistema de estimaciones tiene un corpus de presupuestos históricos ya vectorizado y persistido. La recuperación funciona, la generación se apoya en fuentes reales, y todo el trabajo de las secciones anteriores, citar, verificar, abstenerse, descansa sobre una premisa que rara vez se cuestiona: que los vectores del índice siguen representando fielmente lo que dicen los documentos, y que todos viven en el mismo espacio.

Esa premisa se erosiona sola. Llegan presupuestos nuevos que hay que añadir. Se corrige un presupuesto antiguo y su texto cambia, pero su vector sigue siendo el de antes. Aparece un modelo de embeddings mejor y quieres migrar. Cada uno de estos eventos, si se gestiona mal, degrada la recuperación. Y lo hace de la peor manera posible: sin lanzar un solo error.

## **El fallo que no da error**

La mayoría de los bugs gritan: una excepción, un stack trace, un test en rojo. La deriva del índice vectorial no grita. Susurra, y a veces ni eso.

Hay dos formas de que el índice se pudra. La primera es la **deriva de contenido**: un presupuesto se indexó, después alguien corrigió una cifra en el documento original, y el vector almacenado sigue representando el texto viejo. La búsqueda recupera ese fragmento creyendo que dice 40 h cuando el documento actual dice 60. La generación cita una fuente que ya no coincide con su contenido, una atribución falsa que no es culpa del modelo, sino del índice.

La segunda es más insidiosa: la **mezcla de versiones**. Imagina que reembebes la mitad del corpus con un modelo nuevo y dejas la otra mitad con el viejo. Ahora tienes vectores de dos modelos distintos en la misma tabla. La similitud coseno entre un vector del modelo A y uno del modelo B no significa nada, son dos espacios geométricos diferentes, pero la base de datos los compara igual y te devuelve un número. Un número plausible. Un vecino "cercano" que no tiene ningún sentido semántico. No hay error, no hay excepción: solo recuperación silenciosamente rota, y una generación que se fundamenta en fragmentos irrelevantes recuperados con una métrica sin sentido.

![art5-fig13-fallo-silencioso.jpg](https://media1-production-mightynetworks.imgix.net/asset/f3018c28-f3c2-4278-a4b4-498c32edd774/art5-fig13-fallo-silencioso.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

Esto es lo que hace que el ciclo de vida del índice merezca cuidado: el coste de equivocarse no es una caída visible, es una degradación invisible que descubres meses después, cuando alguien se queja de que "las estimaciones ya no son tan buenas" y no tienes ni idea de por qué.

## **Versionar el índice: cada vector sabe cómo se hizo**

La defensa contra la mezcla de versiones es conceptualmente simple: cada vector lleva grabado cómo se produjo, y las consultas nunca cruzan versiones. Un vector solo se compara con otros nacidos exactamente del mismo proceso.

"El mismo proceso" es más que "el mismo modelo". Es el modelo, su dimensión, si se normalizó, y la configuración de preprocesamiento (chunking y limpieza) con la que se generó el texto que se embebió. Cualquiera de esas piezas que cambie produce vectores que no son comparables con los anteriores.

```python
class EmbeddingVersion(BaseModel):
    model: str                 # "text-embedding-3-small"
    dimensions: int            # 1536
    normalized: bool
    preprocessing_id: str      # id/hash of the chunking + cleaning config

    @property
    def key(self) -> str:
        return f"{self.model}:{self.dimensions}:{self.normalized}:{self.preprocessing_id}"
```

Esa `key` se guarda junto a cada chunk, en una columna `embedding_version`, y se convierte en parte obligatoria de toda consulta de recuperación:

```sql
- Retrieval always scopes to the single active embedding version.
- Comparing vectors across versions is meaningless, so we never do it.

SELECT chunk_id, document_id, content
FROM chunks
WHERE embedding_version = :current_version
ORDER BY embedding <=> :query_vector
LIMIT :k;
```

![art5-fig14-versionado-vector.jpg](https://media1-production-mightynetworks.imgix.net/asset/6b327a7a-baca-40d1-bc8e-2063d7bd084c/art5-fig14-versionado-vector.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El `WHERE embedding_version = :current_version` no es una optimización: es una garantía de corrección. Sin él, una migración a medias contamina silenciosamente cada búsqueda. Con él, los vectores de la versión vieja simplemente dejan de participar, aunque sigan físicamente en la tabla durante la transición.

## **Cuándo y cómo reindexar**

El principio que decide cuándo hay que reindexar es el mismo que justifica el versionado: **cualquier cosa que cambie cómo se produce un vector invalida su comparación con los vectores producidos de otra forma**. De ahí salen los disparadores.

Un documento nuevo o corregido afecta solo a ese documento: es reindexación incremental, el caso común y barato. Un cambio de modelo de embeddings, de dimensión, o de la estrategia de chunking afecta a todo el corpus: es una migración de versión, cara y poco frecuente. La regla práctica: si el cambio toca un documento, reindexa ese documento; si toca el proceso, reindexa todo.

Para la reindexación incremental, la pieza clave es saber qué ha cambiado sin reembeber lo que no. Un hash del contenido de la fuente, guardado junto al chunk, resuelve esto: si el hash actual del documento no coincide con el que se embebió, el vector está obsoleto.

```python
def is_stale(chunk: StoredChunk, source_hash: str, current: EmbeddingVersion) -> bool:
    """A chunk is stale if its source text changed or it belongs to an old version."""
    return chunk.source_hash != source_hash or chunk.embedding_version != current.key

async def reindex_incremental(documents: list[Document], current: EmbeddingVersion) -> None:
    for document in documents:
        source_hash = content_hash(document.text)
        existing = await get_chunks(document.id)
        if existing and not any(is_stale(c, source_hash, current) for c in existing):
            continue  # up to date, skip

        await delete_chunks(document.id)
        chunks = chunk_and_embed(document, current)  # reuses the existing ingestion pipeline
        await insert_chunks(chunks)
        log.info("document_reindexed", document_id=document.id, version=current.key)
```

Dos cosas que conviene notar. La primera: `chunk_and_embed` no se reimplementa aquí; es el mismo pipeline de ingesta que ya vectoriza los documentos, invocado con la versión actual. Reindexar no inventa un camino nuevo, reutiliza el existente. La segunda: la reindexación incremental solo es válida *dentro de una versión*. En cuanto la versión activa cambia, insertar chunks nuevos junto a los viejos es precisamente la mezcla de versiones que queremos evitar. El incremental es la herramienta del día a día; no es la herramienta de una migración.

## **Migrar de versión: nunca a medias**

Cuando cambia el modelo, no hay reindexación incremental que valga. Hay que reembeber todo el corpus con el modelo nuevo, y mientras eso ocurre, la búsqueda tiene que seguir funcionando con el modelo viejo. La forma segura es construir el índice nuevo al lado del viejo, verificarlo, y cambiar de uno a otro de golpe.

```python
async def migrate_embedding_version(new: EmbeddingVersion) -> None:
    """Re-embed the whole corpus into a new version, then cut over atomically.

    Never mix versions in the live query space: build alongside, verify, switch.
    The old vectors keep serving queries until the switch; if verification
    fails, nothing changes for the user.
    """
    await build_shadow_index(new)          # embed every document with the new model
    if await verify_shadow_index(new):     # counts match, dimensions correct, sample queries sane
        await promote_active_version(new)  # atomic switch of the active version pointer
        await drop_old_version_vectors()   # only after a successful, verified switch
    else:
        await discard_shadow_index(new)
        log.error("embedding_migration_aborted", version=new.key)
```

![art5-fig15-migracion-blue-green.jpg](https://media1-production-mightynetworks.imgix.net/asset/1cf73d82-e6a8-4171-9b4d-4c6c9c82e8da/art5-fig15-migracion-blue-green.jpg?ixlib=rails-4.3.1&fm=jpg&q=75&auto=format&w=1400&h=1400&fit=max&impolicy=ResizeCrop&constraint=downsize&aspect=fit)

El patrón es el clásico blue/green aplicado a vectores. Mientras se construye el índice sombra, las consultas siguen sirviéndose de la versión activa, el `WHERE embedding_version` apunta a la vieja y el usuario no nota nada. El cambio de versión activa es un solo paso atómico: antes, todo el mundo busca en la vieja; después, todo el mundo en la nueva. No existe un instante en el que las dos se mezclen en una consulta. Y si la verificación del índice sombra falla, porque faltan documentos, porque las dimensiones no cuadran, porque unas consultas de prueba devuelven vecinos absurdos, se descarta y no pasa nada: el usuario sigue con la versión que funcionaba.

La verificación antes de promover no es opcional. Una migración que cambia la versión activa sin comprobar que el índice nuevo está completo y es sano puede sustituir un índice bueno por uno roto en un solo paso atómico, que es exactamente el escenario que el blue/green pretendía evitar.

## **Trade-offs honestos**

**El incremental es barato y es una trampa fuera de su versión.** Para documentos nuevos o corregidos, reembeber solo lo que cambió es la opción correcta y casi gratis. Pero usar el incremental cuando lo que ha cambiado es el modelo es cómo se llega a la mezcla de versiones. La pregunta antes de cada reindexación es siempre la misma: ¿cambió el documento o cambió el proceso? La respuesta decide la herramienta.

**Migrar cuesta dinero y tiempo, y hay que presupuestarlo.** Reembeber un corpus entero son tantas llamadas al modelo de embeddings como chunks tengas, más el almacenamiento temporal del índice sombra, que durante la transición duplica el espacio de vectores. No es una operación de rutina: es una migración, se planifica como tal, y el coste se asume a cambio de la seguridad de no romper la búsqueda en producción.

**La detección de obsolescencia es tan buena como tu captura de cambios.** El hash de contenido funciona si tienes el texto actual de la fuente para hashearlo. Si un presupuesto se modifica en un sistema externo y nadie te avisa, tu índice no se entera de que está obsoleto. Detectar la deriva de contenido exige, en algún punto, un mecanismo de sincronización o un rehasheo periódico; el hash por sí solo no descubre cambios de los que nunca te enteras.

**Saltarse el versionado parece gratis hasta que no lo es.** "Nunca vamos a cambiar de modelo" es una de las frases más caras de un sistema RAG, porque acabarás cambiándolo, saldrá uno mejor, o más barato y entonces la falta de versionado convierte una migración limpia en una contaminación silenciosa imposible de diagnosticar. La columna `embedding_version` es un seguro baratísimo contra un fallo invisible y carísimo. Ponla desde el principio, aunque hoy solo tengas una versión.

**Reindexar por calendario malgasta o se queda corto.** Un cron que reindexa todo cada noche quema cómputo reembebiendo lo que no ha cambiado; uno que reindexa cada mes deja acumularse la obsolescencia entremedias. Donde se pueda, ata la reindexación a eventos de cambio, un presupuesto aprobado, un documento corregido en lugar de a un reloj. El reloj es el último recurso, no el primero.

## **Lo que esto deja sin resolver**

Con versionado, reindexación incremental por deriva de contenido y migraciones blue/green, el índice deja de pudrirse en silencio: cada vector sabe cómo se hizo, las consultas nunca cruzan versiones, y un cambio de modelo no rompe la búsqueda a mitad de camino.

Pero queda una pregunta que ninguna de estas garantías responde, y es la misma a la que vuelve todo en esta materia. Has migrado a un modelo de embeddings nuevo, con todo el cuidado del mundo. La búsqueda no se ha roto. Pero, ¿ha mejorado? ¿El modelo nuevo recupera presupuestos más relevantes que el viejo, o has gastado una migración cara para quedarte igual, o incluso para empeorar un poco sin notarlo? El blue/green garantiza que no rompes nada visible; no garantiza que el cambio fuera una mejora.

Mantener el índice sano evita que la calidad se degrade por accidente. Pero saber si una decisión de diseño, un modelo nuevo, un prompt distinto, otra forma de ensamblar el contexto, mejora o empeora el sistema de verdad es algo que no se contesta inspeccionando una respuesta ni verificando un índice. Se contesta midiendo, sobre un conjunto representativo, con números comparables entre versiones. Sin esa medida, cada migración y cada ajuste son una apuesta a ciegas con una venda muy bien puesta.