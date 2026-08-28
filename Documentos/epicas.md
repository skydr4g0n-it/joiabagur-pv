# Épicas - Sistema de Gestión de Puntos de Venta para Joyería

Este documento describe las épicas del proyecto, agrupadas en dos bloques:

- **EP1–EP10 — MVP (Fase 1):** el sistema de gestión de puntos de venta. Sus User Stories viven en `Documentos/Historias/` con el formato `HU-EP[X]-[NNN].md`.
- **EP11–EP17 — Proyecto Final de IA:** búsqueda semántica, venta asistida y agentes sobre el catálogo existente. Sus User Stories viven en `Documentos/Historias/AI-Eng/` con el formato `HU-AIENG-[NNN].md`.

Cada épica agrupa funcionalidades relacionadas y contiene referencias a las User Stories correspondientes.

---

## Bloque 1 — MVP (EP1–EP10)

---

## Épica 1: Gestión de Productos

**Descripción:**  
Permite gestionar el catálogo centralizado de productos de la joyería, incluyendo la creación, edición, importación desde Excel y asociación de fotos de referencia para el reconocimiento de imágenes.

**Alcance:**
- Importación masiva de productos desde archivos Excel con matching por SKU
- Creación y edición manual de productos (SKU, nombre, descripción, precio, colección)
- Gestión de fotos de referencia (subida, eliminación, ordenamiento, foto principal)
- Visualización del catálogo completo con fotos asociadas
- Validación de datos y manejo de errores en importaciones

**Entidades del modelo de datos relacionadas:**
- `Product` (SKU único, precio, descripción, colección)
- `ProductPhoto` (múltiples fotos por producto, ordenamiento, foto principal)
- `Collection` (agrupación opcional de productos)

**User Stories:**
- [HU-EP1-001: Importar productos desde Excel](Historias/HU-EP1-001.md)
- [HU-EP1-002: Crear producto manualmente](Historias/HU-EP1-002.md)
- [HU-EP1-003: Editar producto existente](Historias/HU-EP1-003.md)
- [HU-EP1-004: Subir fotos de referencia a producto](Historias/HU-EP1-004.md)
- [HU-EP1-005: Gestionar fotos de producto (eliminar, reordenar, marcar principal)](Historias/HU-EP1-005.md)
- [HU-EP1-006: Visualizar catálogo de productos](Historias/HU-EP1-006.md)
- [HU-EP1-007: Buscar productos por SKU o nombre](Historias/HU-EP1-007.md)

---

## Épica 2: Gestión de Inventario

**Descripción:**  
Gestiona la asignación de productos a puntos de venta y el stock de dichos productos, permitiendo asignaciones manuales, importaciones masivas, ajustes manuales y consultas del inventario actual.

**Regla de negocio clave:** La presencia de un registro en `Inventory` (independientemente de la cantidad) determina que el producto está asignado al punto de venta y es visible para los operadores asignados a dicho punto de venta.

**Alcance:**
- **Asignación manual de productos a puntos de venta** (crear registros en Inventory con cantidad inicial 0)
- **Desasignación de productos** de puntos de venta (soft delete con preservación de historial)
- Importación de stock desde Excel (suma a cantidades existentes, con asignación implícita si el producto no está en el inventario del POS)
- Visualización de stock por punto de venta
- Vista centralizada de stock total y por ubicación
- Ajustes manuales de inventario con trazabilidad
- Validación de stock no negativo

**Entidades del modelo de datos relacionadas:**
- `Inventory` (asignación de productos a POS y stock actual por producto y punto de venta)
- `InventoryMovement` (historial completo de movimientos con trazabilidad)
- `Product` (referencia al producto del catálogo global)
- `PointOfSale` (referencia al punto de venta)

**User Stories:**
- [HU-EP2-001: Importar stock desde Excel](Historias/HU-EP2-001.md)
- [HU-EP2-002: Visualizar stock por punto de venta](Historias/HU-EP2-002.md)
- [HU-EP2-003: Visualizar stock centralizado (todos los puntos de venta)](Historias/HU-EP2-003.md)
- [HU-EP2-004: Realizar ajuste manual de inventario](Historias/HU-EP2-004.md)
- [HU-EP2-005: Consultar historial de movimientos de inventario](Historias/HU-EP2-005.md)
- [HU-EP2-006: Asignar/desasignar productos a puntos de venta](Historias/HU-EP2-006.md)

---

## Épica 3: Registro de Ventas

**Descripción:**  
Permite registrar ventas en los puntos de venta, con actualización automática del inventario y trazabilidad completa de las transacciones.

**Alcance:**
- Registro de ventas con método de pago
- Actualización automática de stock al registrar venta
- Registro de foto asociada a la venta (cuando se usa reconocimiento de imagen)
- Validación de stock disponible antes de venta
- Validación de método de pago asignado al punto de venta
- Registro de usuario operador que realiza la venta
- Edición manual de precio de venta cuando el punto de venta lo permite, con trazabilidad de precios modificados
- Carrito de ventas con persistencia local y checkout masivo atómico (`POST /api/sales/bulk`)
- Agrupación de ventas creadas en checkout masivo mediante `BulkOperationId`
- Prevención de envíos duplicados mediante clave de idempotencia

**Entidades del modelo de datos relacionadas:**
- `Sale` (venta con precio snapshot, cantidad, método de pago, fecha, indicador de precio modificado, `BulkOperationId` opcional)
- `SalePhoto` (foto opcional asociada a la venta)
- `InventoryMovement` (movimiento automático generado por la venta)
- `PaymentMethod` y `PointOfSalePaymentMethod` (validación de métodos disponibles)
- `User` (operador que realiza la venta)

**User Stories:**
- [HU-EP3-001: Registrar venta con reconocimiento de imagen](Historias/HU-EP3-001.md) *(incluye validación de stock y selección de método de pago)*
- [HU-EP3-002: Registrar venta manual (sin foto)](Historias/HU-EP3-002.md) *(incluye validación de stock y selección de método de pago)*
- [HU-EP3-003: Registrar venta con precio manual modificado](Historias/HU-EP3-003.md) *(edición de precio cuando el POS lo permite, auditoría de precios modificados)*
- [HU-EP3-004: Carrito de ventas y checkout masivo](Historias/HU-EP3-004.md) *(carrito persistente, checkout atómico multi-línea, idempotencia)*

---

## Épica 4: Reconocimiento de Imágenes con IA

**Descripción:**  
Sistema de identificación de productos mediante reconocimiento de imágenes usando inteligencia artificial, generando sugerencias ordenadas por precisión.

**Alcance:**
- Captura de foto del producto vendido
- Procesamiento de imagen mediante modelo de IA
- Generación de 3-5 sugerencias de productos ordenadas por precisión/confianza
- Visualización de sugerencias con fotos de referencia
- Validación manual del operador antes de confirmar

**Entidades del modelo de datos relacionadas:**
- `ProductPhoto` (fotos de referencia para entrenamiento/comparación)
- `ProductPhotoEmbedding` (vectores de características MobileNetV2 almacenados por foto, usados para similitud coseno)
- `SalePhoto` (foto capturada en el punto de venta)
- `Product` (productos candidatos sugeridos)

**Consideraciones técnicas:**
- Procesamiento de imágenes en cliente (navegador) usando TensorFlow.js
- **Método de inferencia principal (implementado):** Similitud coseno sobre embeddings MobileNetV2 almacenados en base de datos. Más rápido y fiable que el clasificador para catálogos pequeños.
  - Los embeddings se generan automáticamente al subir/eliminar fotos
  - "Generar Embeddings" en la página de IA permite regeneración masiva (~30-60 segundos)
  - La similitud coseno se calcula en el navegador con Float32Arrays; ~366 comparaciones en <1ms
  - Umbrales: `SIMILARITY_THRESHOLD = 0.70` (mínimo para aparecer en sugerencias), `MIN_TOP_SIMILARITY = 0.50` (mínimo del top-1)
- **Método de inferencia de respaldo:** Clasificador entrenado (Dense 256 → 128 → N clases). Se usa cuando no existen embeddings generados (instalación inicial o rollback).
- Generación de 3-5 sugerencias ordenadas por similitud/confianza
- Manejo de errores cuando no hay correspondencia fiable (redirigir a venta manual)
- Almacenamiento de fotos: sistema de archivos local en desarrollo, S3/Blob Storage en producción

**User Stories:**
- [HU-EP4-001: Reconocimiento de productos mediante imagen](Historias/HU-EP4-001.md) *(consolida captura, procesamiento, visualización y selección)*

---

## Épica 5: Gestión de Devoluciones

**Descripción:**  
Permite registrar devoluciones de productos vendidos, asociándolas a una o más ventas originales, incrementando el stock automáticamente y manteniendo trazabilidad completa. Soporta devoluciones parciales, categorización obligatoria y foto opcional.

**Alcance:**
- Registro de devolución asociada a una o más ventas originales (multi-venta)
- Soporte para devoluciones parciales (devolver parte de las unidades vendidas)
- Ventana de devolución de 30 días desde la venta
- Devolución obligatoria en el mismo punto de venta de la venta
- Categoría de devolución obligatoria (Defectuoso, Tamaño incorrecto, No satisfecho, Otro)
- Motivo de texto libre opcional (máximo 500 caracteres)
- Foto opcional de devolución (ej: foto del producto defectuoso)
- Incremento automático de stock en el punto de venta
- Generación automática de movimiento de inventario (tipo "Return")
- Validación de cantidad disponible (vendida - ya devuelta)
- Operadores pueden registrar devoluciones en sus puntos de venta asignados

**Entidades del modelo de datos relacionadas:**
- `Return` (devolución con cantidad, categoría y motivo)
- `ReturnSale` (relación muchos a muchos entre devoluciones y ventas, con cantidad y precio snapshot)
- `ReturnPhoto` (foto opcional asociada a la devolución)
- `InventoryMovement` (movimiento automático de tipo "Return")
- `Sale` (ventas originales referenciadas)
- `Inventory` (stock incrementado)

**User Stories:**
- [HU-EP5-001: Registrar devolución de producto vendido](Historias/HU-EP5-001.md)
- [HU-EP5-002: Buscar ventas elegibles para asociar devolución](Historias/HU-EP5-002.md)
- [HU-EP5-003: Consultar historial de devoluciones](Historias/HU-EP5-003.md)

---

## Épica 6: Gestión de Métodos de Pago

**Descripción:**  
Configuración y gestión de métodos de pago disponibles en el sistema, con asignación específica por punto de venta.

**Alcance:**
- Lista general de métodos de pago predefinidos (Efectivo, Bizum, Transferencia, Tarjetas TPV, PayPal)
- Asignación de métodos de pago a puntos de venta específicos
- Activación/desactivación de métodos por punto de venta
- Validación de métodos disponibles al registrar ventas

**Entidades del modelo de datos relacionadas:**
- `PaymentMethod` (métodos de pago generales con código único)
- `PointOfSalePaymentMethod` (relación muchos a muchos con activación/desactivación)

**User Stories:**
- [HU-EP6-001: Configurar métodos de pago disponibles en el sistema](Historias/HU-EP6-001.md)
- [HU-EP6-002: Asignar métodos de pago a punto de venta](Historias/HU-EP6-002.md)
- [HU-EP6-003: Activar/desactivar método de pago en punto de venta](Historias/HU-EP6-003.md)

---

## Épica 7: Autenticación y Gestión de Usuarios

**Descripción:**  
Sistema de autenticación y gestión de usuarios con roles (Administrador y Operador), incluyendo asignación de operadores a puntos de venta.

**Alcance:**
- Login con usuario y contraseña
- Gestión de roles (Admin con acceso completo, Operador con acceso restringido)
- Asignación de operadores a puntos de venta específicos
- Control de acceso basado en roles y asignaciones
- Gestión de usuarios (crear, editar, desactivar)

**Entidades del modelo de datos relacionadas:**
- `User` (usuarios con roles Admin/Operator, autenticación)
- `UserPointOfSale` (asignación de operadores a puntos de venta)
- `PointOfSale` (puntos de venta asignables)

**User Stories:**
- [HU-EP7-001: Login de usuario con usuario y contraseña](Historias/HU-EP7-001.md)
- [HU-EP7-002: Crear nuevo usuario](Historias/HU-EP7-002.md)
- [HU-EP7-003: Editar usuario existente](Historias/HU-EP7-003.md)
- [HU-EP7-004: Asignar operador a punto de venta](Historias/HU-EP7-004.md)
- [HU-EP7-005: Desasignar operador de punto de venta](Historias/HU-EP7-005.md)
- [HU-EP7-006: Control de acceso según rol y asignaciones](Historias/HU-EP7-006.md)

---

## Épica 8: Gestión de Puntos de Venta

**Descripción:**  
Permite crear, editar y gestionar los puntos de venta del sistema, incluyendo asignación de operadores y métodos de pago.

**Alcance:**
- Creación y edición de puntos de venta (nombre, código, dirección, teléfono, email)
- Asignación de operadores a puntos de venta
- Asignación de métodos de pago a puntos de venta
- Activación/desactivación de puntos de venta
- Visualización de puntos de venta disponibles según rol
- Configuración de política de edición manual de precio por punto de venta

**Entidades del modelo de datos relacionadas:**
- `PointOfSale` (información del punto de venta, incluye `AllowManualPriceEdit`)
- `UserPointOfSale` (asignación de operadores)
- `PointOfSalePaymentMethod` (asignación de métodos de pago)

**User Stories:**
- [HU-EP8-001: Crear punto de venta](Historias/HU-EP8-001.md)
- [HU-EP8-002: Editar punto de venta existente](Historias/HU-EP8-002.md)
- [HU-EP8-003: Activar/desactivar punto de venta](Historias/HU-EP8-003.md)
- [HU-EP8-004: Visualizar puntos de venta disponibles](Historias/HU-EP8-004.md)
- [HU-EP8-005: Configurar edición manual de precio por punto de venta](Historias/HU-EP8-005.md)

---

## Épica 9: Consultas y Reportes

**Descripción:**  
Proporciona funcionalidades de consulta y visualización de datos históricos de ventas e inventario, con filtros y búsquedas.

**Alcance:**
- Consulta de historial de ventas con filtros (punto de venta, fecha, producto, método de pago, operador)
- Visualización de detalles de ventas (foto, SKU, precio, método de pago, fecha, operador)
- Consulta de inventario con búsqueda de productos
- Visualización de movimientos de stock históricos
- Paginación de resultados para optimización

**Entidades del modelo de datos relacionadas:**
- `Sale` (con índices optimizados para consultas por punto de venta, producto, usuario, método de pago)
- `SalePhoto` (fotos asociadas a ventas)
- `Inventory` (stock actual)
- `InventoryMovement` (historial de movimientos)

**Optimizaciones:**
- Índices compuestos en `Sale` para consultas frecuentes
- Paginación obligatoria (máx 50 items por página)
- Filtros eficientes por fecha, punto de venta, producto

**User Stories:**
- [HU-EP9-001: Consultar historial de ventas con filtros](Historias/HU-EP9-001.md)
- [HU-EP9-002: Visualizar detalles de una venta](Historias/HU-EP9-002.md)
- [HU-EP9-003: Consultar inventario con búsqueda](Historias/HU-EP9-003.md)
- [HU-EP9-004: Consultar movimientos de inventario](Historias/HU-EP9-004.md)

---

## Épica 10: Gestión de Componentes de Joyas

**Descripción:**  
Permite gestionar los componentes que constituyen las joyas (materiales, mano de obra, etc.) mediante una tabla maestra, asignarlos a productos con cantidades y precios por defecto o override, calcular costes y precios de venta sugeridos, y generar reportes de márgenes. Solo visible para administradores.

**Decisiones de diseño tomadas:**
- **Precio oficial vs sugerido:** `Product.Price` es el precio oficial de venta. El precio calculado por componentes es solo informativo/sugerencia.
- **Override obligatorio (asignación manual):** Cada asignación de componente a producto debe tener precios de coste y venta definidos (manual o desde plantilla).
- **Override opcional:** Solo en plantillas: al aplicar plantilla se cargan precios desde la tabla maestra como valores por defecto.
- **Precisión decimal:** 4 decimales para cantidad, coste y venta.
- **Orden:** Los componentes se listan en el orden especificado en la UI; se permite reordenar con drag-and-drop.
- **Integración:** Gestión de componentes integrada dentro de la sección Productos (subsección).
- **Visibilidad:** Componentes y totales calculados ocultos para todos los roles (campo solo admin).
- **Componentes desactivados:** No se pueden asignar nuevos; los ya asignados a productos mantienen su asignación.

**Alcance:**
- Tabla maestra de componentes (Descripción, CostPrice, SalePrice opcionales, activar/desactivar)
- Asignación de componentes a productos con cantidad y precios override
- Autocomplete por descripción para buscar componentes
- Cálculo de totales en tiempo real (TotalCostPrice, TotalSalePrice)
- Sincronización de precios desde maestro con confirmación
- Advertencia de desviación de precio (>10%) con acción rápida para ajustar
- Plantillas de componentes (lista de componentes + cantidades, precios desde master)
- Reporte de márgenes por producto (tabla, filtros, totales, export Excel)
- Reporte de productos sin componentes (con botón para editar)

**Entidades del modelo de datos relacionadas:**
- `ProductComponent` (tabla maestra: Descripción, CostPrice, SalePrice opcionales, IsActive)
- `ProductComponentAssignment` (ProductId, ComponentId, Quantity, CostPrice, SalePrice, DisplayOrder)
- `ComponentTemplate` (plantillas: Id, Name, Description)
- `ComponentTemplateItem` (TemplateId, ComponentId, Quantity)

**User Stories:**
- [HU-EP10-001: Gestionar tabla maestra de componentes](Historias/HU-EP10-001.md)
- [HU-EP10-002: Asignar componentes a producto en edición](Historias/HU-EP10-002.md)
- [HU-EP10-003: Asignar componentes a producto en creación](Historias/HU-EP10-003.md)
- [HU-EP10-004: Sincronizar precios desde maestro](Historias/HU-EP10-004.md)
- [HU-EP10-005: Advertencia de desviación de precio (10%)](Historias/HU-EP10-005.md)
- [HU-EP10-006: Gestionar plantillas de componentes](Historias/HU-EP10-006.md)
- [HU-EP10-007: Reporte de márgenes por producto](Historias/HU-EP10-007.md)
- [HU-EP10-008: Reporte de productos sin componentes](Historias/HU-EP10-008.md)

**Matriz de dependencias entre User Stories de EP10:**

| Historia | Depende de | Es base para |
|----------|------------|--------------|
| HU-EP10-001 | EP7 (auth, roles) | HU-EP10-002, HU-EP10-003, HU-EP10-006 |
| HU-EP10-002 | HU-EP10-001, HU-EP1-003, EP7 | HU-EP10-003, HU-EP10-004, HU-EP10-005, HU-EP10-006, HU-EP10-007 |
| HU-EP10-003 | HU-EP10-001, HU-EP10-002, HU-EP1-002, EP7 | HU-EP10-006 |
| HU-EP10-004 | HU-EP10-002 | — |
| HU-EP10-005 | HU-EP10-002 | — |
| HU-EP10-006 | HU-EP10-001, HU-EP10-002, HU-EP10-003 | — |
| HU-EP10-007 | HU-EP10-002, EP9 (Reportes), EP7 | — |
| HU-EP10-008 | HU-EP10-001, HU-EP1-003, EP9, EP7 | — |

**Orden recomendado de implementación EP10:** 001 → 002 → 003 → 004 → 005 → 006 → 007, 008 (007 y 008 pueden hacerse en paralelo tras 002).

---

## Bloque 2 — Proyecto Final de IA (EP11–EP17)

> Las épicas EP1–EP10 cubren el MVP del sistema de punto de venta. Las siguientes cubren el **Proyecto Final del Máster de IA**: incorporan búsqueda semántica, venta asistida y agentes sobre el catálogo existente, mediante el microservicio `jbg-ai`.
>
> **Convención de nomenclatura.** A diferencia del MVP, las historias del PF **no** se numeran por épica: siguen una serie plana `HU-AIENG-[NNN]` en `Documentos/Historias/AI-Eng/`, porque el trabajo se organiza por *change* de OpenSpec (C01–C39) y una misma historia puede atravesar varias épicas. Cada épica indica abajo qué changes agrupa.
>
> **El número de la historia es el del change, no el de creación** *(regla fijada el 2026-08-16, al redactar HU-AIENG-008)*. `HU-AIENG-[NNN]` y su ticket `T-AIENG-[NNN]` toman el número de `C[NN]`, de modo que el trío historia ↔ ticket ↔ change se lee sin tabla de equivalencias. Los changes se cogen por desbloqueo y no por orden, así que la serie tendrá huecos —`006` y `007` esperan a C06 y C07— y eso es correcto: un hueco significa «ese change aún no se ha redactado», que es exactamente lo que se quiere saber de un vistazo.
>
> **Fuentes:** [diseño del sistema de IA](Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) (§4 alcance acordado, §6 frontera, §7 diseño RAG) y [plan de changes](Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (tabla maestra C01–C39).

---

## Épica 11: Plataforma del Servicio de IA

**Descripción:**
Cimientos del microservicio `jbg-ai`: esqueleto ejecutable, contratos HTTP congelados, autenticación entre servicios, esquema vectorial y despliegue. Es la épica habilitadora: sin ella ninguna de las siguientes puede empezar.

**Alcance:**
- Servicio Python con FastAPI, `uv`, configuración por entorno y `GET /health`
- Contratos `/v1/*` congelados con modelos Pydantic, stubs deterministas y snapshot OpenAPI versionado
- JWT interno HS256 entre .NET y Python, con scope por usuario, rol y punto de venta
- Cliente tipado `IAiGatewayClient` en .NET con timeouts, reintento y circuit breaker
- Esquema `ai` con pgvector, migraciones y rol de base de datos dedicado
- Despliegue del contenedor en EC2, secretos en SSM y health enriquecido

**Changes asociados:** C01, C02, C03, C05, C17

**User Stories:**
- [HU-AIENG-001: Esqueleto ejecutable del servicio de IA](Historias/AI-Eng/HU-AIENG-001.md) *(C01 — hecho)*
- [HU-AIENG-002: Contratos congelados y autenticación de servicio](Historias/AI-Eng/HU-AIENG-002.md) *(C02 — hecho)*
- [HU-AIENG-003: Cliente tipado .NET hacia `jbg-ai` con resiliencia y token de servicio](Historias/AI-Eng/HU-AIENG-003.md) *(C03 — hecho)*
- [HU-AIENG-005: Cimiento de persistencia vectorial — extensión `vector`, esquema `ai` y migraciones Alembic](Historias/AI-Eng/HU-AIENG-005.md) *(C05 — hecho)*

---

## Épica 12: Corpus y Enriquecimiento del Catálogo

**Descripción:**
Construcción del corpus sobre el que opera todo el sistema RAG: perfiles de producto extraídos con LLM contra vocabularios cerrados, confianza por campo y revisión humana híbrida, más el corpus de conocimiento comercial que permite responder con citas verificables.

**Alcance:**
- ✅ Corpus JSONL de 436 productos reales con procedencia dual, pipeline offline en `scripts/catalog/` e ingesta local de `Description` (C06a)
- Pipeline de enriquecimiento: normalización determinista → extracción estructurada → validación → confianza por campo
- `materials[]` como lista contra vocabulario cerrado; nunca se inventa un material por defecto
- Entidad `ProductAiProfile` en .NET con su ciclo de aprobación
- Texto canónico (`SourceText`) y `source_hash`: solo se recalcula el embedding si cambia el hash
- Corpus de conocimiento comercial (materiales, tallas, cuidados, políticas), troceado y citable
- Generador de mundo sintético (CLI `jbg_ai.data.world`, YAML de 12 POS, Poisson, ingest local) para disponer de inventario y ventas coherentes con el catálogo

**Changes asociados:** C06a (hecho), C06b (hecho), C08, C09 (hecho), C10 (hecho), C11 (hecho), C23

**User Stories:**
- [HU-AIENG-006a: Ingesta del catálogo real y corpus enriquecido versionado](Historias/AI-Eng/HU-AIENG-006a.md) *(C06a — corpus JSONL + informe)*
- [HU-AIENG-006b: Ampliación sintética del catálogo — LLM, colecciones nuevas e ingesta local](Historias/AI-Eng/HU-AIENG-006b.md) *(C06b — hecho; CLI en `jbg_ai.data`; sin familias)*
- [HU-AIENG-009: Pipeline de enriquecimiento del catálogo — extracción estructurada con vocabularios cerrados](Historias/AI-Eng/HU-AIENG-009.md) *(C09 — hecho; extractor real de `POST /v1/enrich/products`)*
- [HU-AIENG-010: Simulador de mundo sintético — POS, inventario e histórico de ventas](Historias/AI-Eng/HU-AIENG-010.md) *(C10 — hecho; CLI `world simulate` / `world ingest`; YAML en git, JSONL gitignored)*
- [HU-AIENG-011: SourceText canónico y cliente de embeddings con idempotencia por hash](Historias/AI-Eng/HU-AIENG-011.md) *(C11 — hecho; biblioteca `jbg_ai.indexing`, sin HTTP ni SQL)*

**Entregable C06a.** El corpus versionado vive en [`data/catalog/real/generated/catalog-real-enriched.jsonl`](../data/catalog/real/generated/catalog-real-enriched.jsonl) (sidecar `.meta.json` al lado; `generator_version` `c06a-assist/v2`). Cada línea lleva identidad + `data_origin` / `text_provenance` / `text_quality_tier` (`rich` / `sparse` / `original`); **no** emite `variant_group_key`, `variant_label` ni `family_seed`. La pasada de vendedor, los ratios y la limitación §15 están en [`Proyecto Final AIEng/informes/c06a-catalog-enrichment-report.md`](Proyecto%20Final%20AIEng/informes/c06a-catalog-enrichment-report.md). Los scripts son el pipeline offline [`scripts/catalog/`](../scripts/catalog/). El xlsx crudo sigue gitignored.

**Entregable C06b (JSONL).** El corpus sintético vive en [`data/catalog/synthetic/generated/catalog-synthetic.jsonl`](../data/catalog/synthetic/generated/catalog-synthetic.jsonl) (sidecar al lado; `generator_version` `c06b-synth/v3`, `prompt_version` `catalog-synth/v3`). 764 líneas, híbrido 1.200 con el real. Tiers `rich` / `sparse` / `short` (nunca `empty` ni `original`); el copy se recorta por frases enteras y se aproxima a las medias del real. CLI en [`ai-service/src/jbg_ai/data/`](../ai-service/src/jbg_ai/data/README.md). Recuentos, muestras, ingesta local y nota §15: [`Proyecto Final AIEng/informes/c06b-synthetic-catalog-report.md`](Proyecto%20Final%20AIEng/informes/c06b-synthetic-catalog-report.md). Ingesta Docker (`INSERT` en `:5433` / `joiabagur_pv`): 10 colecciones + 764 productos; GET familia sobre un sintético → 204.

**Entregable C09 (extractor).** `POST /v1/enrich/products` con `STUB_MODE=false` corre el pipeline en [`ai-service/src/jbg_ai/enrichment/`](../ai-service/src/jbg_ai/enrichment/) (vocabularios YAML, talla por regex `Name` > `Description`, LiteLLM temp 0, confianza por span). Prompt [`ai-service/prompts/enrichment/v1.md`](../ai-service/prompts/enrichment/v1.md); `prompt_version = enrichment/v1`. Las puertas de lote (unicidad de SKU, vocabulario, cobertura de tags por estrato) viven en el auditor, **fuera del HTTP**: el POST de 50 no responde 422 por esas cifras. Compose y el snapshot se quedan en `STUB_MODE=true` hasta que haya `JPV_RAG_LLM_API_KEY`.

**Entregable C10 (mundo).** Receta en [`data/world/pos-profiles.yaml`](../data/world/pos-profiles.yaml) (`generator_version` `c10-world/v1`, semilla `20260823`). CLI `python -m jbg_ai.data world simulate|ingest` en [`ai-service/src/jbg_ai/data/world/`](../ai-service/src/jbg_ai/data/README.md). Ingesta Docker (`:5433` / `joiabagur_pv`): 12 POS, 3 operadores, 6.720 inventario, 22.961 ventas; `"Products"` intacto. Informe: [`Proyecto Final AIEng/informes/c10-synthetic-world-report.md`](Proyecto%20Final%20AIEng/informes/c10-synthetic-world-report.md). JSONL y dump **gitignored**. `is_supply_source` solo en YAML (columna SQL = C19).

**Entregable C11 (biblioteca de indexación).** Paquete [`ai-service/src/jbg_ai/indexing/`](../ai-service/src/jbg_ai/indexing/) — constructor `source-text/v1` (`build_source_text` / `hash_source_text`) y cliente LiteLLM de embeddings 1536d con caché in-memory, *batch* 64 y backoff. **Renderer y embeddings sin HTTP ni SQL.** `jbg_ai.api.main` no importa `indexing`. El dreno de catálogo (`POST /v1/index/sync`) lo entrega C13 en el mismo paquete (el router de índice sí importa). `JPV_EMBEDDING_*` no bloquean `/health` y no caen a `JPV_RAG_LLM_API_KEY`. Tests en [`ai-service/tests/indexing/`](../ai-service/tests/indexing/). Change OpenSpec [`add-source-text-and-embedding-client`](../openspec/changes/archive/2026-08-25-add-source-text-and-embedding-client/).

---

## Épica 13: Familias de Producto y Desambiguación de Variantes

**Descripción:**
Resuelve el caso de negocio crítico: variantes visualmente casi idénticas que provocan errores de venta. La IA propone agrupaciones y el administrador las aprueba, edita o rechaza; la familia resultante es una entidad de negocio editable sin tocar nada de IA.

**Alcance:**
- ✅ Entidades `ProductFamily` y `ProductFamilyMember` en .NET, con pertenencia excluyente garantizada por índice único, etiqueta de variante y orden declarados de forma idempotente, y cinco endpoints de administración (C07)
- Propuesta asistida de familias por similitud de embedding, tipo de pieza y raíz común de nombre
- Pantalla de revisión y aprobación por lotes (segundo caso de intervención humana del PF)
- Alerta de huérfanos: productos con similitud alta a una familia a la que no pertenecen
- Pantalla de revisión de perfiles de IA con métricas de calidad

**Changes asociados:** C07 (hecho), C18, C28

**Nota de secuencia.** C07 entrega la entidad y su edición manual, no la inteligencia: agrupar ~350 familias a mano es inviable y por eso existe C18. Lo que C07 hace posible es que haya un sitio donde esas familias vivan y se corrijan, y que `Product` no gane ninguna columna en el proceso. C07 reserva además `Origin`, `ApprovedByUserId` y `ApprovedAt` para que C18 —que no tiene turno de migración de EF Core— pueda registrar la aprobación humana sin abrir uno.

---

## Épica 14: Búsqueda Semántica Híbrida

**Descripción:**
El corazón del Proyecto Final. Búsqueda que combina la rama vectorial y la léxica, filtra por punto de venta, entiende restricciones estructurales de la consulta y se abstiene cuando no hay confianza suficiente.

**Alcance:**
- Indexación del catálogo en el esquema `ai` mediante feed paginado con cursor `since` y *tombstones*
- **C12 (hecho, archivado 2026-08-26):** `GET /api/ai/index-feed/catalog` (página 50) y `GET /api/ai/index-feed/pos-availability` (página 200), autenticados **solo** con header `X-Index-Feed-Key` (`IndexFeed:ApiKey`, ≥ 32 caracteres). Un JWT de usuario o un token C03 responden **401**. **Sin migración EF** y **sin HTTP push** hacia Python. Spec viva `index-feed`. Runbook AutoBulk: [`informes/c12-catalog-autobulk-runbook.md`](Proyecto%20Final%20AIEng/informes/c12-catalog-autobulk-runbook.md).
- **C13 (hecho, archivado 2026-08-26):** `jbg-ai` tira del feed de catálogo (`POST /v1/index/sync`, CLI `python -m jbg_ai.indexing sync`). Mapa de procedencia commiteado en [`ai-service/src/jbg_ai/indexing/sku_provenance.json`](../ai-service/src/jbg_ai/indexing/sku_provenance.json). OpenAPI con keyset `since_id` / `cursor_id`. **Sin POS** y **sin editar** `indexing/embeddings.py`. Auth de catálogo (`get_catalog_principal`, sin `pos_id`). `drift_count` compara el SHA-256 del conjunto de `product_id` con **un** GET de la primera página del feed (`aggregateHash`).
- **C14 (hecho, archivado 2026-08-27):** retriever vectorial de `POST /v1/retrieval/products` cuando `STUB_MODE=false`. Paquete [`ai-service/src/jbg_ai/retrieval/`](../ai-service/src/jbg_ai/retrieval/): embebe la query con `LiteLlmEmbeddingClient` (`max_attempts=1`, **sin editar** `indexing/embeddings.py`), busca con `<=>` cosine sobre HNSW, umbral de distancia `JPV_RETRIEVAL_DISTANCE_THRESHOLD` default **0,65**, overfetch **después** del umbral. `mode=hybrid` y `lexical` ejecutan la rama vectorial hasta C21 (`debug.notes` incluye `vector_only_until_c21`). Índice vacío / sin `JPV_EMBEDDING_API_KEY` / sin `DATABASE_URL` → **503**; abstención real → 200 + `low_confidence`. **Sin** `ai.query_log`, **sin** regenerar OpenAPI, **sin** filtrar por `pos_id`. Historia [HU-AIENG-014](Historias/AI-Eng/HU-AIENG-014.md).
- **C15 (hecho, 2026-08-28):** `POST /api/ai/search` en [`AiSearchController`](../backend/src/JoiabagurPV.API/Controllers/AiSearchController.cs). Pide la **ventana máxima del contrato en una sola llamada** (`top_k = 20` → 60 candidatos) y **no repide**: el retriever aplica su umbral antes del `LIMIT`, así que repedir devolvería las mismas filas cobrando un segundo embedding. **Hidratación autoritativa** en una consulta conjunta: descarta lo que no tiene inventario activo en ese POS o cuyo producto está inactivo, **conserva la cantidad cero** marcándola, y devuelve la cantidad **de ese POS**. Buscador degradado propio con `to_tsvector('spanish', …)` calculado en consulta —**sin índice y sin migración**—, semántica OR y orden por `ts_rank`. Flag por POS en configuración (`AiSearch:EnabledPointOfSaleIds`, `IOptionsMonitor`) y **`SearchOrigin.Disabled = 3`**. Caché de candidatos con el POS en la clave y rate limit por usuario. Punto de venta **obligatorio**; el admin puede elegir cualquiera **activo**. Historia [HU-AIENG-015](Historias/AI-Eng/HU-AIENG-015.md).
- Recuperación vectorial sobre HNSW y léxica con `ts_rank` en español, fusionadas con RRF
- Diccionario de sinónimos del dominio aplicado en expansión de consulta, nunca en indexación
- Prefiltro blando: la disponibilidad penaliza el score pero **nunca excluye** un candidato
- Sobre-recuperación (`top_k × 3`, tope 60) para que .NET tenga margen tras hidratar
- Abstención por umbral: devolver cero resultados es información válida
- Endpoint de búsqueda en .NET con hidratación, circuit breaker y fallback léxico
- Panel de búsqueda asistida en el frontend

**Changes asociados:** C12, C13, C14, C15, C16, C20, C21, C22, C25

**User Stories:**
- [HU-AIENG-012: Feeds HTTP de indexación con cursor, tombstones y autenticación de servicio](Historias/AI-Eng/HU-AIENG-012.md) *(C12 — `GET /api/ai/index-feed/catalog` y `.../pos-availability`; API Key `X-Index-Feed-Key`; sin migración / sin push)*
- [HU-AIENG-013: Indexador de `ai.product_document` desde el feed de catálogo](Historias/AI-Eng/HU-AIENG-013.md) *(C13 — pull del feed de catálogo; mapa SKU en `src/jbg_ai/indexing/sku_provenance.json`; OpenAPI keyset; sin POS / sin `embeddings.py`)*
- [HU-AIENG-014: Recuperación vectorial real en `POST /v1/retrieval/products`](Historias/AI-Eng/HU-AIENG-014.md) *(C14 — retriever vectorial; umbral 0,65; hybrid=vector hasta C21; sin `query_log` / sin OpenAPI / sin `embeddings.py`)*
- [HU-AIENG-015: Endpoint de búsqueda asistida en .NET con hidratación autoritativa](Historias/AI-Eng/HU-AIENG-015.md) *(C15 — `POST /api/ai/search`; ventana máxima en una llamada sin repetición; hidratación por POS que conserva el stock cero; buscador degradado con full-text español sin índice; flag en configuración con `SearchOrigin.Disabled`; caché de candidatos y rate limit; sin migración)*

---

## Épica 15: Venta Asistida, Sustitutos y Agentes

**Descripción:**
Capa de generación y agéntica. Convierte un conjunto de candidatos en una respuesta útil para el operador: agrupada por familia, con avisos calculados por reglas, argumentario con citas y sugerencias de sustitutos o complementarios.

**Alcance:**
- Respuesta estructurada con `groups[]` por familia y `variant_label` destacado
- Avisos calculados por reglas (variantes en la familia, talla ausente, stock crítico), nunca generados libremente
- Argumentario generado en tiempo de consulta con `citations[]`, no persistido
- **Toda cifra de precio o stock se emite como placeholder** que resuelve .NET; si alguno queda sin resolver, la respuesta se rechaza
- Guardrails, enrutado de intención y pregunta de aclaración ante consultas ambiguas
- Agente asistente de venta con *tools* de solo lectura e intervención humana
- Sustitutos por falta de stock y complementarios por reglas y co-ocurrencia
- Tarjeta de asistencia y desambiguación por familia en el frontend

**Changes asociados:** C26, C27, C30, C31, C32, C34, C36

---

## Épica 16: Inventario Asistido y Señales de Demanda

**Descripción:**
Segundo agente del proyecto. Propone reposiciones, traslados entre puntos de venta y acciones sobre stock parado, siempre con aprobación humana. Las señales numéricas se calculan en SQL en .NET; el LLM solo redacta y prioriza.

**Alcance:**
- Señales de demanda calculadas en SQL: ventas a 7/30/60 días, cobertura, días sin venta, stock en otros puntos de venta
- Perfil comercial por punto de venta, calculado periódicamente
- Entidad `InventoryRecommendation` con ciclo de aprobación y auditoría
- Agente de inventario con propuestas priorizadas y justificadas
- Pantalla de revisión de recomendaciones y vista imprimible por punto de venta

**Changes asociados:** C19, C29, C33, C35, C37

---

## Épica 17: Evaluación y Observabilidad de IA

**Descripción:**
Sin medición no hay proyecto de IA defendible. Cubre la telemetría de uso real, el conjunto de evaluación etiquetado a mano, las métricas de recuperación y generación, y los escenarios adversarios.

**Alcance:**
- Telemetría consulta → selección (`ProductSearchEvent`) desde el primer día
- Golden set de consultas etiquetadas y línea base de métricas de recuperación
- Ablations para medir el efecto de cada componente (sinónimos, híbrido, señales de negocio)
- Validador anti-alucinación y escenarios de agente
- Casos adversarios: fuera de dominio, inyección, stock cero, consulta imposible, PII
- Documentación final del proyecto con evidencias y limitaciones declaradas

**Changes asociados:** C04, C24, C38, C39

**User Stories:**
- [HU-AIENG-004: Telemetría de búsqueda asistida — evento consulta→selección](Historias/AI-Eng/HU-AIENG-004.md) *(C04 — hecho)*

---

## Resumen de Épicas

| Épica | Descripción Breve | User Stories Estimadas |
|-------|-------------------|------------------------|
| **EP1** | Gestión de Productos | 7 |
| **EP2** | Gestión de Inventario | 6 |
| **EP3** | Registro de Ventas | 4 |
| **EP4** | Reconocimiento de Imágenes con IA | 1 |
| **EP5** | Gestión de Devoluciones | 3 |
| **EP6** | Gestión de Métodos de Pago | 3 |
| **EP7** | Autenticación y Gestión de Usuarios | 6 |
| **EP8** | Gestión de Puntos de Venta | 5 |
| **EP9** | Consultas y Reportes | 4 |
| **EP10** | Gestión de Componentes de Joyas | 8 |
| **TOTAL MVP** | | **47** |

### Épicas del Proyecto Final de IA

Se miden por *changes* de OpenSpec, no por número de historias: la serie `HU-AIENG-[NNN]` es plana y se genera a demanda por change.

| Épica | Descripción Breve | Changes | Ruta crítica |
|-------|-------------------|---------|--------------|
| **EP11** | Plataforma del Servicio de IA | C01, C02, C03, C05, C17 | 🔴 completa |
| **EP12** | Corpus y Enriquecimiento del Catálogo | C06a (hecho), C06b (hecho), C08, C09 (hecho), C10 (hecho), C11 (hecho), C23 | 🔴 parcial |
| **EP13** | Familias de Producto y Desambiguación | C07, C18, C28 | 🟢 |
| **EP14** | Búsqueda Semántica Híbrida | C12, C13, C14, C15, C16, C20, C21, C22, C25 | 🔴 mayoritaria |
| **EP15** | Venta Asistida, Sustitutos y Agentes | C26, C27, C30, C31, C32, C34, C36 | 🔴 parcial |
| **EP16** | Inventario Asistido y Señales de Demanda | C19, C29, C33, C35, C37 | 🟢 |
| **EP17** | Evaluación y Observabilidad de IA | C04, C24, C38, C39 | 🔴 parcial |
| **TOTAL PF** | | **39 changes** | |

---

## Orden de Implementación

Este orden de implementación ha sido definido considerando las dependencias entre épicas y la necesidad de construir primero las bases del sistema antes de implementar funcionalidades más complejas. Este orden es **fundamental para generar los tickets de trabajo en el orden correcto de desarrollo**.

**Orden de implementación confirmado:**

1. **EP7**: Autenticación y Gestión de Usuarios (base del sistema)
   - Sin autenticación no se puede acceder al sistema
   - Los roles y permisos son necesarios para todas las demás funcionalidades
   - Base para control de acceso en el resto del sistema

2. **EP8**: Gestión de Puntos de Venta (necesario para el resto)
   - Los puntos de venta son necesarios para inventario, ventas y asignaciones
   - Debe estar disponible antes de asignar operadores o métodos de pago

3. **EP6**: Gestión de Métodos de Pago (necesario para ventas)
   - Los métodos de pago deben estar configurados antes de registrar ventas
   - Necesario para asignar métodos a puntos de venta

4. **EP1**: Gestión de Productos (necesario para ventas e inventario)
   - El catálogo de productos es base para inventario y ventas
   - Las fotos de productos son necesarias para reconocimiento de imágenes

5. **EP2**: Gestión de Inventario (necesario para ventas)
   - El stock debe estar gestionado antes de poder registrar ventas
   - Las validaciones de stock requieren inventario configurado

6. **EP3**: Registro de Ventas (funcionalidad principal)
   - Requiere: productos, inventario, métodos de pago y puntos de venta
   - Funcionalidad core del sistema

7. **EP4**: Reconocimiento de Imágenes con IA (mejora de ventas)
   - Mejora la experiencia de registro de ventas
   - Requiere productos con fotos de referencia (EP1)
   - Puede desarrollarse en paralelo con EP3 pero se integra después

8. **EP5**: Gestión de Devoluciones (complemento)
   - Requiere ventas registradas (EP3)
   - Funcionalidad complementaria que mejora la gestión completa

9. **EP9**: Consultas y Reportes (análisis)
   - Requiere datos existentes (ventas, inventario, devoluciones)
   - Funcionalidad de análisis que se beneficia de tener datos históricos

10. **EP10**: Gestión de Componentes de Joyas (costes de producción)
   - Requiere: EP1 (productos), EP7 (admin), EP9 (reportes para sección Reportes)
   - Extiende la gestión de productos con componentes, costes y reportes de márgenes
   - Orden interno de EP10: HU-EP10-001 → HU-EP10-002 → HU-EP10-003 → HU-EP10-004 → HU-EP10-005 → HU-EP10-006 → HU-EP10-007 → HU-EP10-008

> **Nota importante:** Este orden debe respetarse al generar los tickets de trabajo para asegurar que las dependencias estén resueltas antes de implementar funcionalidades que las requieren.

### Orden de Implementación del Proyecto Final (EP11–EP17)

Las épicas del PF **presuponen el MVP terminado**: operan sobre el catálogo, el inventario y los puntos de venta que ya existen. Su orden no es estrictamente secuencial por épica, sino por olas de trabajo con dependencias cruzadas entre changes:

1. **EP11** (cimientos) — sin el esqueleto, los contratos y el esquema vectorial no arranca nada.
2. **EP12** en paralelo con el resto de EP11 — el corpus es el insumo de la búsqueda.
3. **EP14** — requiere corpus indexado (EP12) y contratos (EP11). Es la ruta crítica principal.
4. **EP13** — puede avanzar en paralelo desde que existe el índice; su aprobación humana alimenta la desambiguación de EP15.
5. **EP15** — requiere recuperación funcionando (EP14) y familias (EP13).
6. **EP16** — requiere señales de demanda sobre histórico de ventas (EP12) y el patrón agéntico de EP15.
7. **EP17** — la telemetría (C04) se implanta desde el primer día; la evaluación formal necesita recuperación (EP14) y generación (EP15).

> El orden fino, con olas fechadas, dependencias exactas y pares que no deben ejecutarse en paralelo, está en el [plan de changes](Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (§4 grafo de dependencias y §5 calendario). Ese documento manda sobre este resumen.

---

## Notas

- Las User Stories se crearán siguiendo el formato definido en `Documentos/Procedimientos/Procedimiento-UserStories.md`
- Las historias de EP10 incluyen requisitos funcionales (RF), no funcionales (RNF), criterios de aceptación Given/When/Then y matriz de dependencias explícita
- Cada User Story tendrá su propio archivo en `Documentos/Historias/` con el formato `HU-EP[X]-[NNN].md`
- Las épicas están diseñadas para cubrir todos los casos de uso del MVP definidos en el README
- El modelo de datos está optimizado para soportar todas estas épicas de manera eficiente
- Las funcionalidades de Fase 2 (alertas, reportes avanzados, dashboard, etc.) no están incluidas en este MVP
- **Nota:** Algunas historias han sido consolidadas para evitar duplicación. Ver `Documentos/aclaraciones-tecnicas.md` para detalles.

