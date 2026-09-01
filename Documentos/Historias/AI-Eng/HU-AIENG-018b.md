# HU-AIENG-018b: Revisión humana de familias de producto y alerta de huérfanos

## Formato estándar

Como **Administrador del catálogo**, quiero **revisar una a una las familias que la IA agrupó, ver qué miembros el vector no respalda y qué productos sueltos deberían pertenecer a una familia, y que mis decisiones se recuerden**, **para** **que la agrupación deje de ser una aprobación en bloque que nadie miró, y para que el proyecto pueda declarar con un número cuánto acierta el agrupador y cuánto cuesta revisarlo**.

---

## Descripción

Change OpenSpec `add-family-review-ui-and-orphan-alert` / **C18b**, épica **EP13 — Familias de Producto y Desambiguación de Variantes**. Marcado 🟢 en el plan. Prerrequisito: **C18a** (`add-family-suggestion-and-approval`, archivado el 2026-08-31). Es **hoja del grafo**: ningún change depende de él.

Esta historia es **la segunda mitad de C18**, partido el 2026-08-30/31 por la regla 5 del plan. C18a entregó el motor determinista y el camino de escritura; C18b entrega la intervención humana y la señal de calidad que sólo tiene sentido cuando ya hay familias contra las que medirse.

### El hallazgo que gobierna la historia: la ficha de C18b describe un mundo que C18a ya no dejó en pie

La ficha del plan promete *«pintar la cola de revisión que C18a ya calcula: 15 miembros marcados, 4 grupos rechazados y 37 productos excluidos»*. **Los tres números están caducados**, y el mecanismo que los produciría ya no los produce. Verificado el 2026-08-31 contra el Postgres local (`jpv-pv-postgres`) en la sesión de exploración previa a este change:

| Lo que la ficha promete pintar | Lo que hay hoy | Por qué |
|---|---|---|
| 15 miembros marcados | **0 recalculables** | Los 486 miembros ya pertenecen a una familia, y `build_candidate_groups` los excluye en su paso 1 por la regla de convergencia. Las marcas vivían **sólo en la respuesta de `suggest`** y C18a decidió deliberadamente no persistir propuestas (D3 de su `design.md`) |
| 4 grupos rechazados | **2** — `Alianzas Plata`/`Alianzas oro` y `Cadena oro`/`Cadena plata` | `Encargos` y `Presión` salieron del índice con `ProfileReviewStatus = Rejected` en el mismo lote de C18a. Ya no son candidatos, así que su grupo no llega a formarse |
| 37 productos excluidos por la puerta de `piece_type` | **11** — nueve joyas sintéticas y dos llaveros conservados | 26 de los 37 estaban entre los 32 retirados del índice |
| «una propuesta descartada reaparece» | **0 propuestas** | C18a aplicó las 156 que produjo. `POST /v1/families/suggest` hoy devuelve lista vacía |

Estado medido, que es el punto de partida real de esta historia:

| | |
|---|---|
| `Products` / `ProductAiProfiles` | 1.200 / 1.200 (los 1.200 activos) |
| `ai.product_document` | **1.168** (1.200 − 32 retirados) |
| `ProductFamilies` / `ProductFamilyMembers` | **156 / 486** |
| Familias con `Origin = AiApproved` | **156 / 156**. Familias `Manual`: **0** |
| Documentos con `family_id` | **486** |
| **Documentos activos sin familia** | **682** — de ellos **671 con `piece_type`** y 11 sin él |
| Perfiles `Approved` / `Rejected` | 1.168 / 32 |

**La consecuencia:** si C18b se construye literalmente como la ficha dice —una pantalla sobre `suggest` y `/apply`— entrega **una pantalla vacía**. Es exactamente la firma que este proyecto persigue desde C17 (*«compila, pasa, valida, y llega vacío»*), y sería su cuarta aparición tras A1 en C04, B5 en C16 y el índice en C17.

Pero **sí queda trabajo, y es otro**: 156 familias que nadie ha mirado y 671 huérfanos activos con tipo de pieza. La historia se reencuadra sobre eso.

### El segundo hallazgo: marcados y huérfanos son el mismo predicado a los dos lados de la línea de pertenencia

No son dos funcionalidades. Son una consulta de vecindad sobre `ai.product_document` leída en dos direcciones:

- **Miembro marcado** — un producto de **otra** familia está más cerca de él que su propio peor hermano, por más de un margen. Es el veto relativo de C18a, aplicado a familias **persistidas** en lugar de a familias **propuestas**.
- **Huérfano candidato** — un producto **sin familia** está más cerca de los miembros de una familia F que el peor hermano de F, por más de un margen.

Ambos producen el mismo objeto de revisión —el par `(producto, familia)`— y admiten el mismo veredicto humano. Eso permite **un endpoint, una consulta, una tabla de veredictos y un parámetro de margen**, y hace que `apply_relative_veto` de C18a se reutilice casi tal cual.

### El tercer hallazgo: el criterio del huérfano hay que medirlo, y la medición desmintió la hipótesis de partida

La exploración entró con la hipótesis de que el umbral relativo se dispararía en cientos sobre 671 huérfanos, y que un criterio de **pureza de vecindad** (de los *k* vecinos más próximos, cuántos son de una misma familia) sería más seguro por estar acotado por construcción. **Medido el 2026-08-31 sobre el corpus real, es al revés:**

| | huérfanos | **A** · margen relativo > 0,02 | **B** · pureza ≥ 3 de 5 | A ∧ B |
|---|---|---|---|---|
| `data_origin = real` | 216 | **21** | 19 | 6 |
| `data_origin = synthetic` | 434 | **1** | **55** | 0 |
| **total** | **650** | **22** | **74** | **6** |

*(650 y no 671: 21 huérfanos tienen un `piece_type` del que ninguna familia existente es miembro, así que no pueden puntuar contra ninguna.)*

**A dispara 95 % sobre catálogo real; B dispara 74 % sobre sintético.** Y ese 74 % es precisamente la trampa que el `design.md` de C18a ya tenía escrita como el fallo del clustering puro por embedding: *«fracasa en el sintético, donde `v2`/`v3`/`v4`/`v5` son casi-duplicados deliberados»*. La lista de B lo confirma línea a línea — `Anillo Llama Eterna v3` → `Anillo llama eterna v2`, `Collar Vía Láctea v2` → `Collar via lactea`, `Anillo Orión v3` → `Anillo orion v2`. Son familias **distintas por construcción** de C06b, y B las nomina como miembros que faltan.

Curva del margen, para calibrar la cola: `θ = 0 → 40` · `θ = 0,02 → 22` · `θ = 0,05 → 5` · `θ = 0,08 → 3`.

### El cuarto hallazgo: la alerta no es sólo una lista de calidad, diagnostica el agrupador de C18a

Los primeros por margen no son ruido. Son hermanos de verdad que la fusión por material no vio, **y la causa es nombrable en cada caso**:

| Huérfano | Familia candidata | Margen | Por qué C18a no lo agrupó |
|---|---|---|---|
| `Pendientes botón erizo de mar S dorado` | `Pendientes boton erizo de mar` | 0,109 | **`dorado` no está en `materials`** de `enrichment/vocabularies.yaml` |
| `Colgante Lapa Mini Dorado` | `Colgante lapa` | 0,096 | ídem |
| `Colgante Estrella de Mar v2` | `Colgante estrella de mar` | 0,094 | sintético colado en familia real — es el hallazgo (d) del informe de C18a, y aquí la respuesta correcta es **descartar** |
| `Pendientes botón estrella de mar dorado` | `Pendientes boton estrella de mar` | 0,056 | **`dorado`** |
| `Colgante mejillón M plata y oro` | *(apunta a la familia equivocada)* | 0,047 | **`plata y oro` son dos materiales**; la fusión sólo admite uno |
| `Anillo pie Erizo XL` | `Anillo erizo de mar` | 0,047 | `pie` es un calificador que ni talla ni material contemplan |

Verificado en [`vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml): `materials.terms` incluye `baño de oro`, y `synonyms` mapea `chapado en oro` y `gold plated` hacia él. **`dorado` falta.** Y como el agrupador lee `name`, no `materials[]` del perfil, **añadir ese sinónimo recupera familias sin reenriquecer nada y sin salto de prompt** — a diferencia de la ampliación de `piece_type.terms`, que sí exige `enrichment/v2` y pertenece al change `fix-enrichment-vocabulary-gaps`.

### El quinto hallazgo: una familia contaminada es un imán, y por eso el orden interno importa

De los 25 primeros por margen, **cuatro apuntan a la misma familia**: `Colgante estrella de mar`, cuyo peor hermano es **0,778** cuando la media del corpus ronda 0,85–0,95. Es la familia que se comió un sintético. Como el criterio compara contra el peor hermano, **cuanto peor es una familia más huérfanos atrae**: `Colgante Ancla` entra con similitud 0,797 sólo porque el listón de esa familia está por los suelos.

Se resuelve con orden, no con lógica: **auditar los miembros primero** limpia la familia, sube su peor hermano y elimina cuatro falsos positivos sin escribir una línea. Las dos mitades del change se alimentan entre sí.

### El sexto hallazgo: la contención por el turno de migración ha caducado

El `design.md` de C18a rechazó persistir descartes con este argumento explícito: *«el turno de migración de EF Core es único y lo esperan C19, C27 y C29»*. **Ese argumento ya no se sostiene.** Con la anulación de la rama de C19 el 2026-08-31, el propio plan lo dice en su §12: *«De seis migraciones planificadas quedan cuatro: C19 y C29 se anularon, y las tres primeras ya están archivadas — la única viva es la de C27, y lleva corte pre-autorizado»*. La séptima migración hoy cuesta la migración y su test, no una negociación de turno.

---

## Alcance de esta historia (sí)

- **`POST /v1/families/audit`** en `jbg-ai` — **décima ruta del contrato congelado**, con modelos Pydantic propios y respuesta determinista bajo `STUB_MODE`. Devuelve en una sola llamada:
  - `flagged_members[]` — miembros de familias **persistidas** cuyo peor hermano es batido por un producto de otra familia, con el margen;
  - `orphan_candidates[]` — productos activos sin familia nominados por el **margen relativo** (criterio A), ordenados con la pureza de vecindad (criterio B) como señal secundaria, con la puerta de `piece_type` aplicada y **reportando `data_origin`**;
  - `rejected_groups[]` y `excluded_products[]` recalculados sobre el estado actual.
- **Reutilización de `jbg_ai.families`**: `veto.apply_relative_veto` y `repository.load_member_similarities` sirven al nuevo caso cambiando el universo de «familias propuestas» por «familias persistidas». No se declara ningún vocabulario nuevo (misma regla que D12 de C18a).
- **`materials.synonyms` += `dorado: baño de oro`** en `enrichment/vocabularies.yaml`, con **diff obligatorio de propuestas antes y después** para comprobar que no fusiona grupos que no debía ni dispara la guarda de raíz degenerada en sitios nuevos. Espejo en `frontend/src/lib/materials-vocabulary.ts` y su test de fijación.
- **Regeneración de `ai-service/openapi.json`** y actualización de `test_openapi_snapshot_is_stable`.
- **`IAiGatewayClient.AuditFamiliesAsync`** y sus DTOs en .NET.
- **`POST /api/ai/catalog/family-audit`** en `AiCatalogController`, sólo administradores.
- **`FamilyReviewVerdict`** — entidad nueva y **séptima migración de EF Core**: par `(ProductId, FamilyId)`, veredicto, revisor, instante, margen en el momento de revisar y nota opcional. Con FKs reales, de modo que borrar una familia se lleva sus veredictos en cascada.
- **`GET /api/product-families`** — listado paginado (máx. 50) con filtros por origen, tipo de pieza y «tiene marcados», que hoy **no existe**.
- **`DELETE /api/product-families/{id}`** — disolver una familia, que hoy **no existe**: vaciarla con `ReplaceMembers([])` deja una familia fantasma.
- **Carcasa de revisión en el frontend**, ruta de administrador, **primer inquilino de una superficie que C28 reutilizará**: tabla con navegación por teclado, confirmación en bloque, cronómetro por ítem y registro de qué cambió.
- **Ejecución de la revisión sobre las 156 familias**, ítem a ítem, más la cola de marcados y la de huérfanos.
- **Métrica del agrupador** para el README del Proyecto Final: tasa de corrección (cuántas de 156 alteró la persona) y tiempo medio de revisión, reportadas por `data_origin`.
- **Informe del lote** versionado en `Documentos/Proyecto Final AIEng/informes/c18b-family-review-report.md`.

### Ampliación del alcance, 2026-09-01: lo que el uso real destapó

Tres huecos que **no se veían leyendo el diseño** y aparecieron al ejecutar la revisión completa
de 58 decisiones sobre el corpus. Se añaden al change en lugar de dejarse como deuda para C28,
porque los tres afectan a lo que este change entrega y uno de ellos a la métrica del §16.

- **Aplicar el veredicto al catálogo.** Registrar un juicio no mueve una pertenencia, y la
  auditoría omite los pares juzgados a propósito, así que **siete decisiones se quedaron sin
  efecto y nada lo señalaba**. Lectura nueva de los veredictos con la acción pendiente calculada
  en el servidor, pestaña de aplicación, y ejecución por el camino de C07.
- **Corregir la etiqueta de variante de un miembro ya dentro.** No existía en la pantalla: las
  cuatro correcciones de la primera revisión hubo que aplicarlas por API a mano.
- **Persistir el tiempo por ítem.** El cronómetro vivía en estado de componente y **los tiempos de
  la primera sesión se perdieron al cerrar la pestaña**. Se guarda por juicio y la media se
  calcula desde lo guardado; sin tiempos medidos se informa la ausencia, nunca un cero.

Y una cuarta, aparecida al escribir el test de la métrica: **la población se captura al registrar**
(`SubjectWasMember`), porque un miembro rechazado que se saca de su familia queda indistinguible de
un candidato rechazado y derivarla del estado actual falla justo en los juicios ejecutados.

**Coste:** dos migraciones más sobre la misma tabla nueva. Aceptadas porque el change ya tiene el
turno y son columnas de su propia tabla.

## Fuera de alcance (no)

- **La pantalla de revisión de perfiles de enriquecimiento y su endpoint de métricas** — **C28**. C18b construye la carcasa; C28 es su segundo inquilino y aporta sus campos, su confianza por campo y su `source: rule|inferred`.
- **Ampliar `piece_type.terms`** con `diadema`, `gemelos`, `cinturon` y `llavero`, y el salto a `enrichment/v2` — es el change `fix-enrichment-vocabulary-gaps`, propuesto en el §0 del plan y **sin número asignado** (no confundir con **C20 `add-synonym-dictionary`**, que es un diccionario de sinónimos **de consulta**, en `retrieval/`, y no tiene relación). C18b sólo toca `materials.synonyms`, que no exige reenriquecimiento.
- **Reenriquecer producto alguno.** C18b no llama al extractor ni al proveedor de embeddings más allá de la reindexación que provoquen los cambios de pertenencia.
- **Cambiar el algoritmo de agrupación de C18a** más allá del sinónimo `dorado`: no se toca la fusión por material, ni la guarda de raíz degenerada, ni el rango canónico de tallas.
- **Persistir propuestas de `suggest`.** La decisión D3 de C18a sigue vigente: lo que se persiste es el **veredicto sobre un par (producto, familia)**, no una propuesta.
- **Reabrir `aiAvailable: false`**, `source-text/v1`, `embedding_version` ni `indexing/embeddings.py`.
- La agrupación por familia en la venta asistida (**C30**) y la confirmación de variante en la interfaz (**C36**).
- Escala métrica de longitud en el vocabulario de talla: **descartada el 2026-08-31** (`Cadena Barbara oro 40/42/45 cm` son tres cadenas distintas, no una pieza en tres tallas).

---

## Decisiones de diseño ya acordadas

Cerradas en la sesión de exploración del 2026-08-31, con medición sobre el corpus vivo.

| # | Decisión | Motivo |
|---|---|---|
| **D1** | **El alcance se reencuadra: auditar lo que existe, no pintar propuestas que ya no hay.** El objeto de la pantalla son las 156 familias persistidas, sus miembros marcados y los 671 huérfanos. El camino `suggest`/`apply` queda como vía residual para catálogo que entre después | Los tres números de la ficha están caducados y `suggest` devuelve vacío. Construirla literalmente entregaría una pantalla vacía, que es la firma que este proyecto persigue desde C17 |
| **D2** | **Python calcula, .NET conduce, y se mueve el contrato congelado a la décima ruta:** `POST /v1/families/audit`, con las dos listas en una sola respuesta | `.NET` **no mapea el esquema `ai`** (verificado: cero referencias en `Infrastructure/`) y los vectores son de Python. Extender `suggest` no ahorra nada —el snapshot compara el JSON entero y rompe igual— y mezclaría dos poblaciones disjuntas con cadencias distintas: `suggest` converge a vacío, la auditoría es señal permanente. Dos rutas separadas duplicarían el join más caro para una pantalla que muestra ambas listas. Lo autoriza la doctrina de `IAiGatewayClient` que ya ejerció C18a |
| **D3** | **El veredicto humano se persiste en .NET, en la entidad `FamilyReviewVerdict`, con la séptima migración de EF Core** | La contención por el turno **ha caducado**: anulados C19 y C29, sólo queda la de C27, y lleva corte pre-autorizado (§12 del plan). Una tabla en `ai` reintroduciría *«un estado paralelo a .NET que nada invalida y que envejece en silencio»* —el motivo por el que C18a rechazó esa alternativa—, porque `ai.product_document` es una **proyección** que se lapida y reconstruye, y una tabla a su lado no hereda ese ciclo de vida. Con FKs reales, borrar una familia se lleva sus veredictos |
| **D4** | **Lo que se descarta es el par `(producto, familia)`, no la propuesta** | Los tres objetos descartables no son equivalentes: una propuesta **no tiene clave estable** y hoy hay cero; un miembro marcado y un huérfano candidato **comparten clave** y son los que existen. Y esa misma fila **es el sello de aprobación por ítem** que la decisión 7 de C18a aplazó explícitamente a este change: una tabla responde a tres promesas de la ficha |
| **D5** | **Nomina el margen relativo (A); ordena la pureza de vecindad (B)** | Medido: A dispara 21 real / 1 sintético; B dispara 19 real / **55 sintético**. B camina directo a la trampa que el `design.md` de C18a documentó — los `vN` de C06b son familias distintas por construcción. Los 6 de la intersección A∧B son el núcleo de alta confianza y encabezan la lista |
| **D6** | **Primero la auditoría de miembros, después la de huérfanos** | `Colgante estrella de mar` tiene peor hermano **0,778** por estar contaminada, y atrae 4 de los 25 primeros por margen. Limpiarla sube el listón y elimina esos falsos positivos **sin lógica adicional**. Las dos mitades se alimentan |
| **D7** | **θ vive en configuración y se fija *después* de la auditoría de miembros**, arrancando generoso (`θ = 0`, 40 nominados) | Fijarlo ahora sería calibrarlo contra un defecto que el propio change va a arreglar (D6). Y con los veredictos persistidos, **un descarte se paga una vez**: un huérfano descartado no vuelve nunca, mientras que uno que θ dejó fuera no aparece jamás. La asimetría favorece la generosidad. Mismo patrón que `JPV_FAMILY_VETO_MARGIN`, que C24 barrerá con el golden set |
| **D8** | **Se reaprueban las 156 familias ítem a ítem**, no sólo las marcadas | Es lo que genera la métrica que el §16 del diseño exige y que **hoy no tiene ninguna evidencia detrás**: cero productos y cero familias han pasado por revisión humana real. Las 156 llevan `Origin = AiApproved` con aprobador e instante **de un lote que se disparó de una vez** |
| **D9** | **`dorado: baño de oro` entra en este change**, no en `fix-enrichment-vocabulary-gaps` | Es un **sinónimo de material**, y el agrupador lee `name`: recupera familias **sin reenriquecer y sin salto de prompt**. La ampliación de `piece_type.terms` sí exige ambas cosas y se queda en el otro change. Y sin el sinónimo, la alerta nominaría tres huérfanos cuya respuesta correcta no es «añádelo» sino «arregla el vocabulario» |
| **D10** | **Carcasa de revisión compartida; C18b primer inquilino, C28 segundo** | Ambos son *frontend + `Application/`*, sólo administrador, revisión por lotes de salida de IA, y **EP13 ya los agrupa**. 156 juicios seguidos exigen teclado y confirmación en bloque, que es literalmente lo que la ficha de C28 describe. Y las dos pantallas alimentan la misma tabla del README: corrección del **agrupador** y corrección del **extractor** |
| **D11** | **Dos caminos de escritura, y la pantalla declara cuál usa**: producto **sin** familia → `/api/ai/catalog/family-suggestions/apply` (C18a); producto **con** familia → `PUT /api/product-families/{id}/members` (C07) | Son contratos distintos con semánticas distintas. Y el segundo pisa la mina que el apply de C07 dejó anotada: el reemplazo declarativo falla si las altas se declaran añadiéndolas a la colección de navegación, y *«sólo se manifiesta cuando una misma petición borra e inserta a la vez»* — que es exactamente **mover un producto de una familia a otra** |
| **D12** | **Revisar no mueve el corpus; sólo lo mueve cambiar.** Confirmar una familia escribe una fila de veredicto y no toca `Product.UpdatedAt` ni el hash del documento | Desacopla «revisar las 156» de «mover el corpus»: probablemente se muevan una decena de documentos, no 486. Aun así el change va **antes de la línea base de C24**, por el mismo argumento que ordenó C18a: `preprocessing_id` sigue siendo `source-text/v1` y no delataría el cambio |
| **D13** | **La métrica del agrupador se versiona y va al README** | Precedente de C06a, C06b, C10, C12 y C18a. Es la evidencia del renglón *«métricas de revisión humana»* del §16, reportada por `PromptVersion` y `data_origin` como pide la disciplina que C24 ya aplica |

### Parámetros y recortes fijados el 2026-08-31

Cerrados confirmando la opción por defecto de las seis preguntas abiertas del ticket. Ninguno bloquea el apply.

| # | Decisión | Motivo |
|---|---|---|
| **D14** | **`dorado` es sinónimo de `baño de oro`**, no de `oro` | El catálogo vende `Colgante Erizo S oro` y `Colgante dorado erizo de mar S` por separado, luego la tienda los distingue. La hipótesis es **falsable**: si el mapeo estuviera mal, el grupo aparecería rechazado por `duplicate_variant_labels` en vez de fusionarse, y el diff lo enseñaría |
| **D15** | **Se acepta la etiqueta canónica `baño de oro`** aunque el dependiente diga `dorado` | La spec viva lo exige en el eje de material y su motivo sigue vigente: dos grafías darían dos etiquetas para la misma cosa, un par que **pasa la guarda de unicidad —compara etiquetas, no significados— y llega a la vitrina como dos variantes indistinguibles**. Se anota como limitación en el informe |
| **D16** | **Un veredicto no se invalida solo** cuando el producto se reenriquece o se reembebe | Se guarda `MarginAtReview` y se muestra junto al actual —*«revisado el T con margen 0,16; hoy 0,31»*— en lugar de una lógica de reaparición que nadie mantendría. El dato para juzgar si el veredicto envejeció queda delante de quien lo revisa |
| **D17** | **`JPV_FAMILY_ORPHAN_MARGIN` se fija tras la auditoría de miembros**, arrancando en `0` | Fijarlo antes sería calibrarlo contra el imán que el propio change arregla (D6). Y con veredictos persistidos **un descarte se paga una vez**, mientras que un huérfano que el margen dejó fuera no aparece jamás: la asimetría favorece la generosidad |
| **D18** | **El registro de veredictos es endpoint propio**, no un modo de la auditoría | Auditar es lectura y no debe escribir nunca — la misma separación que C18a impuso entre `suggest` y `apply`. El escenario 1, que exige que la auditoría no toque nada, sólo es verificable si el camino de escritura es otro |
| **D19** | **De la carcasa se extrae sólo lo que la ficha de C28 pide por escrito** | Diseñar para dos inquilinos con uno a la vista produce abstracciones equivocadas. Lo especificado se comparte; lo conjeturado, no. Si C28 necesita más, lo extrae C28, que es cuando se sabrá qué |
| **D20** | ~~El comportamiento con `jbg-ai` caído sale de alcance~~ → **revisada el 2026-08-31: entra en alcance.** La pantalla **debe distinguir** «el servicio no contestó» de «no hay nada que revisar», con escenario de aceptación y test | El recorte inicial dejaba el requisito en el cliente .NET —que sí debe distinguir los dos casos— pero no en la superficie que la persona mira, y ahí el cliente no basta: una lista vacía pintada sin más **es** la respuesta equivocada, la distinga o no la capa de debajo. Es además la forma exacta en que se materializó el riesgo de C17, donde la búsqueda devolvía diez resultados plausibles por el camino léxico sin decir que la asistencia estaba apagada. Y aquí el daño sería peor: sobre una pantalla de calidad de catálogo, «no hay nada que revisar» se lee como **«el catálogo está limpio»** |

---

## Criterios de Aceptación

### Escenario 1: La auditoría lee las familias existentes y no escribe nada

- **Dado que** existen 156 familias con 486 miembros y 682 productos activos sin familia
- **Cuando** un administrador solicita la auditoría de familias
- **Entonces** la respuesta contiene los miembros marcados con su margen, los huérfanos candidatos con la familia a la que se parecen, los grupos rechazados por la guarda y los productos excluidos por la puerta de `piece_type`
- **Y** no se crea, modifica ni elimina ninguna familia, ninguna pertenencia ni ningún veredicto
- **Y** ningún `Product.UpdatedAt` cambia

### Escenario 2: El miembro marcado se calcula sobre familias persistidas, no propuestas

- **Dado que** un producto pertenece a una familia y un producto de **otra** familia está más cerca de él que su propio peor hermano, por más del margen configurado
- **Cuando** se solicita la auditoría
- **Entonces** ese miembro aparece marcado, con el margen por el que el extraño ganó y la identidad del extraño
- **Y** el miembro **no** se elimina de su familia
- **Y** la marca se produce aunque el producto no aparezca en ninguna respuesta de `suggest`, porque ya pertenece a una familia

### Escenario 3: El huérfano se nomina por margen relativo y nunca por umbral absoluto

- **Dado que** un producto activo sin familia comparte tipo de pieza con los miembros de una familia F y está más cerca de ellos que el peor hermano de F, por más del margen
- **Cuando** se solicita la auditoría
- **Entonces** aparece como candidato a F, con la similitud, el peor hermano de F y el margen
- **Y** un producto con similitud alta en términos absolutos pero que no bate el peor hermano de ninguna familia **no** aparece
- **Y** el margen se lee de configuración: cambiarlo altera el resultado sin tocar código

### Escenario 4: La puerta de tipo de pieza y el origen del dato se respetan en la alerta

- **Dado que** el catálogo contiene 434 huérfanos sintéticos y 216 reales
- **Cuando** se solicita la auditoría
- **Entonces** ningún huérfano se propone para una familia de un tipo de pieza distinto al suyo
- **Y** un producto sin `piece_type` no se propone para ninguna familia
- **Y** cada candidato informa de su `data_origin`, de modo que las dos poblaciones pueden contarse por separado

### Escenario 5: Confirmar una familia la registra como revisada y no mueve el corpus

- **Dado que** una familia aprobada por lotes en C18a no ha sido revisada por nadie
- **Cuando** el administrador la confirma sin cambiar nada
- **Entonces** queda registrado el veredicto por cada par `(producto, familia)`, con el revisor, el instante y el margen en el momento de revisar
- **Y** ni `Product.UpdatedAt` ni el hash del documento cambian
- **Y** una sincronización incremental posterior no emite ninguno de esos productos

### Escenario 6: Un descarte se recuerda y no reaparece

- **Dado que** el administrador descartó a un huérfano como candidato de una familia
- **Cuando** se solicita la auditoría de nuevo
- **Entonces** ese par `(producto, familia)` no vuelve a aparecer en la lista de candidatos
- **Y** el mismo producto sí puede aparecer como candidato de **otra** familia distinta
- **Y** el descarte sobrevive al cierre de sesión y a un cambio de navegador

### Escenario 7: Sacar un miembro de una familia sí mueve el corpus, y el índice lo ve sin sincronización completa

- **Dado que** un miembro marcado no pertenece realmente a su familia
- **Cuando** el administrador lo saca a través de la pantalla
- **Entonces** la pertenencia se elimina mediante `ProductFamilyService`, nunca por SQL directo
- **Y** el `Product.UpdatedAt` de ese producto queda estampado
- **Y** una sincronización **incremental** desde un cursor anterior emite exactamente ese producto y ninguno más
- **Y** su documento pierde las líneas `Familia:` y `Variante:`

### Escenario 8: Disolver una familia no deja fantasmas

- **Dado que** una familia agrupa productos que no son la misma pieza
- **Cuando** el administrador la disuelve
- **Entonces** la familia deja de existir, no queda como familia sin miembros
- **Y** sus productos pasan a no pertenecer a ninguna familia y quedan libres para asignarse
- **Y** los veredictos registrados contra esa familia desaparecen con ella
- **Y** el índice deja de emitir `family_id` para esos productos tras una sincronización incremental

### Escenario 9: El sinónimo de material recupera familias y su efecto se comprueba, no se supone

- **Dado que** `dorado` no figuraba en el vocabulario de materiales y `Pendientes botón erizo de mar S dorado` quedó huérfano
- **Cuando** se añade `dorado` como sinónimo de `baño de oro` y se vuelven a solicitar propuestas
- **Entonces** ese producto se propone como miembro de `Pendientes boton erizo de mar`
- **Y** el diff completo de propuestas antes y después queda registrado en el informe, no sólo el caso buscado
- **Y** ninguna raíz que antes formaba familia queda degradada al tipo de pieza pelado por el nuevo token

### Escenario 10: Un operador no puede auditar ni emitir veredictos

- **Dado que** un usuario con rol Operador está autenticado
- **Cuando** invoca la auditoría, el listado de familias, el borrado de una familia o el registro de un veredicto
- **Entonces** la petición se rechaza con 403 Forbidden
- **Y** no se crea, modifica ni elimina ningún dato
- **Y** un usuario no autenticado recibe 401 Unauthorized

### Escenario 11: El servicio de IA no responde y la pantalla no lo presenta como catálogo limpio

- **Dado que** `jbg-ai` no está disponible o el circuito está abierto
- **Cuando** el administrador abre la pantalla de revisión
- **Entonces** las listas que dependen de vectores —miembros marcados y huérfanos candidatos— se declaran **no disponibles** de forma explícita
- **Y** ese estado se distingue visualmente de la lista que sí se pudo calcular y salió vacía
- **Y** la revisión de las familias existentes sigue siendo posible, porque no necesita vectores
- **Y** en ningún caso se presenta una lista vacía como si significara «no hay nada que revisar»

### Escenario 12: Fuera de alcance explícito

- **Dado que** esta historia entrega la carcasa de revisión
- **Cuando** se completa
- **Entonces** la revisión de perfiles de enriquecimiento, su confianza por campo y su endpoint de métricas **no** están implementados: son **C28**, segundo inquilino de la misma carcasa
- **Y** `piece_type.terms` no se amplía y ningún producto se reenriquece: eso es `fix-enrichment-vocabulary-gaps`
- **Y** la agrupación por familia en la venta asistida (C30) y la confirmación de variante en la interfaz (C36) siguen sin implementarse

---

## Notas adicionales

- **Actor:** Administrador. Los operadores no participan: la familia es dato de catálogo y su lectura ya está abierta a cualquier usuario autenticado desde C07, sin filtrar por punto de venta.
- **Volumen de revisión esperado:** 156 familias a reaprobar, más los miembros que la auditoría marque, más 22–40 huérfanos según θ. La cola de huérfanos es entre el 12 % y el 20 % de la carga; **el grueso son las 156**, y esa proporción es lo que hace razonable arrancar generoso con θ (D7).
- **El cuello de botella es de atención, no de calendario.** El §7.8 del diseño lo corrigió el 2026-08-31: *«es una sola persona revisando»*. El riesgo real no es tardar, es que revisar degenere en dar al botón — que es exactamente el fallo que el mecanismo existe para evitar. De ahí que la carcasa lleve cronómetro por ítem: el tiempo medio es a la vez métrica de entrega y señal de que la revisión sigue siendo real.
- **Limitación conocida:** un veredicto no se invalida solo cuando la evidencia cambia. Si un producto se reenriquece o se reembebe, su vecindad cambia y un descarte antiguo puede quedar obsoleto. Se mitiga guardando el **margen en el momento de revisar** y mostrando la comparación con el actual, en lugar de inventar una lógica de reaparición automática que nadie va a mantener.
- **Limitación conocida:** los 21 huérfanos cuyo `piece_type` no tiene ninguna familia existente no pueden puntuar contra nada y quedan fuera de la alerta por construcción. No es un defecto: no hay familia a la que pertenecer.
- **Tres estados que la pantalla no puede confundir**, y que es lo que D20 exige tras revisarse: *(1)* la lista se calculó y salió vacía; *(2)* el servicio no contestó, así que no se sabe; *(3)* la lista se calculó y tiene contenido. El segundo pintado como el primero es el fallo de C17 repetido, y sobre una pantalla de calidad de catálogo se lee como «el catálogo está limpio». La revisión de familias no depende de vectores y sigue disponible en el estado *(2)*.
- **Divergencia heredada, sin resolver aquí:** la spec viva `product-family` justifica la distinción con las colecciones diciendo que un producto puede pertenecer *«to one of many unrelated collections»*, pero [`Product.cs:31`](../../../backend/src/JoiabagurPV.Domain/Entities/Product.cs#L31) declara `Guid? CollectionId`, una FK única y anulable: ambas cardinalidades son 0..1. Los discriminadores reales, medidos: una colección abarca 1–154 productos (mediana 15) y 13–16 tipos de pieza; una familia, 2–4 de un solo tipo.
- **Change asociado:** [`add-family-review-ui-and-orphan-alert`](../../../openspec/changes/add-family-review-ui-and-orphan-alert/), rama `c18b-add-family-review-ui-and-orphan-alert`, creada desde `ai-eng` en `6ffd390`.

---

## Referencias

- Ticket técnico: [T-AIENG-018b](../../../openspec/changes/add-family-review-ui-and-orphan-alert/ticket.md)
- Épica: [EP13 — Familias de Producto y Desambiguación de Variantes](../../epicas.md)
- Diseño: [`proyecto-final-diseno-rag-joiabagur.md`](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) §7.5 (flujo mixto y alerta de huérfanos), §7.8 (revisión híbrida y vía revisada), §11.5 (métricas del enriquecimiento), §16 (checklist de entrega)
- Plan: [`proyecto-final-plan-changes-openspec.md`](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md), ficha C18b, §0 (partición de C18 y anulación de la rama de C19), §12 (turno de migración)
- Historia anterior: [HU-AIENG-018a](HU-AIENG-018a.md) · Informe del lote: [`informes/c18a-family-suggestion-report.md`](../../Proyecto%20Final%20AIEng/informes/c18a-family-suggestion-report.md)
- Decisiones previas: [`2026-08-31-add-family-suggestion-and-approval/design.md`](../../../openspec/changes/archive/2026-08-31-add-family-suggestion-and-approval/design.md) (decisiones 1, 3, 4, 7, 9 y 10), [`2026-08-17-add-product-family-entity/design.md`](../../../openspec/changes/archive/2026-08-17-add-product-family-entity/design.md) (reserva de columnas y trampa del reemplazo declarativo)
- Specs vivas: [`family-suggestion`](../../../openspec/specs/family-suggestion/spec.md), [`product-family`](../../../openspec/specs/product-family/spec.md), [`ai-service-api-contracts`](../../../openspec/specs/ai-service-api-contracts/spec.md), [`ai-gateway-client`](../../../openspec/specs/ai-gateway-client/spec.md), [`ai-vector-schema`](../../../openspec/specs/ai-vector-schema/spec.md), [`index-feed`](../../../openspec/specs/index-feed/spec.md)
- Historias relacionadas: [HU-AIENG-007](HU-AIENG-007.md) (entidad de familia), [HU-AIENG-016](HU-AIENG-016.md) (patrón de panel asistido en frontend), [HU-AIENG-017](HU-AIENG-017.md) (tarjeta de estado de IA para administrador)
- Frontend: [`analisis-metronic-frontend.md`](../../Propuestas/analisis-metronic-frontend.md) — componentes reutilizables antes de proponer UI nueva
- Apuntes del máster: `Sesiones Master AIEng/S11_RAG_avanzado/`, `S08_BBDD_Vectoriales/`, `S16_Produccion_II/`

---

## Tareas

1. Completar los artefactos OpenSpec del change: `proposal`, **`design.md`** —hay decisión con alternativas reales y medición para resolverlas—, specs delta y `tasks`.
2. **Medir el efecto de `dorado`** antes de nada: añadir el sinónimo, re-ejecutar `suggest` y **diffear las propuestas completas** contra el estado actual. Si degrada alguna raíz existente, se revierte y el caso se documenta.
3. **Extender `jbg_ai.families`** al caso de familias persistidas: cargar pertenencias reales, calcular peor hermano por familia y mejor extraño por miembro, y nominar huérfanos por margen relativo con la puerta de `piece_type`, ordenando con la pureza de vecindad.
4. **`POST /v1/families/audit`**: router, modelos Pydantic, respuesta determinista bajo `STUB_MODE`, exclusión de los pares ya juzgados que .NET envía en la petición.
5. **Regenerar `ai-service/openapi.json`** con la orden del README y actualizar `test_openapi_snapshot_is_stable`.
6. **`IAiGatewayClient.AuditFamiliesAsync`** y sus DTOs en `JoiabagurPV.Application`.
7. **`FamilyReviewVerdict`**: entidad, configuración EF, **séptima migración**, índice único por par `(ProductId, FamilyId)` y borrado en cascada desde la familia. Test de desfase modelo↔migración con el arnés de C04.
8. **`GET /api/product-families`** paginado con filtros, y **`DELETE /api/product-families/{id}`**, ambos sólo administradores, con FluentValidation.
9. **`POST /api/ai/catalog/family-audit`** en `AiCatalogController`, con el manejo de `AiNotImplementedException` / `AiUnavailableException` establecido por C09, y el endpoint de registro de veredictos.
10. **Carcasa de revisión en frontend**: ruta de administrador, servicio `family-review.service.ts`, tipos de los DTOs, tabla con TanStack Table, navegación por teclado, confirmación en bloque, cronómetro por ítem, y estados que distinguen «no disponible» de «vacío» (D20). Reutilizar componentes de [`analisis-metronic-frontend.md`](../../Propuestas/analisis-metronic-frontend.md) antes de crear ninguno.
11. **Ejecutar la revisión**: primero los miembros marcados (D6), después fijar θ sobre números recalculados (D7), después los huérfanos, y las 156 familias ítem a ítem (D8).
12. **Sincronización incremental** tras los cambios de pertenencia, verificando que se emiten exactamente los productos estampados y ninguno más.
13. **Informe del lote** en [`informes/c18b-family-review-report.md`](../../Proyecto%20Final%20AIEng/informes/) con la tasa de corrección del agrupador, el tiempo medio de revisión, el reparto por `data_origin` y el diff del sinónimo `dorado` (D13).
14. ~~**Actualizar la ficha C18b del plan**~~ — **hecho el 2026-08-31, antes de abrir el change.** Ficha reescrita, marcada 🗄️, zona corregida a *Python + .NET + frontend*, entrada fechada en el §0, fila de la tabla maestra, recuento de migraciones (de cuatro a cinco), lista de pares que no se abren a la vez, y la nota del §6 que daba C18b por recortable sin efectos.
15. Enlazar la HU en [`Documentos/epicas.md`](../../epicas.md) (EP13) y actualizar `Documentos/modelo-de-datos.md` con la entidad nueva.
16. `openspec validate --all --strict` en verde antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 4 — es el **segundo caso de intervención humana del Proyecto Final** y hoy el único que puede producir evidencia: cero productos y cero familias han pasado por una revisión real. Sin él, el renglón *«métricas de revisión humana»* del §16 no tiene nada detrás, y las 156 familias siguen siendo una aprobación en bloque que nadie miró. Además es la única señal de calidad que detecta que el agrupador de C18a se dejó miembros fuera.
- **Urgencia (mercado / feedback):** 3 — es **hoja del grafo**, ningún change depende de él, y por eso no tapona nada. Pero cambia pertenencias, así que arrastra la restricción de orden de C18a: **antes de la línea base de C24**. El volumen de corpus movido es pequeño (D12), lo que hace la restricción barata de cumplir.
- **Complejidad / esfuerzo:** 4 — cuatro superficies (librería Python, ruta HTTP, tres endpoints .NET más migración, y la carcasa de frontend), la primera migración de EF Core desde C08, y la primera pantalla de administración construida para ser reutilizada por otro change.
- **Riesgos y dependencias:**
  - **Construir la ficha literalmente entrega una pantalla vacía.** Es el riesgo principal y es el que motiva el reencuadre. **Mitigado por D1**, y verificable: el escenario 1 exige que la auditoría devuelva las listas sobre 156 familias y 671 huérfanos reales, no sobre propuestas.
  - **La alerta de huérfanos puede degenerar en vertedero.** Es lo que ocurrió con el veto `mediana − k·MAD` de C18a, que disparaba al 16,9 %. **Mitigado por D5**, que elige el criterio con medición y no con argumentos, y por D7, que deja θ en configuración.
  - **Una familia contaminada atrae falsos positivos.** Medido: `Colgante estrella de mar`, con peor hermano 0,778, se lleva 4 de los 25 primeros. **Mitigado por D6** con orden, no con lógica.
  - **Mover un producto de una familia a otra pisa la trampa documentada de C07**: el reemplazo declarativo falla cuando una misma petición borra e inserta. **Mitigado** declarando los miembros por identificador y no añadiéndolos a la colección de navegación, y con un test que reordena e intercambia etiquetas.
  - **La séptima migración.** Ya no compite por turno (§12 del plan), pero es la primera desde C08 y paga el arnés de desfase modelo↔migración. **Mitigado** porque ese arnés existe desde C04 y lo heredaron C07 y C08.
  - **Mover el contrato congelado a diez rutas** rompe `test_openapi_snapshot_is_stable`. Deliberado, autorizado por la doctrina de `IAiGatewayClient` y regenerado en el mismo change. Trabajando en solitario, el acuerdo con «quien posee el cliente .NET» que pide `CLAUDE.md` es una nota, no un bloqueo.
  - **El sinónimo `dorado` puede fusionar de más.** Reconocer un token de material afecta a todos los nombres, no sólo a los tres buscados. **Mitigado por la tarea 2**, que exige el diff completo de propuestas antes de aceptarlo, y por el escenario 9.
  - **Diseñar la carcasa para dos inquilinos con uno solo a la vista** puede producir una abstracción equivocada. **Mitigado** entregando C18b como pantalla concreta y extrayendo lo común sólo donde C28 lo pide por escrito en su ficha —tabla editable, atajos de teclado, aprobación masiva por campo, registro de quién revisó y qué cambió—, que es lo que ya está especificado y no conjeturado.
  - **La revisión de 156 familias puede degenerar en dar al botón.** Es el fallo que el mecanismo existe para evitar. **Mitigado** por el cronómetro por ítem, cuya lectura hace visible el problema en la propia métrica de entrega.
