# HU-AIENG-008: Perfil IA revisable del catálogo — enriquecimiento por lotes con revisión híbrida por campo

## Formato estándar

Como **Administrador del catálogo**, quiero **generar por lotes el perfil IA de los productos —materiales, tipo de pieza, piedra, talla y etiquetas comerciales— con la confianza y el origen de cada campo, y que solo llegue a revisión humana lo que de verdad lo necesita** **para** **tener un catálogo enriquecido e indexable antes del 3 de septiembre sin revisar a mano mil fichas campo por campo, y poder decir con números qué parte de ese catálogo ha mirado una persona y qué parte no**.

---

## Descripción

Cuarto change de la Ola 1 del Proyecto Final de IA (change OpenSpec `add-product-ai-profile-entity` / C08, épica **EP12 — Corpus y Enriquecimiento del Catálogo**). Marcado 🟢 como relleno paralelizable y 🗄️ porque **ocupa el turno único de migración de EF Core**. Su único prerrequisito, C03, está archivado.

El catálogo real de JoiaBagur no tiene ni un solo atributo estructurado que sirva para buscar por semántica. `Product` guarda SKU, nombre, descripción, precio, colección y un booleano de actividad: **nada más**. No hay tipo de pieza, ni materiales, ni piedra, ni talla. Toda la búsqueda asistida que sostiene el hito del 19 de agosto —filtro por solape de materiales (§7.3), filtros estructurales por reglas (§7.6), agrupación por familia, sustitutos por materiales coincidentes— presupone unos atributos que hoy **no existen en ninguna parte**. Esta historia es la que los crea, y la que decide quién responde de ellos.

Porque el problema no es solo extraerlos: es que **un atributo inventado por un modelo y aprobado por nadie es peor que un atributo ausente**. Si el sistema afirma que un anillo es de plata y es de acero, la operadora que se fía vende mal y la culpa es del sistema. De ahí la decisión 5 del diseño (§7.8): la revisión no es «todo o nada», sino **híbrida por campo**. Los campos sensibles —tipo de pieza, materiales, piedra, talla— exigen revisión humana **si el valor es inferido**, y no la exigen si viene de una regla determinista. Las etiquetas comerciales, cuyo error no vende mal nada, se auto-aprueban por encima de un umbral de confianza.

Esa política, sola, tiene un problema operativo que el diseño nombra sin rodeos: con ~1.000 productos, revisar todos los campos sensibles inferidos son horas de trabajo humano que no existen antes del 3 de septiembre, y si solo se indexa lo aprobado **el corpus queda vacío y no hay demo**. La salida acordada son dos vías declaradas y distinguibles en el dato: un lote de 120-150 fichas revisadas de verdad y cronometradas —de donde salen la tasa de corrección real del extractor y el tiempo medio de revisión que el README exhibirá— y el resto marcado como aprobado en masa, indexado, y **excluido de toda métrica de revisión humana**. Esta historia construye el mecanismo de ambas y se asegura de que la segunda no pueda disfrazarse de la primera.

Hay una tercera cosa que esta historia hace y que su ficha en el plan no anticipa. C08 es el **primer y único consumidor** de `POST /v1/enrich/products`, la ruta que C02 congeló y que nadie ha llamado todavía. Al ir a usarla se ve que el contrato **no puede sostener la decisión 5**: sus perfiles propuestos no dicen de dónde sale cada valor. Sin ese `source`, la regla central —*sensible inferido → revisión; sensible por regla → no*— no es implementable, y los cuatro tests de enrutado de la ficha no tendrían nada que distinguir. Renegociar el contrato aquí es barato precisamente porque nadie más lo consume; hacerlo en C09 sería tarde, porque C08 ya se habría construido sobre la forma equivocada.

**Alcance de esta historia (sí):**

- Entidad `ProductAiProfile` en el dominio .NET, **un perfil por producto**, con valores vigentes, procedencia por campo, propuesta original de la IA y estado de revisión.
- **Una única migración de EF Core** con las siete columnas `jsonb`, el índice único sobre `ProductId`, los dos índices de consulta y las reglas de borrado declaradas a mano.
- **Renegociación del contrato** `POST /v1/enrich/products`: `source` (`rule` | `inferred`) en cada valor propuesto, campos `piece_type`, `stone_type` y `size_label`, y desglose del `tags` plano en `color_tags`, `style_tags` y `occasion_tags`. Incluye el stub determinista, el snapshot `ai-service/openapi.json` y sus tests.
- **Scope de catálogo** sin punto de venta, en los dos lados: constructor nuevo en .NET, `pos_id` opcional en las rutas de catálogo de `jbg-ai`, y **dos guardas independientes** que impiden que un token de catálogo llegue a una ruta de recuperación.
- Operación `EnrichAsync` en el cliente tipado, con **familia de ruta propia** (`ai-enrich`): presupuesto de tiempo generoso, cortacircuitos aislado del de recuperación y **sin reintento automático**.
- **Política de enrutado híbrido** como clase pura, con umbrales en configuración validada al arranque.
- Endpoint `POST /api/ai/catalog/enrich-batch`, **solo Administrador**, con modo `Routed` (por defecto) y `AutoBulk`, tope de lote espejo del contrato e **idempotencia por `SourceHash`**.
- Almacenamiento que C28 necesitará para sus métricas: propuesta cruda inmutable, revisor, instante y duración de revisión.
- Tests: los seis de la ficha más los que abren los huecos anteriores, incluidos los detectores de esquema sobre el catálogo de PostgreSQL.

**Fuera de alcance (no):**

- **Cualquier ruta de lectura.** Ni consulta de perfil, ni cola de revisión, ni métricas, ni panel → **C28**. El feed de indexación → **C12**. Misma disciplina que C04 aplicó a la telemetría.
- **Aprobar o rechazar un perfil.** No hay endpoint de revisión: es de C28. C08 solo deja el estado en el que el enrutado lo pone.
- **El extractor real**: prompt versionado, vocabularios cerrados de materiales, normalización de sinónimos («plata de ley», «925» → `plata`) y puertas de calidad de lote → **C09**. Esta historia se ejerce contra el stub determinista de C02.
- **Familias.** `family_id` y `variant_label` siguen viajando en el contrato y **se ignoran deliberadamente**: la familia es entidad de negocio de C07 y su propuesta es de C18.
- **`ProductTextEmbedding`** de las especificaciones funcionales v2: no se crea, y no debe crearse — los vectores viven en `ai.product_document` desde C05.
- Trabajo en segundo plano, cola de enriquecimiento, reintentos programados o cualquier forma de asincronía.
- **Cualquier escritura sobre `Product`**: ni `Name`, ni `SKU`, ni `Price`, ni `Description`. Criterio de aceptación explícito de las specs v2 §4.9.
- Interfaz de usuario, en cualquier forma.

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Principio rector | **La IA propone, .NET decide y una persona responde de lo que importa.** Cada campo lleva escrito de dónde sale y cuánta confianza tenía, para que la decisión de revisarlo sea del sistema y no del criterio del día |
| Quién renegocia el contrato de enriquecimiento | **C08.** Es el único consumidor que existe o existirá antes de C09, así que romperlo hoy no invalida ningún código. Diferirlo a C09 obligaría a construir la entidad sobre una forma que ya se sabe insuficiente |
| Qué se añade al contrato | `source` (`rule` \| `inferred`) en cada valor propuesto —**sin él la decisión 5 no es implementable**—, `piece_type`, `stone_type`, `size_label`, y el desglose de `tags` en `color_tags` / `style_tags` / `occasion_tags` |
| Por qué el desglose de etiquetas también ahora | `ai.product_document` ya nació en C05 con las tres columnas separadas, y C27 recomienda complementarios por *solape de `color_tags`/`style_tags`*. Un `tags` plano habría que partirlo en algún sitio, y ese sitio sería adivinado |
| Qué pasa con el snapshot OpenAPI | `test_openapi_snapshot_is_stable` se pone **rojo a propósito**. Volver a verde regenerando `openapi.json` **es** el acto de renegociación, no un trámite: es la señal que el plan diseñó para que un cambio de contrato no pase inadvertido |
| Llamada sin punto de venta | **Scope de catálogo en los dos lados.** `AiCallScope` gana un segundo constructor y `PointOfSaleId` pasa a opcional; `jbg-ai` gana una dependencia de autenticación que no exige `pos_id`, usada **solo** por las rutas de catálogo. Es el camino que C03 dejó anticipado por escrito en su propio código |
| Por qué no un `pos_id` centinela | La spec viva de C03 lo prohíbe con nombre y apellidos: desde C22 el `pos_id` del token es el **único filtro duro** del recuperador, y un valor comodín llegando ahí es una fuga entre puntos de venta disfrazada de parámetro de conveniencia |
| Doble cierre de esa frontera | El cliente .NET **rechaza** un scope de catálogo en recuperación **y** `jbg-ai` sigue exigiendo `pos_id` en sus rutas de recuperación. Dos cierres independientes, ambos con test: que uno se relaje por descuido no abre la puerta |
| Estado y origen de revisión | **Dos columnas ortogonales.** `ReviewStatus` (`Pending` \| `Approved` \| `Rejected`) dice *en qué punto está*; `ReviewOrigin` (`AutoBulk` \| `Human`) dice *quién lo puso ahí*. Es lo que permite que C12 indexe por estado y C28 mida solo lo humano, sin que ninguna de las dos consultas mienta |
| Por qué no un cuarto valor en el estado | Con `AutoApproved` como cuarto valor, todo `== Approved` escrito de memoria en cualquier change futuro deja fuera medio corpus **sin dar ningún error**. Dos columnas hacen imposible ese olvido |
| La vía masiva | Modo `AutoBulk` en la petición: aprueba todo, **pero `FieldConfidenceJson` y `FieldSourceJson` siguen registrando lo que el enrutado habría dicho**. El atajo del §7.8 existe, está declarado y queda escrito en el dato, en lugar de disolverse en él |
| Campos sensibles | `piece_type`, `materials`, `stone_type`, `size_label`. La **pertenencia a familia**, que §7.8 también lista, queda fuera: es de C07 y C18, y duplicar aquí su autoridad crearía dos verdades sobre lo mismo |
| Métricas de C28 sin migración propia | C28 no está marcado 🗄️ y el plan cuenta seis migraciones. C08 reserva `ProposedProfileJson` —propuesta cruda **inmutable**, de la que sale la tasa de corrección por campo— y `ReviewDurationMs` —que mide el navegador y queda **nulo en aprobación masiva**, donde el número mentiría |
| Por qué no una entidad de auditoría de revisión | Daría historial de revisiones múltiples y atribución exacta, pero cuesta tabla, repositorio, dos claves foráneas y una transacción compuesta, y **fija la forma de la auditoría de C28 antes de haber diseñado C28**. En una campaña de 120-150 fichas revisadas una vez, ese historial no lo lee nadie |
| Significado de `SourceHash` | **Hash de las entradas** del enriquecimiento (SKU + nombre + descripción + colección, orden fijo, SHA-256). **No es** el `source_hash` de C11, que Python calcula sobre el `doc_text` canónico para decidir si recalcula el embedding. Dos hashes, dos propósitos, nombre casi idéntico: hay que decirlo en voz alta o se confundirán |
| Para qué sirve ese hash | Dos cosas que valen lo mismo: **no volver a pagar el LLM** por un producto que no ha cambiado, y **no machacar en silencio** una ficha que alguien ya revisó |
| Al cambiar el hash | Hay propuesta nueva: el perfil vuelve al resultado del enrutado, `ReviewOrigin` vuelve a `AutoBulk` y los campos de revisión se limpian, con traza en el log. Versionar perfiles sería más fino y no cabe en la sesión |
| Un perfil por producto | **Índice único sobre `ProductId`.** Sin él, dos perfiles del mismo producto son un fallo mudo que C12 convierte en documentos duplicados dentro del índice vectorial |
| Vocabularios | **`text`, nunca `ENUM` de PostgreSQL** — misma decisión que C05 y mismo motivo: `piece_type`, `stone_type` y el vocabulario de materiales los cierra C09, no este change |
| Borrado de producto | **`RESTRICT`.** El valor por defecto del framework para una relación requerida es `CASCADE`, que aquí significaría que borrar un producto se lleva por delante el trabajo de revisión. `Product` además ya se desactiva con `IsActive` en lugar de borrarse |
| Dónde vive el enrutado | **Clase de política pura**, sin base de datos ni HTTP. Los cuatro tests `Routing_*` deben correr en milisegundos y sin contenedor; metidos dentro del servicio que persiste, no pueden |
| Umbrales | **En configuración validada al arranque**, no constantes. Un umbral que C24 y C25 tendrán que recalibrar contra el golden set y está compilado dentro del código es un umbral que no se recalibra |
| Presupuesto de la llamada | **Familia de ruta propia** `ai-enrich`, con cortacircuitos aislado. Un lote de extracción no tiene nada que ver con los 0,8 s de recuperación, y una llamada lenta de enriquecimiento **no puede** abrir el circuito que empuja la búsqueda a su vía degradada |
| Reintento | **Ninguno automático.** Un reintento sobre una extracción es coste de LLM duplicado sin ninguna razón para esperar un resultado distinto, y §12 se compromete a que el coste esté instrumentado |
| Tamaño de lote | **Tope 50**, espejo del `MAX_BATCH_SIZE` del contrato. Los ~1.000 productos de la vía masiva son 20 llamadas; no hay trabajo en segundo plano y eso se declara como limitación, no se disimula |
| `jbg-ai` sin implementar | El 501 del contrato se traduce a **503 con un mensaje que nombra C09**. Aquí no hay degradación posible: el enriquecimiento ocurre o no ocurre, y fingir lo contrario sería inventar datos |

**Referencias:**
[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C08, reglas transversales de testing, §0 revisiones),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§6.2 qué vive dónde, §6.3 frontera y contrato de sincronización, §7.1 pipeline de enriquecimiento, §7.2 esquema del índice, §7.3 filtro por materiales, **§7.8 revisión humana híbrida**),
[joiabagur-ia-especificaciones-funcionales-v2.md](../../Proyecto%20Final%20AIEng/joiabagur-ia-especificaciones-funcionales-v2.md) (§4.5 flujo de administración, §4.6 modelo de datos, §4.9 criterios de aceptación),
[Extracción de datos estructurados](../../Sesiones%20Master%20AIEng/S4_Productos_IA_avanzados/Extraccion%20de%20datos%20estructurados.md) y [Guardrails y validación de outputs](../../Sesiones%20Master%20AIEng/S4_Productos_IA_avanzados/Guardrails%20y%20validacion%20de%20outputs.md) (confianza por campo, validación de salida),
[Calidad del Dato y decisiones de Arquitectura](../../Sesiones%20Master%20AIEng/S6_Fundamentos_Data_Driven_AI/Calidad%20del%20Dato%20y%20decisiones%20de%20Arquitectura.md),
[epicas.md](../../epicas.md) (EP12), [modelo-de-datos.md](../../modelo-de-datos.md), [modelo-c4.md](../../modelo-c4.md),
[HU-AIENG-002.md](HU-AIENG-002.md) (contrato congelado), [HU-AIENG-003.md](HU-AIENG-003.md) (cliente y scope), [HU-AIENG-004.md](HU-AIENG-004.md) (arnés de test de esquema), [HU-AIENG-005.md](HU-AIENG-005.md) (esquema `ai`),
specs vivas `openspec/specs/ai-gateway-client/spec.md`, `openspec/specs/ai-service-auth/spec.md`, `openspec/specs/ai-service-api-contracts/spec.md`, `openspec/specs/ai-vector-schema/spec.md`,
contrato `ai-service/openapi.json`,
change OpenSpec `openspec/changes/add-product-ai-profile-entity/` y su ticket técnico.

---

## Criterios de Aceptación

### Escenario 1: Un lote de productos produce perfiles con procedencia por campo
**Dado que** existe un conjunto de productos activos en el catálogo sin perfil IA
**Cuando** un administrador solicita el enriquecimiento de ese lote
**Entonces** se persiste un perfil por producto, y solo uno
**Y** cada perfil guarda tipo de pieza, materiales, piedra, talla y las tres familias de etiquetas comerciales
**Y** guarda, por cada campo, **la confianza con la que se propuso y si el valor es inferido o viene de una regla determinista**
**Y** conserva íntegra la propuesta original de la IA, separada de los valores vigentes

### Escenario 2: Un campo sensible inferido deja el perfil pendiente de revisión
**Dado que** el extractor propone el tipo de pieza, los materiales, la piedra o la talla **como valor inferido**
**Cuando** se aplica el enrutado de revisión en su modo por defecto
**Entonces** el perfil queda en estado pendiente de revisión
**Y** el detalle por campo permite saber **cuál** de ellos lo dejó pendiente
**Y** ese perfil no es candidato a indexarse mientras siga pendiente

### Escenario 3: Un campo sensible que viene de una regla no exige revisión
**Dado que** un campo sensible se ha resuelto de forma determinista y llega marcado como procedente de una regla
**Cuando** se aplica el enrutado de revisión
**Entonces** ese campo **no** exige revisión humana, por muy sensible que sea
**Y** si ningún otro campo la exige, el perfil queda aprobado
**Y** el origen `rule` queda registrado, de modo que la decisión sea auditable después

### Escenario 4: Las etiquetas comerciales con confianza alta se aprueban solas
**Dado que** el extractor propone etiquetas de color, estilo u ocasión con una confianza por encima del umbral configurado
**Cuando** se aplica el enrutado de revisión
**Entonces** esas etiquetas se auto-aprueban sin intervención humana
**Y** por debajo del umbral, las mismas etiquetas envían el perfil a revisión
**Y** el umbral se lee de la configuración de la aplicación, no de una constante en el código

### Escenario 5: Un producto puede tener varios materiales a la vez
**Dado que** una pieza es de plata con baño de oro
**Cuando** se persiste su perfil y se vuelve a leer
**Entonces** conserva los dos materiales, en una estructura de lista y no en un texto concatenado
**Y** una pieza sin evidencia de material conserva una lista vacía, nunca un material por defecto ni un nulo

### Escenario 6: La vía masiva aprueba, pero no oculta lo que el enrutado habría dicho
**Dado que** el administrador ejecuta el lote en modo masivo para poder indexar el catálogo completo
**Cuando** el lote termina
**Entonces** los perfiles quedan aprobados y son candidatos a indexarse
**Y** su origen de revisión queda marcado como aprobación masiva, distinguible de la revisión humana
**Y** la confianza y el origen por campo **siguen registrando lo que el enrutado habría decidido**, de modo que se pueda saber después qué porcentaje del corpus nadie miró

### Escenario 7: Repetir el lote sin cambios no vuelve a pagar el modelo
**Dado que** un producto ya tiene perfil y ni su SKU, ni su nombre, ni su descripción, ni su colección han cambiado
**Cuando** se vuelve a solicitar el enriquecimiento de ese producto
**Entonces** el producto se omite y se contabiliza como omitido por no haber cambiado
**Y** **no se realiza ninguna llamada al servicio de IA** por ese producto
**Y** si ese perfil había sido revisado por una persona, su revisión permanece intacta
**Y** existe una forma explícita de forzar el reenriquecimiento cuando se quiera de verdad

### Escenario 8: Un operador no puede enriquecer el catálogo
**Dado que** un usuario con rol de operador está autenticado
**Cuando** solicita el enriquecimiento de un lote de productos
**Entonces** la respuesta es 403
**Y** no se crea ni se modifica ningún perfil
**Y** una petición sin autenticar recibe 401

### Escenario 9: El token de catálogo no abre la puerta de la recuperación
**Dado que** el enriquecimiento del catálogo no pertenece a ningún punto de venta y su llamada se autoriza con un scope sin punto de venta
**Cuando** ese mismo scope se intenta usar contra una ruta de recuperación
**Entonces** la llamada se rechaza en el propio cliente, antes de salir del proceso
**Y** si aun así llegara al servicio de IA, la ruta de recuperación la rechaza igualmente
**Y** ninguna ruta acepta un valor comodín en lugar de un punto de venta real

### Escenario 10: El esquema conserva lo que se rompe sin dar ningún error
**Dado que** la migración se ha aplicado sobre una base de datos limpia
**Cuando** se inspecciona el catálogo de PostgreSQL
**Entonces** las columnas de documentos JSON son de tipo `jsonb` y no texto
**Y** existe un índice **único** sobre el identificador de producto, que hace imposible un segundo perfil del mismo producto
**Y** el borrado de un producto está restringido y no arrastra en cascada el perfil ni el trabajo de revisión
**Y** el modelo y las migraciones no tienen diferencias pendientes

### Escenario 11: Renegociar el contrato rompe los dos lados hasta actualizarlos
**Dado que** este change amplía el contrato de enriquecimiento con el origen por campo y los tres campos sensibles nuevos
**Cuando** se ejecuta la suite del servicio de IA antes de regenerar el snapshot
**Entonces** el test de estabilidad del snapshot **falla**, señalando que la frontera se ha movido
**Y** tras regenerar el snapshot, la suite vuelve a verde
**Y** el test de deriva de contrato del lado .NET verifica que los modelos del cliente coinciden con el snapshot publicado

### Escenario 12: Fuera de alcance explícito
**Dado que** esta historia está implementada
**Cuando** se revisa el entregable
**Entonces** no existe ninguna ruta de lectura de perfiles, ni de aprobación, ni de métricas
**Y** no existe ninguna pantalla
**Y** ningún dato generado por IA ha modificado el nombre, el SKU, el precio ni la descripción de un producto
**Y** no se ha creado ninguna entidad de embeddings textuales en el lado .NET
**Y** la propuesta de familia y de variante que el contrato devuelve se ignora, sin crear ninguna relación con las familias de producto

---

## Notas adicionales

- **Actor:** Administrador. El operador no interviene en ningún punto de esta historia; su única relación con ella es que **no puede ejecutarla**. Los beneficiarios indirectos son C12 (feed de indexación, que filtra por estado de revisión), C13 (indexador), C21 (filtros estructurales por tipo de pieza y materiales), C26 (sustitutos por materiales coincidentes), C27 (complementarios por solape de etiquetas) y C28 (pantalla de revisión y métricas).

- **Por qué un change 🟢 tiene tanto peso.** La ficha lo marca como relleno paralelizable porque no está en la ruta crítica, pero **C12 lo tiene como prerrequisito** y C12 sí lo está. Un C08 que deje mal resuelto el predicado de aprobación no se nota aquí: se nota en que el índice de C13 se llena de propuestas sin revisar, o se queda vacío.

- **La zona real son seis carpetas, no tres.** La ficha del plan dice *«Domain/, Application/, API/Controllers/»*. La migración obliga a `Infrastructure/`, los tests a `Tests/`, y la renegociación del contrato a `ai-service/`. Es la misma corrección que C04 tuvo que registrar en su día, y **debe anotarse en el §0 del plan de changes** para que la próxima ficha no repita el error.

- **Sobre el turno de migración.** Este change ocupa el slot único de EF Core, compartido con C04 (hecho), C07, C19, C27 y C29. Hay que anunciarlo antes de empezar y mergearlo antes de que otro abra el suyo. **No compite** con las migraciones de Alembic de C05: son árboles independientes.

- **La suite de .NET viene con rojos previos.** `CLAUDE.md` lo documenta: decenas de fallos preexistentes, algunos dependientes del orden de ejecución. La línea base se mide antes de empezar y se comparan **nombres** de tests fallidos, nunca el recuento. Dos trampas concretas acechan a los tests de esta historia: un `HttpClient` compartido que conserva las cookies de sesiones anteriores —hay que pedir un cliente nuevo a la factoría para afirmar el 403— y los teléfonos generados por Bogus que desbordan `PointOfSale.Phone`.

- **El corpus real todavía no existe.** Esta historia no depende de él: se ejerce contra el stub determinista de C02, que responde perfiles completos sin llamar a ningún modelo. Cuando C06 traiga el catálogo híbrido y C09 el extractor real, el mismo endpoint y el mismo enrutado funcionan sin cambios — que es exactamente para lo que sirve haber congelado un contrato.

- **Limitación declarada para el README:** el enriquecimiento es **síncrono y por lotes de 50**. Enriquecer ~1.000 productos son veinte llamadas encadenadas a mano o desde un script. No hay cola, ni reanudación, ni progreso observable. A la escala del proyecto es aceptable; a escala real no lo sería, y conviene que quede escrito como decisión y no como olvido.

- **OpenSpec:** se implementa vía el change `add-product-ai-profile-entity`. **Lleva `design.md`**: cuatro de sus decisiones tienen alternativas defendibles con coste asimétrico, y tres de ellas cruzan la frontera .NET/Python. Además de la capability nueva, el change modifica tres specs vivas (`ai-gateway-client`, `ai-service-auth`, `ai-service-api-contracts`).

- **Línea de corte prevista.** Si la sesión se desborda (regla 5 del plan), el corte es limpio: **entidad + configuración EF + migración + tests de esquema** forman una mitad archivable por sí sola que **libera el turno de migración** y desbloquea a C12; **contrato + scope de catálogo + cliente + enrutado + endpoint** son la segunda, no llevan migración y conviven con el C07 del compañero. El orden importa: la primera mitad es la que otra persona está esperando.

---

## Tareas

> Ordenadas para que las tareas 1-3 formen una mitad completa y archivable (esquema, migración y detectores) y las 4-9 la segunda (contrato, frontera, enrutado y endpoint), por si hay que aplicar la línea de corte.

1. Definir `ProductAiProfile` en el dominio, con valores vigentes, procedencia por campo, propuesta original inmutable y estado y origen de revisión como conceptos separados.
2. Escribir la configuración de EF Core declarando **a mano** lo que falla en silencio: tipo `jsonb` de las siete columnas, índice único sobre el producto, índices de consulta y reglas de borrado restringidas. Generar la migración única.
3. Extender el arnés de aserciones de esquema heredado de C04 **solo** con lo que esta historia necesita —unicidad de índice—, y escribir los detectores de esquema, verificando que cada uno falla al romper a propósito lo que vigila.
4. Renegociar el contrato de enriquecimiento en `jbg-ai`: origen por campo, campos sensibles nuevos, desglose de etiquetas, stub determinista coherente y regeneración del snapshot con sus tests.
5. Abrir el scope de catálogo en los dos lados, con las dos guardas independientes que impiden que llegue a una ruta de recuperación, y sus tests en ambos lenguajes.
6. Añadir la operación de enriquecimiento al cliente tipado y registrar su familia de ruta propia, con presupuesto de tiempo, cortacircuitos aislado y sin reintento.
7. Implementar la política de enrutado híbrido como clase pura, con sus umbrales en configuración validada al arranque, y sus cuatro tests unitarios.
8. Implementar el servicio de enriquecimiento por lotes con idempotencia por hash de entradas y los dos modos de revisión, y exponerlo en el endpoint solo para administradores.
9. Actualizar la documentación afectada, registrar en el §0 del plan de changes la corrección de zona y la renegociación del contrato, y verificar la suite completa y `openspec validate --all --strict`.

---

## Estimaciones y atributos de priorización

> Valores propuestos a partir de la guía de estimación de [Procedimiento-TicketsTrabajo.md](../../Procedimientos/Procedimiento-TicketsTrabajo.md) (§4.6). **Pendientes de validar** en la sesión de refinamiento del equipo.

- **Puntos de historia:** **8** — es el change más ancho de la Ola 1 en superficie: cruza los dos lenguajes, mueve un contrato congelado, ocupa el turno de migración y añade una política de decisión con umbrales. No hay algoritmo difícil, pero sí muchas piezas que tienen que encajar a la vez y tres specs vivas que hay que modificar sin romperlas.
- **Impacto en usuario / Valor de negocio:** **4** — indirecto pero grande. Es el change que hace que el catálogo se pueda buscar por lo que las piezas *son* y no solo por cómo se llaman, y el que sostiene la evidencia de revisión humana que el proyecto va a defender.
- **Urgencia (mercado / feedback):** **4** — 🟢 fuera de la ruta crítica, pero **C12 sí está en ella** y lo tiene como prerrequisito junto con C07. Retrasarlo retrasa el feed, el indexador y, en cascada, el hito del 19 de agosto.
- **Complejidad / Esfuerzo:** **4** — la dificultad no está en ninguna pieza aislada, sino en cuatro decisiones que la ficha no anticipaba y que había que cerrar antes de escribir una línea: el contrato incompleto, el scope sin punto de venta, la doble naturaleza de `auto_bulk` y el almacenamiento que C28 no puede crearse a sí mismo.
- **Riesgos y dependencias:**
  - **Prerrequisito:** C03, archivado. Ocupa el **turno único de migración de EF Core**: hay que anunciarlo y no solaparlo con C07, C19, C27 ni C29.
  - **Riesgo:** el scope de catálogo se cuela en una ruta de recuperación y se convierte en una fuga entre puntos de venta → mitigado con **dos cierres independientes**, uno en cada lado, ambos con test (escenario 9).
  - **Riesgo:** dos perfiles del mismo producto pasan desapercibidos y C12 indexa documentos duplicados → mitigado con el índice único afirmado contra el catálogo de PostgreSQL (escenario 10).
  - **Riesgo:** una segunda pasada del lote machaca fichas ya revisadas por una persona → mitigado con la idempotencia por hash de entradas y el forzado explícito (escenario 7).
  - **Riesgo:** `AutoBulk` degenera en «aprobamos todo y no lo contamos», que es justo la trampa que §7.8 se compromete a no hacer → mitigado porque el modo queda escrito en el dato y la procedencia por campo sigue registrando lo que el enrutado habría dicho (escenario 6).
  - **Riesgo:** los umbrales se fijan a ojo y quedan compilados, imposibilitando la recalibración contra el golden set de C24 → mitigado con configuración validada al arranque (escenario 4).
  - **Riesgo:** renegociar el contrato desborda la sesión → mitigado con la línea de corte, que deja el contrato entero en la segunda mitad.
  - **Riesgo:** las columnas `jsonb` acaban como `text` sin dar ningún error, o el borrado en cascada se queda con el valor por defecto del framework → mitigado con los detectores de esquema heredados de C04.
  - **Riesgo aceptado:** C09 podría descubrir, al implementar el extractor de verdad, que el contrato renegociado aquí necesita un ajuste más. Se asume: el coste de una segunda renegociación es un snapshot y dos suites, y el de construir la entidad sobre una forma que ya se sabe insuficiente es rehacerla entera.
  - No depende del catálogo real, ni del proveedor de modelos, ni de ningún change de Python posterior: se implementa y se prueba contra el stub determinista de C02.
