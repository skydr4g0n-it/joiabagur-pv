# HU-AIENG-030a: La capa estructurada de venta asistida — tres modos, avisos por reglas y citas verificables sin llamar a ningún modelo

## Formato estándar

**Como** desarrollador del proyecto,
**quiero** que `POST /v1/assist/sale` deje de ser un fixture y devuelva candidatos agrupados por familia, avisos calculados por reglas y **citas que resuelven a un fragmento real del corpus**, sin invocar a ningún proveedor,
**para** que la venta asistida de .NET y su tarjeta de frontend puedan construirse sobre una forma de respuesta real y medible, y para que el argumentario en prosa llegue después como una capa cuyo valor se pueda **medir contra esta**.

---

## Descripción

`POST /v1/assist/sale` está en el contrato congelado desde C02 y **hoy sirve un fixture**:
[`stubs/responses.py`](../../../ai-service/src/jbg_ai/stubs/responses.py) fabrica familias
sintéticas y una frase con placeholders, y
[`api/routers/assist.py`](../../../ai-service/src/jbg_ai/api/routers/assist.py) responde **501**
cuando `STUB_MODE=false`, con `DELIVERED_BY = "C30 (add-assist-generation-with-rule-warnings)"`
escrito en el propio módulo. Esta historia es la primera mitad de ese C30.

El andamio está mucho más construido de lo que la ficha del plan sugería, y esta historia **no debe
reconstruirlo**:

| Pieza | Estado verificado | Qué aporta |
|---|---|---|
| [`retrieval/orchestrator.py`](../../../ai-service/src/jbg_ai/retrieval/orchestrator.py) | `retrieve_products()` vivo, fusión en dos etapas desde C25, `match_reasons` con procedencia real desde C21 | Los candidatos y su *por qué* |
| [`knowledge/search.py`](../../../ai-service/src/jbg_ai/knowledge/search.py) | `search_knowledge()` es **un callable, no una ruta**, y su docstring declara que *«the only consumer is C30»* | La recuperación citable, ya medida |
| [`knowledge/indexer.py`](../../../ai-service/src/jbg_ai/knowledge/indexer.py) | `document_id(slug)` y `chunk_id(doc_slug, sec_slug)` = `uuid5(KNOWLEDGE_NAMESPACE, …)` | Direccionamiento **por clave primaria**, sin migración |
| [`knowledge/corpus.py`](../../../ai-service/src/jbg_ai/knowledge/corpus.py) | `material_sheet_slug(canonical)` y `missing_material_sheets()` | El invariante 1:1 ficha↔material, ya con test |
| [`retrieval/abstention.py`](../../../ai-service/src/jbg_ai/retrieval/abstention.py) | Regla relativa de C25, **activa por defecto** (`α = 0,03`, `N = 15`) | La señal de «el catálogo no puede contestar» |
| `ai-service/src/jbg_ai/assist/` | **No existe** | La zona de esta historia, limpia |
| `IAiGatewayClient` (.NET) | Cinco métodos, **ninguno de assist** | `/v1/assist/sale` tiene **cero consumidores hoy** |

**Esa última fila gobierna la decisión más cara de la historia.** El coste de mover el contrato
congelado está en su **mínimo histórico ahora mismo** y crece de forma monótona a partir de C34.

### Por qué se parte C30, y por qué esta mitad va primera

El corte no es por tamaño: es por **dependencia real de los consumidores**. C34 (`GET
/api/ai/products/{id}/sales-assist`) y C36 (la tarjeta) necesitan **la forma** de la respuesta, no
la prosa. Así que esta mitad entrega la estructura completa **sin una sola llamada a un proveedor**
—y aun así con citas verificables, porque el corpus está indexado y el direccionamiento de las
fichas de material es determinista— y C30b añade el argumentario encima.

De ahí sale una **ablación que nadie estaba buscando**: misma ruta, mismos candidatos, mismas
citas, con prosa y sin ella. Es la única fila de la tabla del §11.2 que aísla lo que aporta el LLM
frente a lo que ya aportaba la recuperación.

### Cinco supuestos de la ficha del plan que el árbol refuta

Comprobados contra el repositorio antes de escribir código. Las once decisiones, con sus
alternativas descartadas y las mediciones estáticas del corpus, están en
[`c30-exploration-decisions.md`](../../Proyecto%20Final%20AIEng/informes/c30-exploration-decisions.md).

**1 · El contrato congelado no puede agrupar por familia.**

```
AssistGroup REQUIRED: ["family_id","members"]
  family_id: {"type":"string"}                                    ← NO nullable
RetrievalResult.family_id: {"anyOf":[{"type":"string"},{"type":"null"}]}   ← sí nullable
```

Y **~58 % del catálogo no pertenece a ninguna familia**: C18b cerró con **156 familias y 486
miembros** sobre las ~1.168 filas indexadas. El fixture disimula el problema porque fabrica un
`family_id` para cada grupo. Pasa a nulable, con el invariante *sin familia ⇒ exactamente un
miembro*, que es una nulabilidad convertida en algo que un test cierra.

**2 · El único consumidor previsto está anclado a pieza, y la petición sólo acepta texto.**
C34 expone dos rutas **por producto**; `AssistRequest.query` es obligatoria y no hay `product_id`.
El flujo por consulta **ya está servido** por `POST /api/ai/search` (C15) y el panel (C16). De ahí
los **tres modos**:

| modo | `product_id` | `query` | caso de mostrador | consumidor |
|---|---|---|---|---|
| **M1** | — | ✓ | *«¿cómo se limpia la plata?»* | bucle de C32 y escenarios de C38 |
| **M2** | ✓ | — | *«véndeme esta pieza»* | C34 → tarjeta de C36 |
| **M3** | ✓ | ✓ | *«¿este anillo se puede mojar?»* | C34 con `?question=` → caja en la tarjeta |

La regla correcta es **«al menos uno»**, no «exactamente uno»: M3 es el modo de mejor relación
valor/coste y es el que hace realizable el ejemplo que el §7.7 del diseño usa por su nombre.

**3 · Dos de los cuatro avisos no son de Python.** «Stock crítico» y «miembros sin stock» necesitan
el stock **real**. En Python sólo existe `qty_bucket`, y `ports.py` lo declara sin ambigüedad:
*«Carried for the availability demotion and never emitted: a bucket on the wire would be the
beginning of one»*, además de poder desfasarse minutos por el §15.10. **Pasan a C34, tras
hidratar.** Es el **segundo caso de la misma forma**: la ficha de C34 ya lleva anotada la exclusión
por stock que C26 retiró de la suya el 12 de septiembre por idéntico motivo.

**4 · Las citas se morían en la frontera.**

```
KnowledgeCitation (C23, 10 campos)          Citation (contrato, 3 campos)
citation_id    "material-plata#cuidados"    source   (str libre)   REQUIRED
document_title                              snippet  (str)         REQUIRED
section_title                               product_id
claim_scope    general | establecimiento         ✗  SE PIERDE
doc_type · score · source_ref                    ✗
```

`claim_scope` no es decorativo: su docstring dice que *«travels with the fragment and is not
optional: a commitment of the establishment read aloud as if it were a fact of the world is the
failure mode the whole marking mechanism exists to prevent»*, y son **25 de 161** fragmentos
(15,5 %). Y `citation_id` es lo que hace la cita **resoluble y localizadora** — *«resolves, locates
and opens the file and the heading in git»*.

**5 · La abstención está al 10 %, y el camino de assist no la mira.** `jpv_abstention_enabled` está
**activa por defecto** con `α = 0,03` y `N = 15`, y en esa banda abstiene en **2 de 20** consultas
fuera de dominio y en **0 de 43** contestables. O sea: **18 de 20 llegan con candidatos**, sobre un
golden set cuya categoría mayor son precisamente esas **20 de 72**. Sin puerta, esta capa
contestaría *«¿qué tiempo hace mañana?»* con cinco familias y —cuando llegue C30b— un argumentario
convencido, **durante toda una vuelta de manivela**, porque el arreglo es C31 y C31 lleva a C30 de
prerrequisito.

> **Lo que esta historia hace y lo que no, sobre la abstención:** no clasifica intención —eso es de
> C31 entero— y **no enciende nada**, porque la regla ya corre. Lo que hace es **honrarla y
> declararla**: no generar cuando ha saltado, y decirlo en `abstained`.

### El hueco que la exploración descubre y que no es de esta historia

El corpus de C23 —**32 documentos y 161 fragmentos**, indexado y calibrado desde el 6 de
septiembre— **no tiene hoy ninguna ruta hasta la pantalla del joyero**. Diez de esos documentos son
conversación de mostrador pura (`joyas-playa-piscina-y-deporte`, `niquel-y-piel-sensible`,
`regalar-sin-saber-la-talla`, `perfume-cremas-y-cosmetica`, `joyas-y-ninos`,
`guardar-y-viajar-con-joyas`, `cuidados-generales`, `ocasiones-y-tradicion`, `menorca-y-el-origen`,
`glosario-de-joyeria`) y ninguno es alcanzable. Y C23 **daba por hecho que sí lo era**: su fixture
de fuera de dominio dice *«son preguntas que un operador podría teclear de verdad en el mismo
cuadro de texto»*.

Esta historia entrega **el modo M3 que lo hace posible**; la superficie —`?question=` en C34 y la
caja en C36— es de esas dos fichas y queda anotada en ellas.

### Las dos reglas de citación, y por qué son distintas en cada modo

```
M2  (pieza, sin pregunta)  →  NO hay búsqueda vectorial
  Direccionamiento por clave primaria con chunk_id(document_slug, section_slug):
     material-<slug>#cuidados-y-limpieza-en-casa
     material-<slug>#piel-sensible-y-alergias
  Medido: las NUEVE fichas canónicas tienen esas dos secciones, y son `general` en las nueve.
  Invariante duro: sólo claim_scope == "general" entra en un argumentario que nadie preguntó.
  Motivo: material-bano-de-oro tiene una SÉPTIMA sección, «Nuestra garantía sobre el baño»,
  que es claim_scope: establecimiento y cuyo último párrafo dice literalmente
  «estas condiciones se confirman en tienda antes de trasladarlas a un cliente».

M1 / M3  (hay una pregunta humana)  →  search_knowledge, con filtro de slug ASIMÉTRICO
  EXCLUIR       material-<slug> de cada una de las NUEVE canónicas que la pieza NO declara
  PASAR SIEMPRE faq (10) · politica (4) · talla (4) · piedras-* (3)
                material-piezas-mixtas · material-marcajes-y-punzones
```

El filtro es **asimétrico a propósito**. Es seguro dentro del conjunto de las nueve porque son
**mutuamente excluyentes por construcción** —el invariante 1:1 de C23 contra los nueve términos de
`materials.terms`— y **confundibles por construcción**: C23 las describe como *«structurally
identical — same skeleton, same register, same vocabulary»* y advierte que *«cosine collapses by
homogeneity»*, que es el motivo por el que tuvo que añadir la rama léxica. Pero un filtro **general**
por material cortaría **23 de los 32 documentos** y con ellos casi toda pregunta real de mostrador:
sería falsa abstención en masa, y el proyecto ya zanjó esa asimetría en C25 con medición.

Y hay un detalle que el filtro debe respetar: `marcajes-y-punzones` y `piezas-mixtas` llevan
`doc_type = material` pero **no son salidas de `material_sheet_slug(canonical)`**, así que pasan. Es
lo correcto: *«¿qué significa el 925?»* es contestable sobre una pieza de acero.

---

### Alcance de esta historia (sí)

1. **Movimiento del contrato congelado, en un solo bloque**, con `openapi.json` regenerado en esta
   misma historia mientras la ruta tiene cero consumidores.
2. **Tres modos** con validación de «al menos uno» entre `product_id` y `query`.
3. **`intent` derivado estructuralmente**: `product_pitch` en M2, `unclassified` en M1 y M3.
4. **Agrupación por `family_id`** con `variant_label` destacado, y **`family_roster(family_id)`
   nuevo en `ProductSearchPort`**, leyendo **sólo `ai.product_document`**.
5. **`warnings[]` como códigos de vocabulario cerrado**: `family_has_variants` y
   `size_label_missing`. El copy castellano es del frontend.
6. **Citas verificables sin LLM**, con las dos reglas de arriba y el invariante de `claim_scope`.
7. **Puerta de abstención**: no generar cuando la regla de C25 ha saltado, y declararlo en
   `abstained`.
8. **Sustitución del stub por la implementación real** cuando `STUB_MODE=false`; el fixture se
   conserva para `STUB_MODE=true`.
9. **Capability nueva `assist-generation`** y **deltas** sobre `ai-service-api-contracts`,
   `knowledge-corpus` y `retrieval-abstention`.
10. **Los tres spikes previos**, con sus cifras escritas antes de decidir sobre ellas.

### Fuera de alcance (no)

1. **El argumentario en prosa.** `pitch` se emite **vacío**, `prompt_version` **nulo** y `usage` a
   cero. Es C30b.
2. **Cualquier llamada a un proveedor.** Ni LLM ni embeddings nuevos: M2 no usa vectores y M1/M3
   reutilizan la recuperación que ya existe.
3. **Clasificar la intención.** El enrutado catálogo / conocimiento / ambos / fuera de dominio es
   C31 entero, y `unclassified` es el único valor que esta historia puede emitir en M1 y M3.
4. **El bucle agéntico y sus tools.** Es C32, aunque `family_roster` y el filtro de slug le dejen
   `listar_familia` y `consultar_conocimiento` medio construidas.
5. **Los dos avisos de stock.** `stock_critical` y `family_members_out_of_stock` son de C34.
6. **La superficie de operario.** Ni `?question=` en .NET ni la caja en la tarjeta: son C34 y C36.
7. **Tocar `backend/` o `frontend/`.** Esta historia es **sólo `ai-service/`**.
8. **Migración de base de datos.** Ninguna: el roster lee `ai.product_document` y el filtro de
   slug opera sobre la **clave primaria** de `ai.knowledge_document`, derivada con el
   `document_id(slug)` que ya existe.
9. **Reindexar, recalibrar umbrales o mover pesos de fusión.** El 0,51 de conocimiento y la banda
   de abstención se consumen, no se re-fijan.

### Decisiones de diseño ya acordadas

| # | Decisión | Alternativa descartada, y por qué |
|---|---|---|
| 1 | **Renegociar el contrato ahora, en bloque** | Un `family_id` sintético (`solo:<uuid>`) es una mentira en el cable: .NET y el frontend tendrían que reconocer un prefijo que ningún esquema declara, y nada en el tipo impediría que `family_has_variants` dispare en un grupo sintético. Mover sólo el mínimo obliga a una segunda negociación cuando C34 ya exista y sea caro |
| 2 | `family_id` **nulable** + invariante *sin familia ⇒ un miembro* | Descartar los productos sin familia pierde el 58 % del catálogo, incluido el primer resultado de la mayoría de consultas |
| 3 | **Tres modos, «al menos uno»** | *«Exactamente uno»* excluye M3. Una ruta nueva `/v1/assist/product` rompe el MUST de diez rutas, y C23 ya argumentó contra añadir rutas por comodidad. Que C34 sintetice una consulta desde los metadatos deja el argumentario hablando de piezas parecidas y no de la elegida |
| 4 | `reason` por candidato se sirve reusando **`match_reasons`** | Un campo nuevo con vocabulario nuevo, cuando `match_reasons` ya lleva procedencia real desde C21 y el panel ya sabe mapear sus códigos a badges |
| 5 | **Avisos como códigos**, copy en el frontend | Prosa castellana en Python produce una lista de procedencia mezclada cuando C34 apila los suyos, que el frontend no puede distinguir ni estilar. Cambiar el tipo a `list[Warning{code,params}]` es un movimiento de esquema mayor sin necesidad |
| 6 | **Los dos avisos de stock son de C34** | Calcularlos desde `qty_bucket` rompe el invariante del cable y puede emitir un aviso falso: «stock crítico» con doce unidades en el cajón es la credibilidad del asistente en el mostrador |
| 7 | `Citation` **reformada**, con `claim_scope` y `citation_id` | Meter `citation_id` en `source` funciona y pierde `document_title`/`section_title`, dejando al frontend pintando un slug |
| 8 | `citations[]` son **fragmentos del corpus, y sólo eso** | Citar el catálogo es decoración: los metadatos del producto ya viajan en la respuesta, así que citarlos no verifica nada. El anclaje al catálogo se expresa con `match_reasons` |
| 9 | En M2, **lookup determinista** por `chunk_id` | Una búsqueda vectorial paga un *embedding* y reintroduce el riesgo de cita espuria para resolver algo que una clave primaria resuelve exacto |
| 10 | **Lista blanca de secciones**, nunca «todas las de la ficha» | «Todas» mete la garantía de taller de `material-bano-de-oro` en un argumentario que nadie pidió. El riesgo no crece linealmente con el número de secciones: es un escalón, y está en secciones concretas |
| 11 | En M1/M3, filtro de slug **asimétrico** | Un filtro general por material corta 23 de 32 documentos y produce falsa abstención en masa. No filtrar deja que la ficha de un material que la pieza no declara gane el k-NN, sobre nueve fichas que C23 llama *«structurally identical»* |
| 12 | `abstained`, **nunca `low_confidence`** | Ese nombre ya tiene un significado medido —consenso entre ramas— *anticorrelacionado* con lo que aquí hace falta: dispara en 1 de 20 fuera de dominio y en 10 de 43 contestables |
| 13 | `intent` **estructural**, sin heurística de palabras clave | Un mini-router por palabras clave es trabajo que C31 borra, y el repo ya pagó por andamio una vez con C25bis |
| 14 | El valor efectivo de la abstención viaja **por parámetro** | Leerlo del entorno impide al arnés barrer configuraciones en un proceso, que es el patrón de C20, C23 y C25 |
| 15 | La pieza no indexada es **un error, no una abstención** | Se reutiliza el patrón de C26: `source_document` devuelve `None` y el router convierte los tres casos inservibles —desconocido, inactivo, sin indexar— en tres frases distintas |

### Referencias

- **Decisiones de exploración:** [c30-exploration-decisions.md](../../Proyecto%20Final%20AIEng/informes/c30-exploration-decisions.md)
- **Diseño:** §7.5 (familias), §7.6 (prefiltro y sobre-recuperación), **§7.7** (generación, avisos y citas, con su bloque revisado del 13 sep), §9.1 (un agente), §11.2–11.3, §15 limitaciones 12 y 13, §16 — [proyecto-final-diseno-rag-joiabagur.md](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md)
- **Ficha del plan:** C30a en el §3 de [proyecto-final-plan-changes-openspec.md](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md), y la entrada del §0 del 13 de septiembre
- **Capabilities vivas que se consumen:** [`ai-service-api-contracts`](../../../openspec/specs/ai-service-api-contracts/spec.md) · [`knowledge-corpus`](../../../openspec/specs/knowledge-corpus/spec.md) · [`retrieval-abstention`](../../../openspec/specs/retrieval-abstention/spec.md) · [`hybrid-fusion`](../../../openspec/specs/hybrid-fusion/spec.md) · [`product-family`](../../../openspec/specs/product-family/spec.md)
- **Consumidores aguas abajo:** C34 y C36 en el mismo §3 del plan, las dos con sus añadidos del 13 de septiembre
- **Change:** `add-assist-structure-and-rule-warnings` · **Épica:** EP15

---

## Criterios de Aceptación

### Escenario 1: Una pieza con familia devuelve su grupo con las variantes

- **Dado que** un producto indexado pertenece a una familia con tres miembros,
- **Cuando** se solicita la asistencia de venta con su `product_id` y sin consulta,
- **Entonces** la respuesta trae **un solo grupo** cuyo `family_id` es el de esa familia,
- **Y** el grupo lista los miembros con su `variant_label` cuando lo tienen,
- **Y** `intent` vale `product_pitch`,
- **Y** `pitch` viene **vacío**, `prompt_version` **nulo** y `usage` a cero.

### Escenario 2: Una pieza sin familia devuelve un grupo de un solo miembro

- **Dado que** un producto indexado no pertenece a ninguna familia,
- **Cuando** se solicita la asistencia de venta con su `product_id`,
- **Entonces** la respuesta trae un grupo con `family_id` **nulo**,
- **Y** ese grupo contiene **exactamente un miembro**, el producto solicitado,
- **Y** el aviso `family_has_variants` **no** aparece.

### Escenario 3: El aviso de variantes sale del roster y no de los candidatos recuperados

- **Dado que** un producto pertenece a una familia de cuatro miembros y la recuperación sólo devolvió dos de ellos,
- **Cuando** se solicita la asistencia de venta,
- **Entonces** el aviso `family_has_variants` **sí** aparece,
- **Y** aparece porque el roster de la familia declara cuatro miembros, no porque los candidatos fueran dos.

### Escenario 4: Falta la talla y se avisa con un código, no con prosa

- **Dado que** un producto indexado no declara `size_label`,
- **Cuando** se solicita la asistencia de venta,
- **Entonces** `warnings` contiene el código `size_label_missing`,
- **Y** todos los elementos de `warnings` pertenecen al vocabulario cerrado declarado,
- **Y** ninguno de ellos es una frase en lenguaje natural.

### Escenario 5: Los avisos de stock no los emite este servicio

- **Dado que** un producto tiene un *bucket* de disponibilidad de cero en el punto de venta del token,
- **Cuando** se solicita la asistencia de venta,
- **Entonces** `warnings` **no** contiene `stock_critical` ni `family_members_out_of_stock`,
- **Y** la respuesta no incluye ninguna cifra ni *bucket* de disponibilidad en ningún campo.

### Escenario 6: El argumentario de una pieza cita las fichas de sus materiales, y sólo las suyas

- **Dado que** un producto declara `materials: ["plata"]`,
- **Cuando** se solicita la asistencia de venta con su `product_id` y sin consulta,
- **Entonces** `citations` trae los fragmentos de `material-plata` de la lista blanca de secciones,
- **Y** cada cita lleva su `citation_id`, su `document_title`, su `section_title`, su `doc_type` y su `claim_scope`,
- **Y** ninguna cita procede de la ficha de un material que el producto no declara.

### Escenario 7: Ningún compromiso de la casa entra en un argumentario que nadie preguntó

- **Dado que** un producto declara `materials: ["baño de oro"]`, cuya ficha incluye una sección con `claim_scope: establecimiento`,
- **Cuando** se solicita la asistencia de venta con su `product_id` y **sin** consulta,
- **Entonces** ninguna de las citas devueltas tiene `claim_scope: establecimiento`,
- **Y** las citas devueltas son las de la lista blanca de secciones, todas con `claim_scope: general`.

### Escenario 8: Una pregunta sobre la pieza no puede citar la ficha de otro material

- **Dado que** un producto declara `materials: ["acero"]`,
- **Cuando** se solicita la asistencia de venta con su `product_id` y la consulta *«¿se puede mojar?»*,
- **Entonces** ninguna cita devuelta procede de las fichas de las ocho materiales canónicas que el producto no declara,
- **Y** las citas que sí procedan de `material-acero` se devuelven con normalidad.

### Escenario 9: El filtro de material no cierra la puerta al resto del corpus

- **Dado que** un producto declara `materials: ["acero"]`,
- **Cuando** se solicita la asistencia de venta con la consulta *«¿se puede llevar a la piscina?»*,
- **Entonces** las citas de documentos de tipo `faq`, `politica`, `talla` y de las fichas de piedras **no** quedan excluidas por el filtro,
- **Y** tampoco quedan excluidas `material-piezas-mixtas` ni `material-marcajes-y-punzones`, que comparten prefijo con las fichas de material pero no son fichas de material.

### Escenario 10: Una consulta libre sin pieza se atiende y su intención no se declara resuelta

- **Dado que** no se aporta `product_id`,
- **Cuando** se solicita la asistencia de venta con la consulta *«¿cómo se limpia la plata?»*,
- **Entonces** la respuesta se sirve con las citas que el corpus soporte,
- **Y** `intent` vale `unclassified`,
- **Y** la respuesta no afirma haber clasificado la consulta como de catálogo, de conocimiento ni de fuera de dominio.

### Escenario 11: Una petición sin pieza y sin consulta se rechaza

- **Dado que** la petición no aporta ni `product_id` ni `query`,
- **Cuando** se envía,
- **Entonces** se rechaza con un error de validación,
- **Y** el mensaje indica que se requiere al menos uno de los dos.

### Escenario 12: Cuando el catálogo no puede contestar, no se genera y se declara

- **Dado que** la regla de abstención salta para una consulta,
- **Cuando** se solicita la asistencia de venta con ella,
- **Entonces** `abstained` vale verdadero,
- **Y** `groups` viene vacío,
- **Y** la respuesta **no** reutiliza `low_confidence` para expresar esta decisión.

### Escenario 13: Una consulta contestable no se silencia

- **Dado que** una consulta del conjunto de evaluación tiene respuesta en el catálogo,
- **Cuando** se solicita la asistencia de venta con ella,
- **Entonces** `abstained` vale falso,
- **Y** la respuesta trae al menos un grupo.

### Escenario 14: Una pieza que no está en el índice es un error, no una abstención

- **Dado que** se aporta el `product_id` de un producto que no existe en el índice, o que existe pero está inactivo, o que existe y no tiene embedding,
- **Cuando** se solicita la asistencia de venta,
- **Entonces** se responde con un error que distingue los tres casos,
- **Y** en ninguno de ellos se responde `200` con `abstained` verdadero, que afirmaría que el catálogo no puede contestar cuando el problema es la pieza.

### Escenario 15: El punto de venta lo manda el token y nunca el cuerpo

- **Dado que** el token declara un punto de venta y el cuerpo de la petición trae otro distinto en `pos_id`,
- **Cuando** se solicita la asistencia de venta,
- **Entonces** el ámbito aplicado es el del token,
- **Y** `effective_pos_id` en la respuesta es el del token,
- **Y** una petición sin token válido recibe `401`.

### Escenario 16: Ninguna cifra de precio ni de stock viaja en la respuesta

- **Dado que** los productos del índice llevan una copia de su precio para ordenar,
- **Cuando** se solicita la asistencia de venta en cualquiera de los tres modos,
- **Entonces** ningún campo de la respuesta contiene un precio ni una cantidad de stock,
- **Y** el hecho de que `pitch` venga vacío no se usa como excusa para omitir esta comprobación, que se hace sobre la respuesta completa.

### Escenario 17: El contrato publicado y el vivo no divergen

- **Dado que** los modelos de petición y respuesta han cambiado,
- **Cuando** se ejecuta la comprobación del *snapshot* de OpenAPI,
- **Entonces** el `openapi.json` comprometido coincide con el esquema vivo,
- **Y** la regeneración se ha hecho con el perfil canónico documentado.

### Escenario 18: Con los stubs apagados la ruta deja de responder 501

- **Dado que** `STUB_MODE` está desactivado,
- **Cuando** se solicita la asistencia de venta con una petición válida,
- **Entonces** la respuesta **no** es `501`,
- **Y** con `STUB_MODE` activado la ruta sigue sirviendo el fixture determinista, sin entrada ni salida externas.

### Escenario 19: Fuera de alcance explícito

- **Dado que** esta historia entrega la capa estructurada y no el argumentario,
- **Cuando** se sirve cualquier respuesta en cualquiera de los tres modos,
- **Entonces** `pitch` viene vacío y `prompt_version` nulo,
- **Y** no se realiza ninguna llamada a un proveedor de modelos ni de *embeddings* que no estuviera ya en la recuperación,
- **Y** ninguna respuesta contiene `stock_critical`, `family_members_out_of_stock` ni un `intent` distinto de `product_pitch` o `unclassified`.

---

## Notas adicionales

- **Actor:** desarrollador del proyecto. La ruta es interna de `jbg-ai` y sólo la consume .NET con
  el token de servicio HS256; **el navegador nunca llama a Python**.
- **Es una historia de contrato antes que de funcionalidad.** Lo más caro que hace es mover el
  `openapi.json` congelado, y lo hace **ahora** porque `IAiGatewayClient` no tiene método de assist
  y C34 y C36 no existen: hoy el coste es cero y a partir de C34 no lo será. El README de
  `ai-service` ya fija la doctrina — *«Regenerating is a contract negotiation, not a chore»* — y el
  precedente es propio: C18a y C18b regeneraron el *snapshot* en el mismo change en que movieron la
  frontera.
- **Entrega citas verificables sin llamar a ningún modelo**, y eso no es una curiosidad: convierte
  a C30b en una capa cuyo valor se puede medir contra esta, que es la ablación que el §11.2 pide y
  que ninguna otra fila de esa tabla aporta.
- **Limitación conocida que hereda:** el roster de familia es la foto del índice a fecha del último
  sync, así que el aviso `family_has_variants` puede quedar desfasado esa ventana. Es degradación y
  no eliminación, coherente con el invariante del §15.10, y se declara.
- **Limitación conocida del alcance:** el modo M1 se implementa y **no recibe pantalla**. Su
  consumidor es el bucle de C32 y el arnés de C38, y eso entra como limitación 12 del §15.
- **Corrección registrada durante la exploración:** la primera redacción del informe de decisiones
  afirmaba que la abstención estaba desactivada por defecto, tomándolo de un estado intermedio del
  apply de C25. Está **activa** (`true`, `α = 0,03`, `N = 15`). La decisión no cambia, porque lo que
  la sostiene es el 18 de 20; lo que cambia es el trabajo, que es propagar y declarar en vez de
  encender.
- **Change de OpenSpec:** `add-assist-structure-and-rule-warnings`. **Rama:**
  `c30a-add-assist-structure-and-rule-warnings`.

---

## Tareas

1. **Puerta de entrada**: línea base de las dos suites por **nombres de test** y no por recuento
   (`git stash push -u`, correr, `git stash pop`), y `openspec validate --all --strict` en verde
   antes de tocar nada.
2. **Los tres spikes**, con sus cifras escritas antes de decidir sobre ellas: el umbral de
   conocimiento contra consultas de producto **en dos brazos** (con y sin filtro de slug) sobre las
   72 consultas del golden set; la viabilidad de reutilizar el vector de consulta entre recuperación
   y conocimiento; y la cardinalidad máxima del roster de familia.
3. **Modelos de contrato** (`api/schemas/assist.py` y `common.py`): `product_id`, validación de «al
   menos uno», `family_id` nulable, `match_reasons` en el miembro, `Citation` reformada, `abstained`
   y `prompt_version`.
4. **Regeneración del `openapi.json`** con el perfil canónico y actualización de su prueba de
   *snapshot*.
5. **`family_roster(family_id)`** en `ProductSearchPort` y su implementación SQL sobre
   `ai.product_document` únicamente, con el tope que fije el spike 3.
6. **Filtro por documento en la búsqueda de conocimiento**: parámetro nuevo en `search_knowledge` y
   en el protocolo del índice, con la cláusula en las dos sentencias, sobre la clave primaria
   derivada de `document_id(material_sheet_slug(term))`.
7. **Paquete `jbg_ai/assist/`**: resolución de modo, agrupación, roster, reglas de aviso con su
   vocabulario cerrado, direccionamiento determinista de citas para M2, y puerta de abstención.
8. **Cableado del router**: implementación real cuando `STUB_MODE=false`, fixture conservado cuando
   está activo.
9. **Tests de contrato y de comportamiento** en el árbol espejo de `ai-service/tests/`, sin una sola
   llamada real a un LLM ni a *embeddings*, con fakes inyectados y fixtures.
10. **Capability nueva `assist-generation` y deltas** de `ai-service-api-contracts`,
    `knowledge-corpus` y `retrieval-abstention`, con `openspec validate --all --strict` en verde.
11. **Informe de implementación** con las cifras de los tres spikes y con lo que la implementación
    refute de esta historia.
12. **Documentación**: `Documentos/epicas.md`, plan de changes, `ai-service/README.md` y las fichas
    de C34 y C36 si el trabajo mueve algo de lo que ya llevan anotado.

---

## Estimaciones y atributos de priorización

| Atributo | Valor |
|---|---|
| Puntos de historia | _Pendiente_ — a fijar en refinamiento |
| Impacto en usuario / valor de negocio | **5/5** — el §6 del plan la marca como **«nunca se recorta»**, y es el nodo de arranque de la cadena crítica que queda: `C30a → C34 → C36` y `C30a → C30b → C31 → C32 → C38` |
| Urgencia | **5/5** — es el **único change libre que desbloquea algo**, y mueve el contrato congelado. El argumento es de coste y no de calendario: hoy `/v1/assist/sale` tiene cero consumidores y a partir de C34 los tendrá |
| Complejidad / esfuerzo | **4/5** — sin migración, sin `backend/` y sin `frontend/`, y con la recuperación y el corpus ya construidos. Lo caro es el bloque de contrato, el filtro asimétrico —que hay que llevar a las dos sentencias y al protocolo— y la disciplina de no dejar entrar ni una llamada a un proveedor |
| Riesgos | Que el umbral de conocimiento devuelva citas espurias sobre consultas de producto en M1, donde no hay filtro posible (mitigado por el spike 1 en dos brazos, y acotado porque M2 no usa vectores y M3 sí filtra); que la lista blanca de secciones se relaje en implementación y entre un `claim_scope: establecimiento` (mitigado por el Escenario 7 y por un invariante en la capability); que el filtro de slug se aplique de más y corte los 23 documentos temáticos (mitigado por el Escenario 9); que el roster se dé por pequeño y una familia de ocho miembros desborde el contexto (mitigado por el spike 3); que la regeneración del `openapi.json` arrastre cambios no intencionados del perfil canónico (mitigado por el Escenario 17); y que el alcance se desborde hacia el argumentario, que es precisamente lo que el desdoble existe para evitar |
| Dependencias | **C07**, **C21** y **C23**, los tres archivados. Consume además **C22** (ámbito por punto de venta), **C25** (abstención y fusión en dos etapas) y **C18a/C18b** (las familias que hacen que `family_id` no sea nulo en todas las filas). **Bloquea a C30b y a C34**, y con C34 a C36 y a C38 |
