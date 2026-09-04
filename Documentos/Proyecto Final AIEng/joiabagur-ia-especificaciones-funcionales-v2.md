# Especificaciones funcionales IA - Joiabagur PV

**Versión:** 2  
**Fecha:** 2026-07-24  
**Repositorio base:** https://github.com/skydr4g0n-it/joiabagur-pv/  
**Alcance:** enriquecimiento de catálogo, búsqueda semántica + venta asistida y recomendaciones de inventario.  
**Fuera de alcance:** reconocimiento visual, chatbot generalista, virtual try-on, fine-tuning, agentes que modifiquen stock sin aprobación humana.

---

## 0. Cambios aplicados en esta versión

### Cambios solicitados

1. `Material` pasa a ser un array de materiales: `Materials[]`.
2. Se eliminan del perfil IA de producto los campos:
   - `VariantGroupKey`
   - `SalesPitchShort`
   - `OperatorHint`
   - `CareInstructions`
   - `SearchAliases`

### Impacto funcional y adaptación

| Campo eliminado | Funcionalidad afectada | Adaptación propuesta |
|---|---|---|
| `VariantGroupKey` | Agrupación de variantes S/M/L y desambiguación | Sustituir por entidad explícita `ProductFamily` + `ProductFamilyMember`. La familia no depende de una clave textual dentro del perfil IA. |
| `SalesPitchShort` | Venta asistida | No guardar frase comercial por producto. Mostrar `Reason`, señales de recomendación y argumentario por hotel. Si se quiere texto comercial, generarlo dinámicamente desde metadatos aprobados. |
| `OperatorHint` | Avisos internos al operador | Generar avisos mediante reglas: producto con variantes, talla ausente, stock bajo, productos similares, etc. No persistir texto libre generado por IA. |
| `CareInstructions` | Ficha ampliada de producto | Se elimina de esta fase. No afecta al flujo interno de POS. Puede recuperarse en una fase futura si hay e-commerce o comunicación al cliente. |
| `SearchAliases` | Búsqueda semántica | La búsqueda usará nombre, descripción, colección, tipo, materiales, piedra, colores, estilos, ocasiones, talla y familia. No se guarda lista de sinónimos. |

---

## 1. Contexto y objetivos

Joiabagur PV es una aplicación interna para puntos de venta de joyería. La app ya dispone de catálogo, fotos, ventas, inventario por punto de venta, operadores asignados a POS, roles, movimientos de inventario, devoluciones y stock bajo.

Objetivos de esta fase:

1. **Vender más** mediante catálogo enriquecido, venta asistida, sustitutos y recomendaciones.
2. **Reducir errores de selección de producto**, especialmente en hoteles con operadores que no conocen todo el catálogo.
3. **Ahorrar tiempo administrativo** en reposición, rotación y preparación de mercancía.
4. **Mejorar la distribución de stock** entre hoteles y tienda central.

---

## 2. Principios de diseño

1. **Datos estructurados antes que IA compleja.** El valor vendrá de estructurar tipo de joya, materiales, talla, familia, stock y ventas.
2. **La IA no es fuente de verdad para stock ni precio.** Stock, precio, permisos y ventas salen siempre de PostgreSQL/API.
3. **Aprobación humana.** La IA propone metadatos, sustitutos, reposiciones y traslados; el administrador aprueba.
4. **Coste bajo.** Generar metadatos una vez y recalcular solo si cambia el producto.
5. **Control por POS.** Los operadores solo ven productos activos y asignados a su punto de venta.
6. **Familias explícitas para variantes.** Para productos visualmente parecidos, la talla/variante debe mostrarse de forma prominente.

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

La funcionalidad no reemplaza `Product.Name`, `Product.SKU`, `Product.Description`, `Product.Price` ni `Product.CollectionId`; añade una capa revisable por administración.

## 4.2. Usuarios

- **Administrador:** genera, revisa y aprueba metadatos IA.
- **Operador:** consume los metadatos en búsqueda y venta asistida.
- **Agente de inventario:** usa los metadatos para sustitutos, rotación y argumentarios por hotel.

## 4.3. Datos a generar o extraer

| Campo | Tipo | Descripción | Ejemplo |
|---|---|---|---|
| `PieceType` | string | Tipo de joya | anillo, pendientes, collar, pulsera |
| `Materials` | string[] | Materiales detectados o confirmados | ["plata", "baño oro"] |
| `StoneType` | string nullable | Piedra preciosa o decorativa si aplica | perla, circonita, coral |
| `ColorTags` | string[] | Colores/acabados | dorado, plateado, verde |
| `StyleTags` | string[] | Estilo comercial | minimalista, boho, elegante, llamativo |
| `OccasionTags` | string[] | Ocasiones de venta | regalo, boda, diario, verano |
| `SizeLabel` | string nullable | Talla o variante | S, M, L, ajustable |
| `AiConfidence` | decimal | Confianza global de extracción | 0.82 |
| `ReviewStatus` | enum | Estado de revisión | Pending, Approved, Rejected |

## 4.4. Agrupación de variantes mediante `ProductFamily`

Para productos visualmente parecidos, se introduce una entidad explícita de familia.

Ejemplo:

```text
ProductFamily: Anillo erizo de mar
Variantes:
- SKU ERIZO-S · talla S
- SKU ERIZO-M · talla M
- SKU ERIZO-L · talla L
```

### Reglas funcionales

- Si varios productos pertenecen a la misma `ProductFamily`, la UI debe mostrar que existen variantes.
- En búsqueda y venta asistida, `SizeLabel` debe mostrarse de forma destacada.
- Si la talla no se puede extraer con confianza, el producto queda pendiente de revisión.
- El sistema debe alertar al admin si detecta productos parecidos sin familia asignada.
- La agrupación de familias debe poder editarse manualmente.

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
MaterialsJson text               -- array string[]
StoneType string nullable
SizeLabel string nullable
ColorTagsJson text               -- array string[]
StyleTagsJson text               -- array string[]
OccasionTagsJson text            -- array string[]
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

### `ProductFamily`

```text
Id uuid PK
Name string
Description text nullable
CreatedAt timestamp
UpdatedAt timestamp
```

### `ProductFamilyMember`

```text
Id uuid PK
ProductFamilyId uuid FK
ProductId uuid FK
VariantLabel string nullable     -- S, M, L, ajustable, talla 12...
SortOrder int
CreatedAt timestamp
UpdatedAt timestamp
```

## 4.7. Embeddings

Usar embeddings textuales para búsqueda semántica de catálogo. El texto fuente debe ser reproducible y generado solo con datos reales o aprobados.

Ejemplo de `SourceText`:

```text
SKU: ERIZO-M
Nombre: Anillo erizo de mar talla M
Descripción: ...
Colección: Verano
Tipo: anillo
Materiales: plata, baño oro
Piedra: ninguna
Talla: M
Familia: Anillo erizo de mar
Estilo: marino, original, verano
Ocasiones: regalo, diario, verano
Colores: dorado
```

### Reglas

- Regenerar embedding si cambia `SourceHash`.
- No mezclar embeddings visuales con embeddings semánticos.
- Mantener versión de modelo en cada embedding.
- Para menos de 1000 productos, la búsqueda puede ser híbrida con bajo coste.

## 4.8. Endpoints sugeridos

```http
POST /api/ai/catalog/products/{productId}/enrich
POST /api/ai/catalog/products/enrich-batch
GET  /api/ai/catalog/products/{productId}/profile
PUT  /api/ai/catalog/products/{productId}/profile/review
POST /api/ai/catalog/products/{productId}/embedding/regenerate
GET  /api/ai/catalog/quality-issues
POST /api/product-families
PUT  /api/product-families/{familyId}/members
```

## 4.9. Criterios de aceptación

- El admin puede generar metadatos IA para un producto.
- El admin puede revisar y aprobar/rechazar metadatos.
- `Materials` admite múltiples valores.
- El sistema identifica tipo de pieza, materiales y piedra cuando aparecen en nombre/descripción.
- El sistema marca como baja confianza los campos inciertos.
- Los productos aprobados generan embedding textual.
- Las variantes S/M/L quedan visibles y agrupadas mediante `ProductFamily`.
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
- `% productos con ProductFamily cuando aplica`.
- `% productos con Materials revisados`.
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
5. Mostrar motivos de recomendación y señales relevantes.
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

```text
score_total =
  score_sku_exacto * peso_alto
  + score_nombre * peso_alto
  + score_semantico * peso_medio
  + score_tags * peso_medio
  + score_materiales * peso_medio
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
- filtros rápidos: tipo, materiales, piedra, color, precio, talla;
- POS actual preseleccionado;
- cards de resultado con foto, SKU, nombre, talla, precio, stock y motivo de recomendación;
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
Motivo: coincide con anillo, estilo marino, talla M y está disponible en este hotel.
Aviso calculado: existen variantes S y L muy similares.
[Seleccionar para venta]
```

El aviso no se guarda como texto IA; se calcula por reglas a partir de `ProductFamily`, `SizeLabel`, stock y similitud.

## 5.7. Desambiguación

Cuando varios productos sean similares:

- agrupar por `ProductFamily`;
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
GET  /api/products/{productId}/family
POST /api/products/search-events
```

## 5.10. Criterios de aceptación

- El operador puede buscar con texto natural.
- Los resultados se limitan a productos visibles para su POS.
- Los resultados muestran stock real y precio real.
- Las variantes se agrupan y desambiguan.
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
| Misma familia de producto | Alto |
| Materiales coincidentes | Alto |
| Color/acabado coincidente | Alto |
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
   Motivo: mismo tipo, estilo marino, materiales compatibles, precio similar, stock 3 en Hotel A.
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
Packing List - Hotel A - 2026-07-24

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
RecommendationType enum: Replenish, Transfer, Substitute, Rotate, Liquidate, Promote, Review
ProductId uuid FK
FromPointOfSaleId uuid nullable
ToPointOfSaleId uuid nullable
SuggestedQuantity int nullable
Priority enum: High, Medium, Low
Reason text
SignalsJson text
Status enum: Proposed, Approved, Rejected, Applied, Expired
CreatedByRunId uuid nullable
ReviewedByUserId uuid nullable
ReviewedAt timestamp nullable
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
Provider string nullable
Model string nullable
ErrorMessage text nullable
```

### `InventoryPolicy`

```text
Id uuid PK
ProductId uuid nullable
CollectionId uuid nullable
PointOfSaleId uuid nullable
MinStock int nullable
TargetStock int nullable
MaxStock int nullable
ReplenishmentFrequencyDays int nullable
Priority int
IsActive bool
CreatedAt timestamp
UpdatedAt timestamp
```

## 6.5. Endpoints sugeridos

```http
POST /api/ai/inventory/recommendations/generate
GET  /api/ai/inventory/recommendations
POST /api/ai/inventory/recommendations/{id}/approve
POST /api/ai/inventory/recommendations/{id}/reject
POST /api/ai/inventory/recommendations/{id}/apply
GET  /api/ai/inventory/recommendations/{id}/alternatives
POST /api/ai/inventory/packing-lists/generate
GET  /api/ai/inventory/packing-lists/{id}
POST /api/ai/inventory/packing-lists/{id}/approve
POST /api/ai/inventory/packing-lists/{id}/mark-prepared
POST /api/ai/inventory/packing-lists/{id}/mark-applied
GET  /api/ai/pos/{pointOfSaleId}/sales-profile
POST /api/ai/pos/{pointOfSaleId}/sales-profile/generate
```

## 6.6. Beneficios y ROI

### Directos

- Menos roturas de stock en hoteles con mayor venta.
- Menos tiempo de revisión manual de inventario.
- Mejor distribución entre POS.
- Más ventas recuperadas mediante sustitutos.
- Menos stock parado.

### Indirectos

- Mejores decisiones por hotel.
- Mejor planificación de reposición.
- Histórico de decisiones aceptadas/rechazadas.
- Aprendizaje sobre qué productos funcionan en cada POS.

### KPIs

- `stockouts por POS`.
- `días sin stock en top sellers`.
- `% recomendaciones aprobadas`.
- `% recomendaciones aplicadas`.
- `% sustitutos aceptados`.
- `ventas de sustitutos sugeridos`.
- `stock parado > 60/90 días`.
- `tiempo administrativo semanal de reposición`.
- `ventas antes/después en POS tratado`.

---

# 7. Arquitectura técnica propuesta

## 7.1. Módulos backend

```text
Application/AiCatalog
  - ProductEnrichmentService
  - ProductProfileReviewService
  - ProductEmbeddingService
  - ProductFamilyService

Application/AiSalesAssist
  - ProductSemanticSearchService
  - AssistedSaleRecommendationService
  - ProductSubstitutionService
  - ProductSearchEventService

Application/AiInventory
  - InventoryRecommendationService
  - ReplenishmentRecommendationService
  - StockTransferRecommendationService
  - InventorySubstituteService
  - InventoryPackingListService
  - StockRotationRecommendationService
  - PointOfSaleSalesProfileService
```

## 7.2. Servicios IA comunes

```text
IAiTextProvider
  - GenerateJsonAsync<T>()

IAiEmbeddingProvider
  - EmbedAsync(text)

AiUsageLogger
  - registra proveedor, modelo, feature, tokens y coste estimado

PromptTemplateService
  - versiona prompts por funcionalidad

StructuredOutputValidator
  - valida JSON antes de persistir
```

## 7.3. Proveedores

Implementar abstracción para poder cambiar de proveedor:

```text
DeepSeekProvider
OpenAiProvider
LocalEmbeddingProvider opcional
```

Recomendación inicial:

| Uso | Modelo/proveedor sugerido |
|---|---|
| Enriquecimiento catálogo | modelo barato con JSON output |
| Embeddings texto | proveedor económico o local |
| Explicaciones inventario | modelo barato |
| Ranking/search | principalmente reglas + embeddings |
| Inventario | reglas + métricas; LLM solo para resumen/explicación |

---

# 8. Roadmap propuesto

## Fase 1 - Catálogo IA base

- Crear `ProductAiProfile`.
- Soportar `Materials[]`.
- Generar metadatos por producto/lote.
- Revisión humana.
- Crear `ProductFamily` y `ProductFamilyMember`.
- Generar embeddings textuales.

## Fase 2 - Búsqueda semántica + venta asistida

- Búsqueda híbrida.
- Resultados filtrados por POS y stock.
- Cards con foto, SKU, precio, talla y motivo.
- Desambiguación por familias.
- Sustitutos si no hay stock.
- Registro de eventos de búsqueda.

## Fase 3 - Inventario inteligente base

- Reposición recomendada.
- Traslados sugeridos.
- Stock bajo inteligente.
- Sustitutos por falta de stock.

## Fase 4 - Packing list + rotación

- Packing list por hotel/POS.
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
| IA extrae mal materiales/talla | Revisión humana y `AiConfidence`. |
| Operador selecciona variante errónea | `ProductFamily`, `SizeLabel` destacado y avisos calculados por reglas. |
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
4. Definir si `ProductFamily` se crea manualmente, por IA o mediante flujo mixto.
5. Definir si las packing lists aplicadas crean movimientos de inventario directamente o solo guían el ajuste manual existente.
6. Definir si se capturará feedback del operador en sustitutos y venta asistida.
7. Definir si `StoneType` debe seguir siendo un único valor o evolucionar también a array en el futuro.

---

# 11. Resumen ejecutivo

La recomendación es construir una base común de inteligencia de catálogo y reutilizarla en dos direcciones:

1. **Venta asistida:** búsqueda semántica, desambiguación, sustitutos y argumentarios.
2. **Inventario inteligente:** reposición, traslados, sustitutos, packing lists, rotación/liquidación y argumentario por hotel.

La pieza central queda así:

```text
ProductAiProfile + ProductTextEmbedding + ProductFamily/ProductFamilyMember + ProductRecommendation
```

Los cambios clave de esta versión son:

- `Materials` es array.
- La agrupación de variantes sale de `ProductAiProfile` y pasa a `ProductFamily`.
- No se guardan textos comerciales o avisos libres generados por IA en el perfil del producto.
- La búsqueda se basa en metadatos aprobados, familia, embedding y datos reales de inventario.
- Los avisos al operador se calculan por reglas y contexto, no por campos textuales persistidos.
