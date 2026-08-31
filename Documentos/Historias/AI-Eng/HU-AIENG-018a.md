# HU-AIENG-018a: Propuesta asistida de familias de producto y aprobación por lotes

## Formato estándar

Como **Administrador del catálogo**, quiero **que el sistema me proponga qué productos son la misma pieza en varias variantes y poder aprobar esas agrupaciones en bloque**, **para** **que las ~155 familias del catálogo existan de verdad sin crearlas a mano una por una, y para que la búsqueda, los avisos de venta y la desambiguación de variante dejen de operar sobre un campo que hoy está vacío en los 1.200 productos**.

---

## Descripción

Change OpenSpec `add-family-suggestion-and-approval` / **C18a**, épica **EP13 — Familias de Producto y Desambiguación de Variantes**. Marcado 🟢 en el plan, **sin migración de EF Core**. Prerrequisitos: **C07** (`add-product-family-entity`, archivado el 2026-08-17) y **C13** (`add-product-document-indexer`, archivado el 2026-08-26), ambos hechos.

Esta historia es **la primera mitad de C18**, partido en la sesión de exploración del 2026-08-30/31 según la regla 5 del plan (*«si un change se desborda de la sesión, se parte, y se entrega primero la mitad que desbloquea»*). C18a entrega el motor y el camino de escritura; **C18b** entrega la pantalla de revisión por lotes y la alerta de huérfanos.

### El hallazgo que gobierna la historia: la tubería está construida entera y vacía

C07, C12 y C13 dejaron el camino de familias completo de punta a punta —entidad con índice único de pertenencia excluyente, cinco endpoints de administración, emisión de `familyId` / `familyName` / `variantLabel` en el feed de indexación, mapeo en el indexador, columna `family_id` con índice B-tree en `ai.product_document`, y los campos `family_id` / `variant_label` / `family_match` en el contrato de recuperación desde C02—. **Y no hay una sola fila.** Verificado el 2026-08-30 contra el Postgres local:

| Tabla | Filas |
|---|---|
| `Products` / `ProductAiProfiles` / `ai.product_document` | 1.200 / 1.200 / 1.200 |
| documentos con `embedding` | 1.200 |
| **`ProductFamilies` / `ProductFamilyMembers`** | **0 / 0** |
| **documentos con `family_id`** | **0** |

C06b lo dejó escrito a propósito —*«el catálogo híbrido nace sin filas de miembro»*— y el `qa.md` de C07 lo anotó igual: *«La reserva para C18 no está ejercida. `Origin` se escribe siempre como `Manual`; `ApprovedByUserId` y `ApprovedAt` no tienen hoy ningún camino de escritura»*. **C18a no construye tubería: construye las filas.**

Cuatro changes dependen de que existan, y ninguno lo dice en el grafo del plan:

| Change | Test que hoy pasaría en vacío |
|---|---|
| C25 `add-business-signals-ranking` 🔴 | `test_ambiguous_variant_penalty_applies_only_within_family` |
| C26 `add-substitutes-retrieval` | `test_same_family_variant_ranks_first_when_available` |
| **C30** `add-assist-generation-with-rule-warnings` 🔴 *(nunca se recorta)* | `test_variants_grouped_by_family_id` |
| **C36** `add-frontend-assist-card-and-family-disambiguation` 🔴 *(nunca se recorta)* | `should require variant confirmation when family has multiple members` |

El plan se contradice: declara irrecortables dos changes cuya mitad de familia queda vacía si C18 no se hace, y a C18 no lo declara irrecortable. La corrección va en las tareas de esta historia.

Y C16 ya pinta la talla **sólo cuando `variantLabel` existe** — el hueco está reservado en la interfaz desde el 2026-08-29 y nunca se ha llenado.

### El segundo hallazgo: C18a mueve el 30 % del corpus, y nada avisará de ello

`build_source_text` ([`source_text.py:78`](../../../ai-service/src/jbg_ai/indexing/source_text.py#L78)) emite dos líneas que hoy están ausentes en los 1.200 documentos:

```
Talla: L
Familia: ————  vacía en 1200/1200      ◀── C18a la llena en ~358
Variante: ————  vacía en 1200/1200     ◀── C18a la llena en ~358
```

La spec viva `product-document-indexer` es explícita: *«A change that alters canonical `doc_text` (including a `family_name` rename) MUST change the hash and MUST call embed»*. Es decir: **~358 documentos cambian de texto, de hash y de vector.**

Lo delicado no es el reindexado —el indexador lo hace bien— sino que **no queda marcado**. La columna que S11 (*Reindexación y versionado de embeddings*) prescribe para distinguir corpus incomparables existe y está bien construida desde C05/C13:

```
ai.product_document.embedding_version = "openai/text-embedding-3-small:1536:source-text/v1"
                                          └ modelo ┘ └dims┘ └ preprocessing_id ┘
```

Pero **C18a cambia el contenido, no el preprocesado**: el corpus anterior y el posterior llevarán la **misma cadena**. Es la firma que la propia sesión describe —*«la deriva no grita, susurra»*—, trasladada de la recuperación a la evaluación: si C24 midiera su línea base antes de C18a y C25 produjera la tabla de ablations después, las filas compararían corpus distintos sin que nada lo señalase.

De ahí la consecuencia de orden que esta historia arrastra: **C18a debe ejecutarse antes que cualquier change que mida** (C20, C21, C24), y debe escribir **todas** las familias de una vez para que el corpus se mueva **una sola vez**.

### El tercer hallazgo: el mecanismo que el diseño prescribe no funciona tal como está escrito

El §7.5 del diseño dice *«agrupa candidatos por similitud de embedding (**umbral alto**) + mismo `piece_type` + raíz común de nombre»*. Medido sobre los 1.200 vectores reales, **ningún umbral absoluto separa las dos poblaciones**:

| | peor hermano *(hay que incluirlo)* | mejor extraño *(hay que excluirlo)* |
|---|---|---|
| real | 0,847 – 0,920 | 0,867 – **0,936** |
| sintético | 0,896 – 0,948 | 0,845 – **0,945** |

Dos casos concretos:

- **`Anillo Bruma grapas {amatista, citrino, granate, peridoto, topacio}`** — familia real, coseno interno 0,895–0,946. El vecino no perteneciente, `Anillo Bruma bata plata y oro + piedra`, puntúa **0,926**: por encima del peor hermano.
- **`Anillo Aurora Boreal S/M/L/XL` vs `Anillo Aurora Boreal v2 S/M/L/XL`** — dos familias distintas por construcción, máximo cruzado **0,9445**, contra un mínimo intra-familia de 0,9497. **Cinco milésimas.**

Pero en **relativo** el embedding es excelente: el vecino más próximo es hermano en **96,2 %** (50/52) de los miembros reales y **99,7 %** (305/306) de los sintéticos, y sólo **6 productos de 358 (1,7 %)** tienen un extraño más cerca que su peor hermano.

**Conclusión adoptada: la raíz del nombre agrupa, el embedding veta.** Es la inversión del enunciado del §7.5, y ese 1,7 % irreducible es lo que justifica —con un número, no con una afirmación— que exista revisión humana.

### El cuarto hallazgo: el vocabulario de variante, y por qué no se separan los ejes

El catálogo real y el sintético no expresan las variantes igual. Descomponiendo las familias candidatas por **qué eje las separa**:

| | REAL (~68 fam) | SINTÉTICO (87 fam) |
|---|---|---|
| solo eje **talla** | 33 (49 %) | 87 (100 %) |
| solo eje **material** | 28 (41 %) | 0 |
| **rejilla talla × material** | **3 (4 %)** | 0 |
| sin eje detectado *(pieza base sin token)* | 4 (6 %) | 0 |

**El 90 % de las familias tiene un solo eje y por tanto una etiqueta limpia.** Separar `variant_label` en dos columnas (`SizeLabel` + `MaterialLabel`) costaría una migración de EF Core —la *séptima*, que el `design.md` de C07 se gastó tres columnas nulables en evitar— más un cambio en la plantilla `source-text/v1` que elevaría el `preprocessing_id` a `v2` y forzaría **reindexar los 1.200**, no los 358. **Ganancia: representación limpia para 3 familias de 155.** Se descarta por relación coste/beneficio.

Y sobre las escalas de talla (`XS/S/M/L/XL` frente a `mini/pequeño/mediano/grande`), la decisión es **separar orden de etiqueta**: la etiqueta se guarda **literal** —`mini` no es `XS`; es la palabra del taller y la que el operador dice al cliente—, y el orden se calcula con un **rango canónico interno** que alimenta el `Position` que C07 ya persiste e indexa. Sólo 2 familias mezclan ambas escalas, y van a la cola de revisión en lugar de a una regla.

### El quinto hallazgo: la guarda de raíz degenerada detecta que hay servicios en el catálogo

Al quitar material y talla, seis raíces colapsan hasta quedar en el tipo de pieza pelado. Al mirarlas, tres **no son productos**:

```
[presion]   Presión Oro / Presión plata      ← componente, no pieza
[encargos]  Encargos plata / Encargos Oro    ← SERVICIO del taller
[arreglos]  Arreglos plata / Arreglos oro    ← SERVICIO del taller
[cadena]    Cadena plata / Cadena oro        ← genérico
[alianzas]  Alianzas Plata / Alianzas oro    ← ¿familia legítima?
[anillo]    Anillo plata S/M/L/XL            ← familia legítima, rota por el stripping
```

Ese último caso obliga a un ajuste del algoritmo: **`Anillo plata S/M/L/XL` tiene raíz correcta (`anillo plata`) si sólo se quita la talla, y degenera si además se quita el material.** Por eso el material **no se elimina globalmente**, sino que se usa para **fusionar** grupos ya formados. Los otros cinco casos van a la cola de revisión de C18b como incidencia de calidad del catálogo.

---

## Alcance de esta historia (sí)

- **Librería de agrupamiento en Python**, determinista, sin LLM y sin llamadas de red, en `ai-service/src/jbg_ai/families/`:
  - normalización de raíz (*casefold*, sin acentos, puntuación y espacios colapsados);
  - agrupación **L2** por raíz tras retirar el sufijo de talla (latino y en palabra);
  - **fusión** de grupos cuyas raíces difieran en exactamente un token de material;
  - **guardas**: no fusionar si la raíz resultante queda en el tipo de pieza pelado o por debajo de dos tokens;
  - puerta de `piece_type`: nunca se agrupa a través de tipos de pieza, y **un `piece_type` nulo no agrupa con ninguno** — el nulo es valor propio de la puerta, no comodín;
  - **veto relativo por embedding** sobre los candidatos ya formados — el miembro cuyo coseno al centroide cae por debajo de `mediana − k·MAD` **se marca para revisión, no se elimina**. **`k = 2` sobre los 5 vecinos más próximos, y ambos en configuración, nunca en el código**;
  - **reutilización de los vocabularios cerrados de [`enrichment/vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml)** (materiales, talla en sus dos escalas, tipo de pieza) y de su `fold()`, sin declarar ninguna lista nueva (D12 revisada);
  - **rango canónico de tallas**, lo único que el vocabulario no puede aportar porque su lista está agrupada por escala y no ordenada por magnitud (D12b);
  - detección de `variant_label` como el fragmento retirado, **verbatim normalizado**;
  - `position` por **rango canónico interno** de tallas, nunca persistido como etiqueta.
- **`POST /v1/families/suggest`** en `jbg-ai`: novena ruta del contrato, con modelos Pydantic propios, respuesta determinista bajo `STUB_MODE`, y **excluyendo los productos que ya pertenecen a una familia** para que el flujo converja al repetirse.
- **Regeneración de `ai-service/openapi.json`** y del test de deriva.
- **`IAiGatewayClient.SuggestFamiliesAsync`** en .NET, con sus DTOs.
- **`POST /api/ai/catalog/family-suggestions`** (sólo administradores) que devuelve propuestas **sin escribir nada**, y **`POST /api/ai/catalog/family-suggestions/apply`** que recibe de vuelta el subconjunto aceptado y lo persiste.
- **Escritura a través de `ProductFamilyService`**, nunca por SQL directo, con `Origin = AiApproved`, `ApprovedByUserId` y `ApprovedAt` — **la reserva de C07 se ejerce por primera vez**.
- **Ejecución del lote** sobre el corpus real: ~155 familias, ~450 miembros.
- **Sincronización incremental** (`POST /v1/index/sync` sin `full`) y verificación de que el índice ve las familias.
- **Reestructuración del plan de changes** al orden C18a → C19 → C18b, y **nota de la divergencia spec/código en `Product.CollectionId`**.

## Fuera de alcance (no)

- **La pantalla de revisión por lotes** y el sello de aprobación por ítem — **C18b**.
- **La alerta de huérfanos** — **C18b**: necesita familias ya existentes, es intrínsecamente una segunda pasada.
- **Persistencia de propuestas** y lista de descartes: `apply` devuelve lo aceptado, así que no hay estado que envejecer ni tabla que crear.
- **Cualquier migración de EF Core.** C18a no ocupa el turno único, que queda libre para C19.
- Separar `variant_label` en dos columnas; cambiar `source-text/v1`; regenerar los 1.200 embeddings.
- La agrupación por familia en la venta asistida (C30) y la confirmación de variante en la interfaz (C36).
- El bloqueo o la corrección de las entradas de catálogo que no son productos (`Encargos`, `Arreglos`, `Presión`): se **listan**, no se tocan.
- `IsSupplySource` y las señales de demanda — **C19**.

---

## Decisiones de diseño ya acordadas

| # | Decisión | Motivo |
|---|---|---|
| **D1** | **.NET conduce, Python calcula.** El administrador llama a .NET, .NET llama a `jbg-ai` con su JWT, y .NET persiste | [`ProductFamilyService.cs:201`](../../../backend/src/JoiabagurPV.Application/Services/ProductFamilyService.cs#L201) estampa `Product.UpdatedAt` de los productos que entran y salen. **Escribir por SQL directo desde Python no lo estampa, y entonces el feed incremental nunca emite esos 358 productos** — sin un solo error. Además, la única credencial Python→.NET es `X-Index-Feed-Key`, de solo lectura: escribir exigiría un admin JWT nuevo con poder total sobre el catálogo |
| **D2** | **Se mueve el contrato congelado.** `POST /v1/families/suggest` es la novena ruta; `openapi.json` se regenera y `test_openapi_snapshot_is_stable` se actualiza deliberadamente | `IAiGatewayClient` lleva escrita la doctrina: *«every other contracted endpoint is added by the change that first calls it»*. C17 fijó el criterio: romper el test de deriva **es el resultado correcto**, porque la frontera se ha movido de verdad |
| **D3** | **Sin persistencia de propuestas.** `apply` recibe de vuelta el subconjunto aceptado | Evita una tabla en `ai` y, sobre todo, **la séptima migración de EF Core** que C07 se gastó tres columnas en evitar. `suggest` es determinista y converge porque excluye los productos ya asignados. El único estado que se pierde es el rechazo, que es de C18b |
| **D4** | **L2 + fusión por material**, `variant_label` verbatim, `Position` por rango canónico, etiqueta compuesta aceptada en las 3 rejillas | El stripping global de material degenera `Anillo plata S/M/L/XL` a la raíz `anillo`; la fusión no. Separar los ejes cuesta migración + `source-text/v2` + reindexado completo para arreglar **3 familias de 155** |
| **D5** | **La raíz agrupa, el embedding veta**, y el veto es **relativo** al grupo, nunca un umbral absoluto | Medido: el vecino próximo es hermano en 96,2 % / 99,7 %, pero las poblaciones de «peor hermano» y «mejor extraño» se solapan (0,847–0,936 en real). Un corte fijo no existe |
| **D6** | **Sincronización incremental**, nunca `--full` | Un `--full` taparía el fallo de D1 en lugar de exponerlo. El incremental es la única prueba real de que el estampado de C07 funciona |
| **D7** | **La alerta de huérfanos es de C18b** | Necesita familias existentes para medirse, y su salida natural es una lista en pantalla. Meterla aquí obligaría a inventar una superficie de lectura sin consumidor |
| **D8** | **Todas las familias se escriben en un lote**, con `Origin = AiApproved` y el administrador que dispara el lote como aprobador | El corpus debe moverse **una sola vez**, antes de que C24 mida. Escribir un subconjunto ahora y el resto en C18b lo movería dos veces, la segunda después de la línea base |

### Parámetros fijados el 2026-08-31

Cerrados aplicando la opción por defecto de las preguntas abiertas del ticket. Ninguno bloquea el apply.

| # | Decisión | Motivo |
|---|---|---|
| **D9** | **`piece_type` nulo es valor propio de la puerta**: un producto sin tipo de pieza no agrupa con ninguno | Es el lado seguro. La tasa de nulos no pudo medirse en la exploración; se mide al abrir el apply para **confirmar** el parámetro, no para decidirlo |
| **D10** | **Veto relativo con `k = 2` sobre los 5 vecinos más próximos**, ambos en configuración | Calibrado contra los 6 productos que la exploración identificó como solapados (1,7 % de 358). En configuración porque el valor se revisará con la medición de C24, y un umbral incrustado en el código no se puede barrer |
| **D11** | **`Alianzas Plata` / `Alianzas oro` va a la cola de revisión**, no a una regla | La guarda de raíz degenerada la bloquea por longitud. Si es familia legítima, lo decide una persona en C18b; si no lo es, la guarda ya acertó. En ningún caso lo resuelve el algoritmo |
| **D12** | ~~Vocabulario de materiales declarado en Python con test de fijación~~ → **revisada el 2026-08-31 al implementar: se reutiliza [`enrichment/vocabularies.yaml`](../../../ai-service/src/jbg_ai/enrichment/vocabularies.yaml). No se declara ninguna lista nueva** | La decisión original daba por hecho que había que crear el vocabulario en Python y aceptar una duplicación. Es al revés: **Python ya es el original** —`materials.terms`, y `size_label.terms` con **las dos escalas** y sus sinónimos (`pequeña`, `mediana`, `grandes`)— y `frontend/src/lib/materials-vocabulary.ts` es el espejo, como declara su propia cabecera. Declarar una lista dentro de `families/` habría creado la duplicación que D12 quería evitar, un borde más adentro. El test de fijación se conserva, pero ahora guarda **la reutilización**, no una copia |
| **D12b** | **Sólo el rango canónico de tallas es nuevo**, y `variant_label` guarda la **subcadena tal como aparece en el nombre**, no la forma canónica | El vocabulario sabe qué tokens son talla, pero no que `mini` va antes que `grande`: su lista está agrupada por escala, no ordenada por magnitud, y el orden es lo que `Position` necesita. Y `resolve()` canonicaliza `pequeña` → `pequeno`, lo que contradiría el escenario que exige guardar `pequeña`: se **detecta** con el vocabulario y se **guarda** lo que el catálogo escribió |
| **D13** | **El doble etiquetado del golden set de C24 queda fuera de C18a** y se decide en la reestructuración del plan | La ficha de C24 lo da por hecho entre dos personas y el §6 lo declara irrenunciable; trabajando en solitario no existe. Debe resolverse **antes** de abrir C24, no dentro de C18a |
| **D14** | **El informe del lote se versiona** en `Documentos/Proyecto Final AIEng/informes/c18a-family-suggestion-report.md` | Precedente de C06a, C06b, C10 y C12. Es donde vive la evidencia del recuento y de la cola de revisión que el README va a citar |

---

## Criterios de Aceptación

### Escenario 1: El administrador obtiene propuestas y el catálogo no cambia

- **Dado que** existen 1.200 productos indexados y ninguna familia
- **Cuando** un administrador invoca `POST /api/ai/catalog/family-suggestions`
- **Entonces** la respuesta contiene las familias propuestas con sus miembros, la etiqueta de variante detectada por miembro y el motivo de agrupación
- **Y** cada propuesta indica si algún miembro quedó marcado por el veto del embedding
- **Y** no se ha creado, modificado ni borrado ninguna `ProductFamily` ni ningún `ProductFamilyMember`
- **Y** ningún `Product.UpdatedAt` ha cambiado

### Escenario 2: Al aprobar el lote, las familias quedan registradas como aprobadas por IA

- **Dado que** un administrador ha recibido las propuestas
- **Cuando** invoca `POST /api/ai/catalog/family-suggestions/apply` devolviendo el subconjunto que acepta
- **Entonces** se crean las familias con sus miembros en el orden declarado y con su etiqueta de variante
- **Y** cada familia registra `Origin = AiApproved`, el identificador del administrador que aprobó y el instante de aprobación
- **Y** la respuesta informa de cuántas familias y miembros se crearon
- **Y** una familia creada a mano por los endpoints de C07 sigue registrando `Origin = Manual`

### Escenario 3: El índice ve las familias sin necesidad de una sincronización completa

- **Dado que** el lote se ha aprobado y `Product.UpdatedAt` se ha estampado en los productos que entraron en una familia
- **Cuando** se ejecuta `POST /v1/index/sync` **sin** `full`
- **Entonces** el feed emite exactamente los productos estampados, ni uno más
- **Y** al terminar, `ai.product_document.family_id` deja de ser nulo en esos productos
- **Y** su `doc_text` incluye las líneas `Familia:` y `Variante:`
- **Y** su `source_hash` ha cambiado y su embedding se ha recalculado

### Escenario 4: Un producto que ya pertenece a otra familia no tumba el lote

- **Dado que** una de las propuestas incluye un producto que entretanto fue asignado a otra familia
- **Cuando** el administrador aplica el lote
- **Entonces** la operación identifica qué productos entran en conflicto y qué familia los retiene
- **Y** el resto de familias del lote se crea correctamente
- **Y** ninguna familia queda a medias

### Escenario 5: La agrupación nunca cruza tipos de pieza ni acepta raíces degeneradas

- **Dado que** el catálogo contiene `Anillo erizo de mar M` y `Colgante erizo de mar M`
- **Cuando** se generan las propuestas
- **Entonces** ambos productos no aparecen en la misma familia
- **Y** dado que existen `Encargos plata` y `Encargos Oro`, cuya raíz queda por debajo del mínimo, **no** se propone familia para ellos
- **Y** `Anillo plata S/M/L/XL` **sí** se propone como familia, porque el material no se retira de la raíz sino que se usa para fusionar

### Escenario 6: La etiqueta de variante se guarda literal y el orden es canónico

- **Dado que** una familia agrupa `Colgante hoja roble pequeña`, `mediana` y `grande`
- **Cuando** se aprueba
- **Entonces** las etiquetas de variante persistidas son `pequeña`, `mediana` y `grande`, sin traducir a `S`, `M` ni `L`
- **Y** el orden de los miembros sigue el rango canónico de tallas y no el alfabético
- **Y** en una familia cuyos miembros se distinguen sólo por material, la etiqueta es el token de material y no una talla
- **Y** en una de las tres rejillas, la etiqueta compuesta —`mini oro`— sigue siendo única dentro de su familia

### Escenario 7: Un miembro que el vector no respalda se marca, no se elimina

- **Dado que** un candidato comparte raíz y tipo de pieza con su grupo pero su coseno al centroide cae por debajo del umbral relativo del propio grupo
- **Cuando** se genera la propuesta
- **Entonces** el miembro aparece en la propuesta señalado para revisión, con su distancia
- **Y** no se elimina silenciosamente de la agrupación
- **Y** la propuesta sigue siendo aplicable si el administrador la acepta tal cual

### Escenario 8: Un operador no puede proponer ni aprobar familias

- **Dado que** un usuario autenticado con rol de operador
- **Cuando** invoca cualquiera de los dos endpoints de sugerencia de familias
- **Entonces** la petición se rechaza con 403 Forbidden
- **Y** ninguna familia se crea ni se modifica
- **Y** un llamante no autenticado recibe 401 Unauthorized

### Escenario 9: El servicio de IA no está disponible y el catálogo no queda a medias

- **Dado que** `jbg-ai` no responde, o responde 501 porque la ruta aún no está implementada
- **Cuando** un administrador pide propuestas
- **Entonces** el endpoint de .NET responde 503 con un mensaje que nombra la causa
- **Y** no se escribe nada en el catálogo
- **Y** el fallo queda registrado con su `trace_id`

### Escenario 10: Fuera de alcance explícito

- **Dado que** esta historia entrega el motor y el camino de escritura
- **Cuando** se revisa lo entregado
- **Entonces** **no** existe ninguna pantalla de revisión de familias — es C18b
- **Y** **no** existe alerta de huérfanos — es C18b
- **Y** **no** se ha creado ninguna migración de EF Core, ni ninguna tabla de propuestas
- **Y** `source-text/v1` y `embedding_version` permanecen sin cambios

---

## Notas adicionales

- **Actor:** Administrador. Los operadores no participan: la familia es dato de catálogo, y su lectura ya está abierta a cualquier usuario autenticado desde C07 sin filtrar por punto de venta.
- **Volumen esperado:** ~155 familias (≈68 sobre el catálogo real y 87 sobre el sintético) y ~450 miembros, sobre 1.200 productos. La cifra exacta del tramo real depende de detalles de normalización que el change fija; las mediciones de la exploración dan un rango de 64–68.
- **Cola de revisión resultante:** ~11 familias de 155 (**7 %**) — 3 rejillas de dos ejes, 2 con escalas de talla mezcladas, 6 con raíz degenerada (de las cuales `Encargos`, `Arreglos` y `Presión` no son piezas), más los ~6 productos que el veto del embedding señala. Es el número que justifica la revisión humana de C18b y el que debe aparecer en el README del Proyecto Final.
- **Familia frente a colección.** Son cosas distintas y conviene dejarlo escrito porque la spec viva lo justifica mal: una colección agrupa 1–154 productos (mediana 15) atravesando **13–16 tipos de pieza**; una familia agrupa 2–4 productos de **un solo tipo**. El test operativo es el de C36: *la familia es el conjunto sobre el que el operador está obligado a preguntar antes de cobrar.*
- **Limitación conocida:** un rechazo no se recuerda. Al repetir `suggest`, una propuesta descartada vuelve a aparecer. Es aceptable mientras la aprobación sea por lotes; C18b introduce la lista de descartes.
- **Limitación conocida:** la tasa de nulos de `piece_type` en `ai.product_document` no se pudo medir durante la exploración (el contenedor de Postgres se detuvo). El comportamiento está **fijado por D9** —el nulo no agrupa con nadie—, así que la medición del apply sirve para **confirmar el parámetro y dimensionar su efecto**, no para decidirlo. Si la tasa resultara alta, la puerta perdería fuerza y el peso recaería sobre el veto del embedding: se anotaría en el informe del lote y en `design.md`, sin cambiar la regla.
- **Change asociado:** [`add-family-suggestion-and-approval`](../../../openspec/changes/add-family-suggestion-and-approval/), rama `c18a-add-family-suggestion-and-approval`, creada desde `ai-eng` en `f5212a7`.

---

## Referencias

- Ticket técnico: [T-AIENG-018a](../../../openspec/changes/add-family-suggestion-and-approval/ticket.md)
- Épica: [EP13 — Familias de Producto y Desambiguación de Variantes](../../epicas.md)
- Diseño: [`proyecto-final-diseno-rag-joiabagur.md`](../../Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) §2.2 (decisión abierta 4), §7.5 (flujo mixto), §7.8 (revisión híbrida), §8.3 (D4), §11.1 (categoría de variante del golden set)
- Plan: [`proyecto-final-plan-changes-openspec.md`](../../Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md), ficha C18
- Specs vivas: [`product-family`](../../../openspec/specs/product-family/spec.md), [`index-feed`](../../../openspec/specs/index-feed/spec.md), [`product-document-indexer`](../../../openspec/specs/product-document-indexer/spec.md), [`ai-service-api-contracts`](../../../openspec/specs/ai-service-api-contracts/spec.md), [`ai-vector-schema`](../../../openspec/specs/ai-vector-schema/spec.md)
- Decisiones previas: [`2026-08-17-add-product-family-entity/design.md`](../../../openspec/changes/archive/2026-08-17-add-product-family-entity/design.md) (§6 orden, §7 reserva para C18), [`2026-08-16-add-product-ai-profile-entity/design.md`](../../../openspec/changes/archive/2026-08-16-add-product-ai-profile-entity/design.md) (la familia queda fuera de los campos sensibles)
- Historias relacionadas: [HU-AIENG-007](HU-AIENG-007.md) (entidad de familia), [HU-AIENG-013](HU-AIENG-013.md) (indexador), [HU-AIENG-016](HU-AIENG-016.md) (el panel que ya reserva el hueco de la talla)
- Apuntes del máster: `Sesiones Master AIEng/S11_RAG_avanzado/Reindexacion y Versionado Embeddings.md`, `S08_BBDD_Vectoriales/`, `S10_Tecnicas_Recuperacion/`

---

## Tareas

1. Completar los artefactos OpenSpec del change: `proposal`, **`design.md`** —hay decisión con alternativas reales y medición para resolverla—, specs delta y `tasks`.
2. **Librería `jbg_ai.families`**: normalización de raíz, agrupación L2, fusión por material con guardas, puerta de `piece_type` (nulo = valor propio, D9), veto relativo por embedding con `k = 2` sobre 5 vecinos leídos de configuración (D10), detección de `variant_label` y rango canónico de tallas. Sin LLM, sin red, determinista.
3. **Reutilizar los vocabularios de `enrichment/vocabularies.yaml`** (D12 revisada) y declarar sólo el rango canónico de tallas (D12b), con un test que falla si alguien vuelve a declarar una lista dentro de `families/`.
4. **`POST /v1/families/suggest`**: router, modelos Pydantic, exclusión de productos ya asignados, respuesta determinista bajo `STUB_MODE`.
5. **Regenerar `ai-service/openapi.json`** con la orden del README y actualizar `test_openapi_snapshot_is_stable`.
6. **`IAiGatewayClient.SuggestFamiliesAsync`** y sus DTOs en `JoiabagurPV.Application`.
7. **`AiCatalogController`**: `POST family-suggestions` y `POST family-suggestions/apply`, sólo administradores, con validación FluentValidation y el manejo de `AiNotImplementedException` / `AiUnavailableException` ya establecido por C09.
8. **Camino de escritura** a través de `ProductFamilyService`, con `Origin = AiApproved`, aprobador e instante, y propagación del conflicto por producto.
9. **Ejecutar el lote** sobre el corpus y dejar constancia del recuento, de la cola de revisión y de la tasa de nulos de `piece_type` en [`informes/c18a-family-suggestion-report.md`](../../Proyecto%20Final%20AIEng/informes/) (D14).
10. **Sincronización incremental** y verificación de que `family_id` deja de ser nulo sin recurrir a `--full`.
11. **Reestructurar el plan de changes** al orden **C18a → C19 → C18b**: tabla maestra (§2), grafo de dependencias (§4) —hoy no dibuja C18→C25, C18→C26, C18→C30 ni C18→C36—, calendario (§5) y lista de *nunca se recorta* (§6), donde C30 y C36 son irrecortables mientras C18 no lo es. Añadir al §0 la revisión fechada con la medición del coseno que corrige el §7.5, y **dejar planteada la decisión sobre el doble etiquetado del golden set de C24 trabajando en solitario** (D13), para que se resuelva antes de abrir C24.
12. **Anotar la divergencia spec/código en `Product.CollectionId`**: la spec viva `product-family` justifica la distinción con las colecciones diciendo que un producto puede pertenecer *«a one of many unrelated collections»*, pero [`Product.cs:31`](../../../backend/src/JoiabagurPV.Domain/Entities/Product.cs#L31) declara `Guid? CollectionId`, una FK única y anulable. Ambas cardinalidades son 0..1; los discriminadores reales son el tipo de pieza y el tamaño.
13. **Medir la tasa de nulos de `piece_type`** al abrir el change para confirmar D9 y dimensionar su efecto, y anotarla en el informe y en `design.md`.
14. Enlazar la HU en [`Documentos/epicas.md`](../../epicas.md) (EP13) durante el apply.
15. `openspec validate --all --strict` en verde antes de archivar.

---

## Estimaciones y atributos de priorización

- **Puntos de historia:** _Pendiente_
- **Impacto en usuario / valor de negocio:** 4 — no es visible por sí misma, pero es la única fuente de familias del sistema, y sin ellas la desambiguación de variantes —que el diseño llama *el caso crítico* y a la que el golden set de C24 dedica 10 de sus 60–70 consultas— no existe. Además ejerce por primera vez la reserva de aprobación humana de C07.
- **Urgencia (mercado / feedback):** **4** — marcada 🟢 en el plan, pero con una restricción de orden dura: **debe ir antes de C20, C21 y C24**, porque mueve el 30 % del corpus y `embedding_version` no lo distinguirá.
- **Complejidad / esfuerzo:** 3 — el algoritmo es determinista y está medido; la superficie son tres capas (librería Python, ruta HTTP, dos endpoints .NET) sin migración ni interfaz.
- **Riesgos y dependencias:**
  - **Escribir por SQL directo desde Python rompería el estampado en silencio** y el índice nunca vería las familias. Mitigado por D1: se escribe siempre a través de `ProductFamilyService`, y el escenario 3 lo verifica con sincronización incremental, no completa.
  - **Mover el contrato congelado** rompe `test_openapi_snapshot_is_stable`. Es deliberado y está autorizado por la doctrina de `IAiGatewayClient`; se regenera en el mismo change. Al trabajar en solitario, el acuerdo con «quien posee el cliente .NET» que pide `CLAUDE.md` es una nota, no un bloqueo.
  - **El corpus se mueve una sola vez, o el riesgo vuelve.** Si se escribiera sólo un subconjunto, C18b lo movería otra vez, ya después de la línea base de C24. Mitigado por D8.
  - **Sobre-agrupamiento por fusión de material.** Mitigado con la guarda de raíz degenerada, la puerta de `piece_type` y el veto relativo; las excepciones van a la cola de revisión y no a una regla.
  - **La cola de revisión no tiene pantalla hasta C18b.** Aceptado: en C18a la aprobación es por lotes y las excepciones se listan en el informe.
  - **`piece_type` sin medir.** Si su tasa de nulos fuese alta, la puerta perdería fuerza y el peso recaería sobre el veto del embedding. **Mitigado por D9**, que fija el comportamiento por el lado seguro sin esperar a la medición; la tarea 12 la confirma y la anota.
  - **El veto relativo puede quedar mal calibrado.** `k = 2` sobre 5 vecinos sale de los 6 solapamientos medidos, que es una muestra pequeña. **Mitigado por D10**, que lo deja en configuración: si C24 muestra que corta de más o de menos, se barre sin tocar código.
  - **Dependencia de orden con C19:** ninguna técnica. C19 es 🗄️ y C18a no, así que no compiten por el turno de migración y pueden ejecutarse seguidos en cualquier orden. El plan se reordena a C18a → C19 → C18b sólo porque C18a gatea la medición y C19 no.
