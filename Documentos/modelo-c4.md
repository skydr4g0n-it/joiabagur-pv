# Modelo C4 - Sistema de Gestión de Puntos de Venta para Joyería

Este documento describe la arquitectura del sistema utilizando el modelo C4, proporcionando diferentes niveles de abstracción desde el contexto general hasta los componentes internos.

---

## Tabla de Contenidos

1. [Nivel 1: Contexto del Sistema](#nivel-1-contexto-del-sistema)
2. [Nivel 2: Contenedores](#nivel-2-contenedores)
3. [Nivel 3: Componentes](#nivel-3-componentes)
   - [3.1 Componentes del Backend](#31-componentes-del-backend)
   - [3.2 Componentes del Frontend](#32-componentes-del-frontend)
   - [3.3 Componentes del Servicio de IA](#33-componentes-del-servicio-de-ia)
4. [Notas sobre Desarrollo vs Producción](#notas-sobre-desarrollo-vs-producción)

---

## Nivel 1: Contexto del Sistema

El **Sistema de Gestión de Puntos de Venta para Joyería** permite gestionar inventario, registrar ventas y facilitar la identificación de productos mediante reconocimiento de imágenes con inteligencia artificial en múltiples puntos de venta (propios y de terceros).

### Actores

- **Administrador**: Usuario con acceso completo al sistema. Puede gestionar productos, inventario, usuarios, puntos de venta, métodos de pago y consultar reportes de todos los puntos de venta.

- **Operador**: Usuario con acceso restringido a puntos de venta asignados. Puede registrar ventas, consultar inventario y gestionar devoluciones en sus puntos de venta asignados.

### Diagrama de Contexto

```mermaid
C4Context
    title Contexto del Sistema - Sistema de Gestión de Puntos de Venta

    Person(admin, "Administrador", "Gestiona productos, inventario, usuarios y puntos de venta")
    Person(operador, "Operador", "Registra ventas en puntos de venta asignados")

    System(sistema, "Sistema de Gestión de Puntos de Venta", "Gestiona inventario, ventas y reconocimiento de productos mediante IA")

    Rel(admin, sistema, "Gestiona el sistema completo")
    Rel(operador, sistema, "Registra ventas y consulta inventario")
```

### Descripción

El sistema permite a los administradores gestionar el catálogo de productos, inventario por punto de venta, usuarios y configuración del sistema. Los operadores utilizan el sistema principalmente desde dispositivos móviles para registrar ventas mediante reconocimiento de imágenes o manualmente, reduciendo errores en la clasificación de productos.

**Características principales:**
- Gestión centralizada de productos e inventario
- Registro de ventas con reconocimiento de imágenes mediante IA
- Gestión de múltiples puntos de venta
- Trazabilidad completa de ventas e inventario
- Optimizado para uso móvil en puntos de venta

---

## Nivel 2: Contenedores

El sistema está compuesto por cinco contenedores principales: una aplicación web frontend, una API backend, un servicio de IA, una base de datos PostgreSQL y un servicio de almacenamiento de objetos.

### Contenedores

#### Frontend Web Application
- **Tecnología**: React/Vue/Angular (SPA), TypeScript
- **Responsabilidades**:
  - Interfaz de usuario para administradores y operadores
  - Reconocimiento de imágenes con IA en cliente (TensorFlow.js/ONNX.js)
  - Gestión de sesión y autenticación
  - Comunicación con API backend mediante HTTP/REST
- **Despliegue**: En AWS producción actual, assets del SPA van **embebidos** en la imagen Docker servida tras nginx en EC2; en desarrollo, servidor local (Vite). CDN sigue siendo patrón válido en Azure u otras cuentas.

#### Backend API
- **Tecnología**: ASP.NET Core Web API (.NET 10), C#
- **Responsabilidades**:
  - Lógica de negocio y reglas de dominio
  - Autenticación y autorización (JWT)
  - Procesamiento de importaciones Excel
  - Validaciones de stock y métodos de pago
  - Gestión de archivos y almacenamiento
- **Despliegue**: Contenedor Docker en **EC2** (pila actual, imagen bundlada) u otros hosts (App Service en Azure, ECS/App Runner en variantes legado)

#### AI Service (`jbg-ai`)
- **Tecnología**: Python 3.11, FastAPI, uvicorn, `uv`, pydantic-settings
- **Responsabilidades**:
  - Recuperación vectorial e híbrida sobre el índice del catálogo (pgvector)
  - Generación con LLM, atribución con citas y guardrails
  - Enriquecimiento del catálogo e indexación (`/v1/enrich`, `/v1/index`)
  - Bucles agénticos de asistencia a la venta y de inventario
  - Evaluación offline (golden set, métricas de recuperación y generación)
- **Lo que NO hace**: no calcula precio, stock ni permisos; no escribe ni lee el esquema `public` por SQL; no atiende al navegador
- **Despliegue**: contenedor Docker en la misma EC2, en red interna; **el puerto no se publica en nginx**. En desarrollo, servicio `jbg-ai` del Compose (`8001` → 8000)
- **Estado actual**: esqueleto ejecutable con `GET /health` (C01). Los routers `/v1/*` y la autenticación de servicio llegan en C02

> **Regla de frontera (diseño §6.2):** *Python calcula parecidos y redacta; .NET calcula números y decide.* El backend .NET actúa de **hidratador** y es la autoridad final: descarta cualquier candidato que ya no cumpla las reglas de negocio.

#### PostgreSQL Database
- **Tecnología**: PostgreSQL 15+ con extensión **pgvector**
- **Responsabilidades**:
  - Almacenamiento persistente de todos los datos del sistema
  - Gestión de productos, inventario, ventas, usuarios, puntos de venta (esquema `public`, propiedad de .NET)
  - Índice vectorial y documentos del corpus (esquema `ai`, propiedad de `jbg-ai`)
  - Índices optimizados para consultas frecuentes
- **Despliegue**: RDS PostgreSQL (AWS) en producción, contenedor `pgvector/pgvector:pg15` en desarrollo

#### Object Storage
- **Tecnología**: AWS S3 / Azure Blob Storage
- **Responsabilidades**:
  - Almacenamiento de fotos de productos (ProductPhoto)
  - Almacenamiento de fotos de ventas (SalePhoto)
  - Almacenamiento de archivos Excel importados (temporal)
- **Despliegue**: S3 bucket (AWS) o Blob Storage container (Azure) en producción, sistema de archivos local en desarrollo

### Diagrama de Contenedores

```mermaid
C4Container
    title Contenedores del Sistema

    Person(admin, "Administrador")
    Person(operador, "Operador")

    System_Boundary(sistema, "Sistema de Gestión de Puntos de Venta") {
        Container(frontend, "Frontend Web Application", "React 19 + TypeScript (SPA)", "Interfaz de usuario y reconocimiento de imágenes en cliente")
        Container(api, "Backend API", "ASP.NET Core Web API (.NET 10)", "Lógica de negocio, autenticación, hidratación y gestión de datos")
        Container(ai, "AI Service (jbg-ai)", "Python 3.11 + FastAPI", "Recuperación vectorial, generación con LLM, enriquecimiento e indexación")
        ContainerDb(db, "PostgreSQL Database", "PostgreSQL 15+ con pgvector", "Esquema public (negocio) y esquema ai (vectores)")
        Container(storage, "Object Storage", "AWS S3", "Almacenamiento de fotos y archivos")
    }

    System_Ext(llm, "Proveedor LLM", "Modelos de lenguaje y embeddings")

    Rel(admin, frontend, "Usa", "HTTPS")
    Rel(operador, frontend, "Usa", "HTTPS")
    Rel(frontend, api, "Realiza peticiones HTTP/REST", "HTTPS")
    Rel(api, db, "Lee y escribe", "PostgreSQL Protocol")
    Rel(api, storage, "Lee y escribe", "S3 API")
    Rel(api, ai, "Consulta con JWT interno de servicio", "HTTP, red Docker interna")
    Rel(ai, db, "Lee y escribe solo el esquema ai", "PostgreSQL Protocol")
    Rel(ai, api, "Sincroniza el índice vía feed paginado", "HTTP")
    Rel(ai, llm, "Genera texto y embeddings", "HTTPS")
```

> El frontend **nunca** se comunica con `jbg-ai`. Si el servicio de IA no responde, el backend degrada al buscador léxico existente y marca `ai_available: false`: el sistema no se cae por culpa de la IA.

### Flujos Principales

#### Flujo de Autenticación
1. Usuario ingresa credenciales en Frontend
2. Frontend envía petición a Backend API (`POST /api/auth/login`)
3. Backend API valida credenciales contra PostgreSQL Database
4. Backend API genera token JWT y lo retorna al Frontend
5. Frontend almacena token y redirige según rol

#### Flujo de Reconocimiento de Imágenes y Venta
1. Operador captura foto del producto en Frontend
2. Frontend procesa imagen localmente con TensorFlow.js/ONNX.js
3. Frontend muestra 3 sugerencias ordenadas por confianza
4. Operador selecciona producto correcto
5. Frontend envía venta a Backend API (`POST /api/sales`)
6. Backend API valida stock y método de pago
7. Backend API crea registro en PostgreSQL Database
8. Backend API sube foto a Object Storage
9. Backend API actualiza inventario en PostgreSQL Database

#### Flujo de Importación de Productos
1. Administrador sube archivo Excel en Frontend
2. Frontend envía archivo a Backend API (`POST /api/products/import`)
3. Backend API procesa Excel y hace matching por SKU
4. Backend API actualiza/crea productos en PostgreSQL Database
5. Backend API retorna resumen de importación al Frontend

---

## Nivel 3: Componentes

### 3.1 Componentes del Backend

El Backend API está organizado en servicios de dominio, controladores REST, repositorios y servicios compartidos.

#### Servicios de Dominio

- **Authentication Service**: Gestiona autenticación de usuarios, generación de tokens JWT, validación de credenciales y control de sesión.

- **User Service**: Gestión de usuarios (crear, editar, desactivar), asignación de operadores a puntos de venta, validación de permisos según roles.

- **Product Service**: Gestión del catálogo de productos (crear, editar, buscar), importación desde Excel con matching por SKU, validación de datos.

- **Inventory Service**: Gestión de stock por punto de venta, importación de stock desde Excel, ajustes manuales, validación de stock disponible, generación de movimientos de inventario.

- **Sale Service**: Registro de ventas, validación de stock y métodos de pago, resolución de precio (oficial o manual según política del POS), persistencia de campos de auditoría de precio (`PriceWasOverridden`, `OriginalProductPrice`), actualización automática de inventario, generación de movimientos de inventario.

- **Return Service**: Gestión de devoluciones, asociación con venta original, incremento automático de stock, generación de movimientos de inventario.

- **Payment Method Service**: Gestión de métodos de pago disponibles, asignación de métodos a puntos de venta, validación de métodos asignados.

- **Point of Sale Service**: Gestión de puntos de venta (crear, editar, activar/desactivar), configuración de política de edición manual de precio (`AllowManualPriceEdit`), validación de asignaciones de operadores.

- **Report Service**: Consultas de historial de ventas con filtros, consultas de inventario, consultas de movimientos de stock, generación de reportes.

#### Servicios Compartidos

- **File Storage Service**: Abstracción para almacenamiento de archivos (local en desarrollo, S3/Blob Storage en producción), gestión de fotos de productos y ventas.

- **Stock Validation Service**: Validación de stock disponible antes de ventas, usado por Sale Service y Return Service.

- **Payment Method Validation Service**: Validación de métodos de pago asignados a puntos de venta, usado por Sale Service.

- **Excel Import Service**: Procesamiento de archivos Excel para importación de productos e inventario, validación de formato y datos.

#### Infraestructura

- **Controllers**: Endpoints REST API organizados por dominio (AuthController, ProductController, SaleController, etc.), validación de entrada, manejo de errores.

- **Repositories**: Acceso a datos mediante Entity Framework Core, abstracción de persistencia, implementación de patrones de repositorio.

- **DbContext**: Configuración de Entity Framework Core, definición de entidades y relaciones, migraciones de base de datos.

- **Middleware**: Autenticación JWT, manejo de errores global, logging, CORS, rate limiting.

#### Diagrama de Componentes del Backend

```mermaid
C4Component
    title Componentes del Backend API

    Container_Boundary(api, "Backend API") {
        Component(authService, "Authentication Service", "C#", "Autenticación y generación de tokens JWT")
        Component(userService, "User Service", "C#", "Gestión de usuarios y asignaciones")
        Component(productService, "Product Service", "C#", "Gestión de catálogo de productos")
        Component(inventoryService, "Inventory Service", "C#", "Gestión de stock e inventario")
        Component(saleService, "Sale Service", "C#", "Registro y gestión de ventas")
        Component(returnService, "Return Service", "C#", "Gestión de devoluciones")
        Component(paymentService, "Payment Method Service", "C#", "Gestión de métodos de pago")
        Component(posService, "Point of Sale Service", "C#", "Gestión de puntos de venta")
        Component(reportService, "Report Service", "C#", "Consultas y reportes")
        
        Component(fileStorageService, "File Storage Service", "C#", "Abstracción de almacenamiento de archivos")
        Component(stockValidationService, "Stock Validation Service", "C#", "Validación de stock disponible")
        Component(paymentValidationService, "Payment Method Validation Service", "C#", "Validación de métodos de pago")
        Component(excelService, "Excel Import Service", "C#", "Procesamiento de archivos Excel")
        
        Component(controllers, "Controllers", "ASP.NET Core", "Endpoints REST API")
        Component(repositories, "Repositories", "Entity Framework Core", "Acceso a datos")
        Component(dbContext, "DbContext", "Entity Framework Core", "Configuración de EF Core")
        Component(middleware, "Middleware", "ASP.NET Core", "JWT, CORS, logging, rate limiting")
    }

    ContainerDb(db, "PostgreSQL Database")
    Container(storage, "Object Storage")

    Rel(controllers, authService, "Usa")
    Rel(controllers, userService, "Usa")
    Rel(controllers, productService, "Usa")
    Rel(controllers, inventoryService, "Usa")
    Rel(controllers, saleService, "Usa")
    Rel(controllers, returnService, "Usa")
    Rel(controllers, paymentService, "Usa")
    Rel(controllers, posService, "Usa")
    Rel(controllers, reportService, "Usa")
    
    Rel(saleService, stockValidationService, "Usa")
    Rel(saleService, paymentValidationService, "Usa")
    Rel(productService, excelService, "Usa")
    Rel(inventoryService, excelService, "Usa")
    Rel(productService, fileStorageService, "Usa")
    Rel(saleService, fileStorageService, "Usa")
    
    Rel(authService, repositories, "Usa")
    Rel(userService, repositories, "Usa")
    Rel(productService, repositories, "Usa")
    Rel(inventoryService, repositories, "Usa")
    Rel(saleService, repositories, "Usa")
    Rel(returnService, repositories, "Usa")
    Rel(paymentService, repositories, "Usa")
    Rel(posService, repositories, "Usa")
    Rel(reportService, repositories, "Usa")
    
    Rel(repositories, dbContext, "Usa")
    Rel(dbContext, db, "Lee y escribe")
    Rel(fileStorageService, storage, "Lee y escribe")
    Rel(middleware, controllers, "Intercepta")
```

### 3.2 Componentes del Frontend

El Frontend está organizado en módulos funcionales, servicios y componentes compartidos.

#### Módulos Funcionales

- **Auth Module**: Componentes de login, gestión de sesión, almacenamiento de tokens, redirección según rol, interceptor HTTP para incluir tokens.

- **Product Module**: Componentes para gestión de productos (listado, creación, edición), importación desde Excel, gestión de fotos de productos, búsqueda por SKU o nombre.

- **Inventory Module**: Visualización de stock por punto de venta, vista centralizada de inventario, ajustes manuales de inventario, historial de movimientos.

- **Sale Module**: Componentes para registro de ventas (manual y con reconocimiento), selección de método de pago, validación de stock, edición manual de precio cuando el POS lo permite, indicador de precio modificado en historial/detalle, confirmación de venta.

- **Image Recognition Module**: Captura de fotos desde cámara móvil, integración con TensorFlow.js/ONNX.js, procesamiento de imágenes, visualización de sugerencias, manejo de errores de reconocimiento.

- **Return Module**: Registro de devoluciones, búsqueda de venta original, asociación con venta, registro de motivo.

- **Payment Method Module**: Gestión de métodos de pago disponibles (solo admin), asignación de métodos a puntos de venta, activación/desactivación.

- **Point of Sale Module**: Gestión de puntos de venta (solo admin), creación, edición, activación/desactivación, configuración de edición manual de precio, asignación de operadores.

- **User Module**: Gestión de usuarios (solo admin), creación, edición, asignación a puntos de venta, control de roles.

- **Report Module**: Consultas de historial de ventas con filtros, visualización de detalles de ventas, consultas de inventario, consultas de movimientos.

#### Servicios y Componentes Compartidos

- **API Client**: Cliente HTTP (Axios/Fetch) para comunicación con backend, configuración de base URL, manejo de errores HTTP, transformación de respuestas.

- **ML Model Handler**: Gestión del modelo TensorFlow.js/ONNX.js, descarga del modelo, carga en memoria, ejecución de inferencia, gestión de versiones del modelo.

- **State Management**: Gestión de estado global (Redux/Vuex/NgRx según framework), store de autenticación, store de productos, store de inventario.

- **Routing**: Configuración de rutas, protección de rutas según roles, navegación programática.

- **UI Components**: Componentes reutilizables (botones, formularios, tablas, modales), diseño responsive, optimizado para móvil.

#### Diagrama de Componentes del Frontend

```mermaid
C4Component
    title Componentes del Frontend Web Application

    Container_Boundary(frontend, "Frontend Web Application") {
        Component(authModule, "Auth Module", "React/Vue/Angular", "Login y gestión de sesión")
        Component(productModule, "Product Module", "React/Vue/Angular", "Gestión de productos")
        Component(inventoryModule, "Inventory Module", "React/Vue/Angular", "Visualización de inventario")
        Component(saleModule, "Sale Module", "React/Vue/Angular", "Registro de ventas")
        Component(imageRecognitionModule, "Image Recognition Module", "React/Vue/Angular", "Reconocimiento de imágenes con IA")
        Component(returnModule, "Return Module", "React/Vue/Angular", "Gestión de devoluciones")
        Component(paymentModule, "Payment Method Module", "React/Vue/Angular", "Gestión de métodos de pago")
        Component(posModule, "Point of Sale Module", "React/Vue/Angular", "Gestión de puntos de venta")
        Component(userModule, "User Module", "React/Vue/Angular", "Gestión de usuarios")
        Component(reportModule, "Report Module", "React/Vue/Angular", "Consultas y reportes")
        
        Component(apiClient, "API Client", "Axios/Fetch", "Cliente HTTP para comunicación con backend")
        Component(mlModelHandler, "ML Model Handler", "TensorFlow.js/ONNX.js", "Gestión y ejecución del modelo de IA")
        Component(stateManagement, "State Management", "Redux/Vuex/NgRx", "Gestión de estado global")
        Component(routing, "Routing", "React Router/Vue Router", "Navegación y protección de rutas")
        Component(uiComponents, "UI Components", "Material-UI/Vuetify", "Componentes reutilizables")
    }

    Container(api, "Backend API")

    Rel(authModule, apiClient, "Usa")
    Rel(productModule, apiClient, "Usa")
    Rel(inventoryModule, apiClient, "Usa")
    Rel(saleModule, apiClient, "Usa")
    Rel(saleModule, imageRecognitionModule, "Usa")
    Rel(returnModule, apiClient, "Usa")
    Rel(paymentModule, apiClient, "Usa")
    Rel(posModule, apiClient, "Usa")
    Rel(userModule, apiClient, "Usa")
    Rel(reportModule, apiClient, "Usa")
    
    Rel(imageRecognitionModule, mlModelHandler, "Usa")
    Rel(imageRecognitionModule, apiClient, "Usa", "Obtiene fotos de referencia")
    
    Rel(authModule, stateManagement, "Usa")
    Rel(productModule, stateManagement, "Usa")
    Rel(inventoryModule, stateManagement, "Usa")
    Rel(saleModule, stateManagement, "Usa")
    
    Rel(authModule, routing, "Usa")
    Rel(routing, authModule, "Protege rutas")
    
    Rel(productModule, uiComponents, "Usa")
    Rel(inventoryModule, uiComponents, "Usa")
    Rel(saleModule, uiComponents, "Usa")
    Rel(imageRecognitionModule, uiComponents, "Usa")
    Rel(returnModule, uiComponents, "Usa")
    Rel(paymentModule, uiComponents, "Usa")
    Rel(posModule, uiComponents, "Usa")
    Rel(userModule, uiComponents, "Usa")
    Rel(reportModule, uiComponents, "Usa")
    
    Rel(apiClient, api, "Realiza peticiones HTTP/REST")
```

### 3.3 Componentes del Servicio de IA

El servicio `jbg-ai` se organiza en routers de dominio, capa de recuperación y generación, y servicios transversales. **Estado actual (C01):** solo existen la fábrica de aplicación, el health y el middleware de trazas; el resto está planificado en los changes C02–C38.

#### Routers de Dominio (`/v1/*`)

- **Retrieval Router**: búsqueda de productos y sustitutos sobre el índice vectorial, con sobre-recuperación y abstención por umbral.
- **Assist Router**: generación de respuesta estructurada agrupada por familia, con avisos calculados por reglas y citas verificables.
- **Inventory Router**: propuestas de reposición, traslado y rotación generadas por el agente de inventario.
- **Enrich Router**: extracción estructurada de perfiles de producto con confianza por campo.
- **Index Router**: sincronización del índice mediante cursor `since` y consulta de deriva.
- **Evals Router**: resultados del harness de evaluación (solo perfil de desarrollo).

#### Capa de Recuperación y Generación

- **Hybrid Retriever**: fusiona búsqueda vectorial (HNSW sobre pgvector) y léxica (`ts_rank` en español con expansión de sinónimos) mediante RRF.
- **Query Analyzer**: extrae por reglas las restricciones estructurales de la consulta (banda de precio, tipo de pieza, talla, materiales).
- **Embedding Client**: genera embeddings solo cuando cambia el `source_hash`, con versionado por modelo.
- **Generation Service**: redacta el argumentario a partir de metadatos aprobados y chunks del corpus, emitiendo `{{price}}` y `{{stock}}` como placeholders que resuelve .NET.
- **Guardrails / Intent Router**: clasifica la intención, detecta consultas fuera de dominio y aplica la política de abstención.
- **Agent Loop**: bucles agénticos con *tools* de solo lectura y puntos de intervención humana.

#### Servicios Transversales

- **Settings**: configuración por entorno con pydantic-settings y *fail-fast* de variables obligatorias. **Existe (C01).**
- **TraceId Middleware**: propaga `trace_id` desde la cabecera o el claim del JWT hacia los logs estructurados. **Existe (C01).**
- **Service Auth Dependency**: valida el JWT interno HS256 y construye el `ServicePrincipal`; el scope del token prevalece sobre el body.
- **Stub Layer**: respuestas deterministas bajo `STUB_MODE` para que .NET integre sin LLM ni base de datos.
- **Eval Harness**: golden set, métricas de recuperación y validador anti-alucinación (ejecución offline).

#### Diagrama de Componentes del Servicio de IA

```mermaid
C4Component
    title Componentes del AI Service (jbg-ai)

    Container_Boundary(ai, "AI Service (jbg-ai)") {
        Component(retrievalRouter, "Retrieval Router", "FastAPI", "Productos y sustitutos")
        Component(assistRouter, "Assist Router", "FastAPI", "Venta asistida con citas")
        Component(inventoryRouter, "Inventory Router", "FastAPI", "Propuestas de inventario")
        Component(enrichRouter, "Enrich Router", "FastAPI", "Enriquecimiento de catálogo")
        Component(indexRouter, "Index Router", "FastAPI", "Sincronización del índice")
        Component(evalsRouter, "Evals Router", "FastAPI", "Resultados de evaluación (dev)")

        Component(auth, "Service Auth Dependency", "PyJWT", "Valida el JWT interno y fija el scope")
        Component(stubs, "Stub Layer", "Python", "Respuestas deterministas bajo STUB_MODE")
        Component(retriever, "Hybrid Retriever", "pgvector + tsvector", "Vectorial + léxico fusionados con RRF")
        Component(analyzer, "Query Analyzer", "Python", "Restricciones estructurales por reglas")
        Component(embeddings, "Embedding Client", "Proveedor LLM", "Embeddings con versionado")
        Component(generation, "Generation Service", "LLM", "Argumentario con citas y placeholders")
        Component(guardrails, "Guardrails / Intent Router", "Python", "Intención, abstención y seguridad")
        Component(agent, "Agent Loop", "Python", "Bucles agénticos con tools de solo lectura")
        Component(settings, "Settings", "pydantic-settings", "Configuración con fail-fast")
        Component(trace, "TraceId Middleware", "Starlette", "Propagación de trace_id")
    }

    Container(api, "Backend API (.NET)")
    ContainerDb(db, "PostgreSQL · esquema ai")
    System_Ext(llm, "Proveedor LLM")

    Rel(api, auth, "Bearer JWT interno")
    Rel(auth, retrievalRouter, "Inyecta ServicePrincipal")
    Rel(auth, assistRouter, "Inyecta ServicePrincipal")
    Rel(auth, inventoryRouter, "Inyecta ServicePrincipal")
    Rel(auth, enrichRouter, "Inyecta ServicePrincipal")
    Rel(auth, indexRouter, "Inyecta ServicePrincipal")
    Rel(auth, evalsRouter, "Inyecta ServicePrincipal")

    Rel(retrievalRouter, stubs, "Usa si STUB_MODE")
    Rel(retrievalRouter, analyzer, "Usa")
    Rel(retrievalRouter, retriever, "Usa")
    Rel(assistRouter, retriever, "Usa")
    Rel(assistRouter, generation, "Usa")
    Rel(assistRouter, guardrails, "Usa")
    Rel(inventoryRouter, agent, "Usa")
    Rel(enrichRouter, generation, "Usa")
    Rel(indexRouter, embeddings, "Usa")

    Rel(retriever, db, "Consulta vectorial y léxica")
    Rel(embeddings, db, "Escribe documentos y vectores")
    Rel(indexRouter, api, "Feed paginado since-cursor")
    Rel(generation, llm, "Genera texto")
    Rel(embeddings, llm, "Genera embeddings")
    Rel(trace, settings, "Usa")
```

---

### Relaciones entre Componentes Backend y Frontend

#### Flujo de Autenticación
1. **Auth Module** (Frontend) → **API Client** → **Backend API** → **Authentication Service** → **Repositories** → **PostgreSQL Database**
2. Token JWT retornado y almacenado en **State Management**
3. **API Client** incluye token en todas las peticiones mediante interceptor

#### Flujo de Reconocimiento de Imágenes y Venta
1. **Image Recognition Module** (Frontend) captura foto
2. **ML Model Handler** procesa imagen localmente
3. **Image Recognition Module** muestra sugerencias
4. **Sale Module** recibe producto seleccionado
5. **Sale Module** → **API Client** → **Backend API** → **Sale Service**
6. **Sale Service** usa **Stock Validation Service** y **Payment Method Validation Service**
7. **Sale Service** → **Repositories** → **PostgreSQL Database**
8. **Sale Service** → **File Storage Service** → **Object Storage**

#### Flujo de Importación de Productos
1. **Product Module** (Frontend) sube archivo Excel
2. **Product Module** → **API Client** → **Backend API** → **Product Service**
3. **Product Service** usa **Excel Import Service** para procesar archivo
4. **Product Service** → **Repositories** → **PostgreSQL Database**

#### Flujo de Búsqueda Asistida por IA
1. El operador escribe una consulta en lenguaje natural en el **Assisted Search Panel** (Frontend)
2. **API Client** → **Backend API** (JWT de usuario) → **AI Gateway Client**
3. **AI Gateway Client** firma un **JWT interno de servicio** con `user_id`, `role`, `pos_id` y `trace_id`, y llama a **Retrieval Router** de `jbg-ai`
4. **Query Analyzer** extrae restricciones estructurales; **Hybrid Retriever** consulta el esquema `ai` y devuelve candidatos sobre-recuperados con sus razones
5. El **hidratador** del Backend API resuelve precio, stock y permisos reales contra el esquema `public`, descarta lo inválido y trunca al `top_k` pedido
6. Si se pide asistencia, **Assist Router** genera el argumentario con citas y placeholders, que el Backend API sustituye antes de responder
7. Si `jbg-ai` no responde dentro del timeout, el **circuit breaker** degrada al buscador léxico y marca `ai_available: false`

---

## Notas sobre Desarrollo vs Producción

### Almacenamiento de Archivos

**Desarrollo:**
- **File Storage Service** utiliza sistema de archivos local (`./uploads/`)
- Configuración mediante variable de entorno `Storage__Type=Local`
- Sin necesidad de credenciales de cloud

**Producción:**
- **File Storage Service** utiliza AWS S3 o Azure Blob Storage
- Configuración mediante variable de entorno `Storage__Type=Cloud`
- Credenciales gestionadas mediante AWS Secrets Manager / Azure Key Vault
- Políticas de acceso restringidas y pre-signed URLs para acceso temporal

### Base de Datos

**Desarrollo:**
- PostgreSQL ejecutándose en contenedor Docker local
- Puerto 5432 expuesto localmente
- Datos de prueba y seeders para desarrollo
- Sin replicación ni backups automáticos

**Producción:**
- PostgreSQL gestionado (RDS en AWS o Azure Database for PostgreSQL)
- Conexión mediante connection string desde secrets
- Backups automáticos configurados
- Connection pooling optimizado (5-10 conexiones máx para free-tier)

### Frontend

**Desarrollo:**
- Servidor de desarrollo local (Vite/Webpack dev server)
- Hot Module Replacement (HMR) activo
- Source maps para debugging
- Sin optimizaciones de producción

**Producción:**
- Build optimizado y minificado
- En AWS actual: mismo origen que la API (nginx + Docker); en otras variantes, CDN (CloudFront/Azure CDN)
- Cache de assets: cabeceras HTTP / CDN según despliegue
- Code splitting y lazy loading activados

### Seguridad

**Desarrollo:**
- HTTP sin HTTPS (localhost)
- CORS permisivo para localhost
- Logging detallado en consola
- Stack traces completos en errores

**Producción:**
- HTTPS obligatorio (SSL/TLS)
- CORS restrictivo (solo dominios permitidos)
- Logging estructurado a CloudWatch/Application Insights
- Mensajes de error genéricos (sin detalles internos)
- Rate limiting activo

### Monitoreo

**Desarrollo:**
- Logging manual en consola
- Sin métricas automáticas
- Health checks básicos

**Producción:**
- CloudWatch Logs (AWS) o Application Insights (Azure)
- Métricas automáticas (request rate, response time, error rate)
- Health checks en `/health` endpoint
- Alertas configuradas para errores críticos

### Modelo de IA

**Desarrollo:**
- Modelo descargado desde servidor de desarrollo o local
- Sin optimizaciones de tamaño
- Debugging activo

**Producción:**
- Modelo distribuido mediante CDN
- Modelo optimizado y comprimido
- Versionado del modelo para actualizaciones sin interrupciones

### Servicio de IA (`jbg-ai`)

**Desarrollo:**
- Servicio `jbg-ai` del Compose, puerto `8001` publicado solo en local
- PostgreSQL con imagen `pgvector/pgvector:pg15` en el puerto `5433`
- `STUB_MODE` activo: respuestas deterministas sin LLM ni base de datos
- Secreto del JWT interno definido en el Compose, nunca reutilizable en producción

**Producción:**
- Contenedor en la misma EC2, en red Docker interna; **el puerto no se publica en nginx**
- Índice vectorial en el esquema `ai` de la RDS compartida
- Secretos (JWT interno, claves del proveedor LLM) en SSM Parameter Store
- Timeouts, reintento único y circuit breaker aplicados desde el backend .NET
- Degradación explícita: si el circuito se abre, el sistema responde con el buscador léxico

---

## Resumen de Componentes por Épica

### EP1: Gestión de Productos
- **Backend**: Product Service, Excel Import Service, File Storage Service
- **Frontend**: Product Module, API Client

### EP2: Gestión de Inventario
- **Backend**: Inventory Service, Excel Import Service
- **Frontend**: Inventory Module, API Client

### EP3: Registro de Ventas
- **Backend**: Sale Service, Stock Validation Service, Payment Method Validation Service, File Storage Service
- **Frontend**: Sale Module, Image Recognition Module, API Client

### EP4: Reconocimiento de Imágenes con IA
- **Backend**: File Storage Service (para fotos de referencia)
- **Frontend**: Image Recognition Module, ML Model Handler

### EP5: Gestión de Devoluciones
- **Backend**: Return Service, Stock Validation Service
- **Frontend**: Return Module, API Client

### EP6: Gestión de Métodos de Pago
- **Backend**: Payment Method Service, Payment Method Validation Service
- **Frontend**: Payment Method Module, API Client

### EP7: Autenticación y Gestión de Usuarios
- **Backend**: Authentication Service, User Service
- **Frontend**: Auth Module, User Module, API Client

### EP8: Gestión de Puntos de Venta
- **Backend**: Point of Sale Service (incluye configuración de `AllowManualPriceEdit`)
- **Frontend**: Point of Sale Module (incluye switch de edición manual de precio), API Client

### EP9: Consultas y Reportes
- **Backend**: Report Service
- **Frontend**: Report Module, API Client

### EP10: Gestión de Componentes de Joyas
- **Backend**: Component Service, Component Assignment Service, Component Template Service
- **Frontend**: Product Module (subsección de componentes, reportes de márgenes), API Client

### EP11: Plataforma del Servicio de IA
- **AI Service**: Settings, TraceId Middleware, Service Auth Dependency, Stub Layer
- **Backend**: AI Gateway Client (cliente tipado con Polly, emisión del JWT interno)
- **Base de datos**: esquema `ai` con pgvector

### EP12: Corpus y Enriquecimiento del Catálogo
- **AI Service**: Enrich Router, Generation Service, Embedding Client
- **Backend**: ProductAiProfile (entidad y ciclo de revisión), endpoints de feed de indexación

### EP13: Familias de Producto y Desambiguación
- **AI Service**: Hybrid Retriever (propuesta de familias por similitud)
- **Backend**: ProductFamily, ProductFamilyMember
- **Frontend**: pantalla de revisión y aprobación por lotes

### EP14: Búsqueda Semántica Híbrida
- **AI Service**: Retrieval Router, Query Analyzer, Hybrid Retriever, Index Router
- **Backend**: AI Search Endpoint, hidratador, circuit breaker y fallback léxico
- **Frontend**: Assisted Search Panel

### EP15: Venta Asistida, Sustitutos y Agentes
- **AI Service**: Assist Router, Generation Service, Guardrails / Intent Router, Agent Loop
- **Backend**: endpoints de asistencia y recomendaciones
- **Frontend**: tarjeta de asistencia y desambiguación por familia

### EP16: Inventario Asistido y Señales de Demanda
- **AI Service**: Inventory Router, Agent Loop
- **Backend**: Demand Signal Service, InventoryRecommendation, perfil comercial por POS
- **Frontend**: revisión de recomendaciones y vista imprimible

### EP17: Evaluación y Observabilidad de IA
- **AI Service**: Eval Harness, Evals Router
- **Backend**: ProductSearchEvent (telemetría consulta → selección)

---

## Consideraciones de Arquitectura

### Patrones Utilizados

- **Repository Pattern**: Abstracción de acceso a datos en el backend
- **Service Layer**: Separación de lógica de negocio de controladores
- **Dependency Injection**: Inyección de dependencias en ASP.NET Core
- **Strategy Pattern**: File Storage Service permite cambiar entre almacenamiento local y cloud
- **Factory Pattern**: Creación de servicios según configuración

### Optimizaciones para Free-tier

- **Connection Pooling**: Máximo 5-10 conexiones simultáneas a PostgreSQL
- **Paginación**: Todas las listas paginadas (máx 50 items/página)
- **Caching**: Cache en memoria para productos y métodos de pago frecuentes
- **Índices Selectivos**: Solo índices necesarios para consultas frecuentes
- **Compresión**: Respuestas comprimidas (gzip) para reducir ancho de banda

### Escalabilidad Futura

El modelo está preparado para escalar:
- **Read Replicas**: Para reportes pesados
- **Caching Distribuido**: Redis para cache compartido entre instancias
- **Microservicios**: Separación de servicios si es necesario en el futuro
- **CDN Ampliado**: Más puntos de presencia para mejor rendimiento global

---

## Referencias

- [Arquitectura del Sistema](arquitectura.md)
- [Modelo de Datos](modelo-de-datos.md)
- [Épicas del MVP y del Proyecto Final de IA](epicas.md)
- [README del Proyecto](../README.md)
- [Diseño del sistema de IA](Proyecto%20Final%20AIEng/proyecto-final-diseno-rag-joiabagur.md) — frontera de responsabilidad (§6) y diseño RAG (§7)
- [Plan de changes OpenSpec del PF](Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) — C01–C39

