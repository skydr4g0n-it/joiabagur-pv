# HU-AIENG-007: Familias de producto como entidad de negocio editable — variantes explícitas y desambiguables

## Formato estándar

Como **Administrador del catálogo**, quiero **agrupar en familias los productos que son variantes del mismo modelo, poniéndole a cada uno la etiqueta que lo distingue y el orden en que debe mostrarse, y poder corregir esa agrupación cuando esté mal** **para** **que el sistema pueda avisar de que existen tres anillos casi idénticos y obligar a confirmar cuál se vende, en vez de devolver tres resultados indistinguibles y dejar que la operadora acierte por azar**.

---

## Descripción

Tercer change de la Ola 1 del Proyecto Final de IA en ejecutarse, tras C05 y C08 (change OpenSpec `add-product-family-entity` / C07, épica **EP13 — Familias de Producto y Desambiguación de Variantes**). Marcado 🟢 como relleno paralelizable y 🗄️ porque **ocupa el turno único de migración de EF Core**. **No tiene ningún prerrequisito.**

El caso de negocio que esta historia sostiene es el crítico del proyecto y el que motivó todo lo demás: una joyería con anillos que se diferencian solo en la talla. Tres piezas, una foto prácticamente idéntica, tres SKU distintos, y una operadora que en el mostrador escoge el que aparece primero. El error no se detecta en la venta: se detecta cuando el cliente vuelve. Ninguna búsqueda semántica arregla esto por sí sola —los tres productos son legítimamente parecidos y el recuperador hace bien devolviéndolos los tres—; lo que hace falta es que el sistema **sepa que son la misma pieza en tres tallas** y lo diga.

Las especificaciones v2 resolvían esa agrupación con `VariantGroupKey`, **una cadena de texto dentro del perfil de IA**. La revisión de la PR #4 la rechazó, y su **decisión 2** es la que crea esta historia:

> *«Una clave textual generada por IA se rompe ("anillo-erizo-mar" vs "anillo-erizo-de-mar"), no la puede corregir un admin y falla justo en el caso que queremos evitar. Además la entidad hace implementable la alerta de "productos parecidos sin familia".»*

Las tres partes de esa frase son tres requisitos distintos. **Se rompe**: dos variantes de la misma pieza acaban en grupos diferentes por un guion, y el sistema deja de avisar precisamente donde el aviso importaba. **No la puede corregir un admin**: una clave enterrada en un perfil generado no es editable, y si se edita, el siguiente enriquecimiento la machaca. **Hace implementable la alerta**: sin una entidad con identidad propia no hay contra qué comparar para detectar un producto huérfano que debería pertenecer a una familia existente.

Por eso la familia deja de ser un atributo derivado y pasa a ser **una entidad de negocio de pleno derecho, en .NET**, exactamente donde el §6.2 del diseño coloca los *datos revisables por humanos*. Esta historia la crea y le da su superficie de administración manual. **No** le da inteligencia: la propuesta automática por similitud, la alerta de huérfanos y la pantalla de aprobación por lotes son C18, y el flujo mixto del §7.5 —*la IA propone, el admin aprueba, la familia queda editable después*— solo tiene sentido si primero existe lo que se aprueba.

Hay una cuarta cosa que esta historia hace y que su ficha no anticipa. **C18 no está marcado 🗄️** y el plan cuenta seis migraciones de EF Core, ninguna suya. Si C18 necesitara una columna para registrar que una familia salió de una sugerencia aprobada —que es literalmente la evidencia de intervención humana que el proyecto va a defender—, tendría que abrir una séptima en plena Ola 3, compitiendo con C19, C27 y C29. Es la misma situación que C08 resolvió hace un día reservando `ProposedProfileJson` y `ReviewDurationMs` para C28, y se resuelve igual: **C07 reserva ahora las tres columnas de aprobación**, las deja nulas, y C18 las puebla sin abrir migración.

**Alcance de esta historia (sí):**

- Entidades `ProductFamily` (nombre, descripción, origen y datos de aprobación) y `ProductFamilyMember` (producto, etiqueta de variante y orden) en el dominio .NET.
- **Una única migración de EF Core** con los tres índices únicos, los índices de consulta y las reglas de borrado declaradas a mano.
- El invariante **«un producto pertenece como máximo a una familia»** garantizado por un índice único en la base de datos, no por una comprobación aplicativa.
- Repositorio específico con las dos lecturas del change: familia con sus miembros ordenados, y familia de un producto.
- Cinco endpoints, todos de escritura solo para Administrador salvo las dos lecturas: crear familia (opcionalmente con miembros), leer familia, editar nombre y descripción, **reemplazar la lista de miembros de forma declarativa**, y consultar la familia de un producto.
- **Reserva del almacenamiento que C18 necesitará**: origen de la familia, quién la aprobó y cuándo.
- Tests: los cuatro de la ficha, los que abren las decisiones nuevas, y los detectores de esquema sobre el catálogo de PostgreSQL heredados de C04.

**Fuera de alcance (no):**

- **Toda la inteligencia.** Propuesta de familias por similitud de embedding, detección automática de la etiqueta de variante y alerta de huérfanos → **C18**. Esta historia no llama a `jbg-ai` ni una sola vez.
- **La pantalla.** Ni de creación, ni de edición, ni de revisión por lotes → **C18**. Esta historia no tiene interfaz de usuario en ninguna forma.
- **El feed de indexación** que lleva la familia al índice vectorial → **C12**.
- **La agrupación en la venta asistida** y la confirmación explícita de variante → **C30** y **C36**.
- **Listado paginado de familias y borrado de familias.** No los necesita nadie todavía y su forma la decide quien pinte la pantalla.
- **Cualquier escritura sobre `Product`**: ni una columna nueva, ni una propiedad de navegación. El catálogo no se toca.
- **Cualquier cambio en el contrato de `jbg-ai`.** `family_id` y `variant_label` ya viajan en él desde C02, en recuperación, asistencia, inventario y enriquecimiento. `ai-service/openapi.json` **no se regenera**.
- **Cualquier escritura en el esquema `ai`.** `family_id` ya existe ahí desde C05, como `uuid` plano sin clave foránea, y quien lo rellena es el indexador.

**Encaje y verificación previa (Definition of Ready):**

| Comprobación | Resultado |
|---|---|
| Épica | **EP13 — Familias de Producto y Desambiguación de Variantes** ([epicas.md](../../epicas.md)), cuyo alcance abre literalmente con *«Entidades `ProductFamily` y `ProductFamilyMember` en .NET»*. Changes de la épica: C07, C18, C28 |
| Solape con capabilities vivas | **Ninguno.** Las 33 capabilities de `openspec/specs/` no incluyen familias. La adyacente es `product-management`, que cubre `Collection` —el otro eje de agrupación— y **se referencia, no se duplica**. `product-ai-profile` declara expresamente que ignora la familia. `ai-vector-schema` ya reserva `family_id`, `family_name` y `variant_label` |
| Capability que crea | **`product-family`**, nueva. Ninguna spec viva se modifica |
| Changes activos con los que competir | Ninguno: `openspec/changes/` solo tiene `archive/` |
| Capas afectadas ([modelo-c4.md](../../modelo-c4.md)) | Domain → Infrastructure → Application → API. **Sin Frontend**, que es lo que el propio C4 asigna a C18 en su mapeo de EP13 |
| ¿`modelo-c4.md` necesita cambios? | **No.** Su sección EP13 ya nombra `ProductFamily` y `ProductFamilyMember` en el backend; esta historia los hace ciertos |
| Impacto en el modelo de datos | **Dos entidades nuevas y una migración de EF Core.** `Product` no cambia. Hay que añadirlas a [modelo-de-datos.md](../../modelo-de-datos.md) y a *Key Entities* de `openspec/project.md`, que hoy llega hasta `ProductAiProfile` y `ProductSearchEvent` |
| Regla de negocio nueva | *«Un producto pertenece como máximo a una familia»*, que se suma a las doce de `openspec/project.md` |
| Paginación | **No aplica**: esta historia no expone ninguna lista. Cuando C18 añada el listado de familias, la regla de máximo 50 ítems por página de `openspec/project.md` le será exigible |
| Ambigüedades detectadas | Recogidas como **Preguntas Abiertas** en el ticket técnico del change, cada una con su opción por defecto. Ninguna bloquea el apply |

**Decisiones de diseño ya acordadas:**

| Tema | Decisión |
|---|---|
| Principio rector | **La familia es un hecho del catálogo que responde una persona.** C07 construye el sitio donde ese hecho vive y se corrige; C18 construye quien lo propone. Ninguna de las dos puede sostener la autoridad de la otra |
| Familia frente a colección | Son **ejes ortogonales** y no deben confundirse. `Collection` es editorial («Verano 2024»), tiene muchos productos y un producto puede no tener ninguna. `ProductFamily` es *la misma pieza en varias variantes*, y un producto pertenece **como máximo a una** |
| Superficie de API | **Mínimo coherente:** `POST /api/product-families`, `GET /api/product-families/{id}`, `PUT /api/product-families/{id}`, `PUT /api/product-families/{id}/members` y `GET /api/products/{id}/family`. Sin listado paginado ni borrado: «editable» se cumple sobre metadatos **y** miembros, y el listado lo pedirá C18 cuando sepa qué columnas pinta |
| Semántica del reemplazo de miembros | **Declarativa.** El cuerpo del `PUT` declara la lista completa: lo que no aparece se quita, lo nuevo se añade, y el orden sale de la **posición en el array**. Es lo que `PUT` promete —idempotencia— y hace **imposibles por construcción** los huecos y los órdenes duplicados |
| Por qué no `POST`/`DELETE` de miembros sueltos | Alta y baja son la misma operación —*así queda la familia*— y partirlas en dos verbos obliga al cliente a orquestar el orden a mano. Precedente literal en `ComponentTemplateService` |
| Cómo se escribe ese reemplazo | **Borrar todo e insertar todo**, con **cortocircuito**: si la lista pedida es idéntica a la vigente, no se escribe nada. Conservar la identidad de las filas y actualizarlas en su sitio es lo que **crea** el problema, no lo que lo evita: intercambiar dos posiciones es un ciclo de actualizaciones que el motor no puede ordenar, mientras que borrar e insertar se resuelve solo |
| Consecuencia declarada de esa decisión | La fecha de creación de un miembro **no significa «cuándo entró el producto en la familia»** sino cuándo se escribió la lista por última vez. Queda escrito en `modelo-de-datos.md` para que nadie la lea como fecha de alta. Si algún día hace falta historial de pertenencia, es una tabla de auditoría, no un retoque de esta |
| Un producto, una familia | **Índice único sobre el producto**, en la base de datos. Una comprobación aplicativa deja la carrera abierta y, peor, un segundo miembro **no da ningún error**: el feed emitiría dos familias para el mismo producto y el indexador construiría documentos incoherentes. Mismo mecanismo y mismo motivo que el índice único de C08 |
| Qué se responde ante ese conflicto | **409**, nombrando **qué productos** y **qué familia los tiene ya**. Un 409 que solo dice «conflicto» obliga a la pantalla de C18 a adivinar cuál de veinte miembros falló. Dos cierres: comprobación previa en el servicio, que produce el mensaje útil, y traducción de la violación de unicidad de la base por si dos administradores escriben a la vez |
| Etiqueta de variante | **Opcional**, y **única dentro de la familia** cuando viene informada. Un miembro sin etiqueta todavía es un estado real —el §7.4 contempla el aviso *«falta la talla»* y el índice la tiene nulable—; dos «M» en la misma familia son un defecto. En PostgreSQL los nulos no colisionan entre sí, así que un único índice da las dos cosas sin filtro |
| Orden de los hermanos | **Único dentro de la familia**, también en la base. Sin unicidad, dos miembros con el mismo orden producen una lista **no determinista entre recargas**, que es un fallo mudo: la pantalla de desambiguación mostraría S, L, M una vez y S, M, L la siguiente |
| Nombre de la familia | **No único**, pero indexado. Dos familias pueden llamarse igual legítimamente, y forzar unicidad obligaría a C18 a inventar sufijos desambiguadores al aprobar ~350 familias por lotes — que es exactamente el problema de la clave textual generada que la decisión 2 vino a eliminar |
| Familias vacías o de un solo miembro | **Permitidas.** La familia es una entidad con vida propia: se crea primero y se puebla después, y vaciarla es la forma de disolverla sin borrarla. Una familia sin miembros no emite ninguna referencia al índice, luego es invisible aguas abajo y no puede hacer daño |
| Producto sin familia | **204**, distinguible del **404** de producto inexistente. El generador de C06 mete un **15 % de huérfanos a propósito**: es uno de cada siete productos, no un caso borde, y C18 necesita distinguirlo para su alerta mientras C36 lo necesita para decidir si pinta el bloque de variantes |
| Autorización | **Escritura solo Administrador**, como el resto de la administración de catálogo. **Lectura para cualquier usuario autenticado y sin filtrado por punto de venta**: la pertenencia a familia es un hecho del catálogo, no del inventario. Filtrar hermanos por POS metería lógica de stock dentro de un change de dominio y haría el orden dependiente de la existencia |
| Reserva para C18 | **Origen de la familia** (manual o aprobada de una sugerencia), **quién la aprobó** y **cuándo**, las tres nulables. C18 no está marcado 🗄️ y el plan cuenta seis migraciones: sin esta reserva tendría que abrir una séptima en la Ola 3. Precedente exacto y reciente: C08 reservando el almacenamiento de C28 |
| Por qué esa reserva y no más | Registrar además el origen y la confianza **de cada miembro** sería más fiel al §7.8, pero fija la forma de la revisión de C18 antes de haber diseñado C18 — el mismo motivo por el que C08 descartó su entidad de auditoría de revisión |
| Borrado | Familia → miembros **en cascada**; producto → miembro **restringido**. Los miembros no tienen vida propia: son la familia. El producto sí, y además el sistema lo **desactiva en vez de borrarlo**, así que la cascada por defecto del framework significaría que tocar el catálogo destruye la curación |
| Relación con `Product` | **Sin propiedad de navegación.** La clave foránea se declara desde el miembro. `Product` no gana ni una columna ni una colección: es la misma disciplina que C08 aplicó a su perfil, y lo que impide que alguien llegue a las familias por accidente recorriendo el catálogo |
| Vocabulario de etiquetas | **Texto libre acotado en longitud, nunca un tipo enumerado de PostgreSQL.** El vocabulario de tallas lo cerrará C18 al detectarlas; misma decisión y mismo motivo que C05 y C08 tomaron para los suyos |
| Alcance de la migración | **Una sola**, y ocupa el turno único. C08 la liberó al mergearse; hay que anunciarla y no solaparla con C19, C27 ni C29 |

**Referencias:**
[proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (ficha C07, §0 revisiones, reglas de asignación y reglas transversales de testing),
[proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§3 decisión 2, §6.2 qué vive dónde, §6.3 frontera y sincronización, §7.2 esquema del índice, §7.4 avisos por reglas, **§7.5 familias por flujo mixto**, §7.8 revisión humana híbrida),
[joiabagur-ia-especificaciones-funcionales-v2.md](../../Proyecto%20Final%20AIEng/joiabagur-ia-especificaciones-funcionales-v2.md) (§1 campos eliminados, §4.4 reglas funcionales de variantes, §4.6 modelo de datos),
[Calidad del Dato y decisiones de Arquitectura](../../Sesiones%20Master%20AIEng/S6_Fundamentos_Data_Driven_AI/Calidad%20del%20Dato%20y%20decisiones%20de%20Arquitectura.md) y [Limpieza, Normalizacion y Validacion de datos](../../Sesiones%20Master%20AIEng/S6_Fundamentos_Data_Driven_AI/Limpieza,%20Normalizacion%20y%20Validacion%20de%20datos.md),
[epicas.md](../../epicas.md) (EP13), [modelo-de-datos.md](../../modelo-de-datos.md), [modelo-c4.md](../../modelo-c4.md), [arquitectura.md](../../arquitectura.md),
[HU-AIENG-004.md](HU-AIENG-004.md) (arnés de test de esquema que esta historia hereda), [HU-AIENG-005.md](HU-AIENG-005.md) (esquema `ai`, que ya reserva la familia), [HU-AIENG-008.md](HU-AIENG-008.md) (perfil IA, que ignora la familia a propósito),
specs vivas `openspec/specs/product-management/spec.md`, `openspec/specs/product-ai-profile/spec.md`, `openspec/specs/ai-vector-schema/spec.md`,
change OpenSpec `openspec/changes/add-product-family-entity/` y su ticket técnico.

---

## Criterios de Aceptación

### Escenario 1: Una familia se crea con sus variantes en el orden declarado
**Dado que** existen tres productos activos que son la misma pieza en tallas S, M y L
**Cuando** un administrador crea una familia declarando esos tres productos con su etiqueta de variante, en ese orden
**Entonces** la familia queda persistida con sus tres miembros
**Y** el orden en que se declararon queda registrado en el dato, no deducido de otra cosa
**Y** al volver a leer la familia, los miembros salen en ese mismo orden

### Escenario 2: Un producto no puede pertenecer a dos familias
**Dado que** un producto ya pertenece a una familia
**Cuando** un administrador intenta incluirlo en una familia distinta
**Entonces** la operación se rechaza con 409
**Y** la respuesta dice **qué producto** y **a qué familia pertenece ya**, de modo que el error sea accionable sin investigar
**Y** ninguna de las dos familias queda modificada
**Y** el rechazo no depende de una comprobación en memoria: dos administradores escribiendo a la vez obtienen el mismo resultado

### Escenario 3: Consultar un producto devuelve a sus hermanos en orden
**Dado que** un producto pertenece a una familia con otras variantes
**Cuando** se consulta la familia de ese producto
**Entonces** se devuelve la familia con todos sus miembros, incluido el propio producto
**Y** los miembros vienen ordenados por el orden declarado
**Y** cada miembro trae su etiqueta de variante, para que quien pinte la respuesta pueda destacarla

### Escenario 4: Quitar un miembro no disuelve la familia
**Dado que** una familia tiene tres miembros
**Cuando** un administrador declara una lista de miembros que omite uno de ellos
**Entonces** ese producto deja de pertenecer a la familia
**Y** la familia sigue existiendo con los otros dos
**Y** los dos que quedan conservan un orden sin huecos
**Y** el producto retirado no queda asociado a ninguna familia

### Escenario 5: Vaciar una familia la deja existir sin miembros
**Dado que** una familia mal formada tiene miembros que no le corresponden
**Cuando** un administrador declara una lista de miembros vacía
**Entonces** la familia queda sin miembros y sigue existiendo
**Y** todos sus antiguos miembros quedan libres para asignarse a otra familia
**Y** una familia sin miembros no aporta ninguna referencia de familia a ningún producto

### Escenario 6: Reordenar e intercambiar etiquetas funciona sin efectos colaterales
**Dado que** una familia tiene dos miembros y se quiere intercambiar su posición, o corregir que las etiquetas S y M estaban cambiadas
**Cuando** un administrador declara la lista con las posiciones o las etiquetas intercambiadas
**Entonces** la operación se completa correctamente
**Y** el resultado leído después coincide exactamente con lo declarado
**Y** las garantías de unicidad de orden y de etiqueta siguen vigentes al terminar

### Escenario 7: Declarar la misma lista dos veces no vuelve a escribir
**Dado que** una familia ya tiene exactamente los miembros, etiquetas y orden que se van a declarar
**Cuando** se repite la misma declaración
**Entonces** la operación tiene éxito y el resultado es el mismo
**Y** **no se reescribe ninguna fila**, de modo que la operación no genera trabajo de reindexado inventado

### Escenario 8: Las etiquetas de variante distinguen, y lo hacen de verdad
**Dado que** una familia tiene miembros a los que todavía no se les ha detectado la talla
**Cuando** se persisten dos miembros sin etiqueta en la misma familia
**Entonces** ambos se guardan sin error, porque «etiqueta desconocida» es un estado legítimo
**Y** si en cambio se intenta guardar dos miembros con **la misma** etiqueta en la misma familia, la operación se rechaza
**Y** el mismo producto declarado dos veces en la misma petición se rechaza antes de tocar la base de datos

### Escenario 9: Un producto huérfano se distingue de un producto inexistente
**Dado que** el catálogo contiene productos que no pertenecen a ninguna familia
**Cuando** se consulta la familia de uno de esos productos
**Entonces** la respuesta indica sin ambigüedad que el producto existe y no tiene familia
**Y** consultar la familia de un producto que no existe devuelve una respuesta **distinta**
**Y** las dos situaciones son distinguibles por el cliente sin inspeccionar el cuerpo

### Escenario 10: Solo el administrador edita, pero el operador puede consultar
**Dado que** un usuario con rol de operador está autenticado
**Cuando** intenta crear una familia, editarla o cambiar sus miembros
**Entonces** la respuesta es 403 y no se crea ni se modifica nada
**Y** una petición sin autenticar recibe 401
**Y** el mismo operador **sí** puede consultar la familia de un producto, y la recibe completa, sin que sus puntos de venta asignados alteren la lista de hermanos

### Escenario 11: El esquema conserva lo que se rompe sin dar ningún error
**Dado que** la migración se ha aplicado sobre una base de datos limpia
**Cuando** se inspecciona el catálogo de PostgreSQL
**Entonces** existe un índice **único** sobre el producto, que hace imposible que un producto tenga dos familias
**Y** el orden y la etiqueta de variante son **únicos dentro de cada familia**
**Y** borrar una familia arrastra a sus miembros, mientras que borrar un producto está **restringido** y no destruye la curación
**Y** las columnas reservadas para la aprobación admiten nulos, de modo que crear una familia a mano no obligue a inventar un revisor
**Y** el modelo y las migraciones no tienen diferencias pendientes

### Escenario 12: La reserva para el flujo asistido está, y está vacía
**Dado que** esta historia solo crea familias manualmente
**Cuando** se crea una familia por la API
**Entonces** su origen queda registrado como manual
**Y** los campos de quién la aprobó y cuándo quedan vacíos
**Y** existen desde la primera migración, de modo que el flujo asistido pueda poblarlos sin abrir una migración propia

### Escenario 13: Fuera de alcance explícito
**Dado que** esta historia está implementada
**Cuando** se revisa el entregable
**Entonces** no existe ninguna propuesta automática de familias, ni detección automática de etiquetas, ni alerta de huérfanos
**Y** no existe ninguna pantalla
**Y** no se ha realizado ninguna llamada al servicio de IA, ni se ha modificado su contrato
**Y** el producto no ha ganado ninguna columna ni ninguna propiedad de navegación hacia las familias
**Y** no existe ningún endpoint de listado de familias ni de borrado de familias

---

## Notas adicionales

- **Actor:** Administrador para todo lo que escribe. El operador solo aparece en la lectura, y su participación real llega con la venta asistida de C30/C36; aquí su papel es que **no puede editar** y que **sí puede consultar**.

- **Por qué un change 🟢 sin prerrequisitos es de los que no se recortan.** El §6 del plan lo lista entre los que nunca se recortan, y el §4 muestra por qué: **C07 desbloquea a C12 🔴, a C18 y a C30 🔴**. Es, junto con C08, el cuello por el que pasa el feed de indexación. Además la desambiguación de variantes es *el* caso de negocio que la revisión de la PR #4 identificó como crítico.

- **La zona real son cinco carpetas, no tres.** La ficha del plan dice *«Domain/, Application/, API/Controllers/»*. La migración obliga a `Infrastructure/` y los tests a `Tests/`. Es la misma corrección que C04 y C08 tuvieron que registrar, y **debe anotarse en el §0 del plan de changes** para que la próxima ficha 🗄️ no repita el error. A diferencia de C08, esta historia **no** cruza a `ai-service/`.

- **Sobre el turno de migración.** Ocupa el slot único de EF Core, compartido con C04 (hecho), C08 (hecho), C19, C27 y C29. C08 lo liberó al mergearse el 16 de agosto. Hay que anunciarlo antes de empezar y mergearlo antes de que otro abra el suyo. **No compite** con las migraciones de Alembic del servicio de IA: son árboles independientes.

- **El arnés de test de esquema se hereda, no se construye.** C04 lo dejó montado y C08 lo amplió con la unicidad de índice. Esta historia **no necesita extenderlo**: las siete aserciones que le hacen falta —tipos, nulabilidad, unicidad, columnas de un índice y reglas de borrado— ya están disponibles. Se respeta el guardarraíl que C04 escribió para sí mismo: solo se añade lo que este change necesita hoy.

- **La suite de .NET viene con rojos previos.** Decenas de fallos preexistentes, y el conjunto **cambia entre ejecuciones idénticas del mismo commit**. La línea base se mide antes de empezar y se comparan **nombres** de tests fallidos, nunca el recuento. Dos trampas concretas acechan a los tests de esta historia: un cliente HTTP compartido que conserva las cookies de los logins previos —hay que pedir un cliente nuevo a la factoría para afirmar el 401— y los teléfonos generados por Bogus que desbordan el teléfono del punto de venta.

- **Dos huecos detectados que esta historia no cierra y adjudica por escrito.** Primero: con reemplazo declarativo, un producto que **sale** de una familia pierde su fila, y no queda ninguna marca temporal que le diga al feed de C12 que ese producto debe reindexarse sin familia. Segundo: **renombrar** una familia obliga a reindexar a todos sus miembros, porque el índice denormaliza el nombre y el hash canónico lo incluye. Ninguno de los dos se resuelve aquí —el §6.3 ya tiene diseñado el mecanismo, la invalidación que .NET empuja cuando cambia una familia—, pero **ambos son obligación de C12** y deben quedar escritos en el §0 del plan, o se descubrirán con el índice ya servido.

- **El corpus real todavía no existe.** Esta historia no depende de él: se prueba con productos creados en el propio test. Cuando C06 traiga las ~350 familias sintéticas con su 15 % de huérfanos deliberados y C18 la propuesta asistida, la misma entidad y los mismos endpoints funcionan sin cambios.

- **Limitación declarada para el README:** la administración de familias es **manual y sin listado**. Agrupar ~350 familias a mano es inviable, y por eso existe C18; lo que esta historia entrega es el sitio donde esas familias viven y se corrigen, no la forma de crearlas en masa. Conviene que quede escrito como decisión de secuencia y no como carencia.

- **El C4 ya contaba con esto.** La sección EP13 de [modelo-c4.md](../../modelo-c4.md) lista `ProductFamily` y `ProductFamilyMember` en el backend, y asigna al frontend la pantalla de revisión por lotes. Esta historia **no cambia el C4**: lo hace cierto en su mitad de backend y deja intacta la del frontend, que es de C18. Lo que sí hay que actualizar es [modelo-de-datos.md](../../modelo-de-datos.md) —donde las dos entidades no existen— y la lista *Key Entities* de `openspec/project.md`, que hoy termina en `ProductAiProfile` y `ProductSearchEvent`.

- **Familia y colección no son lo mismo, y conviene decirlo donde alguien lo vaya a leer.** `Collection` ya existe, ya está especificada en `openspec/specs/product-management/spec.md` y agrupa productos por criterio editorial. La confusión entre las dos es el error de lectura más probable de esta historia, así que la distinción debe quedar escrita en `modelo-de-datos.md` junto a las entidades nuevas, no solo aquí.

- **OpenSpec:** se implementa vía el change `add-product-family-entity`. **Lleva `design.md`** pese a no estar en la lista del §7 del plan: hay al menos cinco decisiones con alternativas defendibles y coste asimétrico —la reserva para C18, la estrategia de escritura del reemplazo, la unicidad del orden, la unicidad del nombre y las reglas de borrado—. Crea la capability nueva `product-family` y **no modifica ninguna spec viva**.

- **Línea de corte prevista.** Si la sesión se desborda (regla 5 del plan), el corte es limpio: **entidades + configuración de EF + migración + detectores de esquema** forman una mitad archivable por sí sola que **libera el turno de migración** y desbloquea la mitad del prerrequisito de C12; **repositorio + servicio + endpoints + tests de API** son la segunda, no llevan migración y conviven con cualquier otro change. El orden importa: la primera mitad es la que otra persona está esperando.

---

## Tareas

> Ordenadas para que las tareas 1-3 formen una mitad completa y archivable (esquema, migración y detectores) y las 4-7 la segunda (repositorio, servicio y endpoints), por si hay que aplicar la línea de corte.

1. Medir la línea base de la suite de .NET **antes de escribir nada**, guardando los nombres de los tests que ya fallan.
2. Definir las dos entidades en el dominio, con la etiqueta de variante opcional, el orden explícito y las tres columnas de aprobación reservadas para el flujo asistido.
3. Escribir la configuración de EF Core declarando **a mano** lo que falla en silencio —los tres índices únicos, los índices de consulta y las dos reglas de borrado— y generar la migración única. Escribir los detectores de esquema y **verificar cada uno rompiendo a propósito lo que vigila**.
4. Añadir el repositorio específico con las dos lecturas del change: familia con miembros ordenados y familia de un producto.
5. Implementar el servicio de aplicación con el reemplazo declarativo de miembros, su cortocircuito de no-operación y la detección de conflicto por doble pertenencia, con el mensaje que nombra producto y familia.
6. Exponer los cinco endpoints con validación invocada explícitamente, la matriz de autorización acordada y la distinción entre producto huérfano y producto inexistente.
7. Actualizar la documentación afectada —`modelo-de-datos.md` con las dos entidades, sus índices, sus reglas de borrado y la distinción explícita frente a `Collection`; `epicas.md` (EP13); *Key Entities* y la lista de reglas de negocio de `openspec/project.md`; y `backend/README.md` con los cinco endpoints y su matriz de autorización—, registrar en el §0 del plan de changes la corrección de zona, la reserva para C18 y las dos obligaciones heredadas por C12, y verificar la suite completa y `openspec validate --all --strict` con `0 failed`.

---

## Estimaciones y atributos de priorización

> Valores propuestos a partir de la guía de estimación de [Procedimiento-TicketsTrabajo.md](../../Procedimientos/Procedimiento-TicketsTrabajo.md) (§4.6). **Pendientes de validar** en la sesión de refinamiento del equipo.

- **Puntos de historia:** **5** — más estrecho que C08: un solo lenguaje, ningún contrato que renegociar y ninguna llamada saliente. La carga está en dos entidades relacionadas, cinco endpoints, tres índices únicos que interactúan entre sí en el reordenado, y siete aserciones de esquema.
- **Impacto en usuario / Valor de negocio:** **5** — es el change que ataca directamente el error de venta que motivó el proyecto. Ningún otro sustituye lo que hace: sin familias, la búsqueda devuelve tres piezas indistinguibles y el sistema no tiene con qué avisar.
- **Urgencia (mercado / feedback):** **4** — marcado 🟢 y sin prerrequisitos, pero **desbloquea C12 🔴 y C30 🔴**. Retrasarlo retrasa el feed, el indexador y, en cascada, el hito del 19 de agosto.
- **Complejidad / Esfuerzo:** **3** — ninguna pieza es difícil por separado. Lo que hay que pensar bien es la interacción entre el reemplazo declarativo y los índices únicos por familia, y qué se reserva hoy para no obligar a C18 a abrir una séptima migración.
- **Riesgos y dependencias:**
  - **Prerrequisitos:** ninguno. Ocupa el **turno único de migración de EF Core**: hay que anunciarlo y no solaparlo con C19, C27 ni C29. **Bloquea** a C12, C18 y C30.
  - **Riesgo:** un producto acaba en dos familias sin dar ningún error y el indexador construye documentos duplicados → mitigado con el índice único afirmado contra el catálogo de PostgreSQL (escenarios 2 y 11).
  - **Riesgo:** dos miembros con el mismo orden producen una lista de hermanos no determinista, que en la pantalla de desambiguación es peor que no tener orden → mitigado con unicidad de orden en la base (escenario 11).
  - **Riesgo:** el reordenado choca contra esa misma unicidad durante la escritura → mitigado con la estrategia de borrar e insertar, y con dos tests que ejercen el intercambio de posiciones y de etiquetas (escenario 6). Si fallaran, el plan B es escalonar la escritura en una transacción explícita.
  - **Riesgo:** C18 descubre que necesita una columna y tiene que abrir una séptima migración en la Ola 3 → mitigado reservando ahora el origen y los datos de aprobación (escenario 12).
  - **Riesgo:** un producto que sale de una familia nunca se reindexa y conserva la familia antigua en el índice para siempre → **no mitigado aquí a propósito**; queda adjudicado a C12 por escrito, con el mecanismo que el §6.3 ya tiene diseñado.
  - **Riesgo:** el borrado en cascada se queda con el valor por defecto del framework y borrar un producto destruye la curación → mitigado con las reglas declaradas a mano y sus detectores de esquema.
  - **Riesgo aceptado:** la superficie mínima puede quedarse corta cuando C18 pinte su pantalla y necesite un listado paginado. Se asume: añadir una ruta de lectura no cuesta migración, mientras que inventar hoy su forma sin saber qué columnas se pintan sí cuesta rehacerla.
  - No depende del catálogo real, ni del servicio de IA, ni de ningún change de Python: se implementa y se prueba contra productos creados en el propio test.
