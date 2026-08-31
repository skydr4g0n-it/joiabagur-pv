# C18b — Informe de la revisión humana de familias

**Change:** [`add-family-review-ui-and-orphan-alert`](../../../openspec/changes/add-family-review-ui-and-orphan-alert/) · **Rama:** `c18b-add-family-review-ui-and-orphan-alert`
**Estado:** en curso — este documento se rellena durante el apply, no al final.

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

## 7. Auditoría de miembros marcados: resolución

_Pendiente — grupo 7. Requiere juicio humano._

---

## 6. Huérfanos: θ elegido y cola revisada

_Pendiente — grupo 8._

---

## 7. Revisión de las 156 familias

_Pendiente — grupo 9._

---

## 8. Métricas para el README

_Pendiente — tasa de corrección del agrupador y tiempo medio de revisión, reportadas por `data_origin`._

---

## 9. Reconciliación del índice

_Pendiente — grupo 9._

---

## Vuelta atrás

Deshacer los cambios de pertenencia por los mismos endpoints que los hicieron, vaciar `FamilyReviewVerdict`, revertir el sinónimo `dorado`, y resincronizar de forma incremental. El respaldo `pre-c18b.dump` cubre el caso de que algo salga peor de lo previsto:

```bash
docker exec jpv-pv-postgres psql -U postgres -d joiabagur_pv -f /tmp/pre-c18b.dump
```
