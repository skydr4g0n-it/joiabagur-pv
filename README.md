# Sistema de Gestión de Puntos de Venta para Joyería

## Índice

0. [Ficha del proyecto](#0-ficha-del-proyecto)
1. [Descripción general del producto](#1-descripción-general-del-producto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Especificación de la API](#4-especificación-de-la-api)
5. [Historias de usuario](#5-historias-de-usuario)
6. [Tickets de trabajo](#6-tickets-de-trabajo)

---

## 0. Ficha del proyecto

### 0.1. Tu nombre completo

Marcello Orrico

### 0.2. Nombre del proyecto

Sistema de Gestión de Puntos de Venta para Joyería (Joiabagur PV)

### 0.3. Descripción breve del proyecto

Sistema de gestión integral para una joyería que opera en múltiples puntos de venta (propios y de terceros). Permite gestionar inventario, registrar ventas y facilitar la identificación de productos mediante reconocimiento de imágenes con IA (inferencia y entrenamiento en el navegador con TensorFlow.js).

### 0.4. URL del proyecto

https://pv.joiabagur.com

**Entorno de demostración del Proyecto Final de IA:** https://52-49-209-14.sslip.io

Despliegue aislado en una cuenta AWS propia, con el catálogo real y sus 1.200 documentos vectorizados cargados, y dos cuentas de demostración —una de administración y una de operación— cuyas credenciales se entregan aparte. El nombre de dominio deriva de la IP elástica y es un parámetro del despliegue: migrar a un dominio propio no reconstruye ninguna imagen.

### 0.5. URL o archivo comprimido del repositorio

https://github.com/marcello-clearcust/joiabagur-pv

---

## 1. Descripción general del producto

### 1.1. Objetivo

El producto tiene como propósito ofrecer una solución integral de gestión para una joyería con varios puntos de venta (tiendas propias y ubicaciones de terceros como hoteles). Aporta valor al centralizar el catálogo de productos, el inventario por ubicación, el registro de ventas con método de pago y la identificación de productos mediante IA en el punto de venta, reduciendo errores y agilizando el proceso. Está dirigido a administradores (gestión completa) y operadores (registro de ventas e inventario en sus puntos asignados).

### 1.2. Características y funcionalidades principales

- **Gestión de productos e inventario:** Catálogo centralizado (SKU, precio, descripción, colección), gestión de stock por punto de venta con vista centralizada, importación y actualización desde Excel, edición manual de productos e inventario, asociación de fotos de referencia para reconocimiento de imágenes.
- **Registro de ventas:** Captura de ventas por punto de venta (manual o con IA), foto opcional por transacción, registro de método de pago, historial con trazabilidad, validación de stock en tiempo real, actualización atómica de inventario, alertas de stock bajo no bloqueantes.
- **Reconocimiento de productos con IA:** Inferencia en el cliente con TensorFlow.js, identificación mediante cámara en el punto de venta, 3–5 sugerencias ordenadas por confianza (umbral 40%), validación manual del operador, fallback a entrada manual si la confianza es baja.
- **Entrenamiento del modelo de IA:** Entrenamiento en el navegador con TensorFlow.js (sin Python), un clic desde el panel de administración, aceleración GPU vía WebGL 2.0, métricas de salud del modelo y progreso en tiempo real.
- **Gestión de métodos de pago:** Lista general (Efectivo, Bizum, Transferencia, Tarjeta TPV propio/punto de venta, PayPal), asignación por punto de venta y registro del método en cada venta.
- **Gestión de usuarios:** Roles Administrador y Operador, autenticación con usuario y contraseña, operadores asociados a puntos de venta concretos.
- **Otras funcionalidades:** Devoluciones, ajustes manuales de inventario, historial de ventas y movimientos de stock, dashboard con estadísticas y stock crítico.
- **Búsqueda semántica y venta asistida (en desarrollo):** Proyecto Final del Máster de IA. Añade búsqueda semántica sobre el catálogo, sugerencia de sustitutos y argumentario de venta asistido, mediante el microservicio `jbg-ai`. A día de hoy están congelados el contrato HTTP y la autenticación entre servicios, el backend .NET ya dispone del cliente tipado que los consume —con timeouts, reintento único y cortacircuitos— y la capa de persistencia vectorial está lista: esquema `ai` con pgvector, migraciones propias e índices HNSW por similitud coseno. La recuperación vectorial de `POST /v1/retrieval/products` (C14) y el endpoint .NET de búsqueda asistida con hidratación autoritativa (C15) están entregados: el operador puede buscar en lenguaje natural y recibir resultados con el precio y el stock reales de su tienda. **El panel del operador (C16) también está entregado**: describe la pieza con sus palabras, distingue en pantalla los cuatro modos de no encontrar nada —la IA no encontró, la tienda no lo tiene, la asistencia no está sirviendo, o se han hecho demasiadas búsquedas seguidas— y arrastra la búsqueda hasta la caja, de modo que la venta queda atribuida a la consulta que la originó. **Y desde C17 todo lo anterior es demostrable en público**: un entorno aislado en una cuenta AWS propia, con TLS válido, el catálogo real y sus 1.200 documentos vectorizados cargados, y una tarjeta en el panel de administración que informa del estado del servicio de IA — incluida la discrepancia entre el modelo de embeddings configurado y el del índice, que de otro modo devolvería resultados sin sentido sin dar ningún error. La fusión híbrida se entrega en changes posteriores.

### 1.3. Diseño y experiencia de usuario

El usuario aterriza en la pantalla de login; tras autenticarse, accede al dashboard (estadísticas globales para administradores o por punto de venta para operadores). Desde la navegación puede: registrar ventas de forma manual (`/sales/new`), escaneando el código de barras o QR (`/sales/new/scan`), buscando con ayuda en lenguaje natural (`/sales/new/assisted`) o con reconocimiento por imagen (`/sales/new/image`), consultar historial de ventas con filtros y paginación, gestionar productos e inventario (catálogo, importación Excel, stock por POS, ajustes), configurar puntos de venta y métodos de pago, y (solo administradores) acceder al dashboard de modelo de IA y al listado de stock crítico con paginación. La interfaz está optimizada para uso en móvil en el punto de venta (cámara, gestos) y es responsive para administradores. La moneda es euro (EUR) con formato español.

*Se añadirá un videotutorial en esta sección.*

### 1.4. Instrucciones de instalación

**Requisitos previos**

- Backend: .NET 10 SDK, PostgreSQL 14+ (o Docker para desarrollo).
- Frontend: Node.js 20+ y npm, navegador moderno (Chrome 90+, Edge 90+, Safari 14+).

**Pasos**

1. **Backend**
   ```bash
   cd backend/src/JoiabagurPV.API
   dotnet restore
   cp Properties/launchSettings.Example.json Properties/launchSettings.json
   dotnet run
   ```
   La API queda disponible en `http://localhost:5056`. **El copiado del perfil de arranque no es opcional:** `launchSettings.json` está ignorado por git y, sin él, `ASPNETCORE_ENVIRONMENT` queda vacío, .NET asume `Production` y la cookie de sesión sale con `SameSite=None` sin `Secure` — combinación que el navegador descarta, dejando el login en un `200` engañoso y todo lo autenticado en `401`. El detalle está en [backend/README.md](backend/README.md#4-create-your-launch-profile).

   Los ficheros `appsettings*.json` ya vienen versionados con valores de desarrollo que funcionan tal cual; para ajustar algo en tu máquina, crea `appsettings.Local.json` (ignorado por git) o usa user-secrets, en lugar de editar los ficheros versionados. Las migraciones EF Core se aplican solas en cada arranque, junto con la siembra del usuario administrador; para aplicarlas a mano, `dotnet ef database update --project ../JoiabagurPV.Infrastructure`.

2. **Frontend**
   ```bash
   cd frontend
   npm install --legacy-peer-deps
   npm run dev
   ```
   La UI queda disponible en `http://localhost:3000`. El fichero `.env.development` ya apunta a `http://localhost:5056/api`, el mismo puerto que fija el perfil de arranque del backend; solo hay que tocar `VITE_API_BASE_URL` si cambias uno de los dos.

3. **Usuario por defecto (desarrollo)**  
   Usuario: `admin`. Contraseña: `Admin123!`. Cambiar la contraseña tras el primer acceso.

4. **Tests**
   - Backend: `cd backend/src/JoiabagurPV.Tests` y `dotnet test`.
   - Frontend: `cd frontend` y `npm run test`.

Para despliegue en AWS (EC2, nginx, Docker API+SPA, RDS, S3, ECR, OIDC) y CI/CD, ver [Documentos/Guias/deploy-aws-production.md](Documentos/Guias/deploy-aws-production.md). Migración desde App Runner/CloudFront: [Documentos/Guias/deploy-aws-ec2-migration.md](Documentos/Guias/deploy-aws-ec2-migration.md).

---

## 2. Arquitectura del sistema

### 2.1. Diagrama de arquitectura

La aplicación sigue una arquitectura monolítica simple con backend y frontend separados, desplegados en contenedores y servicios cloud en régimen free-tier. Se eligió este enfoque para reducir complejidad operativa, mantener un único despliegue y optimizar costes; el sacrificio es menor escalado independiente por componente.

```mermaid
flowchart TB
    subgraph Cliente["CLIENTE"]
        Browser["Navegador Web"]
        SPA["React SPA"]
        ML["Modelo ML TensorFlow.js"]
        Browser --> SPA
        SPA --> ML
    end
    Nginx["nginx (TLS) + EC2"]
    Gateway["Reverse proxy → contenedor Docker"]
    subgraph Backend["BACKEND API .NET 10"]
        API["ASP.NET Core Web API"]
        EF["Entity Framework Core"]
        API --> EF
    end
    DB["PostgreSQL"]
    Storage["Object Storage S3/Blob"]
    AI["jbg-ai (Python/FastAPI)<br/>red interna, no expuesto en nginx"]
    Cliente -->|HTTPS| Nginx
    Nginx --> Gateway
    Gateway -->|HTTP interno| Backend
    Backend --> DB
    Backend --> Storage
    Backend -->|JWT interno HS256| AI
```

### 2.2. Descripción de componentes principales

- **Backend:** ASP.NET Core Web API (.NET 10), C#, Entity Framework Core, PostgreSQL 15+, JWT para autenticación, Serilog para logging, patrón Repository y capa de servicios. Documentación de API con Scalar.
- **Frontend:** React 19, TypeScript, Vite, Metronic React (Layout 8), Radix UI, Tailwind CSS, React Hook Form + Zod, TensorFlow.js para inferencia y entrenamiento en el navegador.
- **Base de datos:** PostgreSQL con índices para ventas, inventario y productos; connection pooling y paginación (máx. 50 ítems por página).
- **Almacenamiento:** Servicio de ficheros abstracto (local en desarrollo, S3/Blob en producción) para fotos de productos, ventas y devoluciones.
- **Servicio de IA (`jbg-ai`):** Microservicio Python 3.11 con FastAPI en contenedor propio, para recuperación vectorial y generación con LLM. El navegador nunca lo llama: solo el backend .NET, con un JWT interno HS256 sobre la red Docker. .NET conserva la autoridad sobre precio, stock y permisos.

### 2.3. Descripción de alto nivel del proyecto y estructura de ficheros

- `backend/`: Solución .NET en capas (Domain, Infrastructure, Application, API). Controllers en `JoiabagurPV.API/Controllers`, servicios y DTOs en `JoiabagurPV.Application`, entidades e interfaces de dominio en `JoiabagurPV.Domain`, repositorios y DbContext en `JoiabagurPV.Infrastructure`. Tests en `JoiabagurPV.Tests`.
- `frontend/`: SPA React; `src/pages` por módulo (dashboard, sales, products, inventory, etc.), `src/services` para llamadas API, `src/components` para UI y layouts.
- `Documentos/`: Arquitectura, modelo de datos, épicas, historias de usuario, guías de deploy y testing.
- `openspec/`: Especificaciones (specs) y cambios (changes) según metodología OpenSpec (spec-driven development).
- `ai-service/`: Microservicio Python `jbg-ai` (FastAPI) del Proyecto Final de IA. Contenedor independiente, alcanzable solo desde el backend .NET.
- `scripts/catalog/`: pipeline offline de C06a (lectura xlsx, JSONL, ingesta local de `Description`). No forma parte de `jbg-ai`.
- `ai-service/src/jbg_ai/data/`: CLI C06b (`generate|ingest` de catálogo) y C10 (`world simulate|ingest`). `api.main` no lo importa.
- `ai-service/src/jbg_ai/enrichment/`: extractor C09 de `POST /v1/enrich/products` (`STUB_MODE=false`). Prompt en `ai-service/prompts/enrichment/v1.md`.
- `ai-service/src/jbg_ai/indexing/`: biblioteca C11 (`source-text/v1` + embeddings) y dreno C13 del feed de catálogo (`POST /v1/index/sync`, CLI `python -m jbg_ai.indexing sync`). `api.main` no lo importa; el router de índice sí.
- `data/catalog/real/generated/`: corpus JSONL versionado (`data_origin: real`). El xlsx crudo permanece gitignored.
- `data/catalog/synthetic/generated/`: corpus JSONL sintético (`data_origin: synthetic`; 764 líneas; híbrido 1.200 con el real).
- `data/world/`: receta YAML de 12 POS (`pos-profiles.yaml`, en git). JSONL de ventas y `pg_dump` gitignored.
- `terraform/`: Pila de infraestructura AWS de producción (EC2, RDS, S3, ECR, SSM, OIDC).

### 2.4. Infraestructura y despliegue

En producción (AWS): EC2 con nginx (TLS) y un contenedor Docker con API .NET + SPA React; RDS PostgreSQL; S3 (`prod-jpv-files`) para ficheros; ECR; parámetros en SSM; despliegue con GitHub Actions y OIDC. Backups RDS según Terraform (p. ej. 7 días). Detalle en [Documentos/Guias/deploy-aws-production.md](Documentos/Guias/deploy-aws-production.md).

**Entorno de demostración del Proyecto Final de IA (C17):** despliegue independiente en una **cuenta AWS distinta**, con su propio estado de Terraform ([terraform/demo/](terraform/demo/)) y su propio flujo de despliegue. Cuatro contenedores —proxy Caddy con TLS automático, API con la SPA, servicio de IA y PostgreSQL con pgvector— de los que **sólo el proxy publica puertos**: el servicio que custodia la clave del proveedor no es alcanzable desde Internet, y esa frontera se cumple en tres capas independientes (grupo de seguridad, puertos publicados y ausencia de ruta). Los secretos se leen del almacén de parámetros al entorno del proceso y **nunca a disco**. Runbook en [deploy/demo/README.md](deploy/demo/README.md).

### 2.5. Seguridad

- Autenticación JWT (stateless) y refresh tokens para renovación de sesión.
- Contraseñas con BCrypt y salt.
- Control de acceso por roles (Administrator / Operator) y por punto de venta (operadores solo acceden a sus POS asignados).
- CORS configurado por origen permitido; en producción solo dominios de la aplicación.
- HTTPS en producción; secretos de aplicación en AWS SSM Parameter Store en la pila actual.
- Uso de EF Core para evitar inyección SQL; sanitización de entradas frente a XSS.

### 2.6. Tests

- **Backend:** xUnit, Moq, FluentAssertions; tests unitarios de servicios y validadores; tests de integración con Testcontainers (PostgreSQL). Nomenclatura tipo `Method_Scenario_ExpectedResult`. Los controladores críticos (por ejemplo ventas) tienen tests de integración que cubren creación, validación de stock, método de pago y permisos.
- **Frontend:** Vitest, React Testing Library, MSW para simular API; pruebas de componentes y de flujos; E2E con Playwright (en progreso). Documentación en [Documentos/testing-backend.md](Documentos/testing-backend.md) y [Documentos/testing-frontend.md](Documentos/testing-frontend.md).
- **Servicio de IA (`jbg-ai`):** pytest con el `TestClient` de FastAPI (`uv run pytest`); cubre autenticación de servicio, conformidad de los contratos, respuestas stub, extracción de catálogo con LLM falso (`tests/enrichment/`), retriever vectorial con fakes (`tests/retrieval/`) y estabilidad del snapshot OpenAPI. Los tests no llaman a proveedores LLM, APIs de embeddings ni RDS.

---

## 3. Modelo de datos

### 3.1. Diagrama del modelo de datos

El modelo está optimizado para PostgreSQL 15+ y Entity Framework Core. A continuación se muestra el diagrama de entidades principales (relaciones resumidas).

```mermaid
erDiagram
    User ||--o{ UserPointOfSale : "asignado a"
    User ||--o{ Sale : "realiza"
    PointOfSale ||--o{ UserPointOfSale : "tiene asignados"
    PointOfSale ||--o{ Sale : "registra ventas"
    PointOfSale ||--o{ Inventory : "tiene stock"
    Product ||--o{ ProductPhoto : "tiene fotos"
    Product ||--o{ Sale : "se vende"
    Product ||--o{ Inventory : "en stock"
    Product ||--o{ InventoryMovement : "movimiento"
    Sale ||--o{ SalePhoto : "tiene foto"
    Sale ||--o{ InventoryMovement : "genera movimiento"
    Inventory ||--o{ InventoryMovement : "tiene movimientos"
    PaymentMethod ||--o{ Sale : "usado en"
    Return ||--o{ InventoryMovement : "genera movimiento"
    User { uuid Id PK string Username UK string PasswordHash enum Role }
    PointOfSale { uuid Id PK string Name string Code UK bool AllowManualPriceEdit }
    Product { uuid Id PK string SKU UK decimal Price }
    Sale { uuid Id PK uuid ProductId FK uuid PointOfSaleId FK uuid PaymentMethodId FK decimal Price int Quantity }
    Inventory { uuid Id PK uuid ProductId FK uuid PointOfSaleId FK int Quantity bool IsActive }
    InventoryMovement { uuid Id PK uuid InventoryId FK enum MovementType int QuantityChange }
```

Descripción completa y resto de entidades (Return, ReturnSale, Collection, etc.) en [Documentos/modelo-de-datos.md](Documentos/modelo-de-datos.md).

### 3.2. Descripción de entidades principales

- **User:** Id (UUID), Username (único), Email (opcional), PasswordHash (BCrypt), Role (Admin/Operator), IsActive. Relación con UserPointOfSale (asignación a POS) y con Sale.
- **PointOfSale:** Id, Name, Code (único), Address/Phone/Email opcionales, IsActive, AllowManualPriceEdit. Relación con Inventory, Sale, UserPointOfSale, PointOfSalePaymentMethod.
- **Product:** Id, SKU (único, indexado), Name, Description, Price, CollectionId (opcional), IsActive. Relación con ProductPhoto, Sale, Inventory, InventoryMovement.
- **Sale:** Id, ProductId, PointOfSaleId, UserId (operador), PaymentMethodId, Price (snapshot), Quantity, Notes, PriceWasOverridden, OriginalProductPrice, BulkOperationId (opcional), SearchEventId (opcional, búsqueda asistida de la que procede la venta), SaleDate. Índices por POS, producto, usuario, fecha. Relación con SalePhoto e InventoryMovement.
- **Inventory:** Id, ProductId, PointOfSaleId, Quantity, IsActive (asignado/desasignado). Unique(ProductId, PointOfSaleId). La presencia de registro activo determina visibilidad del producto para operadores en ese POS.
- **InventoryMovement:** Id, InventoryId, SaleId/ReturnId (opcionales), UserId, MovementType (Sale, Return, Adjustment, Import), QuantityChange, QuantityBefore, QuantityAfter, Reason (ajustes), MovementDate. Trazabilidad completa de movimientos.

Otras entidades (ProductPhoto, PaymentMethod, PointOfSalePaymentMethod, Return, ReturnSale, Collection, ProductSearchEvent, ProductAiProfile, ProductFamily, ProductFamilyMember, etc.) se describen con detalle en [Documentos/modelo-de-datos.md](Documentos/modelo-de-datos.md).

---

## 4. Especificación de la API

A continuación se describen cuatro endpoints principales en formato OpenAPI (resumen). La API base es `/api` y requiere cabecera `Authorization: Bearer <token>` para endpoints protegidos, salvo `GET /api/ai/index-feed/*`, que autentica con `X-Index-Feed-Key`.

### POST /api/sales — Crear venta

Crea una venta validando stock, método de pago asignado al POS y que el usuario esté asignado al punto de venta (o sea administrador). Actualiza inventario en la misma transacción.

`searchEventId` es opcional y atribuye la venta a la búsqueda asistida de la que procede. Se comprueba que el evento exista **y pertenezca a quien vende**; un identificador desconocido o ajeno deja la atribución nula, sin error de validación y sin alterar nada más de la venta. `POST /api/sales/bulk` lo acepta **por línea**, porque cada línea de un carrito puede venir de una búsqueda distinta o de ninguna.

**Request (application/json)**

| Campo            | Tipo    | Requerido | Descripción                                      |
|------------------|---------|-----------|--------------------------------------------------|
| productId        | uuid    | Sí        | ID del producto                                  |
| pointOfSaleId    | uuid    | Sí        | ID del punto de venta                            |
| paymentMethodId  | uuid    | Sí        | ID del método de pago                            |
| quantity         | integer | Sí        | Cantidad (mayor que 0)                            |
| price            | number  | No        | Override de precio (solo si POS permite edición) |
| notes            | string  | No        | Notas (máx. 500 caracteres)                      |
| photoBase64      | string  | No        | Foto en Base64 (opcional)                         |
| photoFileName    | string  | No        | Nombre original del archivo de la foto           |
| searchEventId    | uuid    | No        | Búsqueda asistida que originó la venta           |

**Responses**

- **201 Created:** Cuerpo con `sale` (objeto con id, productId, pointOfSaleId, etc.), `warning` (opcional), `isLowStock` (boolean), `remainingStock` (número).
- **400 Bad Request:** Validación fallida o stock insuficiente / método de pago no disponible / producto no asignado al POS. Cuerpo con `message` o `errors`.
- **401 Unauthorized:** No autenticado.
- **403 Forbidden:** Operador no asignado al punto de venta.

**Ejemplo de petición**

```json
POST /api/sales
{
  "productId": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "pointOfSaleId": "3fa85f64-5717-4562-b3fc-2c963f66afa7",
  "paymentMethodId": "3fa85f64-5717-4562-b3fc-2c963f66afa8",
  "quantity": 1,
  "notes": "Venta con foto"
}
```

---

### GET /api/sales — Historial de ventas

Devuelve ventas paginadas. Los administradores ven todas; los operadores solo las de sus puntos de venta asignados.

**Query parameters**

| Parámetro      | Tipo   | Descripción                    |
|----------------|--------|--------------------------------|
| startDate      | date   | Fecha inicio (inclusive)       |
| endDate        | date   | Fecha fin (inclusive)          |
| pointOfSaleId  | uuid   | Filtrar por POS                |
| productId      | uuid   | Filtrar por producto           |
| userId         | uuid   | Filtrar por usuario            |
| paymentMethodId| uuid   | Filtrar por método de pago    |
| page           | int    | Página (por defecto 1)         |
| pageSize       | int    | Tamaño de página (p. ej. 20)  |

**Response 200 OK**

- `sales`: array de objetos venta (id, productId, pointOfSaleId, paymentMethodId, price, quantity, saleDate, hasPhoto, etc.).
- `totalCount`, `page`, `pageSize`, `totalPages` (según implementación en `SalesHistoryResponse`).

**401 Unauthorized** si no hay token válido.

---

### GET /api/dashboard/low-stock — Stock bajo (administradores)

Devuelve productos con stock bajo (por defecto cantidad ≤ 2) paginados. Solo rol Administrator.

**Query parameters**

| Parámetro | Tipo | Descripción                          |
|-----------|------|--------------------------------------|
| page      | int  | Página (por defecto 1)               |
| pageSize  | int  | Tamaño de página (entre 1 y 50)      |

**Response 200 OK**

- `items`: array de `{ productName, sku, pointOfSaleName, stock }`.
- `totalCount`, `page`, `pageSize`, `totalPages`.

**401 Unauthorized** / **403 Forbidden** si no autenticado o no administrador.

---

### POST /api/ai/search — Búsqueda asistida

Busca en el catálogo con lenguaje natural. El servicio de IA propone candidatos y **el backend pone la verdad**: precio, stock y qué tiene esa tienda salen de PostgreSQL, nunca de la respuesta de la IA.

**Request body**

| Campo | Tipo | Descripción |
|-------|------|-------------|
| query | string | Consulta en lenguaje natural. Obligatoria, máximo 500 caracteres |
| pointOfSaleId | uuid | **Obligatorio para todos los roles.** El operador debe estar asignado; el administrador puede elegir cualquiera activo |
| pageSize | int | Resultados a mostrar (1–50, por defecto 10) |
| searchSessionId | uuid | Agrupa las reformulaciones de un mismo episodio. El servidor genera uno si falta |
| materials, category | — | Filtros rápidos opcionales |

**Response 200 OK**

- `results`: array de `{ productId, sku, name, price, quantityAtPointOfSale, hasStock, primaryPhotoUrl, collectionName, score, matchReasons, familyId, variantLabel }`, **en el orden de relevancia recibido**.
- `searchEventId`: identificador del evento de telemetría, para reportar después la selección.
- `aiAvailable`, `lowConfidence`: distinguen los **tres** «sin resultados» — la IA se abstuvo, la tienda no tiene ninguno de los candidatos, o la IA no atendió la búsqueda.
- `candidatesReturned`, `survivedHydration`: embudo de la recuperación.

**400 Bad Request** sin punto de venta, con consulta vacía o si el punto de venta no está activo. **403 Forbidden** si el operador no está asignado a él. **429 Too Many Requests** al superar el límite por usuario.

La búsqueda **nunca falla por culpa de la IA**: cualquier fallo del servicio degrada a un buscador léxico acotado al mismo punto de venta y se reporta con `aiAvailable: false`.

---

## 5. Historias de usuario

Se documentan tres historias principales del desarrollo.

### Historia de Usuario 1 — Registrar venta con reconocimiento de imagen

**Como** operador, **quiero** registrar una venta usando reconocimiento de imagen **para** agilizar el proceso y reducir errores en la identificación del producto.

**Descripción:** Registrar una venta capturando una foto del producto, procesándola con IA para obtener sugerencias, seleccionando el producto correcto, validando stock, eligiendo método de pago y confirmando. Incluye validación de stock y método de pago.

**Criterios de aceptación (resumidos):** Venta exitosa con foto y sugerencias de IA; rechazo si stock insuficiente; rechazo si método de pago no asignado al POS; rechazo si operador no asignado al POS; si la IA no ofrece correspondencia fiable (< 60 %), ofrecer otra foto o venta manual. Detalle completo en [Documentos/Historias/HU-EP3-001.md](Documentos/Historias/HU-EP3-001.md).

---

### Historia de Usuario 2 — Crear producto manualmente

**Como** administrador, **quiero** crear productos manualmente en el sistema **para** agregar productos individuales al catálogo sin importar desde Excel.

**Descripción:** Crear productos con SKU, nombre, descripción, precio y colección (opcional). El producto se crea activo por defecto.

**Criterios de aceptación (resumidos):** Creación correcta con SKU único y precio > 0; error si el SKU ya existe; validación de campos obligatorios. Detalle en [Documentos/Historias/HU-EP1-002.md](Documentos/Historias/HU-EP1-002.md).

---

### Historia de Usuario 3 — Reconocimiento de productos mediante imagen

**Como** operador, **quiero** identificar productos mediante reconocimiento de imágenes con IA **para** obtener sugerencias a partir de una foto capturada.

**Descripción:** Flujo de captura de foto, preprocesado en cliente, inferencia con TensorFlow.js/ONNX.js, generación de 3 sugerencias ordenadas por confianza, visualización con fotos de referencia y selección. Si la confianza es < 60 %, ofrecer otra foto o venta manual.

**Criterios de aceptación (resumidos):** Reconocimiento exitoso con sugerencias y fotos; baja confianza con redirección a manual; visualización de sugerencias con SKU, nombre y porcentaje; captura desde cámara en móvil y procesamiento local. Detalle en [Documentos/Historias/HU-EP4-001.md](Documentos/Historias/HU-EP4-001.md).

---

## 6. Tickets de trabajo

Se documentan tres tickets principales a partir de las especificaciones OpenSpec del proyecto: uno de backend, uno de frontend y uno de bases de datos/dominio.

### Ticket 1 (Backend) — Registro de ventas con doble vía de entrada

**Objetivo:** Permitir a los operadores registrar ventas mediante dos métodos (reconocimiento por imagen con foto adjunta o selección manual de producto con foto opcional), validando stock, método de pago, autorización del operador y política de precio del punto de venta.

**Requisitos clave (spec: sales-management):**

- Crear registro Sale aplicando reglas de precio efectivo (precio oficial del producto por defecto; override solo si el POS tiene AllowManualPriceEdit).
- Crear SalePhoto con foto comprimida (JPEG 80 %, ≤ 2 MB) cuando se envía foto.
- Crear InventoryMovement tipo "Sale" y actualizar Inventory.Quantity en la misma transacción.
- Validación doble de stock (previa en formulario y justo antes del commit) para seguridad ante concurrencia.
- Rechazar con 400 si stock insuficiente, producto no asignado al POS, método de pago no disponible o operador no autorizado para el POS.
- Rechazar override de precio manual si el POS no lo permite; validar cantidad > 0.
- Devolver aviso de stock bajo (no bloqueante) cuando el stock restante quede por debajo del umbral configurado.

**Tareas (derivadas de la spec):** Implementar endpoint POST /api/sales con validadores (FluentValidation); integrar IStockValidationService e IPaymentMethodValidationService; ejecutar venta + movimiento de inventario en transacción; devolver sale, warning, isLowStock y remainingStock en la respuesta; tests de integración para escenarios de éxito, stock insuficiente, método de pago inválido y operador no asignado.

**Referencia:** [openspec/specs/sales-management/spec.md](openspec/specs/sales-management/spec.md).

---

### Ticket 2 (Frontend) — Reconocimiento de imágenes con inferencia en cliente

**Objetivo:** Ejecutar la inferencia de ML en el navegador/dispositivo con TensorFlow.js y presentar 3–5 sugerencias de productos con puntuación de confianza para que el operador seleccione el producto correcto.

**Requisitos clave (spec: image-recognition):**

- Descargar el modelo desde GET /api/image-recognition/model en el primer uso; mostrar progreso; cachear en IndexedDB.
- Comprobar versión del modelo (GET /api/image-recognition/model/metadata) y actualizar caché si hay nueva versión; en offline, usar modelo en caché sin comprobación.
- Preprocesar imagen (redimensionar 224x224, normalizar), ejecutar model.predict() en cliente y devolver 3–5 productos ordenados por confianza (umbral 40 %); inferencia < 500 ms en dispositivo móvil.
- Mostrar sugerencias con foto de referencia, SKU, nombre y porcentaje de confianza; permitir seleccionar una para continuar al flujo de venta.
- Si falla la descarga del modelo, mostrar error y redirigir a entrada manual (degradación controlada).

**Tareas (derivadas de la spec):** Componente de captura de foto (cámara en móvil); integración con TensorFlow.js (carga de modelo, preprocesado, predict); componente de lista de sugerencias con fotos y confianza; umbral 40 % y máximo 5 sugerencias; notificación cuando el modelo está desactualizado (> 7 días) y botón "Actualizar modelo"; tests de componente y flujo. Referencia: [openspec/specs/image-recognition/spec.md](openspec/specs/image-recognition/spec.md).

---

### Ticket 3 (Bases de datos / dominio) — Gestión de inventario y asignación a puntos de venta

**Objetivo:** Gestionar la asignación de productos a puntos de venta (registros Inventory), la importación de stock desde Excel, la visualización de stock por POS y los movimientos de inventario con trazabilidad, garantizando reglas de negocio sobre visibilidad y cantidad.

**Requisitos clave (spec: inventory-management):**

- Asignación: el administrador asigna productos del catálogo a un POS creando registros Inventory con Quantity = 0 e IsActive = true. La existencia de un Inventory activo determina que el producto sea visible para los operadores de ese POS. Evitar asignación duplicada; no asignar productos inactivos. Reasignar reactivando registro existente (IsActive = true) preservando cantidad.
- Desasignación: soft delete (IsActive = false) solo cuando Quantity = 0; error explícito si hay stock.
- Importación Excel: columnas SKU y Quantity; punto de venta elegido en la UI. Valores positivos suman al stock existente; valores negativos restan (el stock resultante no puede ser negativo). Crear Inventory (asignación implícita) si el producto no existe en el POS (solo para cantidades positivas). Crear InventoryMovement tipo "Import". Validar SKUs en catálogo y formato antes de importar; la importación es todo o nada. Ofrecer plantilla de descarga con ejemplos positivos y negativos.
- Visualización: administradores ven stock de cualquier POS; operadores solo de sus POS asignados. Incluir productos con cantidad 0.
- Ajustes manuales: crear InventoryMovement tipo "Adjustment" con QuantityChange, Reason y usuario; actualizar Inventory.Quantity y LastUpdatedAt. No permitir stock negativo.

**Tareas (derivadas de la spec):** Modelo de datos Inventory (ProductId, PointOfSaleId, Quantity, IsActive) e InventoryMovement (MovementType, QuantityChange, QuantityBefore, QuantityAfter, Reason, UserId, SaleId/ReturnId opcionales); repositorios y servicios de asignación/desasignación; endpoint de importación Excel con validación y plantilla; endpoints de consulta de stock por POS con control de acceso; tests unitarios e integración para asignación, desasignación con stock > 0 e importación. Referencia: [openspec/specs/inventory-management/spec.md](openspec/specs/inventory-management/spec.md).

---

## Documentación adicional

- [Épicas del MVP](Documentos/epicas.md): épicas, user stories y orden de implementación.
- [Arquitectura del sistema](Documentos/arquitectura.md): stack, diagramas, entornos y seguridad.
- [Modelo de datos](Documentos/modelo-de-datos.md): diagramas ER completos y descripción de entidades.
- [Modelo C4](Documentos/modelo-c4.md): niveles de contexto y componentes.
- [Testing Backend](Documentos/testing-backend.md) y [Testing Frontend](Documentos/testing-frontend.md).
- [Guía de deploy AWS](Documentos/Guias/deploy-aws-production.md).
- [README del backend](backend/README.md), [del frontend](frontend/README.md), [del servicio de IA `jbg-ai`](ai-service/README.md) y [de la pila Terraform](terraform/README.md).
- [Plan de changes del Proyecto Final de IA](Documentos/Proyecto%20Final%20AIEng/proyecto-final-plan-changes-openspec.md) y [especificaciones funcionales v2](Documentos/Proyecto%20Final%20AIEng/joiabagur-ia-especificaciones-funcionales-v2.md).
- [Procedimiento de User Stories](Documentos/Procedimientos/Procedimiento-UserStories.md) y [Procedimiento de Tickets de Trabajo](Documentos/Procedimientos/Procedimiento-TicketsTrabajo.md).
