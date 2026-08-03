# Especificaciones funcionales IA - Joiabagur PV

**Fecha:** 2026-07-22  
**Repositorio base:** https://github.com/skydr4g0n-it/joiabagur-pv/  
**Alcance:** IA de catálogo, búsqueda semántica + venta asistida, recomendaciones de inventario.  
**Fuera de alcance en esta fase:** reconocimiento visual, chatbot interno generalista, virtual try-on, fine-tuning de LLMs, agentes autónomos que modifiquen stock sin aprobación humana.

---

## 1. Contexto y objetivos

Joiabagur PV es una aplicación interna de gestión de puntos de venta para joyería. La base actual ya incluye catálogo, fotos de productos, ventas, inventario por punto de venta, operadores asignados a POS, roles Admin/Operator, historial de ventas, movimientos de inventario, devoluciones y stock bajo.

El objetivo de esta fase de IA es aportar valor operativo con bajo coste:

1. **Vender más** mediante fichas enriquecidas, venta asistida, sustitutos y recomendaciones.
2. **Reducir errores de selección de producto**, especialmente en hoteles donde el operador no conoce bien el catálogo.
3. **Ahorrar tiempo administrativo** en reposición, rotación y preparación de mercancía.
4. **Mejorar la distribución de stock** entre hoteles y tienda central.

---

## 2. Principios de diseño

1. **Primero datos y UX, después IA avanzada.** El valor vendrá de estructurar catálogo, variantes, sustitutos, stock y ventas.
2. **La IA no debe ser fuente de verdad para stock ni precio.** Stock, precio, permisos y ventas deben venir siempre de PostgreSQL/API.
3. **Las acciones sensibles requieren aprobación humana.** El sistema puede proponer reposiciones, traslados o liquidaciones, pero no aplicarlas automáticamente al inicio.
4. **Coste bajo y cacheado.** Generar metadatos una vez y recalcular solo cuando cambien datos relevantes.
5. **Control por POS.** Operadores solo deben ver productos asignados y visibles en sus puntos de venta.
6. **Variante explícita antes que inferencia visual.** Para productos S/M/L visualmente parecidos, la talla debe estar modelada y visible.

---

## 3. Funcionalidades priorizadas

| Prioridad | Funcionalidad | Objetivo |
|---:|---|---|
| 1 | Enriquecer catálogo | Crear metadatos comerciales y semánticos para productos. |
| 2 | Búsqueda semántica + venta asistida | Ayudar al operador a encontrar y vender el producto correcto. |
| 3 | Recomendaciones de inventario | Reposición, sustitutos, packing list, rotación/liquidación y argumentario por hotel. |

---

# 4. Funcionalidad 1 - Enriquecer catálogo

## 4.1. Objetivo

Crear una capa de metadatos IA sobre los productos existentes para mejorar búsqueda, venta asistida, sustitutos e inventario.

La app actual ya tiene productos con `SKU`, `Name`, `Description`, `Price`, `CollectionId` e `IsActive`. Esta funcionalidad no reemplaza esos datos; añade una capa enriquecida y revisable.

## 4.2. Usuarios

- **Administrador:** genera, revisa y aprueba metadatos IA.
- **Operador:** consume los metadatos indirectamente en búsqueda y venta asistida.
- **Agente de inventario:** usa los metadatos para sustitutos, rotación y argumentarios por hotel.

## 4.3. Datos a generar o extraer

| Campo | Descripción | Ejemplo |
|---|---|---|
| `PieceType` | Tipo de joya | anillo, pendientes, collar, pulsera |
| `Material` | Material principal si se puede extraer | plata, acero, baño oro |
| `StoneType` | Piedra preciosa o decorativa si aplica | perla, circonita, coral |
| `ColorTags` | Colores/acabados | dorado, plateado, verde |
| `StyleTags` | Estilo comercial | minimalista, boho, elegante, llamativo |
| `OccasionTags` | Ocasiones de venta | regalo, boda, diario, verano |
| `SizeLabel` | Talla o variante | S, M, L, ajustable |
| `VariantGroupKey` | Agrupación de variantes | anillo-erizo-mar |
| `SalesPitchShort` | Frase de venta breve | “Pieza original inspirada en el mar, fácil de combinar.” |
| `OperatorHint` | Aviso interno | “Confirmar talla antes de vender.” |
| `CareInstructions` | Cuidados básicos | “Evitar perfumes y agua salada.” |
| `SearchAliases` | Sinónimos y búsquedas alternativas | anillo marino, erizo, textura mar |
| `AiConfidence` | Confianza de extracción | 0-1 |
| `ReviewStatus` | Estado de revisión | Pending, Approved, Rejected |

## 4.4. Agrupación de variantes

Debe introducirse un concepto de **familia o grupo de variantes** para productos visualmente parecidos.

Ejemplo:

```text
ProductFamily: Anillo erizo de mar
Variantes:
- SKU ERIZO-S · talla S
- SKU ERIZO-M · talla M
- SKU ERIZO-L · talla L
```

### Reglas funcionales

- Si varios productos comparten `VariantGroupKey`, la UI debe mostrar que existen variantes.
- En búsqueda y venta asistida, la talla/variante debe mostrarse de forma destacada.
- Si la talla no se puede extraer con confianza, el producto debe quedar como “pendiente de revisión”.
- El sistema debe alertar al admin si detecta productos parecidos sin grupo de variante.

## 4.5. Flujo de administración

```text
Admin abre catálogo
  -> selecciona producto o lote
  -> pulsa “Generar metadatos IA”
  -> sistema genera ProductAiProfile
  -> admin revisa campos críticos
  -> admin aprueba/rechaza
  -> si aprueba, se genera/actualiza embedding textual
  -> producto queda disponible para búsqueda semántica y recomendaciones
```

## 4.6. Modelo de datos propuesto

### `ProductAiProfile`

```text
Id uuid PK
ProductId uuid FK Product(Id)
PieceType string nullable
Material string nullable
StoneType string nullable
SizeLabel string nullable
VariantGroupKey string nullable
ColorTagsJson text
StyleTagsJson text
OccasionTagsJson text
SearchAliasesJson text
SalesPitchShort text nullable
OperatorHint text nullable
CareInstructions text nullable
AiConfidence decimal
ReviewStatus enum: Pending, Approved, Rejected
GeneratedByProvider string
GeneratedByModel string
SourceHash string
ReviewedByUserId uuid nullable
ReviewedAt timestamp nullable
CreatedAt timestamp
UpdatedAt timestamp
```

### `ProductTextEmbedding`

```text
Id uuid PK
ProductId uuid FK Product(Id)
EmbeddingModel string
EmbeddingVector vector/json/text según BBDD vectorial disponible
SourceText text
SourceHash string
CreatedAt timestamp
UpdatedAt timestamp
```

### `ProductFamily` opcional

```text
Id uuid PK
Name string
VariantGroupKey string unique
Description text nullable
CreatedAt timestamp
UpdatedAt timestamp
```

### `ProductFamilyMember` opcional

```text
Id uuid PK
ProductFamilyId uuid FK
ProductId uuid FK
VariantLabel string nullable
SortOrder int
```

## 4.7. Embeddings

Usar embeddings textuales específicos para catálogo de joyería si están disponibles. El texto fuente del embedding debe ser controlado y reproducible.

Ejemplo de `SourceText`:

```text
SKU: ERIZO-M
Nombre: Anillo erizo de mar talla M
Descripción: ...
Colección: Verano
Tipo: anillo
Material: plata
Piedra: ninguna
Estilo: marino, original, verano
Ocasiones: regalo, diario, verano
Aliases: anillo erizo, anillo marino
```

### Reglas

- Regenerar embedding si cambia `SourceHash`.
- No mezclar embeddings visuales con embeddings semánticos.
- Mantener versión de modelo en cada embedding.
- Para menos de 1000 productos, el coste y latencia deben ser bajos incluso con búsqueda híbrida.

## 4.8. Endpoints sugeridos

```http
POST /api/ai/catalog/products/{productId}/enrich
POST /api/ai/catalog/products/enrich-batch
GET  /api/ai/catalog/products/{productId}/profile
PUT  /api/ai/catalog/products/{productId}/profile/review
POST /api/ai/catalog/products/{productId}/embedding/regenerate
GET  /api/ai/catalog/quality-issues
```

## 4.9. Criterios de aceptación

- El admin puede generar metadatos IA para un producto.
- El admin puede revisar y aprobar/rechazar metadatos.
- El sistema identifica tipo de pieza, material y piedra cuando aparecen en nombre/descripción.
- El sistema marca como baja confianza los campos inciertos.
- Los productos aprobados generan embedding textual.
- Las variantes S/M/L quedan visibles y agrupadas cuando se detectan.
- Ningún dato generado por IA modifica `Product.Name`, `Product.SKU` o `Product.Price` sin acción explícita del admin.

## 4.10. Beneficios y ROI

### Directos

- Mejora la búsqueda de productos.
- Reduce errores de selección.
- Facilita venta por operadores no expertos.
- Permite recomendar sustitutos y complementarios.

### Indirectos

- Catálogo más limpio y explotable.
- Base para inventario inteligente.
- Base para argumentario por hotel.
- Menos dependencia de formación manual.

### KPIs

- `% productos con ProductAiProfile aprobado`.
- `% productos con VariantGroupKey cuando aplica`.
- `% productos con metadatos de baja confianza`.
- `tiempo medio de búsqueda de producto`.
- `errores/correcciones de producto por POS`.

---

# 5. Funcionalidad 2 - Búsqueda semántica + venta asistida

## 5.1. Objetivo

Ayudar al operador a encontrar el producto correcto y vender mejor, usando búsqueda híbrida y metadatos enriquecidos.

No se plantea como un chat generalista, sino como una interfaz de búsqueda/venta con resultados estructurados.

## 5.2. Casos de uso

1. Buscar producto por descripción natural.
2. Desambiguar productos parecidos.
3. Recomendar alternativas similares.
4. Recomendar complementarios.
5. Mostrar frase de venta y avisos internos.
6. Ayudar cuando un producto no tiene stock.

## 5.3. Ejemplos de consultas

```text
anillo erizo talla M
pendientes dorados pequeños
regalo de menos de 80 euros
algo parecido a este anillo pero más barato
collar para combinar con pendientes dorados
```

## 5.4. Reglas de filtrado obligatorias

Antes de rankear resultados, aplicar:

1. Producto activo.
2. Producto visible/asignado al POS del operador.
3. Registro `Inventory.IsActive = true` para ese POS.
4. Permisos por rol y POS.
5. Stock disponible si el flujo es venta inmediata.

Si el producto tiene `Quantity = 0`, puede mostrarse solo como no vendible y con sustitutos sugeridos.

## 5.5. Ranking híbrido

Orden recomendado:

```text
score_total =
  score_sku_exacto * peso_alto
  + score_nombre * peso_alto
  + score_semantico * peso_medio
  + score_tags * peso_medio
  + score_disponibilidad_pos * peso_alto
  + score_rotacion_pos * peso_medio
  + score_prioridad_comercial * peso_bajo_medio
  - penalizacion_stock_cero
  - penalizacion_variante_ambigua
```

## 5.6. UX recomendada

### Pantalla o panel “Buscar con ayuda”

Elementos:

- input de búsqueda natural;
- filtros rápidos: tipo, material, piedra, color, precio, talla;
- POS actual preseleccionado;
- cards de resultado con foto, SKU, nombre, talla, precio, stock, motivo de recomendación;
- botón “Seleccionar para venta”;
- bloque “También puede encajar”;
- bloque “Si no hay stock, ofrecer sustituto”.

### Card de resultado

```text
[Foto]
Anillo erizo de mar · talla M
SKU: ERIZO-M
Precio: 65 €
Stock Hotel A: 2
Motivo: coincide con anillo, marino, talla M, disponible en este hotel.
Aviso: existen variantes S y L muy similares.
[Seleccionar para venta]
```

## 5.7. Desambiguación

Cuando varios productos sean similares:

- agrupar por familia;
- mostrar diferencias principales;
- pedir confirmación de talla/material/precio;
- destacar foto principal y talla.

Ejemplo:

```text
He encontrado 3 variantes del Anillo erizo de mar.
Confirma talla antes de vender:
- S · stock 1 · SKU ERIZO-S
- M · stock 2 · SKU ERIZO-M
- L · stock 0 · SKU ERIZO-L · no vendible, ver sustitutos
```

## 5.8. Modelo de datos adicional

### `ProductSearchEvent`

```text
Id uuid PK
UserId uuid FK
PointOfSaleId uuid FK
SearchText text
FiltersJson text
ResultsJson text
SelectedProductId uuid nullable
SelectedFromRank int nullable
CreatedSaleId uuid nullable
SearchDurationMs int nullable
CreatedAt timestamp
```

### `ProductRecommendation`

```text
Id uuid PK
ProductId uuid FK
RecommendedProductId uuid FK
RecommendationType enum: Similar, Complementary, Substitute, Upsell, Downsell
Score decimal
Reason text
GeneratedBy string: Rule, Embedding, Manual, Hybrid
IsActive bool
CreatedAt timestamp
UpdatedAt timestamp
```

## 5.9. Endpoints sugeridos

```http
POST /api/products/search/semantic
GET  /api/products/{productId}/sales-assist
GET  /api/products/{productId}/recommendations?pointOfSaleId={id}
GET  /api/products/{productId}/variants
POST /api/products/search-events
```

## 5.10. Criterios de aceptación

- El operador puede buscar con texto natural.
- Los resultados se limitan a productos visibles para su POS.
- Los resultados muestran stock real y precio real.
- Las variantes se agrupan y desambigüan.
- Si un producto está sin stock, el sistema muestra sustitutos disponibles.
- La selección desde búsqueda puede abrir/prellenar el flujo de venta existente.
- El sistema registra eventos de búsqueda y selección para análisis posterior.

## 5.11. Beneficios y ROI

### Directos

- Menos errores al seleccionar producto.
- Menor tiempo de venta.
- Más ventas de sustitutos cuando no hay stock.
- Mejor venta por operadores de hoteles.

### Indirectos

- Datos para detectar productos problemáticos.
- Datos para mejorar catálogo.
- Base para medir adopción y ROI.

### KPIs

- `tiempo búsqueda -> selección`.
- `% ventas iniciadas desde búsqueda asistida`.
- `% consultas sin resultado`.
- `% selección rank 1 / rank 3`.
- `% ventas con sustituto sugerido`.
- `ticket medio ventas asistidas vs no asistidas`.

---

# 6. Funcionalidad 3 - Recomendaciones de inventario

## 6.1. Objetivo

Convertir la reposición manual periódica en un proceso asistido por datos:

- qué reponer;
- dónde reponer;
- qué mover entre POS;
- qué producto similar sugerir si no hay unidades para reponer;
- qué preparar físicamente en una packing list;
- qué liquidar, mover o priorizar por baja rotación;
- qué argumento comercial usar por hotel.

## 6.2. Principio clave

El agente de inventario **propone**, pero el administrador **aprueba**. En la primera fase no debe aplicar movimientos automáticamente.

## 6.3. Subfuncionalidades

## 6.3.1. Reposición recomendada

### Descripción

Generar recomendaciones de reposición por producto y POS usando ventas recientes, stock actual y prioridad del punto de venta.

### Señales mínimas

```text
sales_7d
sales_30d
sales_60d
current_stock
stock_in_other_pos
days_since_last_sale
avg_daily_sales_30d
estimated_days_to_stockout
is_top_seller_in_pos
```

### Reglas iniciales

```text
Si current_stock = 0 y sales_30d > 0
  -> recomendar reposición alta

Si estimated_days_to_stockout < 14 días y sales_30d >= 2
  -> recomendar reposición media/alta

Si producto vendido desde última reposición y stock no recuperado
  -> recomendar reposición
```

---

## 6.3.2. Motor de sustitutos por falta de stock

### Descripción

Cuando un producto no se puede reponer porque no hay stock disponible en otros POS o almacén, el sistema debe sugerir productos similares.

También debe sugerir sustitutos para productos top sellers aunque todavía haya stock, como plan de contingencia.

### Casos de uso

1. Producto vendido y stock actual 0.
2. Producto top seller con riesgo de rotura.
3. Producto sin unidades disponibles para traspasar.
4. Producto descatalogado o no reponible.
5. Producto con variantes similares disponibles.

### Criterios de similitud

| Criterio | Peso recomendado |
|---|---:|
| Mismo tipo de pieza | Alto |
| Misma familia/variante | Alto |
| Mismo material/color | Alto |
| Precio parecido | Medio-alto |
| Estilo/tags similares | Medio |
| Misma colección | Medio |
| Disponible en el POS destino | Alto |
| Stock sobrante en otro POS | Medio-alto |
| Buena rotación en ese hotel | Medio |
| Margen/prioridad comercial | Bajo-medio |

### Salida esperada

```text
Producto no reponible: Anillo erizo de mar M
Motivo: stock global 0
Sustitutos sugeridos:
1. Anillo erizo de mar L
   Motivo: misma familia, stock 2 en tienda central, precio similar.
2. Anillo coral dorado M
   Motivo: mismo tipo, estilo marino, precio similar, stock 3 en Hotel A.
```

### Modelo de datos

```text
InventoryRecommendationAlternative
- Id uuid PK
- InventoryRecommendationId uuid FK
- SubstituteProductId uuid FK Product(Id)
- Score decimal
- Reason text
- StockAtTargetPos int
- StockGlobal int
- PriceDifference decimal
- SimilaritySignalsJson text
- CreatedAt timestamp
```

### Criterios de aceptación

- Si una recomendación de reposición no puede satisfacerse con stock disponible, se generan sustitutos.
- Los sustitutos deben estar activos y tener datos de stock reales.
- Los sustitutos deben explicar el motivo de similitud.
- El admin puede aceptar el sustituto, rechazarlo o marcarlo como no adecuado.
- El feedback del admin se usa para mejorar futuras recomendaciones.

---

## 6.3.3. Traslados sugeridos entre POS

### Descripción

Sugerir movimientos desde POS con stock parado o sobrante hacia POS con ventas recientes o riesgo de rotura.

### Regla ejemplo

```text
Si Hotel A tiene stock 0 y ventas_30d >= 2,
y Tienda Central tiene stock >= 3 y ventas_60d = 0,
-> sugerir mover 2 unidades desde Tienda Central a Hotel A.
```

### Criterios de aceptación

- La recomendación indica origen, destino, producto y cantidad.
- La recomendación incluye señales: stock origen, stock destino, ventas recientes destino, días sin venta origen.
- No se sugieren traslados que dejen el origen por debajo de su mínimo configurado si existe política.

---

## 6.3.4. Reposición con packing list

### Descripción

Convertir recomendaciones aprobadas en una lista física de preparación por hotel/POS.

La packing list debe poder imprimirse o consultarse desde móvil.

### Contenido mínimo

```text
Packing List - Hotel A - 2026-07-22

1. SKU ERIZO-M · Anillo erizo de mar M
   Cantidad: 2
   Origen: Tienda central
   Motivo: vendido 4 veces en 30 días, stock actual 0

2. SKU PEND-DOR-01 · Pendientes dorados pequeños
   Cantidad: 1
   Origen: Tienda central
   Motivo: stock bajo, top seller del hotel

Sustituto incluido:
3. SKU ANIL-CORAL-M · Anillo coral M
   Sustituye a: ERIZO-M
   Motivo: ERIZO-M sin stock global; producto similar disponible
```

### Estados

```text
Draft -> Approved -> Prepared -> Delivered -> Applied -> Cancelled
```

### Modelo de datos

```text
InventoryPackingList
- Id uuid PK
- PointOfSaleId uuid FK
- Status enum: Draft, Approved, Prepared, Delivered, Applied, Cancelled
- GeneratedFromRunId uuid nullable
- Notes text nullable
- CreatedByUserId uuid nullable
- ApprovedByUserId uuid nullable
- CreatedAt timestamp
- UpdatedAt timestamp
```

```text
InventoryPackingListItem
- Id uuid PK
- PackingListId uuid FK
- ProductId uuid FK
- SourcePointOfSaleId uuid nullable
- Quantity int
- Reason text
- RecommendationId uuid nullable
- SubstituteForProductId uuid nullable
- Status enum: Pending, Prepared, Delivered, Applied, Skipped
- CreatedAt timestamp
- UpdatedAt timestamp
```

### Criterios de aceptación

- El admin puede generar una packing list desde recomendaciones aprobadas.
- La packing list agrupa productos por POS destino.
- Cada línea muestra foto, SKU, nombre, cantidad, origen y motivo.
- Se pueden incluir sustitutos cuando el producto original no está disponible.
- La packing list no modifica stock automáticamente hasta que el admin confirme la aplicación o use el flujo existente de ajuste/traspaso.
- El sistema registra quién aprobó y quién marcó como aplicada la lista.

---

## 6.3.5. Recomendaciones de liquidación / rotación

### Descripción

Detectar productos que deberían moverse, destacarse, promocionarse o liquidarse por baja rotación.

### Casos

1. Stock parado en un hotel.
2. Stock alto en tienda central sin ventas recientes.
3. Producto con ventas en otro POS pero parado donde está.
4. Producto de temporada que no rota.
5. Producto con muchas unidades y baja demanda.

### Tipos de recomendación

```text
MoveToBetterPOS
PromoteInAssistedSale
UseAsComplementaryProduct
ApplyDiscountCandidate
ReviewProductData
DeactivateOrLiquidate
```

### Reglas iniciales

```text
Si stock > 0 y days_since_last_sale > 90
  -> marcar como stock parado

Si stock parado en POS A y ventas_60d > 0 en POS B
  -> sugerir traslado a POS B

Si stock global alto y ventas bajas en todos los POS
  -> sugerir promoción/liquidación

Si producto sin ventas y ficha IA incompleta
  -> sugerir revisar catálogo antes de liquidar
```

### Salida esperada

```text
Producto: Collar dorado X
Situación: 6 unidades en Hotel B, 0 ventas en 90 días.
Recomendación: mover 3 unidades al Hotel A.
Motivo: Hotel A ha vendido productos similares 5 veces en 60 días.
Alternativa: marcar como complemento recomendado en ventas de pendientes dorados.
```

### Criterios de aceptación

- El sistema detecta stock parado por POS.
- El sistema diferencia entre “mover”, “promocionar”, “usar como complemento” y “liquidar”.
- El admin puede aceptar/rechazar cada recomendación.
- Las recomendaciones de liquidación requieren confirmación explícita y no cambian precios automáticamente.

---

## 6.3.6. Argumentario por hotel

### Descripción

Generar un perfil comercial por hotel/POS a partir de ventas históricas, catálogo e inventario.

El objetivo es que las recomendaciones de venta e inventario tengan contexto local.

### Señales por POS

```text
top_piece_types
top_materials
top_price_ranges
top_collections
average_ticket
best_selling_products
slow_moving_products
substitute_acceptance_rate
seasonality_notes opcional
```

### Salida esperada

```text
Hotel A - Argumentario comercial

Perfil de venta:
- Funcionan mejor piezas doradas y discretas.
- Rango de precio más frecuente: 50-90 €.
- Los anillos y pendientes tienen mayor rotación.

Recomendación operativa:
- Priorizar reposición de anillos talla M/L.
- Mantener sustitutos dorados para top sellers.
- Usar collares finos como complemento en ventas de pendientes.
```

### Uso en otras funcionalidades

| Funcionalidad | Uso del argumentario |
|---|---|
| Venta asistida | Ordenar recomendaciones según lo que vende mejor en ese hotel. |
| Sustitutos | Priorizar sustitutos que encajan con el perfil del hotel. |
| Reposición | Ajustar cantidades sugeridas. |
| Rotación | Decidir si conviene mover producto a otro hotel. |
| Packing list | Explicar por qué se prepara cada producto. |

### Modelo de datos

```text
PointOfSaleSalesProfile
- Id uuid PK
- PointOfSaleId uuid FK
- ProfilePeriodStart date
- ProfilePeriodEnd date
- TopPieceTypesJson text
- TopMaterialsJson text
- TopPriceRangesJson text
- TopCollectionsJson text
- AverageTicket decimal
- Summary text
- RecommendationsText text
- GeneratedByModel string nullable
- CreatedAt timestamp
```

### Criterios de aceptación

- El admin puede generar/ver un argumentario por hotel.
- El sistema usa ventas históricas del POS para crear el perfil.
- El argumentario no debe inventar datos: las afirmaciones deben derivarse de métricas calculadas.
- El argumentario se usa como señal en búsqueda, sustitutos e inventario.

---

## 6.4. Modelo de datos general para inventario inteligente

### `InventoryRecommendation`

```text
Id uuid PK
RecommendationType enum:
  Replenish,
  Transfer,
  Substitute,
  Rotate,
  Liquidate,
  Promote,
  Review
ProductId uuid FK Product(Id)
FromPointOfSaleId uuid nullable FK PointOfSale(Id)
ToPointOfSaleId uuid nullable FK PointOfSale(Id)
SuggestedQuantity int nullable
Priority enum: High, Medium, Low
Reason text
SignalsJson text
Status enum: Proposed, Approved, Rejected, Applied, Expired
CreatedByRunId uuid nullable
ReviewedByUserId uuid nullable
ReviewedAt timestamp nullable
AppliedAt timestamp nullable
CreatedAt timestamp
UpdatedAt timestamp
```

### `InventoryPolicy`

```text
Id uuid PK
ProductId uuid nullable FK Product(Id)
CollectionId uuid nullable FK Collection(Id)
PointOfSaleId uuid nullable FK PointOfSale(Id)
MinStock int nullable
TargetStock int nullable
MaxStock int nullable
ReplenishmentFrequencyDays int nullable
Priority enum: High, Medium, Low
IsActive bool
CreatedAt timestamp
UpdatedAt timestamp
```

### `InventoryAgentRun`

```text
Id uuid PK
StartedAt timestamp
CompletedAt timestamp nullable
Status enum: Running, Completed, Failed
RecommendationsCreated int
ProviderUsed string nullable
ModelUsed string nullable
ErrorMessage text nullable
```

## 6.5. Servicios backend sugeridos

```text
DemandSignalService
  Calcula ventas, velocidad, días de cobertura y señales por producto/POS.

ProductSubstitutionService
  Calcula sustitutos usando metadatos IA, embeddings, stock y precio.

InventoryRecommendationService
  Genera recomendaciones de reposición, traslado, rotación y liquidación.

PackingListService
  Convierte recomendaciones aprobadas en listas de preparación.

PointOfSaleSalesProfileService
  Genera argumentario y perfil comercial por hotel/POS.

InventoryNarrativeService
  Usa LLM solo para redactar motivos y resúmenes, no para calcular stock.
```

## 6.6. Endpoints sugeridos

```http
POST /api/ai/inventory/recommendations/generate
GET  /api/ai/inventory/recommendations
POST /api/ai/inventory/recommendations/{id}/approve
POST /api/ai/inventory/recommendations/{id}/reject
POST /api/ai/inventory/recommendations/{id}/mark-applied

GET  /api/ai/inventory/products/{productId}/substitutes?pointOfSaleId={id}
POST /api/ai/inventory/packing-lists/from-recommendations
GET  /api/ai/inventory/packing-lists/{id}
POST /api/ai/inventory/packing-lists/{id}/approve
POST /api/ai/inventory/packing-lists/{id}/mark-applied

POST /api/ai/inventory/pos/{pointOfSaleId}/sales-profile/generate
GET  /api/ai/inventory/pos/{pointOfSaleId}/sales-profile
```

## 6.7. UX recomendada

### Pantalla: Inventario inteligente

Pestañas:

1. **Reponer**
2. **Sustituir**
3. **Trasladar**
4. **Packing lists**
5. **Rotación / liquidación**
6. **Argumentario por hotel**

### Card de recomendación

```text
[Foto]
SKU ERIZO-M · Anillo erizo de mar M
Destino: Hotel A
Acción: Reponer 2 uds
Prioridad: Alta
Motivo: 4 ventas en 30 días, stock actual 0.
Origen sugerido: Tienda Central, stock 5.

[Ver sustitutos] [Aprobar] [Rechazar]
```

## 6.8. Criterios de aceptación globales

- El admin puede generar recomendaciones de inventario bajo demanda.
- El sistema propone reposición usando ventas y stock reales.
- El sistema propone sustitutos cuando no hay stock suficiente para reponer.
- El sistema genera packing lists desde recomendaciones aprobadas.
- El sistema detecta stock parado y propone rotación/liquidación.
- El sistema genera un argumentario por hotel basado en ventas históricas.
- Ninguna recomendación modifica stock o precio sin acción explícita del admin.
- Todas las recomendaciones guardan señales/métricas usadas para justificar la decisión.

## 6.9. Beneficios y ROI

### Directos

- Menos roturas de stock.
- Menos tiempo revisando inventario manualmente.
- Mejor distribución de stock entre hoteles.
- Menos ventas perdidas por producto no disponible.
- Más ventas por sustitutos adecuados.

### Indirectos

- Mejor conocimiento del comportamiento comercial por hotel.
- Menos stock inmovilizado.
- Mejor preparación física de reposiciones.
- Mayor disciplina operativa.

### KPIs

| KPI | Objetivo |
|---|---|
| Días sin stock en top sellers | bajar |
| Recomendaciones aceptadas por admin | subir |
| Ventas de sustitutos sugeridos | subir |
| Tiempo semanal dedicado a preparar reposición | bajar |
| Stock parado > 90 días | bajar |
| Packing lists aplicadas sin incidencias | subir |
| Ventas por hotel tras aplicar recomendaciones | subir |

---

# 7. Arquitectura técnica recomendada

## 7.1. Módulo IA dentro del monolito

Mantener la arquitectura actual y añadir servicios dentro del backend .NET.

```text
React SPA
  -> ASP.NET Core API
    -> Application Services
      -> AiCatalogService
      -> ProductSemanticSearchService
      -> ProductSubstitutionService
      -> InventoryRecommendationService
      -> PackingListService
    -> Infrastructure
      -> PostgreSQL / BBDD vectorial
      -> S3/Blob para fotos
      -> AI Provider Gateway
```

## 7.2. Abstracción de proveedores IA

```csharp
public interface IAiTextProvider
{
    Task<T> GenerateJsonAsync<T>(AiJsonRequest request, CancellationToken ct);
}

public interface IAiEmbeddingProvider
{
    Task<float[]> EmbedAsync(string text, CancellationToken ct);
}
```

## 7.3. Uso recomendado de IA

| Caso | IA generativa | Embeddings | Reglas/SQL |
|---|---:|---:|---:|
| Extraer metadatos catálogo | Sí | No | Validación |
| Generar sales pitch | Sí | No | No |
| Búsqueda semántica | No | Sí | Sí |
| Sustitutos | Opcional para explicación | Sí | Sí |
| Reposición | No para cálculo | No | Sí |
| Packing list | Opcional para resumen | No | Sí |
| Liquidación/rotación | Opcional para explicación | Opcional | Sí |
| Argumentario por hotel | Sí para redacción | No | Sí para métricas |

## 7.4. Logging y control de costes

### `AiUsageLog`

```text
Id uuid PK
Feature string
Provider string
Model string
InputTokens int nullable
OutputTokens int nullable
EstimatedCost decimal nullable
UserId uuid nullable
CreatedAt timestamp
```

Reglas:

- Cachear respuestas de catálogo por `SourceHash`.
- No llamar a LLM para cada búsqueda si ya existen embeddings y perfiles.
- Usar LLM barato para redacción y JSON estructurado.
- Limitar generación por lote a admins.

---

# 8. Roadmap sugerido

## Fase 1 - Base de catálogo

- Crear `ProductAiProfile`.
- Generar metadatos por lote.
- Revisar/aprobar metadatos.
- Crear embeddings textuales.
- Agrupar variantes.

## Fase 2 - Búsqueda semántica + venta asistida

- Búsqueda híbrida.
- Cards de venta asistida.
- Desambiguación de variantes.
- Sustitutos si no hay stock.
- Logging de búsquedas y selección.

## Fase 3 - Inventario inteligente básico

- Reposición recomendada.
- Traslados sugeridos.
- Motor de sustitutos.
- Pantalla de recomendaciones.

## Fase 4 - Packing list + rotación

- Packing lists imprimibles/consultables.
- Estados de preparación.
- Stock parado.
- Recomendaciones de mover/promocionar/liquidar.

## Fase 5 - Argumentario por hotel

- Perfil comercial por POS.
- Integración en búsqueda, sustitutos e inventario.
- KPIs de impacto por hotel.

---

# 9. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| IA extrae mal material/talla | Revisión humana y campo `AiConfidence`. |
| Operador selecciona variante errónea | Agrupar variantes y mostrar talla de forma prominente. |
| Sustitutos poco adecuados | Feedback admin y scoring explicable. |
| Recomendaciones de inventario demasiado ruidosas | Prioridad, filtros y umbrales configurables. |
| Coste IA innecesario | Cache, generación por lote, embeddings persistidos. |
| Cambio de stock no autorizado | Todas las acciones sensibles requieren aprobación. |
| Métricas poco fiables por histórico corto | Empezar con reglas simples y recalibrar con datos. |

---

# 10. Decisiones abiertas

1. Definir si existe almacén/tienda central como POS origen preferente.
2. Definir umbrales iniciales por tipo de hotel: principal vs resto.
3. Definir proveedor de embeddings y modelo.
4. Definir si `ProductFamily` será entidad explícita o solo `VariantGroupKey` en `ProductAiProfile`.
5. Definir si las packing lists aplicadas crean movimientos de inventario directamente o solo guían el ajuste manual existente.
6. Definir si se capturará feedback del operador en sustitutos y venta asistida.

---

# 11. Resumen ejecutivo

La recomendación es construir una base común de inteligencia de catálogo y reutilizarla en dos direcciones:

1. **Venta asistida:** búsqueda semántica, desambiguación, sustitutos y argumentarios.
2. **Inventario inteligente:** reposición, traslados, sustitutos, packing lists, rotación/liquidación y argumentario por hotel.

La pieza central es el modelo:

```text
ProductAiProfile + ProductTextEmbedding + ProductFamily/VariantGroup + ProductRecommendation
```

Y para inventario:

```text
InventoryRecommendation + InventoryRecommendationAlternative + InventoryPackingList + PointOfSaleSalesProfile
```

Con este enfoque se evita depender de reconocimiento visual y se obtiene valor más rápido: menos errores, más ventas de sustitutos, mejor reposición y menos trabajo administrativo.
