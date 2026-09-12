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
- Despliegue del contenedor en un **entorno de demostración aislado, en una cuenta AWS propia** —no en la de la tienda, a la que no hay acceso—, secretos en el almacén de parámetros y health enriquecido con contraste del modelo de embeddings contra el índice

**Changes asociados:** C01, C02, C03, C05, C17

**User Stories:**
- [HU-AIENG-001: Esqueleto ejecutable del servicio de IA](Historias/AI-Eng/HU-AIENG-001.md) *(C01 — hecho)*
- [HU-AIENG-002: Contratos congelados y autenticación de servicio](Historias/AI-Eng/HU-AIENG-002.md) *(C02 — hecho)*
- [HU-AIENG-003: Cliente tipado .NET hacia `jbg-ai` con resiliencia y token de servicio](Historias/AI-Eng/HU-AIENG-003.md) *(C03 — hecho)*
- [HU-AIENG-005: Cimiento de persistencia vectorial — extensión `vector`, esquema `ai` y migraciones Alembic](Historias/AI-Eng/HU-AIENG-005.md) *(C05 — hecho)*
- [HU-AIENG-017: Entorno de demostración aislado — despliegue del servicio de IA, salud enriquecida y tarjeta de estado](Historias/AI-Eng/HU-AIENG-017.md) *(C17 — hecho)*

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
- Corpus de conocimiento comercial **general, no por producto** (materiales, piedras, tallas, cuidados, alergias, servicio, glosario y origen de las colecciones), troceado por secciones y citable, con el **alcance de cada afirmación declarado por sección**: `general` si es comprobable fuera, `establecimiento` si es un compromiso de la joyería. Sin guiones de venta: el corpus guarda hechos para citar, el prompt guarda instrucciones para obedecer (C23)
- Generador de mundo sintético (CLI `jbg_ai.data.world`, YAML de 12 POS, Poisson, ingest local) para disponer de inventario y ventas coherentes con el catálogo
- El vocabulario cerrado se amplía **sólo por change**, con salto de versión de prompt y reenriquecimiento de una cohorte enumerada (FIX1)

**Changes asociados:** C06a (hecho), C06b (hecho), C08 (hecho), C09 (hecho), C10 (hecho), C11 (hecho), **C23** (`add-knowledge-corpus-and-indexer` — **hecho**, abierto y archivado el 2026-09-06; capability viva `knowledge-corpus`), **FIX1** (`fix-enrichment-vocabulary-gaps`, fuera de la numeración C — **hecho**, abierto, ejecutado y archivado el 2026-09-05; entró antes de que C24 etiquete)

- **C23 (hecho, abierto y archivado el 2026-09-06):** el **segundo índice** del sistema. `ai.product_document` responde a «enséñame anillos de plata» y no puede responder a «¿este anillo se puede mojar?», porque esa respuesta no vive en ningún producto. C23 construye el corpus de conocimiento general, su troceado por secciones, su indexación idempotente en `ai.knowledge_chunk` —tabla que **existe desde C05 y que ningún código escribe todavía**— y su búsqueda con citas. **La exploración corrigió la ficha y el plan en dos puntos, con medición sobre los 1.200 productos:** (1) el corte pre-autorizado del §13.4 bajaba el alcance a **15 documentos**, pero se expresó **en documentos** cuando la cifra que el diseño fija en D5 está **en chunks (150-250)**: quince dan ~80, la mitad, y con un índice tan pequeño **la abstención no se puede demostrar**. Se entregan **32 documentos ≈ 161 chunks**, que es el centro de D5; el corte no se ignora, se refuta por su propia unidad de medida. (2) `guion_venta` **sale del corpus y no por alcance**: un guion es texto imperativo, y un chunk imperativo recuperado dentro de un prompt es indistinguible de una instrucción — convertiría el propio corpus en superficie de inyección, con C31 todavía sin existir. **Y la medición del catálogo funda tres documentos que habrían sido inventados:** la letra de talla del catálogo **no es una talla de dedo sino el tamaño de la pieza** —el tipo que más etiquetas lleva es `pendientes`, que no tiene ajuste—; las colecciones llevan **nombre de calas y cabos reales de Menorca** (`Es Caló Blanc`, `Biniacolla`, `Sa Mesquida`, `Cala Pregonda`, `Cala Presili`, `Binibeca`, `Cavalleria`), lo que rescata un documento que la propia exploración había descartado; y **once de las 28 «colecciones» no son líneas de diseño** sino cajones operativos (`Varios`, `Composturas`, `Tienda`, `Cursos`…), hallazgo de calidad de catálogo que nadie buscaba. **El problema que gobierna el diseño no es de código:** el corpus lo redacta un asistente, porque los textos comerciales que el §8.1 daba como «a pedir al negocio» nunca llegaron, y la verificación de citas es **estructural, no semántica** — puede pasar al 100 % citando algo falso. De ahí `claim_scope` por sección: el origen del texto es constante y vive en el sidecar y en el README, pero el **alcance** varía dentro de un mismo documento y cambia el comportamiento. Sin migración, sin ruta HTTP, sin tocar `openapi.json` ni `indexing/embeddings.py`. Historia [HU-AIENG-023](Historias/AI-Eng/HU-AIENG-023.md), ticket [T-AIENG-023](../openspec/changes/archive/2026-09-06-add-knowledge-corpus-and-indexer/ticket.md) y mediciones en [c23-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c23-exploration-measurements.md) y [c23-implementation-measurements.md](Proyecto%20Final%20AIEng/informes/c23-implementation-measurements.md).

- **C23 — lo que la implementación midió (2026-09-06).** Corpus entregado: **32 documentos y 161 secciones**, exactamente el recuento fijado de antemano, con **25 secciones `establecimiento`** —el 15,5 %, la cifra que el README declara— y **cero `guion_venta`**. **La rama léxica se queda, por medición**, aunque su papel se aclaró en dos pasos: contra el embebedor *offline* ganaba recall (78,1 % frente a 71,9 %), y contra el real **no gana recall sino orden** —93,8 % en las dos configuraciones, con MRR 0,891 frente a 0,854—. Sigue justificada, por reordenar y no por recuperar. El umbral queda **calibrado en 0,51**, y esa cifra llegó por el camino largo: el barrido *offline* que la spec obliga a usar daba 0,81, y al indexar el corpus de verdad ese valor **citaba cuatro de las cinco preguntas fuera de dominio** — el mecanismo de abstención inoperante, no una imprecisión. Contra el embebedor real hay un hueco limpio entre 0,5062 y 0,5145, así que la regla de D8 se aplica literalmente por primera vez. **Latencia p50 60,7 ms** en caliente, que es la que hereda C30, con la rama léxica costando unos 3 ms. **Y la re-medición contra `ai.product_document` destapó lo que ningún test buscaba:** cuatro secciones habían copiado las cifras del catálogo al texto citable —«`pequeño` encabeza con 108», «el 44,6 % del surtido»—, lo que ata el corpus al surtido de hoy y hace que un producto nuevo deje una sección falsa **en silencio**, con la cita resolviendo y localizando igual. La regla 5 gana su segunda mitad y la ingesta la comprueba: **ni recuento ni proporción del surtido**, y el detector lee el vecindario para no borrar mineralogía legítima. Seis secciones reescritas, decisión **D17** en el `design.md` y tres escenarios nuevos en la spec, incluido el que enuncia la propiedad de verdad: *añadir o retirar un producto no invalida ningún documento*. Suite completa en verde —incluidos los tests de base contra pgvector— en la corrida del 2026-09-06; **cero migraciones** y `openapi.json` byte a byte idéntico.

- **FIX1 (hecho, 2026-09-05):** cierre de las lagunas del vocabulario de enriquecimiento. `piece_type.terms` pasa de ocho a doce con `diadema`, `gemelos`, `cinturon` y `llavero`; prompt **`enrichment/v2`** con la lista ampliada y la línea que advierte de que el catálogo puede contener servicios, consumibles y regalo —la salida `null` ya existía en C09: **lo que faltaba era el encargo, no la opción**—; y `load_prompt()` pasa a derivar la ruta de `PROMPT_VERSION`, que hasta ahora se declaraban por separado y podían sellar un perfil con una versión que no lo produjo. **La exploración corrigió dos cosas de la ficha, con medición contra la base viva:** (1) la población es de **22 productos y no de 11** — once sin tipo, **nueve mal tipados** y dos falsos amigos («Cinturón de Orión», la constelación) que deben quedarse como están; y el mal tipado es peor que el nulo, porque el filtro de categoría es duro y hoy **seis de los 85 `broche` son tres diademas, dos gemelos y un llavero**, más dos diademas en `collar` y una en `colgante`; (2) su criterio de extremo a extremo —*«buscar "diadema" pasa de cero a resultados»*— **ya se cumple hoy**: la rama léxica de C21 alcanza los 11 documentos porque el nombre está en `doc_text`, así que un verificador lo firmaría verde por el motivo equivocado. Los criterios se reescriben como **estructurales**: nulos 11 → 1, facet `diadema` 0 → 11, impostores en `broche` 6 → 0. Reenriquecer sólo los once nulos entregaría un desplegable que ofrece «Diadema» y devuelve **5 de 11**, que es la firma de C17 en su versión peor —no dice cero, dice cinco—, así que la cohorte son los 22 con los dos de Orión como **grupo de control que debe no moverse**. Toca además **dos specs vivas y no una** (`catalog-enrichment-pipeline` y `query-expansion`) y hace saltar **cuatro tests fijados y no dos**, uno de ellos con `DID NOT RAISE` porque usa `diadema` como ejemplo de canónico desconocido. Sin migración, sin tocar `openapi.json`, sin mover `source-text/v1` ni `embedding_version`. Historia [HU-AIENG-FIX1](Historias/AI-Eng/HU-AIENG-FIX1.md), mediciones en [fix1-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/fix1-exploration-measurements.md) y acta de la corrida en [fix1-vocabulary-gaps-measurements.md](Proyecto%20Final%20AIEng/informes/fix1-vocabulary-gaps-measurements.md). **La corrida encontró lo que ningún test podía encontrar:** la línea nueva sobre servicios, consumibles y artículos de regalo dejó sin tipo a dos de los tres llaveros —un llavero *es* un artículo de regalo—, así que `v2` declara la precedencia de la lista cerrada sobre esa advertencia y la cohorte se volvió a correr entera. Grupo de control intacto campo a campo, 19 filas reembebidas por una sola sincronización, `embedding_version` sin mover.

**User Stories:**
- [HU-AIENG-006a: Ingesta del catálogo real y corpus enriquecido versionado](Historias/AI-Eng/HU-AIENG-006a.md) *(C06a — corpus JSONL + informe)*
- [HU-AIENG-006b: Ampliación sintética del catálogo — LLM, colecciones nuevas e ingesta local](Historias/AI-Eng/HU-AIENG-006b.md) *(C06b — hecho; CLI en `jbg_ai.data`; sin familias)*
- [HU-AIENG-009: Pipeline de enriquecimiento del catálogo — extracción estructurada con vocabularios cerrados](Historias/AI-Eng/HU-AIENG-009.md) *(C09 — hecho; extractor real de `POST /v1/enrich/products`)*
- [HU-AIENG-010: Simulador de mundo sintético — POS, inventario e histórico de ventas](Historias/AI-Eng/HU-AIENG-010.md) *(C10 — hecho; CLI `world simulate` / `world ingest`; YAML en git, JSONL gitignored)*
- [HU-AIENG-011: SourceText canónico y cliente de embeddings con idempotencia por hash](Historias/AI-Eng/HU-AIENG-011.md) *(C11 — hecho; biblioteca `jbg_ai.indexing`, sin HTTP ni SQL)*
- [HU-AIENG-023: Corpus de conocimiento comercial e índice de citas verificables](Historias/AI-Eng/HU-AIENG-023.md) *(C23 — **hecho**; 32 documentos Markdown versionados en `data/knowledge/` con ~161 secciones, `claim_scope` por sección con dos valores —`general` frente a `establecimiento`— y **cero** guiones de venta; troceado por secciones sin solape, con los dos títulos dentro de `content` para que entren a la vez en el embedding y en el `tsv` generado; identidad determinista del chunk (`uuid5` de `<doc_slug>#<section_slug>`) más `citation_id` legible, de modo que la cita **resuelve, localiza y abre el fichero del repositorio** — nunca `uuid4`, nunca `chunk_index`, que repuntaría en silencio cada cita al insertar una sección; indexación idempotente con `content_hash` en `metadata` para no re-embeber lo que no cambió; búsqueda híbrida que **importa** `retrieval/fusion.py` de C21 sin reescribir una línea y compone su rama léxica desde los grupos de C20, con umbral de abstención propio porque el 0,65 se calibró para documentos de producto; paquete propio `jbg_ai/knowledge/` como desviación declarada de la ficha, que asignaba zona sólo de indexación y sin embargo pedía un test de búsqueda; mini-medición de ~32 preguntas más fuera de dominio **sin usar las tablas `ai.eval_*`**, que las crea C24; y la generación del corpus planificada en **ocho encargos, uno por bloque y cada uno en su propia ventana o subagente**, porque 161 secciones no caben en una sola y de una vez las últimas fichas dejan de parecerse a las primeras)*
- [HU-AIENG-FIX1: Cerrar las lagunas del vocabulario de enriquecimiento — cuatro tipos de pieza, `enrichment/v2` y una cohorte de veintidós](Historias/AI-Eng/HU-AIENG-FIX1.md) *(FIX1 — **hecho**; `piece_type.terms` de 8 a 12 con `diadema`, `gemelos`, `cinturon` y `llavero`; prompt `v2` con el encargo que faltaba sobre servicios y consumibles, y `v1.md` conservado intacto porque 1.178 perfiles siguen declarando venir de él; `load_prompt()` derivando la ruta de `PROMPT_VERSION`; cohorte enumerada de 22 SKU con `force` —11 sin tipo y **9 mal tipados**— y los dos «Cinturón de Orión» como grupo de control que debe no moverse; espejo del frontend a 12 opciones, con `cinturon` sin tilde como `value` y «Cinturón» como `label`, porque el filtro compara por igualdad exacta; cierre de las cuatro exclusiones del overlay de C20 y forma de superficie `gemelo`; `filigrana` fuera por ser hueco de `style_tags`; **dos deltas de specs vivas** y **cuatro tests fijados** que saltan a propósito; sin migración, sin OpenAPI y sin mover `source-text/v1` ni `embedding_version`)*

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
- ✅ Propuesta asistida de familias y aprobación por lotes: **156 familias y 486 miembros creados** el 2026-08-31 (C18a)
- Pantalla de revisión y aprobación por ítem (segundo caso de intervención humana del PF) — C18b
- Alerta de huérfanos: productos con similitud alta a una familia a la que no pertenecen — C18b
- Pantalla de revisión de perfiles de IA con métricas de calidad — C28

**Changes asociados:** C07 (hecho), **C18a (hecho)**, **C18b (hecho, archivado 2026-09-01)**, C28

**Nota de secuencia.** C07 entrega la entidad y su edición manual, no la inteligencia: agrupar ~350 familias a mano es inviable y por eso existe C18. Lo que C07 hace posible es que haya un sitio donde esas familias vivan y se corrijan, y que `Product` no gane ninguna columna en el proceso. C07 reserva además `Origin`, `ApprovedByUserId` y `ApprovedAt` para que C18 —que no tiene turno de migración de EF Core— pueda registrar la aprobación humana sin abrir uno. **C18a ejerció esa reserva el 2026-08-31**, que hasta entonces no tenía ningún camino de escritura.

**C18 se partió en dos el 2026-08-31**, según la regla 5 del plan: se entrega primero la mitad que desbloquea. **C18a** es el motor y el camino de escritura —lo que hace que `family_id` deje de ser nulo, y con ello que dejen de ser vacuos los tests de familia de C25, C26, C30 y C36—; **C18b** es la pantalla de revisión y la alerta de huérfanos, que necesitan familias ya existentes para tener algo que revisar.

**Entregable C18a.** Motor determinista en [`ai-service/src/jbg_ai/families/`](../ai-service/src/jbg_ai/families/) —raíz normalizada, fusión por material con guarda de raíz degenerada, puerta de `piece_type`, veto **relativo** por embedding que marca y no elimina—, novena ruta del contrato `POST /v1/families/suggest`, y en .NET `POST /api/ai/catalog/family-suggestions` más `/apply`, que persiste vía `ProductFamilyService` para que el feed incremental vea las altas. Reconciliación en **una sola** sincronización: `upserted 486, deleted 32, failed 0`. Informe: [`informes/c18a-family-suggestion-report.md`](Proyecto%20Final%20AIEng/informes/c18a-family-suggestion-report.md).

- [HU-AIENG-007: Entidad de familia de producto y edición manual](Historias/AI-Eng/HU-AIENG-007.md) *(C07 — hecho)*
- [HU-AIENG-018a: Propuesta asistida de familias y aprobación por lotes](Historias/AI-Eng/HU-AIENG-018a.md) *(C18a — hecho; 156 familias / 486 miembros; `Origin = AiApproved`; 32 entradas que no son joyería retiradas del índice con `ReviewStatus = Rejected`, nunca con `IsActive`; cola de revisión de 15 miembros en 5 familias)*
- [HU-AIENG-018b: Revisión humana de familias, alerta de huérfanos y veredicto persistente](Historias/AI-Eng/HU-AIENG-018b.md) *(C18b — hecho, 2026-09-01; **la cola de 15 miembros de C18a ya no existía** y el change se reformuló de «pintar una cola» a «auditar lo que hay»: aquella cola vivía en una respuesta de `suggest` que nunca se persistió, y sus productos ya pertenecen a familias. `POST /v1/families/audit` —**décima ruta** del contrato congelado— recomputa sobre las familias persistidas, reutilizando el veto relativo con otro universo, y en la misma llamada nomina huérfanos: son la misma comparación leída desde los dos lados de la pertenencia. **Nominación por margen relativo, nunca por umbral absoluto** — medido, la pureza de vecindario dispara sobre los casi-duplicados sintéticos y el margen sobre huecos reales del catálogo; la pureza queda como señal de orden. Entidad nueva `FamilyReviewVerdict` sobre el par `(producto, familia)` —**séptima migración del plan, más dos que la propia revisión obligó a añadir**— que es a la vez el registro de descarte y el sello de aprobación por ítem que la aprobación por lotes no podía dar. Listado paginado y disolución de familias en `ProductFamiliesController`. Pantalla de administración en [`/admin/family-review`](../frontend/src/pages/admin/family-review.tsx) con **tres estados por lista** puestos en el tipo (`AuditOutcome`) y no en el render: una auditoría que no se pudo calcular **nunca** se pinta como catálogo limpio. Revisión real ejecutada: **58 juicios, 17 de 18 pertenencias confirmadas y 6 de 40 candidatos aceptados**, 7 aplicados al catálogo. Sinónimo `dorado` → `baño de oro` en el vocabulario de enriquecimiento. Informe en [c18b-family-review-report.md](Proyecto%20Final%20AIEng/informes/c18b-family-review-report.md))*

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
- **C16 (hecho, 2026-08-29):** panel «Buscar con ayuda» en [`/sales/new/assisted`](../frontend/src/pages/sales/assisted.tsx), tercera tarjeta del hub de ventas y entrega al flujo manual por estado de navegación (patrón de `scan.tsx`). **Envío explícito** de la consulta con consultas de ejemplo — nunca `debounce`: la clave de la caché de candidatos incluye la cadena completa, así que ningún prefijo acierta y cada pulsación intermedia facturaría un embedding contra el límite de 30 peticiones por minuto y usuario. Filtros de material (multi-selección) y tipo de pieza sobre el vocabulario cerrado replicado en [`materials-vocabulary.ts`](../frontend/src/lib/materials-vocabulary.ts) con test de fijación; **no disparan búsqueda por sí solos**. Resultados **en el orden recibido**, con insignia de origen y chips de materiales en lugar del `matchReasons` crudo (que es la constante `["vector"]` hasta C21), y talla sólo cuando `variantLabel` exista (lo puebla C18). **Cuatro estados sin resultados** —abstención, sin surtido, degradado o desactivado, y cuota agotada (`429`, que la spec de C15 exige no confundir con indisponibilidad)— más el aviso de **página corta**. Embudo colapsado sólo para administradores. **Tramo .NET sin migración:** `SearchEventId` opcional en `CreateSaleRequest` y `BulkSaleLineRequest`, asignado tras comprobar **existencia y propiedad** del evento; un identificador desconocido o ajeno degrada la atribución a nula y **nunca hace fallar la venta**. Cierra el requisito de atribución de `ai-search-telemetry`, que estaba archivado como cumplido y no tenía camino por el que cumplirse. Historia [HU-AIENG-016](Historias/AI-Eng/HU-AIENG-016.md).
- **C20 (hecho, archivado 2026-09-01):** diccionario de sinónimos **de consulta** para la rama léxica de C21. Dos capas: [`enrichment/vocabularies.yaml`](../ai-service/src/jbg_ai/enrichment/vocabularies.yaml) aporta las clases base y **no se modifica** —tocarlo obliga a `enrichment/v2` y a reenriquecer—, y [`retrieval/query_synonyms.yaml`](../ai-service/src/jbg_ai/retrieval/query_synonyms.yaml) añade lo que no debe entrar en el contrato de extracción: **artefactos del stemmer español** (`collar`/`collares` da 140 documentos frente a 1; `baño`/`bano` da 38 frente a 0, porque pliega tildes agudas pero no la `ñ`), variantes del oficio que la base no tiene, y un puente **direccional** entre vocabularios. `expand_query` es **función pura** y devuelve **grupos de equivalencia más los términos resueltos**, nunca una cadena reescrita: medido, una sola `tsquery` ensanchada saca del top-10 los tres productos llamados literalmente «Sortija». Flag `JPV_QUERY_EXPANSION_ENABLED` con default en `Settings` y **valor por parámetro** del orquestador, para que C24 barra configuraciones sin reiniciar. **Observe-only**: log `stage=expand` y la expansión **no se consume** hasta C21, lo que se declara en vez de disimularse. Sin migración, sin tocar `openapi.json`, sin reindexar. Historia [HU-AIENG-020](Historias/AI-Eng/HU-AIENG-020.md).
- **C21 (hecho, archivado 2026-09-02):** búsqueda híbrida — enciende por fin la columna `tsv` que C05 dejó generada, indexada y **sin consumidor**, y consume los grupos de equivalencia que C20 dejaba calculados y sin leer. **Fusión RRF de tres listas**: la tecleada, la expandida y la vectorial. La exploración midió contra los 1.168 documentos vivos y el proveedor real, y **refutó cuatro cosas escritas antes**: (1) la conjunción estricta entre grupos deja **7 de las 10 consultas reales** del operador en cero documentos, y el *zero-drop* rescata sólo una — se adopta **OR entre grupos con ordenación por coordinación**, que contiene al AND y lo pone en cabeza; (2) `@>` sobre materiales alcanza **60 documentos frente a 913** de `&&`, y 126 documentos no tienen materiales extraídos, así que los filtros deducidos del texto **degradan y nunca excluyen** —*lo que un humano pulsó, filtra; lo que una regla dedujo, degrada*—; (3) la paridad de peso entre ramas es la **peor** de las fusiones (96/120 frente a 105/120 con peso vectorial 0,33), porque la rama vectorial **no abstiene** y bajo RRF vota siempre; (4) el realce de SKU y nombre exacto **no compra nada** — un nombre exacto ya encabeza las dos listas léxicas y ante un SKU la rama vectorial devuelve cero candidatos; (5) dar **profundidades desiguales** a las listas (200 léxica frente a 60 vectorial) cuesta **6-8 puntos de 120**, porque con `k=60` el documento de la posición 200 conserva el 38 % del voto del primero y esa cola larga desplaza al consenso — regla adoptada, **`profundidad ≈ k`, simétrica en 60**; (6) los campos **subjetivos están cubiertos al 11-19 %** (`Ocasiones:` 150 de 1.168, `boda` casa **5** documentos), así que la coordinación los convertía en dictadores: cinco piezas etiquetadas adelantaban a 1.163 igual de válidas — **la coordinación pasa a contar sólo los campos cuya ausencia es evidencia**, con la consecuencia elegante de que una consulta subjetiva queda en manos de la rama vectorial **sin un segundo peso que calibrar**. Y un supuesto de C14 que cae: el **umbral de 0,65 no filtra nada** —deja pasar 1.168 de 1.168 en consultas ordinarias y sólo abstiene ante texto sin sentido—, así que el corte real de la rama vectorial es el `LIMIT` y su recalibración por cuantil queda anotada para C25. Además: `match_reasons` deja de ser la constante `["vector"]`, `mode` deja de mentir, si cae el proveedor de embeddings se sirve la rama léxica **y se dice en pantalla**, `low_confidence` pasa a significar desacuerdo entre ramas **sólo cuando corrieron dos** —con una sola rama ningún candidato puede aparecer dos veces, así que la regla marcaría todas las respuestas y el campo no informaría de nada, y allí conserva el significado de C14: no se devolvió nada—, y se paga la deuda del **singleton del cliente de embeddings** con caché **acotado** —el `dict` sin cota de C11 es inofensivo por petición y una fuga de por vida como singleton—. Sin migración, sin tocar `openapi.json`, sin tocar `backend/`. Historia [HU-AIENG-021](Historias/AI-Eng/HU-AIENG-021.md), mediciones en [c21-hybrid-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c21-hybrid-exploration-measurements.md).
- **C22 (hecho, archivado 2026-09-05):** prefiltro blando por punto de venta. Enciende `ai.pos_projection`, que C05 creó y nadie escribió nunca, tirando del feed `GET /api/ai/index-feed/pos-availability` que C12 dejó servido y C13 tenía prohibido consumir — CLI `python -m jbg_ai.indexing sync-pos`, checkpoint propio (`feed = 'pos-availability'`) y **una revisión de Alembic aditiva** (`ai.pos_projection.computed_as_of`) que el change abrió **contra su propia ficha**: el instante de referencia que su alcance exige no tenía dónde persistirse y, con drenaje incremental, la proyección acabaría con filas contadas contra dos relojes distintos e indistinguibles. La exploración midió y **reencuadró cuatro puntos de la ficha**: (1) el problema de la página corta no era de FORNELLS sino de **ocho de los once puntos de venta** —al menos 6 de cada 20 búsquedas por debajo de una página de 10, peor caso **un solo producto**, y una consulta de MAO-AIR con **cero** supervivientes—; (2) el filtro duro correcto es **`is_assigned_hint`** replicando `Carried()` de .NET, porque excluir lo que la autoridad ya excluye no cuesta nada y los desasignados son el **7-9 %** en los POS con operador — lo que de verdad se degrada sin eliminar es el **stock**, y ahí la señal es gruesa (**MAO-AIR tiene el 34,4 % de su surtido a cero**); (3) el **índice HNSW no se ha usado nunca** en la ruta viva —el planificador elige escaneo exacto desde C14: 8-11 ms frente a **113,7 ms** forzándolo, que además devuelve **40 de las 60 filas pedidas** por `ef_search = 40`—, así que escopar con CTE más distancia exacta no cambia de motor y encima acelera (7,3 ms); (4) el tombstone `unassigned` se aplica como **borrado suave**, porque `IsAssignedHint` viaja hoy hardcodeado a `true` y sin ello el campo sería inalcanzable y C26 no podría distinguir «nunca lo llevaste» de «lo dejaste de llevar». `projection_age_seconds` **gobierna comportamiento** —proyección vacía → 503, vieja → se desactiva el filtro duro y se declara— y sale del checkpoint y **nunca** de `max(refreshed_at)`, porque con un feed incremental ese campo mide cuándo cambió la asignación y no cuándo se miró. Incluye además el **reloj inyectado** (`IndexFeed:SalesAsOf = 2026-08-23T23:59:59Z`): el mundo de C10 termina el 2026-08-23 y, contra el reloj de pared, `sales_30d` cae del **16,28 %** de pares no nulos a **cero el 26 de septiembre** — C25 calibraría sobre una señal muerta y concluiría que la rotación no aporta. Y no es un parche: C24 exige `test_run_is_reproducible_for_same_config_and_seed` y el §16 pide ablations reproducibles, así que un ranking que lee `now()` ya era irreproducible por diseño. Historia [HU-AIENG-022](Historias/AI-Eng/HU-AIENG-022.md), mediciones en [c22-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c22-exploration-measurements.md) y [c22-implementation-measurements.md](Proyecto%20Final%20AIEng/informes/c22-implementation-measurements.md). Al archivarse **nace la capacidad viva `pos-projection`**.
- Recuperación vectorial sobre HNSW y léxica con `ts_rank` en español, fusionadas con RRF
- Diccionario de sinónimos del dominio aplicado en expansión de consulta, nunca en indexación
- Prefiltro blando: el surtido del punto de venta acota, y la disponibilidad penaliza el score pero **nunca excluye** un candidato (**C22**)
- Sobre-recuperación (`top_k × 3`, tope 60) para que .NET tenga margen tras hidratar
- Abstención por umbral: devolver cero resultados es información válida
- Endpoint de búsqueda en .NET con hidratación, circuit breaker y fallback léxico
- Panel de búsqueda asistida en el frontend

**Changes asociados:** C12 (hecho), C13 (hecho), C14 (hecho), C15 (hecho), C16 (hecho), C20 (hecho), C21 (hecho), **C22 (hecho)**, **C25** (`recalibrate-ranking-and-abstention` — **hecho**, abierto el 2026-09-11 y archivado el 2026-09-12; renombrado desde `add-business-signals-ranking`), **C25bis** (`clean-plain-fusion` — **implementado el 2026-09-12**, 45/45, pendiente de archivar)

> **Actualizado el 2026-09-12, al implementar C25bis.** El borrado **no movió nada, y está demostrado**: dos corridas del arnés sobre el mismo golden set y la misma huella de índice dan **315 filas por consulta idénticas** en las cinco configuraciones supervivientes, listas de resultados incluidas, y el único elemento de la procedencia que difiere es la revisión del código. Suite **994 → 997 con cero fallos** a los dos lados. **Tres puntos de su ficha se refutaron por comprobación**: los pesos por lista sí tenían lector vivo —se retiran por ser trampas que la spec prohíbe mover, no por estar muertos—, la variante adaptativa perdedora no existía porque C25 ya la había retirado, y el fallo al arranque no era alcanzable con `extra="ignore"` y tenía más radio de daño que el defecto que prevenía, así que la obligación se acotó a la configuración de evaluación, donde ya estaba implementada: **cero código nuevo**. El principio que queda escrito es *una perilla es algo que se puede poner; un registro es algo que se escribe* — por eso `Provenance.fusion_mode` sobrevive al selector y `judgements.jsonl` conserva `v2-hibrido` en `pooled_in` mientras `POOLED` lo pierde. La fila de referencia queda **histórica y citable** con tres artefactos —informe, JSONL y su propia configuración, movida a `evals/configs/retired/`— y **por qué se retiró sigue demostrable sin ser activable**, como aritmética pura sobre `fuse()`.

- **C25bis (implementado el 2026-09-12, creado el 11):** limpieza del andamio de C25, y **fuera de la numeración C principal** por el mismo motivo que `FIX1`: no sale de la descomposición original del proyecto sino de una consecuencia de C25. Aquél **conserva la fusión plana como modo seleccionable** porque sin ella la fila `v2-hibrido` de la tabla de ablations deja de ser reproducible y el change pierde la referencia contra la que se leen todas las demás filas. Publicada la tabla y congelada la configuración, ese modo pasa a ser lo contrario de lo que era: **un camino muerto, activable por error, cuya aritmética el proyecto midió como defectuosa** — los 60 documentos léxicos ganando al mejor candidato vectorial en toda consulta, y el grado 2 cayendo a la posición 33. Retira además la variante de ponderación adaptativa que pierda el barrido de C25 y las perillas que queden sin lector, con un **inventario comprobado por búsqueda y no por memoria**, porque este subsistema ya sorprendió cuatro veces con cables calculados y sin consumidor (`tsv`, la expansión, `qty_bucket` y `coordination`) y aquí el riesgo es el simétrico: retirar algo que sí tenía lector. **Acepta un coste y lo declara:** la fila de la línea base deja de poder re-medirse y pasa a ser **histórica y citable** —su informe y su JSONL por consulta quedan versionados—, porque la alternativa era mantener vivo un camino medido como roto, y un camino muerto que se puede activar por error es cómo un defecto corregido regresa. **No re-mide nada y no tiene autoridad para mover una cifra:** su criterio de verificación es que las filas supervivientes den cifras **idénticas** tras el borrado, y cualquier diferencia es un fallo del change que se revierte, no un resultado que discutir. Sin migración, sin contrato y sin diff fuera de `ai-service/`. Change [`clean-plain-fusion`](../openspec/changes/archive/2026-09-12-clean-plain-fusion/).

- **C25 (hecho, abierto el 2026-09-11 y archivado el 2026-09-12):** recalibración del ranking y de la abstención. La exploración encontró un **defecto que vale más que todo el alcance original de la ficha: la fusión vigente no fusiona, concatena.** Con `w_typed 0,50 + w_expanded 0,50 = 1,00` votos frente a `w_vector = 0,33`, un documento léxico en el **rango 60** —el peor puesto posible— puntúa 0,008333 y el mejor documento que sólo vio la rama vectorial puntúa 0,005410: **los 60 documentos léxicos ganan al #1 vectorial, en toda consulta, siempre.** Verificado en el run publicado de C24: el grado 2 que la vectorial pone en el #1 cae en la **posición 33** en tres consultas distintas, los 32 anteriores son **sólo léxicos** y la cola conserva **exactamente** el orden vectorial. Y hay un segundo sesgo que nadie había visto: `typed` y `expanded` se truncan por separado, así que la rama léxica puede meter **120 documentos** frente a los 60 de la vectorial — **el doble de huecos y el triple de voto**. La corrección es **fusión en dos etapas con pesos por rama**: las dos listas léxicas se fusionan entre sí y el resultado se fusiona con la vectorial, de modo que el voto total de la rama es exactamente `w_lex` **sin depender de cuántas de sus listas dispararon** (hoy el umbral de cruce es 0,469 o 0,938 según si el AND de `websearch` casó, una propiedad de la consulta que nadie declaró). Medido con `fuse()` real: **sólo importa el cociente `ρ = w_vec / w_lex`**, así que el barrido es de una dimensión, y la **banda útil es `ρ ∈ [0,9 ; 1,1]`** —a 0,95 el #1 vectorial entra en el top-5, a 0,90 cae al 8— donde la rejilla de C24 tenía **un solo punto**: por eso su óptimo parecía un filo de cuchillo. Más una **regla adaptativa `w_lex × cobertura` con cero parámetros**, que consume el `coordination` que hoy se calcula, viaja en el *hit* y **el orquestador no lee nunca** —cuarto cable pelado, tras `tsv`, la expansión y `qty_bucket`—; su punto crítico es el denominador, porque las palabras vacías **cuentan como grupo** (`['de']`, `['una']`, `['y']`) con `tsquery` vacía, y con el denominador ingenuo la regla **recortaría un tercio del peso léxico en `sortija de plata`, que puntúa nDCG 1,000**, destruyendo justo las categorías que existe para no tocar. **Y el juez de C24 es ciego a lo que este change añade:** `criterion.md` no menciona stock ni rotación, así que un barrido que maximice nDCG@5 converge a **peso 0** en todas las señales — se resuelve con una **métrica derivada sin re-etiquetar** (`g_efectivo = máx(grado−1, 0)` si `qty_bucket = '0'`, que no inventa una constante sino que **reutiliza la escala**: el grado 1 ya es *«sustituto plausible que el operador ofrecería como segunda opción»*) y la relevancia pura como **guardarraíl**. Además: la señal de POS se separa del alcance (`LEFT JOIN` que lee frente a `INNER JOIN` que restringe), porque hoy el golden set corre sin POS y **la penalización de disponibilidad de C22 no se disparó ni una vez** en las 192 filas del run; la rotación entra como **desempate declarado y no calibrado**, porque no hay instrumento que la pueda aprobar —la rúbrica no premia rotar, la vía online tiene **31 filas**, y la señal es no nula en el 23,54 % de los pares—; y la abstención se diseña **después** de medir `min(distancia)` **por consulta**, que es la cantidad que decide y que **no existe en ningún artefacto** (C24 midió el solape **por documento**, que es otra pregunta). **Dos puntos de la ficha quedan refutados por medición:** la penalización de variante ambigua —sólo 2 de 156 familias pueden llenar cinco huecos, el panel ya pinta `Talla {variantLabel}`, `variante-talla` ya es la mejor categoría y diversificar **baja** el nDCG@5, así que la agrupación es presentación y pertenece a C30/C36— y la calibración de `1-2` frente a `3+`, que **no tiene función objetivo posible** porque ninguno de los dos pierde grado. Y la **regla de decisión heredada se reformula con argumento y fecha antes de re-medir**: **6 de 8** consultas de ajuste están en el techo del nDCG@5 y **las 8** en el de Recall@5, P@3 y MRR, y **7 de 8 salen de la lista curada de C20/C21** — la condición *«mismo signo en las tres lecturas»* veta subir el peso vectorial con las consultas elegidas para que la léxica ganase, y una partición que C24 declaró **contaminada** (0,942 en ajuste contra 0,535 en nuevas) es evidencia de sobreajuste del titular, **no un grupo de control**. **Al aplicar, la medición confirmó lo grande y refutó tres cosas más.** La fusión por rama vale **+0,083** sobre la línea base en la lectura que decide, y el modelo reprodujo la **posición 33** exacta en las tres consultas. La regla adaptativa por cobertura aporta **+0,128** en `descripcion-sin-anclaje` y **cero exacto** en las otras siete categorías —la predicción falsable de su diseño, confirmada contra el índice vivo— y hace algo que ninguna cifra agregada deja ver: convierte la elección del cociente de rama de **acantilado en meseta**, con el recorrido del barrido cayendo de **0,070 a 0,007**; sin ella, elegir mal `ρ` cuesta siete centésimas. La señal de disponibilidad retira el **91 %** de las piezas agotadas del top-5 y es quirúrgica: sólo mueve 13 de las 48 consultas. **Y se retiran tres puntos, no dos.** La **rotación sale del orden**, refutada durante el apply: como el desempate estricto que su propio requisito describía decidía **cero** pares del top-5, y como clave de ordenación no desempataba sino que **particionaba** —11.067 pares invertidos, sólo el 3,4 % adyacentes y el 71,2 % a más de diez puestos— con coste medido en las dos lecturas; `sales_30d` se sigue leyendo para diagnóstico y **no ordena nada**, con la prohibición devuelta a estructural. Se retira también la **variante binaria** de la regla adaptativa, indistinguible de la continua en los 16 puntos del barrido, y con ella el último número que parecía ajustado: **C25 no deja ni un peso calibrado** — `ρ = 1,0` es de principio y ahora además medido como robusto, y el de disponibilidad decide su **signo y no su valor**, porque con un término binario el orden es invariante a la magnitud. **La abstención resultó no caber en un escalar:** el mejor acierto de las contestables llega a 0,7118 y el de las imposibles arranca en 0,4469, o sea **contención total** y no solape parcial, confirmada después sobre **20** consultas y no cinco; la regla adoptada es **relativa por consulta** y lee la **forma** del perfil —una consulta imposible es *plana*— subiendo la abstención de 0,050 a **0,150 sin silenciar ni una contestable**. **Tres listones no se alcanzan y se declaran en vez de cerrarse:** `Recall@5` **0,758** contra 0,85, abstención **0,150** contra 0,80, y `v3` no bate a `v2b` por el margen —**+0,030** operativo— aunque cumple su propia regla de adopción, porque el golden set es **estructuralmente ciego** a la disponibilidad y lo que falta es resolución y no evidencia. La categoría `fuera-de-dominio` pasa de **5 a 20** consultas, con el equilibrio de material **medido y declarado**: nombrar «de plata» acerca la consulta 0,12 al catálogo y la hace parecer contestable, así que un conjunto construido todo de una forma mediría el metal y no la ausencia. Sin migración, sin tocar `openapi.json`, sin reindexar y sin diff en `backend/`, `frontend/`, `terraform/` ni `.github/workflows/`, verificado contra el punto de nacimiento de la rama. Historia [HU-AIENG-025](Historias/AI-Eng/HU-AIENG-025.md), ticket [T-AIENG-025](../openspec/changes/archive/2026-09-12-recalibrate-ranking-and-abstention/ticket.md), decisiones en [c25-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c25-exploration-measurements.md) y [c25-implementation-measurements.md](Proyecto%20Final%20AIEng/informes/c25-implementation-measurements.md), tabla en [c25-baselines-2026-09-11.md](../ai-service/evals/results/c25-baselines-2026-09-11.md).

**User Stories:**
- [HU-AIENG-012: Feeds HTTP de indexación con cursor, tombstones y autenticación de servicio](Historias/AI-Eng/HU-AIENG-012.md) *(C12 — `GET /api/ai/index-feed/catalog` y `.../pos-availability`; API Key `X-Index-Feed-Key`; sin migración / sin push)*
- [HU-AIENG-013: Indexador de `ai.product_document` desde el feed de catálogo](Historias/AI-Eng/HU-AIENG-013.md) *(C13 — pull del feed de catálogo; mapa SKU en `src/jbg_ai/indexing/sku_provenance.json`; OpenAPI keyset; sin POS / sin `embeddings.py`)*
- [HU-AIENG-014: Recuperación vectorial real en `POST /v1/retrieval/products`](Historias/AI-Eng/HU-AIENG-014.md) *(C14 — retriever vectorial; umbral 0,65; hybrid=vector hasta C21; sin `query_log` / sin OpenAPI / sin `embeddings.py`)*
- [HU-AIENG-015: Endpoint de búsqueda asistida en .NET con hidratación autoritativa](Historias/AI-Eng/HU-AIENG-015.md) *(C15 — `POST /api/ai/search`; ventana máxima en una llamada sin repetición; hidratación por POS que conserva el stock cero; buscador degradado con full-text español sin índice; flag en configuración con `SearchOrigin.Disabled`; caché de candidatos y rate limit; sin migración)*
- [HU-AIENG-016: Panel «Buscar con ayuda» del operador, con atribución de la venta a la búsqueda](Historias/AI-Eng/HU-AIENG-016.md) *(C16 — panel en `/sales/new/assisted`; envío explícito sin `debounce`; filtros sobre vocabulario cerrado; cuatro estados sin resultados incluida la cuota agotada; página corta declarada; embudo sólo para admin; atribución de la venta a la búsqueda, sin migración)*
- [HU-AIENG-020: Diccionario de sinónimos de consulta para la rama léxica](Historias/AI-Eng/HU-AIENG-020.md) *(C20 — base `vocabularies.yaml` sin modificar más overlay de consulta; artefactos del stemmer como contenido de primera clase; grupos de equivalencia en vez de cadena reescrita; puente direccional; flag en la firma del orquestador; observe-only con informe de alcance medido; sin migración y sin OpenAPI)*
- [HU-AIENG-021: Búsqueda híbrida — rama léxica, fusión RRF de tres listas y filtros estructurales que degradan](Historias/AI-Eng/HU-AIENG-021.md) *(C21 — **implementado**; OR con ordenación por coordinación en vez de conjunción estricta; fusión RRF de lista tecleada, expandida y vectorial con pesos configurables y rama vectorial a menor peso; filtros deducidos del texto que degradan y nunca excluyen; `@>` y realce de exacto descartados con medición; degradación honesta a léxico cuando cae el proveedor; `low_confidence` como desacuerdo entre ramas; singleton del cliente de embeddings con caché acotado; sin migración, sin OpenAPI y sin tocar `backend/`)*
- [HU-AIENG-022: Prefiltro blando por punto de venta — la proyección pondera, el surtido acota y el reloj deja de derivar](Historias/AI-Eng/HU-AIENG-022.md) *(C22 — **hecho**, archivado 2026-09-05; sincronización de `ai.pos_projection` desde el feed de disponibilidad con CLI y checkpoint propio; tombstone `unassigned` como borrado suave; filtro duro sobre `is_assigned_hint` replicando `Carried()`; CTE de alcance más KNN exacto en las tres ramas, porque HNSW nunca se usó y forzarlo trunca a 40 de 60; `qty_bucket = '0'` degrada y nunca elimina; `projection_age_seconds` desde el checkpoint —nunca desde `refreshed_at`— gobernando 503 sobre proyección vacía y degradación declarada sobre proyección vieja; reloj inyectado `IndexFeed:SalesAsOf`; flag de ablación para C24; **una revisión de Alembic aditiva** (`computed_as_of`) abierta contra su propia ficha, `openapi.json` regenerado y **tres deltas MODIFIED** sobre specs vivas, más la capacidad nueva `pos-projection`)*
- [HU-AIENG-025: Recalibrar el ranking y la abstención — que la fusión fusione, que el stock pese y que el buscador sepa callar](Historias/AI-Eng/HU-AIENG-025.md) *(C25 — **hecho**, archivado el 2026-09-12; fusión en **dos etapas** con pesos por rama, que corrige el defecto por el que los 60 documentos léxicos ganaban al #1 vectorial **siempre** y lo dejaban en la posición 33; el barrido pasa a **una dimensión** porque sólo importa el cociente `ρ = w_vec / w_lex`, con banda útil `[0,9 ; 1,1]` que la rejilla de C24 sólo tocaba en un punto; regla adaptativa `w_lex × cobertura` **sin parámetros**, consumiendo el `coordination` que se calculaba y se tiraba, con el denominador corregido para excluir los grupos de `tsquery` vacía; **métrica `nDCG@5 operativo`** derivada de los juicios existentes **sin re-etiquetar**, con la relevancia pura como guardarraíl, porque la rúbrica de C24 no menciona stock y un barrido sobre ella converge a peso 0; señal de POS por `LEFT JOIN` **separada** del alcance por `INNER JOIN`, para medir la reordenación sin pagar el coste de recall del prefiltro; rotación como **desempate declarado y no calibrado**; abstención diseñada **después** de medir `min(distancia)` por consulta y con `fuera-de-dominio` ampliada de 5 a 15-20; barrido en fases `capture`/`rescore` que hace el de señales **exacto y sin proveedor**; tabla de **seis filas** con `v2b-fusion` aislando la fusión de las señales y la fusión plana **conservada** como modo para que `v2-hibrido` siga reproduciendo la línea base; **dos puntos de la ficha refutados por medición** —penalización de variante ambigua y calibración de `1-2`/`3+`—; dos capacidades nuevas (`business-signals-ranking`, `retrieval-abstention`) y tres deltas `MODIFIED`; **sin migración, sin OpenAPI y sin tocar `backend/`, `frontend/` ni `terraform/`**)*

---

## Épica 15: Venta Asistida, Sustitutos y Agentes

**Descripción:**
Capa de generación y agéntica. Convierte un conjunto de candidatos en una respuesta útil para el operador: agrupada por familia, con avisos calculados por reglas, argumentario con citas y sugerencias de sustitutos o complementarios.

**Alcance:**
- Respuesta estructurada con `groups[]` por familia y `variant_label` destacado
- Avisos calculados por reglas (variantes en la familia, talla ausente, stock crítico), nunca generados libremente
- Argumentario generado en tiempo de consulta con `citations[]`, no persistido. **Lo que se cita lo construye C23 en EP12**: sin corpus de conocimiento indexado no hay `citations[]`, sólo prosa. C30 lo consume en proceso como la tool `consultar_conocimiento` del agente de venta, sin ruta HTTP de por medio, y **debe propagar el `claim_scope` de cada fragmento**: un compromiso de la joyería no se presenta como un hecho comprobable
- **Toda cifra de precio o stock se emite como placeholder** que resuelve .NET; si alguno queda sin resolver, la respuesta se rechaza
- Guardrails, enrutado de intención y pregunta de aclaración ante consultas ambiguas
- Agente asistente de venta con *tools* de solo lectura e intervención humana
- Sustitutos por falta de stock. ~~Complementarios por reglas y co-ocurrencia~~ — **cortado el 2026-09-12 con medición** (ver abajo)
- Tarjeta de asistencia y desambiguación por familia en el frontend

**Changes asociados:** **C26** (`add-substitutes-retrieval` — **archivado el 2026-09-12**, 62/62), ~~C27~~ (**cortado**), C30, C31, C32, C34, C36

> **Ampliado el 2026-09-12, al implementar C26.** **`POST /v1/retrieval/substitutes` deja de responder 501** y pasa a servir candidatos reales, con lo que cae el **último 501 cerrable** del contrato congelado —`/v1/inventory/propose` también responde 501, pero su rama se anuló el 31 de agosto y eso ya está declarado como limitación—. Sin migración, sin mover `openapi.json` y **sin una sola llamada al proveedor**: sustituto es producto→producto y el embedding de origen ya está almacenado, así que la capacidad entera es una sentencia SQL. Suite de `ai-service` de **997 a 1038 passed, 0 failed**; `openspec validate --all --strict` en **55/0**.
>
> **Tres cosas que la implementación añadió a lo que la exploración ya había refutado.** (1) **`w_size = 0,05` lo fija el barrido, no el diseño**: once puntos de rejilla, y el término resulta hacer algo —de `0` a `0,05`, **+0,1039 de nDCG@5**—, lo que confirma que la conclusión de C25 *«el valor del peso no cambia el orden, sólo su signo»* **no se traslada** aquí. Las dos lecturas del criterio **discrepan** y eso se publica como hallazgo, porque `criterion.md` lo manda: el nDCG graduado premia `0,075`, pero desde `0,07` la lectura binaria cae y entra en un top-5 un anillo liso de la talla correcta y nada más —el grado 0 explícito de la rúbrica—, así que gana el guardarraíl y, dentro de él, `0,06` y `0,05` empatan por debajo del ruido. (2) **El bloque entero se midió antes de descartarlo**: con la clave de bloque, el hermano de familia más cercano de `SKU13` cae del puesto 1 al **4**, detrás de un anillo que está al doble de distancia, y el más lejano sale de la ventana visible. (3) **La tarea de verificar que la tabla de ablations no se movía acabó siendo una corrección**: los ficheros publicados no cambian, pero el *runner* iteraba todas las consultas juzgadas, que pasaron de **63 a 68** al etiquetar las cinco de sustituto, así que una re-ejecución habría absorbido consultas que dos de sus configuraciones **no pueden ejecutar**. La separación quedó en código (`GoldenSet.retrieval_queries`) y no en una convención: antes de C26 los dos conjuntos coincidían y el alcance era correcto **por accidente**.
>
> **Dos limitaciones medidas, declaradas y no cerradas.** `style_similarity` es cero por construcción para **403 de 404** productos reales —el contrato la exige requerida y no nulable, así que se emite el cero y **la ausencia se declara en `match_reasons`**, y no se deriva del embedding porque sería una copia de `score`—; y la rebanada aísla la calidad del sustituto **dado el producto origen correcto**, ya que la cadena «texto → producto → sustitutos» es de C32. A ellas se suma el sesgo declarado de que el etiquetado de las 126 parejas lo hizo quien diseñó el orden, acotado —no eliminado— por que la rúbrica es anterior al change y por que se etiquetó sobre atributos y nunca sobre posiciones. Historia [HU-AIENG-026](Historias/AI-Eng/HU-AIENG-026.md), mediciones en [c26-implementation-measurements.md](Proyecto%20Final%20AIEng/informes/c26-implementation-measurements.md) y rebanada en [c26-substitutes-slice.md](../ai-service/evals/results/c26-substitutes-slice.md).

> **Ampliado el 2026-09-12, al abrir C26.** **C26 (`add-substitutes-retrieval`) pasa a en curso**, con historia ([HU-AIENG-026](Historias/AI-Eng/HU-AIENG-026.md)), ticket ([T-AIENG-026](../openspec/changes/archive/2026-09-12-add-substitutes-retrieval/ticket.md)) y mediciones ([c26-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c26-exploration-measurements.md)). Es el **séptimo change consecutivo cuya exploración refuta lo escrito antes**, tras C21, C22, FIX1, C23, C24 y C25 — y esta vez lo que invierte es el **orden** que la ficha pedía. Cierra el último **501 cerrable** del contrato congelado y ocupa el único eslabón vivo de la cadena crítica `C26 → C34 → C36`.
>
> **Lo que la medición refuta: «misma familia primero» lidera con los candidatos invendibles.** La familia es, por construcción, el conjunto de piezas que se diferencian **justo en el atributo que descalifica** — la talla. Vecinos por coseno de `SKU13 Anillo erizo de mar M`: los tres primeros son el mismo anillo en talla **L, S y XL**, el cuarto es un **colgante** (otro tipo de pieza) y **el primer sustituto usable es el #6**. Pero la familia tampoco se puede excluir: el mejor sustituto de `SKU159 Anillo lapislázuli mediano` es su hermano `mediano oro` —**misma talla, otro material**— y es el **#1**. **La pertenencia a familia es ortogonal; el discriminante es la talla**, y cruza la frontera de la familia en las dos direcciones. Lo confirma el criterio de etiquetado que el proyecto ya tenía escrito: `criterion.md` clasifica «falla la talla que la consulta nombró» como **grado 1 — segunda opción**, no como respuesta.
>
> **El diseño que sale de ahí:** filtro **duro** por `piece_type` —el vector lo viola en 2 de 4 casos—, familia **en el conjunto pero sin prioridad**, y **degradación suave por talla como término continuo en la cola** (`w ≈ 0,05`, barrido; con 0,02 no mueve nada y con 0,08 el hermano cae al puesto 8), **inerte cuando alguna de las dos piezas no declara talla** — porque el **54 % de los anillos** no tiene `size_label` y penalizar por una ausencia es tratarla como valor, que es lo que `ports.py` ya prohíbe. **No reutiliza `demotion_rank`**: su bloque entero de talla particiona, que es exactamente el fallo que C25 midió con la rotación.
>
> **Tres decisiones más, todas medidas.** La **exclusión por stock sale de Python**: estaba especificada dos veces y la versión correcta es la de C34, que respeta la frontera del §6.2 y el invariante del §15.10 —la proyección degrada y nunca elimina—. **`style_similarity` no tiene dato**: sólo **1 de 404** productos reales tiene con quién compartir etiqueta de estilo, frente al **97,8 %** que lo tiene por material, así que se emite el Jaccard y **la ausencia se declara en `match_reasons`** en vez de derivarlo del embedding, que lo convertiría en una copia de `score`. Y **no abstiene**: todo producto del catálogo tiene vecino a menos de **0,255** y el rango de los productos sin familia contiene el de los que la tienen — la misma contención que impidió a C25 re-fijar su umbral escalar. **Cero llamadas al proveedor**: sustituto es producto→producto y el embedding de origen ya está almacenado.
>
> **Cómo se mide:** las cuatro consultas que C24 dejó declaradas sin juicios a nombre de C26 (`q49`–`q52`) se anclan con **`source_product_id` explícito** y se evalúan en **rebanada separada**, porque el endpoint recibe `product_id` y no texto y añadir filas movería el denominador de la tabla publicada. **Entra una quinta consulta sin familia** (`SKU102`), porque las cuatro reservadas tienen familia y el camino sin ella es el **58 %** del catálogo.

> **Actualizado el 2026-09-12 — C27 cortado con medición, no por plazo.** **C27 (`add-complementary-recommendations`) sale del alcance.** Era el corte nº 1 pre-autorizado desde el 31 de agosto, con el disparador *«si el núcleo peligra»*; con prórroga abierta ese disparador no decide nada, así que se sustituyó por uno de evidencia. **Sus dos señales están vacías.** La co-ocurrencia se deriva del `BulkOperationId` y **todas las ventas las escribe el simulador de C10**, cuyo `_pack_operations` baraja las líneas del día y luego escoge deliberadamente el artículo **de lexema o colección distinta**: la matriz está sesgada **en contra** de lo que se le pide medir. Y aunque no lo estuviera, de **4.078 pares** el **98,6 % se ha visto una sola vez**, ninguno tres o más en dieciséis meses, y **463 de 1.168 productos (39,6 %) no tienen ni un socio**. La otra mitad de la regla —solape de `color_tags`/`style_tags`— está indefinida para el **74,7 %** del catálogo y para **403 de 404 productos reales**. Lo que quedaría en pie es `WHERE piece_type <> :tipo AND price_band IN (…) AND stock > 0`, sin una llamada a un LLM: el criterio exacto con el que se anularon cinco changes el 31 de agosto. **Y nunca hubo intención de medirlo:** ni la tabla del §11.1 del diseño ni el golden set reservan categoría a complementarios —las 8 consultas sin juzgar son 4 de C26 y 4 de C31—, así que el change **no puede añadir una fila a la evaluación** a cambio de la última migración EF Core viva. **No hay cestas reales ni las habrá:** el export del 17 de agosto fue catálogo y nada más. Se conservan la ficha, la tabla `ai.co_occurrence` vacía y `cooccurrence.py` con su test; se retiran la tool `buscar_complementarios` de C32, la ruta `.../recommendations` de C34 y el bloque «También puede encajar» de C36. **Condición de reactivación, comprobable:** un export con histórico real a nivel de ticket cuyo percentil 95 de `co_sales_count` sea **≥ 3** — hoy es **1**. Detalle en [c27-cut-measurements.md](Proyecto%20Final%20AIEng/informes/c27-cut-measurements.md).

---

## Épica 16: Inventario Asistido y Señales de Demanda — ⛔ ANULADA (2026-08-31)

> **Toda la rama del agente de inventario está anulada**: C19, C29, C33, C35 y C37. El motivo y sus consecuencias están en el §0 del [plan de changes](Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) (entrada del 2026-08-31) y en el §10 del [diseño RAG](Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md), donde el diseño se conserva como registro. En corto: **cuatro de los ocho cortes pre-acordados vivían dentro de esta rama**, y lo que quedaba en pie tras dispararlos era una migración, un motor de reglas .NET y una pantalla de aprobación — todo el esfuerzo fuera de lo que el Proyecto Final evalúa. Los agregados de venta que el ranking necesita (`sales30d`, `sales90d`, `lastSaleAt`, `qtyBucket`) **ya están implementados** en el feed de indexación de C12 y son normativos desde la spec viva `index-feed`: C19 habría construido una segunda copia de la misma agregación, con el riesgo de que las dos definiciones divergieran.
>
> El alcance de abajo se conserva **como registro de lo que se decidió no hacer**, no como trabajo pendiente. Las fichas de los cinco changes siguen en el plan con su sello ⛔.

**Descripción:**
Segundo agente del proyecto. Propone reposiciones, traslados entre puntos de venta y acciones sobre stock parado, siempre con aprobación humana. Las señales numéricas se calculan en SQL en .NET; el LLM solo redacta y prioriza.

**Alcance *(anulado — registro histórico)*:**
- Señales de demanda calculadas en SQL: ventas a 7/30/60 días, cobertura, días sin venta, stock en otros puntos de venta
- Perfil comercial por punto de venta, calculado periódicamente
- Entidad `InventoryRecommendation` con ciclo de aprobación y auditoría
- Agente de inventario con propuestas priorizadas y justificadas
- Pantalla de revisión de recomendaciones y vista imprimible por punto de venta

**Changes asociados:** ~~C19~~, ~~C29~~, ~~C33~~, ~~C35~~, ~~C37~~ — **los cinco anulados el 2026-08-31**. C33 (`add-pos-sales-profile`) queda anotado en el plan como *rescatable suelto* si alguna vez hiciera falta el perfil comercial por punto de venta para el ranking.

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

**Changes asociados:** C04 (hecho), **C24** (`add-eval-harness-golden-set-and-baselines` — **hecho**, abierto el 2026-09-06 y archivado el 2026-09-11), C38, C39

- **C24 (hecho, abierto el 2026-09-06 y archivado el 2026-09-11):** el **juez imparcial** del recuperador. El sistema tiene una búsqueda híbrida completa —expansión (C20), fusión RRF de tres listas (C21), prefiltro por punto de venta (C22)— y **ninguna de sus decisiones se tomó con una métrica de relevancia**: se tomaron con una rúbrica que los propios informes declararon insuficiente, y los cuatro escribieron *«C24 lo re-mide»*. Esa rúbrica cuenta aciertos como «tipo de pieza correcto y material correcto», y el informe de C21 la recusa él mismo — *«`doc_text` lleva líneas canónicas `Tipo:` y `Materiales:`, y la expansión apunta justo ahí»*—; bajo ella la rama vectorial saca **67 de 120** frente a **107** de la léxica sola, es decir siete puntos de ciento veinte para justificar el proveedor externo y el índice HNSW. **Y el riesgo dejó de ser teórico el mismo 2026-09-06:** en el corpus de conocimiento, el sustituto *offline* de C23 había medido que la rama léxica ganaba +6,2 pp de recall, y contra el embebedor real el veredicto **se invirtió** —93,8 % en las dos configuraciones, sólo mejora el orden—, además de dejar un umbral que citaba cuatro de las cinco preguntas fuera de dominio. De ahí la primera regla del change: **se mide contra el proveedor real y el índice real, nunca contra un sustituto**. **La exploración cerró trece decisiones y reencuadró la ficha en cuatro puntos:** (1) `v0-lexico` son **dos filas y no una** —`v0-nombre`, el `Name.Contains` que la joyería tenía y que responde la decisión 12, y `v0-fts`, el degradado en español que construyó el propio trabajo de IA— porque juntas informan de qué parte de la mejora es tokenizar en español, gratis y sin IA, y qué parte es recuperación semántica; (2) el golden set baja de 60-70 a **48 juzgadas y 56 escritas**, derivadas **desde los pleitos** y no desde la ficha, con una **matriz de trazabilidad comprobada por código** que falla la carga si el conjunto no contiene, por ejemplo, doce consultas cuya respuesta perfecta no comparte ni un término con la consulta — la contención del riesgo de que el golden set confirme a C21 por construcción; (3) `v0-cag` deja de ser una fila de calidad y pasa a ser **la prueba medida de por qué existe RAG**, porque CAG no tiene una sola línea en el sistema y el PF exige describirlo como componente: entrega tokens, coste y **curva de escala** hasta el punto en que deja de caber, con contexto compactado y **sin precio**, porque la autoridad sobre el precio es .NET; (4) **dos desviaciones que tocan fuera de su zona** — el desempate determinista en las dos sentencias de `retrieval/search.py`, sin el cual dos ejecuciones idénticas difieren y el arnés deja de detectar regresiones, y el cambio de defaults en `Settings` bajo una regla escrita **antes** de medir. Historia [HU-AIENG-024](Historias/AI-Eng/HU-AIENG-024.md), ticket [T-AIENG-024](../openspec/changes/archive/2026-09-11-add-eval-harness-golden-set-and-baselines/ticket.md) decisiones en [c24-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c24-exploration-measurements.md) y **mediciones de la implementación** en [c24-implementation-measurements.md](Proyecto%20Final%20AIEng/informes/c24-implementation-measurements.md). **El veredicto, medido el 2026-09-07 sobre las 48 consultas juzgadas:** el buscador que la joyería tenía saca **nDCG@5 0,082**, el degradado en español **0,454**, la rama vectorial sola **0,548** y el híbrido vivo **0,603** — es decir, tokenizar en español aporta +0,372 y es gratis, y la recuperación semántica aporta +0,149 encima. **La rúbrica de C21 queda refutada**: contra un juez que no es parte, la rama vectorial no aporta siete puntos de ciento veinte, sino que **bate a la línea léxica**, y en las doce consultas sin anclaje léxico saca 0,431 frente a 0,035. Tres hallazgos que nadie buscaba: la fusión vigente **pierde más de la mitad** de la ventaja de su rama vectorial justo en esas consultas (0,172 el híbrido frente a 0,431 la vectorial sola); las distancias de los documentos relevantes y las de los irrelevantes **se solapan por completo**, de modo que queda demostrado que C25 necesita un cuantil por consulta y no un escalar; y la regla de defaults, escrita antes de medir, **bloquea** el cambio de `wC` a 1,0 pese a mejorar +0,057 global y +0,073 en las consultas nuevas, porque empeora en la partición de ajuste — que es el caso incómodo para el que la regla se escribió.

**User Stories:**
- [HU-AIENG-004: Telemetría de búsqueda asistida — evento consulta→selección](Historias/AI-Eng/HU-AIENG-004.md) *(C04 — hecho)*
- [HU-AIENG-024: Arnés de evaluación, golden set y líneas base](Historias/AI-Eng/HU-AIENG-024.md) *(C24 — **hecho**, archivado el 2026-09-11; golden set de 48 consultas juzgadas y 56 escritas en `ai-service/evals/golden/`, versionado en git para que cambiar la vara de medir pase por revisión de código, con relevancia graduada 0-2 de anclas mecánicas y publicando **también** la lectura binaria derivada, que es lo que contesta con datos la objeción del apunte de S10 en vez de con argumento; cinco líneas base —`v0-nombre`, `v0-fts`, `v0-cag` acotado, `v1-vectorial`, `v2-hibrido`— y **una** revisión de Alembic con `ai.eval_run/case/result`, que la migración fundacional nunca creó; reproducibilidad por **vectores de consulta congelados** más una tupla de procedencia `(golden_set_version, config_id, index_set_hash, embedding_model_version_key, git_sha)` que sustituye a la semilla aleatoria que la ficha pedía y que no existe en un pipeline determinista; ***pooling* de profundidad adaptativa** —base 20, +10 mientras el tramo siga dando relevantes, tope 60— con juicios **apendables** por `(query_id, product_id)` y `unjudged@5` reportado, de modo que `v3-señales` de C25 pueda profundizar sin re-etiquetar y sepa cuándo su fila no es comparable; desglose por `data_origin` **agrupando por consulta y contando por juicio**, con la recuperación siempre sobre los 1.168 documentos porque restringir el corpus a la porción real daría 436 y **inflaría** el número del titular; y `GET /v1/evals/runs`, publicado en el `openapi.json` congelado desde C02 y con un stub que nombra a C24 por escrito, dejando por fin de ser stub **sin mover el contrato**)*

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
| **EP12** | Corpus y Enriquecimiento del Catálogo | C06a (hecho), C06b (hecho), C08 (hecho), C09 (hecho), C10 (hecho), C11 (hecho), **C23 (hecho)**, **FIX1 (hecho)** | 🔴 parcial |
| **EP13** | Familias de Producto y Desambiguación | C07 (hecho), C18a (hecho), C18b (hecho), C28 | 🟢 parcial |
| **EP14** | Búsqueda Semántica Híbrida | C12, C13, C14, C15, C16, C20, C21, **C22**, **C25** (hechos) | 🟠 parcial |
| **EP15** | Venta Asistida, Sustitutos y Agentes | **C26 (archivado)**, ~~C27~~ *(cortado 12 sep)*, C30, C31, C32, C34, C36 | 🟠 parcial |
| **EP16** | ~~Inventario Asistido y Señales de Demanda~~ | ~~C19, C29, C33, C35, C37~~ | ⛔ **anulada 31 ago** |
| **EP17** | Evaluación y Observabilidad de IA | C04 (hecho), **C24 (hecho)**, C38, C39 · *(C25 amplía el arnés y el golden set desde EP14)* | 🔴 parcial |
| **TOTAL PF** | | **43 fichas · 37 vivas** (5 anuladas, 1 cortada) — **27 archivadas, 10 pendientes** | |

> **Recuento actualizado el 2026-09-05.** Las 42 fichas son 41 numeradas —C01–C39 con C06 y C18 partidas en dos— más **`FIX1` (`fix-enrichment-vocabulary-gaps`)**, que hasta ahora no aparecía en esta tabla: nació de un hallazgo de C18a, va deliberadamente **fuera de la numeración C** y pertenece a EP12 por zona (`enrichment/`, prompts y espejo del frontend). Está **detrás de C22 y antes de que C24 etiquete**, porque `preprocessing_id` sigue siendo `source-text/v1` y no delataría el cambio de vocabulario.
>
> **Ampliado el 2026-09-05, al explorarlo.** FIX1 abrió el mismo día con historia ([HU-AIENG-FIX1](Historias/AI-Eng/HU-AIENG-FIX1.md)), ticket y mediciones ([fix1-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/fix1-exploration-measurements.md)). La exploración **corrigió su ficha en dos puntos**: la población es de **22 productos y no de 11** —nueve de ellos están mal tipados, que es peor que estar sin tipar porque el filtro de categoría es duro— y su criterio de extremo a extremo **ya se cumplía antes del change**, porque la rama léxica de C21 alcanza las once diademas por el nombre. Es el tercer change consecutivo cuya exploración refuta lo escrito antes, tras C21 y C22.
>
> **Ampliado el 2026-09-06, al abrir C24.** **C23 se archivó** ese mismo día y **C24 (`add-eval-harness-golden-set-and-baselines`) pasa a en curso**, con historia ([HU-AIENG-024](Historias/AI-Eng/HU-AIENG-024.md)), ticket y decisiones ([c24-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c24-exploration-measurements.md)). Recuento: **25 archivadas, 12 pendientes**. Se elige por la regla 2 del §5 del plan llevada a su extremo: es **el único change pendiente que bloquea a dos** —C25 y C38— y el siguiente eslabón de la cadena crítica `C21 → C24 → C25 → C26 → C34 → C36`. Es el **quinto change consecutivo cuya exploración refuta lo escrito antes**, tras C21, C22, FIX1 y C23, y lo hace en cuatro puntos: el golden set baja de 60-70 a 48 juzgadas **derivadas desde los pleitos y no desde la ficha**, `v0-lexico` se parte en dos filas porque el repositorio contiene dos buscadores léxicos y sólo uno es anterior al trabajo de IA, `v0-cag` deja de ser una fila de calidad para ser la prueba medida de por qué existe RAG, y el change abre **dos desviaciones fuera de su zona** —el desempate determinista en `retrieval/search.py` y el posible cambio de defaults en `Settings`—. **Y su primera regla la escribió C23 unas horas antes:** el sustituto *offline* con el que aquel change calibró su umbral resultó dejar el mecanismo de abstención inoperante e **invirtió su propio veredicto sobre la rama léxica** al re-medirse contra el proveedor real, así que C24 mide contra el proveedor y el índice reales, nunca contra un sustituto.
>
> **Ampliado el 2026-09-06, al abrir C23.** **C23 (`add-knowledge-corpus-and-indexer`) pasa a en curso**, con historia ([HU-AIENG-023](Historias/AI-Eng/HU-AIENG-023.md)), ticket y mediciones ([c23-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c23-exploration-measurements.md)). Los recuentos de la tabla no se mueven —sigue habiendo 24 archivadas y 13 pendientes— porque abrir no es archivar. Es el **cuarto change consecutivo cuya exploración refuta lo escrito antes**, tras C21, C22 y FIX1, y el primero que refuta **al plan y no a su propia ficha**: el corte pre-autorizado del §13.4 fijaba el alcance en 15 documentos, pero lo expresó en documentos cuando el objetivo del diseño está en chunks. Se elige por desbloqueo y no por calendario, como manda la regla 2 del §5 del plan: **no está en la cadena crítica** `C21 → C24 → C25 → C26 → C34 → C36`, pero es prerrequisito **único** de C30 y con él de toda la rama de generación `C30 → C31 → C32 → C38 → C39`, así que entra por el lado sin taponar a nadie.
>
> **Ampliado el 2026-09-11, al abrir C25.** **C25 pasa a en curso** y se **renombra** de `add-business-signals-ranking` a **`recalibrate-ranking-and-abstention`**, porque el nombre anterior describía un tercio de su alcance; el número se conserva, ya que renumerar rompería las referencias de C26 (`prereq C22, C25`) y C27 (`C10, C25`) a cambio de nada. Los recuentos no se mueven —siguen **26 archivadas y 11 pendientes**— porque abrir no es archivar. Es el **sexto change consecutivo cuya exploración refuta lo escrito antes**, tras C21, C22, FIX1, C23 y C24, y el primero que refuta **dos puntos de su propia ficha con una medición** en lugar de reencuadrarlos: la penalización de variante ambigua —el reparto real de familias de C18a acota la inundación a **2 de 156**, el panel ya pinta `Talla {variantLabel}`, `variante-talla` ya es la mejor categoría con 0,830 y diversificar **baja** el nDCG@5 cuando las hermanas son grado 2— y la calibración de `1-2` frente a `3+`, que **no tiene función objetivo posible** porque con la ganancia efectiva ninguno de los dos pierde grado. **Y encontró un defecto que vale más que todo su alcance original:** la fusión de C21 **no fusiona, concatena** — los 60 documentos léxicos ganan al #1 vectorial **siempre**, medido en el run publicado como la posición 33 en tres consultas distintas, con los 32 anteriores **sólo léxicos** y la cola conservando **exactamente** el orden vectorial. El óptimo que el barrido de C24 encontró (`wC` 0,75-1,0) no era un peso mejor: era **el intervalo de los umbrales de cruce de la fórmula**. Y la regla de decisión que bloqueó aquel cambio se reformula con argumento y fecha **antes** de re-medir, porque su partición de ajuste tiene **6 de 8** consultas en el techo del nDCG@5, **las 8** en el de Recall@5, P@3 y MRR, y **7 de 8** salidas de la lista con la que se calibró la rama léxica: una partición que C24 declaró contaminada (0,942 contra 0,535) es evidencia de sobreajuste del titular, **no un grupo de control**. Historia [HU-AIENG-025](Historias/AI-Eng/HU-AIENG-025.md), ticket [T-AIENG-025](../openspec/changes/archive/2026-09-12-recalibrate-ranking-and-abstention/ticket.md), mediciones en [c25-exploration-measurements.md](Proyecto%20Final%20AIEng/informes/c25-exploration-measurements.md).
>
> **Actualizado el 2026-09-11, al archivar C24.** **C24 (`add-eval-harness-golden-set-and-baselines`) pasa a hecho** y con él la cadena crítica arranca en **C25**. Recuento: **26 archivadas, 11 pendientes**. El change entrega el juez imparcial que cuatro changes archivados prometieron por escrito: 48 consultas juzgadas a mano con relevancia graduada, y un veredicto que **refuta la rúbrica de C21** — aquélla daba 67 de 120 a la rama vectorial contra 107 de la léxica, y contra un juez que no es parte la vectorial (nDCG@5 **0,548**) bate a la línea léxica (**0,454**), con el híbrido vivo en **0,603** y el buscador que la joyería tenía en **0,082**. La regla de cambio de defaults, escrita antes de medir, **bloquea** mover `wC` a 1,0 pese a un +0,057 global: empeora en la partición de ajuste, que es el caso incómodo para el que la regla se escribió. Informe en [c24-implementation-measurements.md](Proyecto%20Final%20AIEng/informes/c24-implementation-measurements.md).
>
> **Actualizado el 2026-09-12, al archivar C25.** **C25 (`recalibrate-ranking-and-abstention`) pasa a hecho** y con él la cadena crítica arranca en **C26**. Recuento: **27 archivadas, 10 pendientes**. Al archivarse **nacen dos capacidades vivas** — `business-signals-ranking` (la disponibilidad como reordenación blanda calibrada contra el golden set) y `retrieval-abstention` (la regla que decide **si** contestar) — y se modifican `hybrid-fusion`, `pos-projection` y `retrieval-evaluation`. El change entrega lo que su exploración encontró y no lo que su ficha pedía: **la fusión de C21 no fusionaba, concatenaba**, y componerla en **dos etapas con pesos por rama** vale **+0,083** sobre la línea base en la lectura que decide (nDCG@5 de 0,673 a **0,740**). La ponderación por cobertura aporta **+0,128** en `descripcion-sin-anclaje` y **cero exacto** en las otras siete categorías — la predicción falsable de su diseño, confirmada — y convierte la elección del cociente de rama de acantilado en meseta (recorrido del barrido de 0,070 a 0,007). La señal de disponibilidad retira el **91 %** de las piezas agotadas del top-5. **Se retiran tres cosas por medición y no por argumento:** la rotación sale del orden (como desempate estricto decidía **0 pares**; como clave particionaba, invirtiendo 11.067), la variante ambigua (es presentación, pasa a C30/C36) y la variante binaria de la regla adaptativa (indistinguible de la continua). **C25 no deja ni un peso calibrado:** `rho = 1,0` es de principio y medido como robusto, y el de disponibilidad decide su **signo y no su valor**. La abstención resultó **no caber en un escalar** — el rango de las imposibles cae **dentro** del de las contestables — así que la regla adoptada es **relativa por consulta** y lee la *forma* del perfil. **Tres listones no se alcanzan y se declaran en vez de cerrarse:** `Recall@5` **0,758** contra 0,85, abstención **0,150** contra 0,80, y `v3` no bate a `v2b` por el margen (**+0,030** operativo) aunque cumple su propia regla de adopción. Queda **C25bis** (`clean-plain-fusion`) desbloqueado, que es quien cierra EP14.
>
> **Actualizado el 2026-09-12, al cortar C27 y abrir C26.** **C27 sale del alcance con cinco mediciones** (detalle en EP15 y en [c27-cut-measurements.md](Proyecto%20Final%20AIEng/informes/c27-cut-measurements.md)) y **C26 pasa a en curso**. Recuento: **27 archivadas, 10 pendientes** — C25bis, C26, C28, C30, C31, C32, C34, C36, C38 y C39.
>
> **Y el hueco que el corte deja a la vista, que gobierna el orden de lo que queda:** `ai-service/src/jbg_ai/assist/` **no existe**. C30 (generación con citas), C31 (guardrails y router de intención) y C32 (bucle agéntico) están a cero, y son lo que el rubro del PF nombra por su nombre — *«escala desde un prototipo CAG hasta un sistema RAG **con agentes**»*. Ésa, y no complementarios, es la deuda grande de EP15.
>
> **Actualizado el 2026-09-12, al archivar C26.** **C26 (`add-substitutes-retrieval`) pasa a hecho** y con él la cadena crítica deja de arrancar en C26 y arranca en **C34**. Recuento: **29 archivadas, 8 pendientes** (C28, C30, C31, C32, C34, C36, C38 y C39) — suben dos de golpe porque `C25bis` se archivó el mismo día. Con C26 cae el **último 501 cerrable** del contrato congelado: `/v1/inventory/propose` sigue respondiendo 501, pero por una rama anulada el 2026-08-31 y ya declarada como limitación, no por falta de turno. Nace la capability viva `substitutes-retrieval` con diez requisitos, y `vector-retrieval` pierde por escrito la obligación de que la ruta siguiera devolviendo 501. **Lo que C26 no se lleva** y queda anotado en la ficha de **C34**: la exclusión por falta de stock, porque la autoridad sobre el stock es de .NET y en Python la disponibilidad degrada y nunca elimina.

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
6. ~~**EP16**~~ — **anulada el 2026-08-31** junto con sus cinco changes. Ya no ocupa lugar en el orden.
7. **EP17** — la telemetría (C04) se implanta desde el primer día. La evaluación se parte en dos y **no espera a la generación**: **C24** sólo necesita recuperación (EP14) y **está abierto desde el 2026-09-06**, mientras que C38 —validador anti-alucinación, RAGAS y escenarios de agente— sí requiere EP15 y se integra en el runner que C24 entrega. **C24 es el único change pendiente que bloquea a dos** (C25 y C38) y está en la cadena crítica `C21 → C24 → C25 → C26 → C34 → C36`.

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

