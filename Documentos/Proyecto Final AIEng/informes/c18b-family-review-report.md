# C18b — Informe de la revisión humana de familias

**Change:** [`add-family-review-ui-and-orphan-alert`](../../../openspec/changes/add-family-review-ui-and-orphan-alert/) · **Rama:** `c18b-add-family-review-ui-and-orphan-alert`
**Estado:** completo — redactado durante el apply, no al final. Última medición: 2026-09-01.

---

## 1. Línea base, antes de tocar nada

**Fecha de medición:** 2026-08-31 · **Respaldo previo:** `pre-c18b.dump` (**39,9 MB**, esquemas `public` y `ai` — 28 tablas y 8 tablas respectivamente), dentro del contenedor `jpv-pv-postgres`, en `/tmp/pre-c18b.dump`.

| | |
|---|---|
| `Products` (todos activos) | **1.200** |
| `ProductFamilies` | **156** — `AiApproved` **156**, **`Manual` 0** |
| `ProductFamilyMembers` | **486** |
| `ai.product_document` | **1.168** (1.200 − 32 retirados por C18a) |
| Documentos con `family_id` | **486** |
| Documentos con `variant_label` | 467 — los 19 restantes son piezas base, cuya etiqueta nula es un valor legítimo |
| **Documentos activos sin familia** | **682** — con `piece_type` **671**, sin `piece_type` **11** |
| Perfiles `Approved` / `Rejected` | 1.168 / 32 |
| `embedding_version` | `openai/text-embedding-3-small:1536:source-text/v1` — **un único valor** |
| Documentos sin `embedding` | **0** |

**Cero familias `Manual`** es el dato que enmarca el change: las 156 llevan aprobador e instante **del lote que se disparó de una vez**, y ninguna registra un juicio sobre esa familia en concreto.

**Y `embedding_version` sigue siendo un único valor**, que es justo el problema que obliga al orden: el corpus de antes y el de después de C18b llevarán la misma cadena, porque cambia el **contenido** y no el preprocesado. Nada distinguiría una medición tomada antes de una tomada después. Por eso este change precede a la línea base de C24.

<details>
<summary>Consulta reproducible</summary>

```sql
SELECT 'Products', count(*)::text FROM public."Products"
UNION ALL SELECT 'Products activos', count(*)::text FROM public."Products" WHERE "IsActive"
UNION ALL SELECT 'ProductFamilies', count(*)::text FROM public."ProductFamilies"
UNION ALL SELECT 'ProductFamilies Manual', count(*)::text FROM public."ProductFamilies" WHERE "Origin" = 1
UNION ALL SELECT 'ProductFamilies AiApproved', count(*)::text FROM public."ProductFamilies" WHERE "Origin" = 2
UNION ALL SELECT 'ProductFamilyMembers', count(*)::text FROM public."ProductFamilyMembers"
UNION ALL SELECT 'ai.product_document', count(*)::text FROM ai.product_document
UNION ALL SELECT 'documentos con family_id', count(*)::text FROM ai.product_document WHERE family_id IS NOT NULL
UNION ALL SELECT 'documentos con variant_label', count(*)::text FROM ai.product_document WHERE variant_label IS NOT NULL
UNION ALL SELECT 'activos sin familia', count(*)::text FROM ai.product_document WHERE is_active AND family_id IS NULL
UNION ALL SELECT '  de ellos con piece_type', count(*)::text FROM ai.product_document WHERE is_active AND family_id IS NULL AND piece_type IS NOT NULL
UNION ALL SELECT '  de ellos sin piece_type', count(*)::text FROM ai.product_document WHERE is_active AND family_id IS NULL AND piece_type IS NULL
UNION ALL SELECT 'perfiles Approved', count(*)::text FROM public."ProductAiProfiles" WHERE "ReviewStatus" = 2
UNION ALL SELECT 'perfiles Rejected', count(*)::text FROM public."ProductAiProfiles" WHERE "ReviewStatus" = 3
UNION ALL SELECT 'embedding_version', string_agg(DISTINCT embedding_version, ', ') FROM ai.product_document
UNION ALL SELECT 'documentos sin embedding', count(*)::text FROM ai.product_document WHERE embedding IS NULL;
```

`FamilyOrigin` es 1-based: `Manual = 1`, `AiApproved = 2`. `ProfileReviewStatus`: `Approved = 2`, `Rejected = 3`.

</details>

---

## 2. Línea base de las suites de test

Medida **sin `git stash`**, y a propósito: en el momento de medirla el árbol de trabajo no tenía ni un cambio de código —sólo markdown—, así que el estado actual **es** la línea base y el guardado no habría aportado nada. El guardarraíl existe para no medir sobre código propio, no para ejecutar el comando.

| Suite | Resultado | Alcance de los fallos |
|---|---|---|
| **Frontend** (`vitest run`) | **113 fallos · 420 pasan · 533 total** | 14 ficheros |
| **Backend** (`dotnet test`) | **47 fallos · 873 pasan · 920 total** · 7 m 38 s | 17 clases |

Los nombres de los **113 + 47** tests fallidos quedan guardados para comparar por nombre al cerrar el change, nunca por recuento.

Clases del backend con fallos, con su reparto — cinco de ellas concentran la mitad:

```
5  UnitTests.Application.ImageCompressionServiceTests    3  IntegrationTests.PointOfSalesControllerTests
5  IntegrationTests.SalesControllerTests                 3  IntegrationTests.EmbeddingEndpointsTests
5  IntegrationTests.ReturnsControllerTests               2  UnitTests.Application.QrCodeServiceTests
5  IntegrationTests.ProductsControllerTests              2  UnitTests.Application.InventoryServiceTests
4  IntegrationTests.RepositoryTests                      2  IntegrationTests.RateLimitingTests
4  IntegrationTests.InventoryIntegrationTests            2  IntegrationTests.AuthorizationTests
                                                         1  ExcelImportServiceTests · UsersControllerTests
                                                            SalesReportControllerTests · PaymentMethodsControllerTests
                                                            ImageRecognitionControllerTests
```

**Ninguna de las 17 clases toca familias**, ni `ProductFamiliesController`, ni `AiCatalogController`, ni `FamilySuggestionControllerTests`. La superficie que C18b modifica está limpia en la línea base, lo que hace la comparación final barata: cualquier fallo nuevo en esas clases es de este change.

Ficheros del frontend con fallos:

```
src/pages/payment-methods/payment-methods.test.tsx      src/services/__tests__/image-recognition.service.test.ts
src/pages/products/__tests__/edit.test.tsx              src/services/__tests__/ml-edge-cases.test.ts
src/pages/products/components/product-photo-upload.test.tsx  src/services/__tests__/model-training.service.test.ts
src/pages/products/edit.test.tsx                        src/services/auth.service.test.ts
src/pages/sales/__tests__/new-image.test.tsx            src/services/payment-method.service.test.ts
src/pages/sales/__tests__/new.test.tsx                  src/services/product.service.test.ts
src/pages/sales/__tests__/sales-index.test.tsx
src/pages/sales/__tests__/scan.test.tsx
```

> **Nota de método.** `CLAUDE.md` cita 118 fallos de 482 en 17 ficheros, medidos el 2026-08-29. Hoy son 113 de 533 en 14. La suite ha crecido en 51 tests desde entonces, así que **los dos números no son comparables** y el que vale es el de hoy. Es justamente el motivo por el que la regla del proyecto es comparar **nombres** y no recuentos.

### Comparación al cerrar el change

Ambas suites reejecutadas enteras el **2026-09-01**, y comparadas contra las listas de `baseline/` por **nombre**:

| Suite | Línea base | Al cerrar | Tests propios |
|---|---|---|---|
| **Frontend** | 113 fallos · 420 pasan · 533 | **113 fallos · 439 pasan · 552** | **+19, todos en verde** |
| **Backend** | 47 fallos · 873 pasan · 920 | **51 fallos · 900 pasan · 951** | **+31, todos en verde** |

**El frontend cierra exacto: los 113 nombres son los mismos 113.** Cero nuevos, cero arreglados, y los 19 tests de la pantalla de revisión pasan.

**El backend no cierra exacto por nombre, y hay que decir en qué.** Aparecen 6 nombres que la línea base no tenía y desaparecen 2 que sí tenía:

```
nuevos          InventoryIntegrationTests   ExcelImport_DownloadTemplate_ShouldSucceed
                                            ExcelImport_NegativeQuantityWithSufficientStock_...
                                            MovementHistory_WithPagination_ShouldReturnPagedResults
                                            Operator_AdjustStock_ShouldBeForbidden
                ProductsControllerTests     Update_WithValidData_ShouldReturnUpdatedProduct
                ReturnsControllerTests      GetReturnsHistory_WithFilters_ReturnsFilteredResults

desaparecidos   ReturnsControllerTests      GetReturnsHistory_WithExistingReturns_ReturnsPagedResults
                SalesControllerTests        CreateSale_OperatorNotAssignedToPOS_ReturnsBadRequest
```

Los ocho caen **dentro de clases que ya fallaban en la línea base** —`InventoryIntegrationTests`, `ProductsControllerTests`, `ReturnsControllerTests`, `SalesControllerTests`—, y ninguna de las cuatro toca familias, ni el controlador de catálogo IA, ni la entidad nueva.

**Y el nombre no es una unidad estable en esta suite.** Se midió en esta misma sesión: **dos ejecuciones del mismo código dieron 48 y 54 fallos**, con nombres distintos dentro de las mismas clases. `CLAUDE.md` avisa de que un puñado de estos fallos dependen del orden; lo que la medición añade es que la inestabilidad llega **al nivel de nombre**, y que la unidad que sí se sostiene entre ejecuciones es la **clase**.

Por eso la comparación que cierra el change se hace por clase, y sale limpia:

> **El conjunto de clases con fallos es idéntico al de la línea base, y ninguna clase de familia aparece en él.**

Y comprobado por el lado positivo, que es el que importa para este change: las siete clases que cubren la superficie tocada —`FamilyReviewControllerTests`, `FamilyReviewVerdictSchemaTests`, `ProductFamiliesControllerTests`, `ProductFamilySchemaTests`, `AiCatalogControllerTests`, `FamilySuggestionControllerTests` y `AiGatewayFamilySuggestionTests`— corren **111 de 111 en verde**.

---

## 3. Curva del margen y criterios de nominación, antes de tocar nada

Reproducidas contra el estado de la sección 1, y coincidentes con lo medido en la exploración.

**Curva del margen relativo**, ahora además desglosada por origen del dato:

| θ | nominados | `real` | `synthetic` |
|---|---|---|---|
| 0 | **40** | 39 | 1 |
| 0,02 | **22** | 21 | 1 |
| 0,05 | 5 | 4 | 1 |
| 0,08 | 3 | 2 | 1 |

**El único candidato sintético sobrevive a todos los umbrales.** Es `Colgante Estrella de Mar v2`, con margen 0,094 — el reverso del hallazgo (d) de C18a, donde un sintético homónimo se coló en una familia real. Su respuesta correcta no es «añádelo» sino **descartarlo**, y por eso la lista de veredictos existe.

**Criterio A (margen) frente a criterio B (pureza de vecindad)**, sobre los 650 huérfanos que pueden puntuar contra alguna familia de su tipo de pieza:

| `data_origin` | huérfanos puntuables | **A** · margen > 0,02 | **B** · pureza ≥ 3 de 5 | A ∧ B |
|---|---|---|---|---|
| `real` | 216 | **21** | 19 | 6 |
| `synthetic` | 434 | **1** | **55** | 0 |

Es la medición que decide el diseño: **A dispara 95 % sobre catálogo real, B dispara 74 % sobre sintético**, porque las familias `vN` de C06b están construidas para ser distintas y la pureza no las sabe separar de un miembro que falta. A nomina, B ordena.

*(Los 671 huérfanos con `piece_type` menos los 650 puntuables son **21** cuyo tipo de pieza no tiene ninguna familia existente: no pueden puntuar contra nada y quedan fuera de la alerta por construcción. No es un defecto — no hay familia a la que pertenecer.)*

---

## 4. El sinónimo `dorado`: diff completo de propuestas

**Verificación del punto de partida, ejecutando el `suggest` real.** Antes de tocar nada, el orquestador devuelve sobre el corpus vivo:

```
propuestas          0
miembros            0
grupos rechazados   2      ← Alianzas Plata/oro · Cadena oro/plata
excluidos por gate  11
ya en familia       486
```

**Los tres números de la ficha de C18b quedan verificados en ejecución**, no por inferencia: 0 propuestas donde la ficha mandaba pintar una cola, 2 grupos rechazados donde decía 4, y 11 excluidos donde decía 37.

**Tras añadir `dorado: baño de oro` a `materials.synonyms`:**

```
propuestas          6      (antes 0)
miembros           12      (antes 0)
grupos rechazados   2      sin cambio
excluidos por gate 11      sin cambio
ya en familia     486      sin cambio
```

**Diff completo, no sólo los casos buscados** — que es lo que la tarea exigía comprobar:

| | |
|---|---|
| Propuestas nuevas | **6** |
| Propuestas desaparecidas | **ninguna** |
| Propuestas modificadas | **ninguna** |
| Grupos rechazados | **idénticos** — ninguna raíz degradada al tipo de pieza pelado |
| Productos excluidos | **idénticos** |

Las seis familias nuevas — 8 productos reales y 4 sintéticos:

| Tipo | Raíz | Miembros |
|---|---|---|
| anillo | `anillo crepusculo` | `Anillo Crepúsculo` (base) · `Anillo Crepúsculo Dorado` |
| collar | `collar elixir` | `Collar Elixir` (base) · `Collar Elixir Dorado` |
| pendientes | `pendientes aro conchiglie` | `Pendientes aro conchiglie` (base) · `… dorado` |
| pendientes | `pendientes aros estrella de mar` | `Pendientes aros estrella de mar` (base) · `… dorado` |
| pendientes | `pendientes aros lapa` | `Pendientes aros lapa` (base) · `… dorado` |
| pendientes | `pendientes oreja de mar boton` | `… botón mini` (base) · `… botón mini dorado` |

**La hipótesis falsable de D14 se sostiene.** Si `dorado` fuese sinónimo de `oro` y no de `baño de oro`, los pares habrían recibido la misma etiqueta y los grupos aparecerían rechazados por `duplicate_variant_labels`. No ocurre: cada pareja sale con `None` para la pieza base y `baño de oro` para la variante, y **no hay ni un grupo rechazado nuevo**.

### Dos correcciones que el diff obligó a hacer sobre las tareas

**(a) Los tres productos que la tarea 2.4 esperaba ver agrupados no se agrupan, y el motivo importa.** `Pendientes botón erizo de mar S dorado` (SKU25), `Colgante Lapa Mini Dorado` (SKU420) y `Pendientes botón estrella de mar dorado` (SKU90) siguen huérfanos. No es un fallo del sinónimo: **sus familias ya existen** —`Pendientes boton erizo de mar` con 4 miembros, `Colgante lapa` con 3, `Pendientes boton estrella de mar` con 3— y la regla de convergencia excluye del pool a los productos que ya pertenecen a una familia, así que la variante `dorado` no tiene con quién agruparse.

De ahí una conclusión que refuerza el change entero: **el sinónimo sólo recupera familias donde los dos miembros siguen libres.** Donde la familia base ya se aprobó en C18a, la variante `dorado` únicamente puede entrar por **la alerta de huérfanos y la pantalla de revisión** — que es exactamente lo que C18b construye. Los tres van a la cola de huérfanos, no a `suggest`.

**(b) La tarea 2.5 no tenía nada que hacer, y su premisa era errónea.** `frontend/src/lib/materials-vocabulary.ts` es espejo de **`materials.terms`**, no de `materials.synonyms`, y su test de fijación pincha los **nueve términos canónicos**. `dorado` es un sinónimo y `baño de oro` ya estaba en la lista, así que el espejo no cambia. Y **no debe cambiar**: el panel ofrece valores canónicos de filtro, y añadir `dorado` daría al operador un filtro que el recuperador no casa nunca.

---

## 5. Primera ejecución de la auditoría, contra el corpus real

Ejecutada con `audit_families` sobre el Postgres local, con `JPV_FAMILY_VETO_MARGIN = 0,05` y `JPV_FAMILY_ORPHAN_MARGIN = 0`:

| | |
|---|---|
| Familias examinadas / miembros | **156 / 486** |
| **Miembros marcados** | **18** |
| **Huérfanos candidatos** | **40** (39 reales, 1 sintético) |
| Grupos rechazados | 2 |
| Excluidos por la puerta | 11 |

### La decisión 5 del diseño queda validada con datos, no con el argumento

**Once de los dieciocho marcados son `Colgante estrella de mar`** —siete de la familia, tres de su gemela `… dorado`, y el intruso—, encabezados por márgenes de 0,147:

```
0,147  SKU82   Colgante estrella de mar M oro     en Colgante estrella de mar
0,140  SKU80   Colgante estrella de mar XS oro    en Colgante estrella de mar
0,127  SKU81   Colgante estrella de mar S oro     en Colgante estrella de mar
 ...
0,084  SKU610  Colgante Estrella de Mar           en Colgante estrella de mar   <- el sintetico colado
```

Es exactamente lo que el `design.md` anticipó: una familia contaminada tiene el peor hermano por los suelos (0,778 frente a una media de 0,85–0,95) y **marca a casi todos sus miembros**, porque cualquier extraño les gana ese listón. El hallazgo (d) de C18a —un sintético que se coló en una familia real— **no marca sólo al intruso: contamina a los siete que le acompañan.**

De ahí que el orden del change no sea negociable: **sacar a `SKU610` sube el listón de esa familia y debería llevarse la mayor parte de los dieciocho de golpe.** Es la limpieza que el grupo 7 hace antes de que el grupo 8 fije θ.

### Y la pureza se comporta como se diseñó: ordena, no nomina

Con las dos señales una al lado de la otra sobre datos reales se ve que **no van juntas**, que es justo el motivo de no usar la pureza como criterio:

| margen | pureza | huérfano | familia candidata |
|---|---|---|---|
| 0,109 | **4** | `Pendientes botón erizo de mar S dorado` | `Pendientes boton erizo de mar` |
| 0,094 | **1** | `Colgante Estrella de Mar v2` *(sintético)* | `Colgante estrella de mar` |
| 0,050 | **0** | `Colgante mejillón plata L` | `Colgante estrella de mar` |
| 0,047 | **4** | `Anillo pie Erizo XL` | `Anillo erizo de mar` |

Los de pureza 0 con margen positivo son los falsos positivos del imán —`Colgante mejillón` no es una estrella de mar—, y los de pureza 4 son los aciertos claros. La pureza **discrimina dentro de la lista que el margen ya eligió**, que es el papel que el diseño le da.

---

## 6. Lo que la implementación obligó a decidir, y no estaba escrito

Tres decisiones que el diseño no había fijado y que salieron al escribir el código.

**El repositorio devuelve una forma de dominio, no el DTO de aplicación.** `IProductFamilyRepository` vive en `Domain`, y ese proyecto **no referencia ningún otro**: un DTO de `Application` en su firma invertiría la estratificación sobre la que se apoya la solución entera. Se añade `ProductFamilySummary` en `Domain` y el servicio mapea, que es una proyección corta y ninguna duplicación de significado.

**Un origen de familia no reconocido responde 400, no la lista sin filtrar.** Servir el conjunto completo contestaría a una pregunta que nadie hizo, y sobre una pantalla de revisión se lee como *«estas son las familias manuales»* cuando son todas.

**Dentro de un lote de veredictos gana el último.** Un revisor que marca la misma fila dos veces antes de enviar se está corrigiendo; insertar ambas rompería el índice único del par y convertiría una pregunta ya respondida en un error de base de datos.

Y un cuarto punto que sí estaba en el diseño pero que el código hace visible: **un cuerpo vacío del servicio de IA se traduce a fallo y nunca a resultado vacío**. En esta ruta «vacío» y «catálogo limpio» son indistinguibles para la pantalla, y sólo uno de los dos es cierto.

### Cómo quedó D20 en el código, que era el punto delicado

Los tres estados no son un condicional en el render: **están en el tipo**.

```ts
export type AuditOutcome =
  | { state: 'loaded'; audit: FamilyAudit }
  | { state: 'unavailable'; reason: string };
```

Un llamante **no puede alcanzar las listas sin pasar por el estado**, que es lo que hace incómodo repetir el fallo en vez de sólo desaconsejarlo. La pantalla distingue tres cosas donde lo fácil habría sido distinguir dos:

| Estado | Lo que dice | Por qué no puede confundirse con el anterior |
|---|---|---|
| `loaded`, con filas | La cola | — |
| `loaded`, vacía | *«Sin hallazgos»*, citando cuántas pertenencias se examinaron | Un recuento es la prueba de que se miró |
| `unavailable` | *«No se ha podido calcular»* — y literalmente *«esto **no** significa que no haya nada que revisar: significa que no se sabe»* | Es la frase que C17 no dijo |

Y el estado es **por lista y no por página**: la pestaña de familias no usa vectores, así que sigue operativa mientras la auditoría no lo esté. Tres de los ocho tests de frontend pinchan exactamente eso.

---

## 7. Auditoría de miembros: las 18 marcas, resueltas

Revisión ejecutada el **2026-08-31** por el administrador, contra el corpus real y por el camino completo (.NET → `jbg-ai` → pgvector). Las 18 marcas se resolvieron **todas**: no queda ninguna sin veredicto.

| | |
|---|---|
| Miembros marcados | **18** |
| Confirmados | **17** |
| Sacados de la familia | **1** — `SKU91` |
| **Tasa de confirmación** | **94 %** |

Las 18, por margen descendente:

| margen | SKU | producto | familia | veredicto |
|---|---|---|---|---|
| 0,147 | SKU82 | Colgante estrella de mar M oro | Colgante estrella de mar | confirmado |
| 0,140 | SKU80 | Colgante estrella de mar XS oro | Colgante estrella de mar | confirmado |
| 0,127 | SKU81 | Colgante estrella de mar S oro | Colgante estrella de mar | confirmado |
| 0,124 | SKU76 | Colgante estrella de mar XS | Colgante estrella de mar | confirmado |
| 0,118 | SKU78 | Colgante estrella de mar M | Colgante estrella de mar | confirmado |
| 0,114 | SKU77 | Colgante estrella de mar S | Colgante estrella de mar | confirmado |
| 0,112 | SKU79 | Colgante estrella de mar L | Colgante estrella de mar | confirmado |
| 0,106 | SKU150 | Anillo rama XL | Anillo rama | confirmado |
| 0,087 | SKU123 | Colgante conchiglie Oro | Colgante conchiglie | confirmado |
| 0,087 | SKU145 | Anillo rama abierto XL | Anillo rama abierto | confirmado |
| **0,084** | **SKU610** | **Colgante Estrella de Mar** *(sintético)* | Colgante estrella de mar | **confirmado** |
| 0,076 | SKU143 | Anillo rama | Anillo rama | confirmado |
| 0,074 | SKU71 | Pendientes botón estrella de mar xs oro | Pendientes boton estrella de mar | confirmado |
| 0,070 | SKU121 | Colgante mini conchiglie | Colgante conchiglie | confirmado |
| 0,066 | SKU122 | Colgante mini conchiglie Oro | Colgante conchiglie | confirmado |
| **0,061** | **SKU91** | Colgante estrella de mar XS dorado | Colgante estrella de mar dorado | **sacado** |
| 0,057 | SKU144 | Anillo rama abierto | Anillo rama abierto | confirmado |
| 0,051 | SKU69 | Pendientes botón estrella de mar | Pendientes boton estrella de mar | confirmado |

### 7.3 — El hallazgo (d) de C18a se resolvió, pero al revés de como el diseño lo predijo

La tarea 7.3 daba por hecho que `SKU610` era un intruso: un sintético colado en una familia real, cuya salida subiría el peor hermano de `Colgante estrella de mar` por encima de 0,778 y arrastraría consigo a la mayoría de los dieciocho. **La persona que revisó lo confirmó como miembro legítimo.**

Y mirando el producto es difícil llevarle la contraria: `Colgante Estrella de Mar` **es** un colgante de estrella de mar, y la familia agrupa exactamente eso. Lo que la etiqueta `synthetic` marca es la procedencia del dato, no un error semántico. C18a leyó *«un sintético dentro de una familia real»* como contaminación porque cruzó una frontera de origen; el revisor leyó la única frontera que le importa al catálogo, que es la del producto, y ahí no hay intrusión.

Tres consecuencias, y ninguna es cosmética:

- **El peor hermano de esa familia no sube, y la predicción de la decisión 5 queda sin comprobar.** No es que se refutara: es que la limpieza que la habría puesto a prueba no llegó a hacerse, porque no había nada que limpiar. Queda como hipótesis abierta.
- **Su dispersión es real, no contaminación.** La familia va de XS a L en dos acabados, y ese recorrido es el que hunde el listón hasta 0,778. Ningún umbral distingue eso de una familia rota.
- **La marca no midió lo que se creía.** Once de las dieciocho —siete de `Colgante estrella de mar`, cuatro de `Anillo rama` y `Anillo rama abierto`— salen de familias amplias y legítimas. La señal detectó amplitud, y se leyó como error.

**La precisión del veto como señal de auditoría sobre miembros es de 1 sobre 18: un 6 %.** Es un dato incómodo y es el dato. No invalida la señal —cuesta 18 juicios y encontró uno real, que es una compra razonable— pero sí invalida cualquier lectura automática de ella: **marcar no es un veredicto, y este número es la razón por la que en este change nada se mueve sin que una persona lo diga.**

---

## 8. Huérfanos: θ fijado y la cola revisada entera

**`JPV_FAMILY_ORPHAN_MARGIN = 0`.** Se fija generoso a propósito, como pedía la tarea 8.1: con θ = 0 entra en la cola todo producto que se acerque a una familia más que el peor miembro de esa familia, sin exigir holgura extra. La cola sale de 40 elementos, que una persona recorre en una sesión, y **la persona es el filtro**. Subir θ habría recortado la cola sin evidencia de estar recortando por el lado bueno; con los 40 revisados uno a uno, ahora esa evidencia existe.

| | |
|---|---|
| Candidatos nominados | **40** (39 reales, 1 sintético) |
| Aceptados como variante | **6** |
| Descartados | **34** |
| **Precisión de la nominación** | **15 %** |

### La precisión depende de la familia destino, y el sentido es el previsto

Repartiendo los 40 por la familia a la que apuntaban aparece el patrón que da sentido a las dos cifras:

| familia destino | candidatos | aceptados | precisión |
|---|---|---|---|
| Colgante estrella de mar | **8** | **0** | **0 %** |
| Pendientes boton erizo de mar | 7 | 1 | 14 % |
| Pendientes boton estrella de mar | 5 | 1 | 20 % |
| Pendientes boton lapa | 4 | 0 | 0 % |
| Anillo erizo de mar | 2 | 0 | 0 % |
| **Pendientes conchiglie** | **2** | **2** | **100 %** |

**La misma familia que se llevó siete de las dieciocho marcas atrajo ocho candidatos y no acertó ni uno.** Es el imán que el diseño anticipó, ahora medido: una familia con el listón hundido no sólo marca a los suyos, sino que **nomina a cualquiera que le pase cerca**. En el otro extremo, `Pendientes conchiglie` —familia estrecha— nomina dos y acierta dos.

De ahí la regla que este informe deja escrita para C28: **la nominación por margen relativo hereda la cohesión de la familia destino.** Su precisión no es una propiedad del umbral, sino de a quién apunta. Ponderarla por la cohesión del destino es la mejora obvia, y no se hace aquí porque exige recalibrar sobre una cola ya revisada — que es justo lo que este change acaba de producir y no existía al empezar.

### 8.3 — Las dos raíces degeneradas siguen abiertas, y no por descuido

La tarea 8.3 heredaba de C18a (D11) dos grupos cuya raíz normaliza al tipo de pieza pelado. **Ninguno llegó a la cola**, y el motivo es distinto en cada caso:

| producto | tipo | por qué no se nominó |
|---|---|---|
| `Alianzas Plata` (SKU327), `Alianzas oro` (SKU397) | anillo | Hay familias de `anillo`, pero ninguna les queda lo bastante cerca: una alianza lisa no se parece a un anillo de rama ni de erizo |
| `Cadena plata` (SKU328), `Cadena oro` (SKU329) y 5 más | cadena | **No existe ni una familia de tipo `cadena`.** Sin familia destino no hay margen que calcular |

Las siete cadenas y las dos alianzas son familias de variante de manual, evidentes a la vista y **fuera del alcance de este change**: C18b lista y disuelve familias, no las crea. Quedan anotadas aquí como entrada para quien retome C28, con los SKU ya identificados.

### 8.4 — Los huérfanos que quedan fuera por construcción

De los **677** productos activos sin familia que quedan tras la revisión, **32 son inalcanzables** para la auditoría, se ponga θ donde se ponga:

| motivo | productos |
|---|---|
| Sin `piece_type` — la puerta del tipo los excluye | **11** |
| `piece_type` del que **ninguna familia** es miembro | **21** — `tobillera` 14, `cadena` 7 |
| **Total fuera por construcción** | **32** |

Los 645 restantes sí son alcanzables y simplemente no superaron θ = 0: ninguna familia les queda más cerca que su peor miembro. Es el resultado correcto para la inmensa mayoría de un catálogo, donde la mayoría de las piezas son únicas.

---

## 9. Revisión, aplicación y reconciliación

### 9.1 — Alcance real de la revisión, dicho con precisión

**Se juzgaron 58 pares `(producto, familia)`** de los 526 posibles (486 pertenencias vivas + 40 candidatos). Los 58 son exactamente lo que la auditoría señaló: las 18 pertenencias que los vectores no sostienen, y los 40 candidatos.

La tarea 9.1 pedía *«revisar las 156 familias ítem a ítem»*, y conviene no leer los 58 como si fueran eso. **Las 156 se revisaron como lista** —la pestaña de familias las recorre con sus miembros y sus etiquetas, y de ahí salieron las cuatro correcciones de etiqueta— pero el veredicto par a par se registró sobre el subconjunto auditado. Juzgar las 486 pertenencias una a una es otro trabajo, y ni la señal ni la pantalla lo exigen: **las 468 no marcadas son precisamente aquellas sobre las que los vectores no tienen objeción.**

### 9.2 — Confirmar sin cambiar no movió el corpus

Es la comprobación que separa un veredicto de una edición, y sale limpia:

| | antes | después | movimiento |
|---|---|---|---|
| `ProductFamilies` | 156 | **156** | ninguno |
| `ProductFamilyMembers` | 486 | **491** | **+6 −1** |
| Familias `Manual` | 0 | **0** | ninguno |

**Los 51 veredictos que no implicaban acción no tocaron una sola fila del catálogo.** Se movieron los 7 pares que la persona decidió aplicar, ni uno más — y se movieron por la ruta declarativa de C07, no por escritura directa.

Los 7 aplicados:

| SKU | producto | familia | acción | etiqueta |
|---|---|---|---|---|
| SKU25 | Pendientes botón erizo de mar S dorado | Pendientes boton erizo de mar | añadido | `S baño de oro` |
| SKU420 | Colgante Lapa Mini Dorado | Colgante lapa | añadido | `mini baño de oro` |
| SKU90 | Pendientes botón estrella de mar dorado | Pendientes boton estrella de mar | añadido | `baño de oro` |
| SKU133 | Pendientes mini conchiglie dorado | Pendientes conchiglie | añadido | `mini baño de oro` |
| SKU17 | Colgante dorado erizo de mar S | Colgante erizo de mar | añadido | `S baño de oro` |
| SKU119 | Pendientes conchiglie largos | Pendientes conchiglie | añadido | `L` |
| SKU91 | Colgante estrella de mar XS dorado | Colgante estrella de mar dorado | **sacado** | — |

**Tres de los seis añadidos son los que la sección 4 predijo que sólo podrían entrar por aquí** —SKU25, SKU420 y SKU90—: sus familias base ya existían, la regla de convergencia los excluía del pool de `suggest`, y el sinónimo `dorado` por sí solo no los alcanzaba. Entraron por la cola de huérfanos, que era la apuesta del change. Y cuatro etiquetas se corrigieron a mano sobre familias ya existentes —SKU25, SKU420, SKU118 (`mini oro`) y SKU117 (`mini`)—, que es el hueco que obligó a añadir la edición de etiqueta al alcance.

### 9.3 — Sincronización incremental, con una salvedad que hay que decir

Se ejecutó `POST /v1/index/sync` en modo incremental, nunca `--full`. El primer intento **falló en 9 de 16 documentos** con `CERTIFICATE_VERIFY_FAILED` contra el proveedor de embeddings — un problema de confianza de certificados de la máquina, no de la aplicación ni de la red (`curl` al mismo host devolvía 200). Se resolvió construyendo un bundle con `certifi` más las 183 raíces del almacén de Windows y apuntando `SSL_CERT_FILE` a él.

**La salvedad:** el segundo pase salió con `since: null` y barrió los 1.168 documentos, no sólo los estampados. El estado final es correcto y está verificado, pero **esta ejecución no demuestra que el estampado del watermark funcione**, que es lo que la tarea 9.3 quería comprobar. Se deja dicho en lugar de dar la casilla por buena: un barrido completo tapa exactamente el fallo que esa tarea buscaba.

### 9.4 — Estado final del índice

| | |
|---|---|
| `ai.product_document` | **1.168** |
| Con `family_id` | **491** — cuadra exactamente con `ProductFamilyMembers` |
| Con `variant_label` | 473 |
| **Sin `embedding`** | **0** |
| `embedding_version` | **un único valor** — sigue siendo `openai/text-embedding-3-small:1536:source-text/v1` |

**`ai.sync_failure` tiene 9 filas, y se dejan donde están.** Son los 9 documentos del incidente de certificados de las 22:04, y los 9 productos —SKU91, 90, 17, 25, 420, 133, 117, 118 y 119— están verificados como reindexados a las 22:09 y con embedding. La tarea 9.4 pedía *«cero filas»*, y esa exigencia parte de una premisa falsa: **la tabla es de sólo inserción.** Nada en `indexing/` borra de ella; sus columnas `attempts` y `next_retry_at` no las lee nadie. No es una cola que se drena, es un registro de incidentes que se acumula.

Vaciarla con un `DELETE` para poner verde una casilla sería destruir la traza de un incidente real y llamarlo cierre. **Se corrige la tarea, no los datos.** Que la tabla parezca una cola y no lo sea es una observación para otro change, no una deuda de éste.

---

## 10. Métricas para el README

| Métrica | Valor | Sobre qué se mide |
|---|---|---|
| **Pertenencias auditadas** | 18 de 486 | las que los vectores no sostienen |
| **Tasa de confirmación del agrupador** | **94 %** (17/18) | sobre las marcadas, no sobre las 486 |
| **Tasa de corrección** | **5,6 %** (1/18) | ídem |
| **Precisión de la marca como señal** | **6 %** | 1 marca útil por cada 18 juicios |
| **Candidatos a huérfano revisados** | 40 | con θ = 0 |
| **Precisión de la nominación** | **15 %** (6/40) | de 0 % a 100 % según la cohesión del destino |
| **Decisiones aplicadas al catálogo** | 7 de 58 | 6 altas, 1 baja |
| **Reparto por `data_origin`** | 56 reales / 2 sintéticos | sobre un corpus indexado de 404 reales y 764 sintéticos |
| **Tiempo medio de revisión** | **no disponible en esta ejecución** | ver abajo |

Las cifras de arriba **no son un cálculo de este documento**: son lo que devuelve `GET /api/ai/catalog/family-review-metrics` una vez aplicado el backfill de `SubjectWasMember` el 2026-09-01.

```json
{"totalJudged":58,"membersJudged":18,"membersConfirmed":17,"candidatesJudged":40,
 "candidatesConfirmed":6,"memberConfirmationRate":94.4,"candidateAcceptanceRate":15,
 "timedJudgements":0,"averageReviewSeconds":null,"pendingActions":0}
```

**`averageReviewSeconds` viene `null` y no `0`**, que era el punto: la métrica informa la ausencia en lugar de afirmar una revisión instantánea. Y **`pendingActions: 0`** confirma por el otro lado que las 7 decisiones que implicaban movimiento están aplicadas y no queda ninguna colgando.

Las dos primeras filas hay que leerlas juntas y con su denominador a la vista: **el 94 % es sobre las 18 marcadas, no sobre las 486 pertenencias.** Decir «el agrupador acierta el 94 %» sin esa coletilla sería inflar la cifra, porque las 468 restantes ni se juzgaron.

**Y el reparto por `data_origin` merece una línea propia.** El corpus indexado es sintético en un 65 %, y sin embargo **56 de los 58 juicios cayeron sobre productos reales**. La auditoría no está midiendo los datos de relleno: apunta casi en exclusiva al catálogo de verdad, que es donde se quería que apuntara.

### El tiempo medio no está, y decir por qué es más útil que estimarlo

`ReviewSeconds` está a `NULL` en las 58 filas. La columna se añadió **después** de esta revisión, precisamente porque durante ella se descubrió que el cronómetro vivía en el estado del componente y moría con la pestaña. La media que el checklist pide **no existe para esta ejecución**, y este informe no la va a inventar.

Lo único que los datos sostienen es una cota. Los veredictos se registraron en **dos lotes**: 40 a las 21:34:27 y 18 a las 21:37:15. Si la revisión de los 18 miembros arrancó justo tras enviar el lote de huérfanos —suposición razonable pero **no verificada**—, esos 168 segundos dan **≈ 9,3 s por ítem como cota superior**. Para los 40 huérfanos no hay ni instante de arranque, así que no hay cota alguna.

Nueve segundos por ítem es un orden de magnitud creíble para decisiones de *«¿esta pieza es una variante de esa familia?»* con la ficha delante, pero **una cota bajo una suposición no es una medición**. Queda como referencia para dimensionar la siguiente sesión, no como el número del entregable. El mecanismo para medirlo de verdad —`ReviewSeconds` por juicio y `GET family-review-metrics` calculando desde lo guardado— **ya está entregado y probado**, y la próxima revisión sí dará la cifra. Cuando no hay tiempos la métrica informa la ausencia y nunca un cero: un cero afirmaría una revisión instantánea.

---

## 11. Lo que queda abierto

| Qué | Por qué no se cierra aquí |
|---|---|
| **Familias de `cadena` y `alianzas`** — 9 productos que piden dos familias manuales | **Delegado a C28 el 2026-09-01**, con los 9 SKU y el motivo escritos en su ficha del plan: crear una familia desde la pantalla es el hueco que hereda, y estos nueve son su caso de prueba |
| **Ponderar la nominación por la cohesión del destino** — su precisión va de 0 % a 100 % según a qué familia apunte | Exige recalibrar sobre una cola ya revisada, que es lo que este change acaba de producir y no existía al empezar |
| **La predicción de la decisión 5** — sin comprobar | No hubo intruso que sacar. Queda como hipótesis, no como resultado |
| **`ai.sync_failure` no se drena** — `attempts` y `next_retry_at` no las lee nadie | Observación de esquema, ajena al alcance |
| **Estampado del watermark sin verificar** — el segundo pase barrió los 1.168 | Necesita una sincronización con `since` real sobre un cambio acotado |

**Cerrado el 2026-09-01, tras la primera versión de este informe:** el backfill de `SubjectWasMember` se ejecutó con autorización expresa (`UPDATE 18`, quedando 18 en `true` y 40 en `false`, exactamente la reconstrucción prevista); las dos raíces degeneradas se delegaron a C28 por escrito; y los tres estados por lista se verificaron **parando `jbg-ai` de verdad**, no sólo con MSW — con el servicio caído la auditoría responde **503** y nunca 200 con listas vacías, mientras el listado de las 156 familias sigue respondiendo 200. Las **62 tareas** del change quedan cerradas.
## Vuelta atrás

Deshacer los cambios de pertenencia por los mismos endpoints que los hicieron, vaciar `FamilyReviewVerdict`, revertir el sinónimo `dorado`, y resincronizar de forma incremental. El respaldo `pre-c18b.dump` cubre el caso de que algo salga peor de lo previsto:

```bash
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -f /tmp/pre-c18b.dump
```
