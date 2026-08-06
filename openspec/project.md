# Project Context

## Purpose

**Sistema de Gestión de Puntos de Venta para Joyería** - An integral management system for a jewelry business operating across multiple points of sale (own stores and third-party locations like hotels). The application enables inventory management, sales registration, and product identification through AI-powered image recognition.

### Key Objectives
- Centralized product catalog with photo-based product identification
- Multi-location inventory tracking with Excel import capabilities
- Sales registration with AI image recognition (3-5 suggestions ordered by confidence)
- Role-based access (Administrator full access, Operator restricted to assigned locations)
- Optimized for mobile use by operators at points of sale
- Free-tier cloud deployment (AWS/Azure)

### MVP Scope (Phase 1)
10 Epics with 47 User Stories covering:
- **EP1**: Product Management (7 stories)
- **EP2**: Inventory Management (6 stories — includes assign/unassign products to POS)
- **EP3**: Sales Registration (4 stories — includes manual price override, cart & bulk checkout)
- **EP4**: AI Image Recognition (1 story)
- **EP5**: Returns Management (3 stories — multi-sale, partial, categorized)
- **EP6**: Payment Methods Management (3 stories)
- **EP7**: Authentication & User Management (6 stories)
- **EP8**: Points of Sale Management (5 stories — includes AllowManualPriceEdit config)
- **EP9**: Queries & Reports (4 stories)
- **EP10**: Jewelry Component Management (8 stories — master table, assignment, templates, margin reports)

---

## Tech Stack

### Backend
- **Runtime**: .NET 10
- **Framework**: ASP.NET Core Web API
- **Language**: C#
- **ORM**: Entity Framework Core
- **Database**: PostgreSQL 15+
- **Authentication**: JWT (JSON Web Tokens)
- **API Documentation**: Scalar (modern alternative to Swagger)
- **Logging**: Serilog
- **Architecture**: Monolithic with layered separation (Domain → Infrastructure → Application → API)

### Frontend
- **Framework**: React 19
- **Language**: TypeScript
- **Build Tool**: Vite
- **UI Template**: Metronic React (Layout 8 - sidebar navigation)
- **UI Components**: Radix UI, Tailwind CSS, Lucide React icons
- **Forms**: React Hook Form + Zod validation
- **Tables**: TanStack Table (React Table)
- **HTTP Client**: Axios/Fetch
- **State Management**: Context API (or Zustand if needed)
- **ML Framework**: TensorFlow.js / ONNX.js (client-side image recognition)

### AI Service (`jbg-ai`)
- **Runtime**: Python 3.11+
- **Framework**: FastAPI + Uvicorn (app factory, `docs_url` disabled)
- **Package Manager**: uv (`pyproject.toml` + `uv.lock`)
- **Configuration**: pydantic-settings with fail-fast on required env
- **Service Auth**: internal HS256 JWT (PyJWT); the .NET API is the only issuer
- **Contract**: frozen `/v1` surface versioned in `ai-service/openapi.json`

### Infrastructure
- **Containers**: Docker, Docker Compose (development)
- **CI/CD**: GitHub Actions
- **Repository**: GitHub
- **Cloud**: AWS (EC2 + Docker bundlado + nginx, RDS PostgreSQL, S3, ECR, SSM Parameter Store; GitHub OIDC para deploy)
- **Target**: Free-tier optimized deployment
- **Locale**: es-ES, currency EUR (€)

### Testing Stack

**Backend:**
- Test Framework: xUnit 2.9.x
- Mocking: Moq 4.20.x
- Assertions: FluentAssertions 7.x
- Test Data: Bogus 35.x
- Integration Tests: Testcontainers 4.x (PostgreSQL)

**Frontend:**
- Test Runner: Vitest 4.x
- Component Testing: React Testing Library 16.x
- User Events: @testing-library/user-event 14.x
- API Mocking: MSW (Mock Service Worker) 2.x
- E2E Testing: Playwright 1.x
- DOM Environment: jsdom 25.x

**AI Service (`jbg-ai`):**
- Test Framework: pytest 9.x
- HTTP Client: httpx (FastAPI `TestClient`)
- No real LLM, embedding or RDS calls; stub tests block socket connections

---

## Project Conventions

### Code Style

**Backend (C#/.NET):**
- Follow Microsoft C# coding conventions
- Use async/await for I/O operations
- Repository pattern for data access
- Service layer for business logic
- DTOs for API contracts
- FluentValidation for input validation
- Structured logging with Serilog

**Frontend (TypeScript/React):**
- Functional components with hooks
- TypeScript strict mode enabled
- Components colocated with tests (`component.tsx` + `component.test.tsx`)
- Services organized by domain module
- Custom hooks for reusable logic
- Prefer Metronic UI components over custom implementations

### Architecture Patterns

**Backend Layers (per Modelo C4):**
1. **Domain (Core)**: Entities, Value Objects, domain interfaces
2. **Infrastructure**: EF Core repositories, DbContext, migrations, File Storage Service
3. **Application (Services)**: Product Service, Sale Service, Inventory Service, etc.
4. **API (Controllers)**: REST endpoints, DTOs, middleware (JWT, CORS, logging)

**Frontend Modules (per Metronic analysis):**
- Auth Module (login, session, token management)
- Product Module (catalog, import, photos)
- Inventory Module (stock views, adjustments)
- Sale Module (registration, payment selection)
- Image Recognition Module (capture, ML inference, suggestions)
- Return Module (registration, history)
- Payment Method Module (configuration, assignment)
- Point of Sale Module (CRUD)
- User Module (management, assignments)
- Report Module (queries, filters)

**Shared Services:**
- File Storage Service (abstraction for local/S3/Blob)
- Stock Validation Service
- Payment Method Validation Service
- Excel Import Service

### Testing Strategy

**Backend Tests:**
- Nomenclature: `Method_Scenario_ExpectedResult` (e.g., `CreateSale_WithInsufficientStock_ShouldThrowException`)
- Structure: AAA (Arrange, Act, Assert)
- Minimum coverage target: 70%
- Unit tests for services and validators
- Integration tests with Testcontainers (PostgreSQL)
- JWT authentication tests for protected endpoints

**Frontend Tests:**
- Nomenclature: `should [behavior] when [condition]` (e.g., `should show error when API returns 401`)
- Prefer accessible queries (`getByRole`, `getByLabelText` over `getByTestId`)
- MSW for API mocking
- Playwright for E2E flows (authentication, CRUD operations)
- Minimum coverage target: 70%

**AI Service (`jbg-ai`) Tests:**
- Nomenclature: `test_<unit>_<scenario>_<expected>` (e.g., `test_health_returns_ok_with_version`)
- Test tree mirrors the `src/jbg_ai/` package; see `ai-service/tests/README.md`
- Injected fakes for LLM and embedding clients — never a real provider, API or RDS
- Markers: `db` (needs PostgreSQL with pgvector), `slow` (evaluation sweeps)

### Git Workflow

- **Main branch**: `master` (production-ready)
- **Integration branch**: `ai-eng` (AI final project work)
- **Feature branches**: `feature/[epic]-[description]`
- **Commits**: Conventional commits format
- **CI/CD**: GitHub Actions for build, test, and deploy

### OpenSpec Validation

- **Project gate**: `openspec validate --all --strict` must report `0 failed`. Use this exact form in Definition-of-Done items.
- **Single change in progress**: `openspec validate <change-name> --strict`.
- The bare form (`openspec validate`, with or without `--strict`) validates nothing and exits 1 — it is not a pass.

### Documentation

- **Language**: Technical documentation in English, User Stories and user-facing guides in Spanish
- **Tickets**: Written in English for code consistency
- **UI Language**: Spanish (es-ES)
- **Location**: `Documentos/` folder for all project documentation
- **User Stories**: `Documentos/Historias/HU-EP[X]-[NNN].md`
- **Work Tickets**: `Tickets/EP[X]/HU-EP[X]-[NNN]/T-EP[X]-[NNN]-[MMM].md`

#### Post-Implementation Documentation Update

After completing an OpenSpec change implementation (e.g., via `openspec-apply`), update the project documentation to reflect the new or modified capability. Review each file below and update only those affected by the change:

| File | Update when... |
|------|---------------|
| `Documentos/epicas.md` | Epic scope, user story list, or story counts changed |
| `Documentos/Historias/HU-EP[X]-[NNN].md` | A new user story is needed for the capability |
| `Documentos/modelo-de-datos.md` | Entity fields, relationships, or indexes changed |
| `Documentos/modelo-c4.md` | New components, containers, or integration points added |
| `Documentos/arquitectura.md` | Architectural patterns, layers, or cross-cutting concerns changed |
| `Documentos/Guias/*.md` | User-facing flows, validations, or FAQ entries affected |
| `README.md` (root) | Installation steps, architecture, data model, or documented API endpoints changed — technical sections only; the deliverable sections (0, 1.1–1.3, 5, 6) are frozen |
| `backend/README.md` | Endpoints, authorization matrix, environment variables, migrations, or test setup changed |
| `frontend/README.md` | Tech stack versions, npm scripts, or test setup changed |
| `ai-service/README.md` | `jbg-ai` contract, settings, layout, non-goals, or the change marker (C01, C02…) changed |
| `ai-service/tests/README.md` | The test tree gains a folder, a marker, or a shared helper in `tests/support/` |
| `terraform/README.md` | AWS resources, variables, outputs, or `/jpv/prod/*` parameters changed |
| `openspec/config.yaml` | A fact restated in the condensed `context` block changed |

Run the `update-docs` command (skill replicated in `.agent/`, `.claude/`, `.codex/`, `.cursor/` and `.opencode/skills/update-docs/`) to detect which of these are affected by the latest committed and uncommitted changes, review them against the real code, and apply the updates after confirmation.

---

## Domain Context

### Business Domain
- **Industry**: Jewelry retail
- **Operations**: Multiple points of sale (own stores + third-party locations like hotels)
- **Key Challenge**: Product identification accuracy - jewelry items can be difficult to distinguish
- **Solution**: AI-powered image recognition with manual confirmation

### Key Entities
- **Product**: SKU (unique), name, description, price, collection (optional)
- **ProductPhoto**: Multiple reference photos per product for ML training
- **PointOfSale**: Store locations with assigned operators, payment methods, and manual price edit policy (`AllowManualPriceEdit`)
- **User**: Admin (full access) or Operator (restricted to assigned locations)
- **Sale**: Transaction with price snapshot (official or manual override), payment method, optional photo, override audit fields (`PriceWasOverridden`, `OriginalProductPrice`), optional `BulkOperationId` for cart checkout grouping
- **SalePhoto**: Optional photo attached to a sale (image recognition or manual)
- **Inventory**: Stock quantity per product per location. `IsActive` flag = product assigned to POS (soft delete)
- **InventoryMovement**: Full audit trail (Sale, Return, Adjustment, Import) with `QuantityBefore`/`QuantityAfter`
- **PaymentMethod**: Efectivo, Bizum, Transferencia, Tarjeta TPV propio, Tarjeta TPV punto de venta, PayPal
- **Return**: Multi-sale returns with category (Defectuoso, TamañoIncorrecto, NoSatisfecho, Otro), optional reason & photo, 30-day window, same POS only
- **ReturnSale**: Many-to-many between Return and Sale with quantity and unit price snapshot
- **ReturnPhoto**: Optional photo for return documentation
- **RefreshToken**: JWT refresh token with revocation and rotation tracking
- **ProductComponent**: Master table of jewelry components (materials, labor) with optional cost/sale prices
- **ProductComponentAssignment**: Component assigned to product with quantity, override prices, display order
- **ComponentTemplate**: Reusable template of components for quick product setup
- **ComponentTemplateItem**: Component within a template with quantity
- **ModelMetadata**: AI model versions with accuracy metrics, only one active at a time
- **ModelTrainingJob**: Training job status tracking (Queued, InProgress, Completed, Failed) with progress

### Business Rules
1. Operators can only access assigned points of sale
2. Sales require valid payment method assigned to the point of sale
3. Stock cannot be negative (validated at application level)
4. Price in Sale is a snapshot (not reference to current product price)
5. Products need at least one photo for image recognition
6. Only one photo can be marked as primary per product
7. Manual sale price edits are only allowed when the POS has `AllowManualPriceEdit = true`; overrides are audited with `PriceWasOverridden` and `OriginalProductPrice`
8. Returns must be at the same POS as the original sale, within 30 days, with mandatory category
9. Cart checkout is atomic (all-or-nothing) with idempotency key to prevent duplicates; all lines share same POS and payment method
10. Inventory record presence (`IsActive = true`) determines product assignment to POS (visible to operators)
11. Jewelry component prices use 4-decimal precision; component management is admin-only
12. AI model trains in-browser via TensorFlow.js (MobileNetV2 transfer learning); confidence threshold 40%

---

## Important Constraints

### Free-tier Optimization
- **Database connections**: Max 5-10 simultaneous (connection pooling)
- **Pagination**: Mandatory for all lists (max 50 items/page)
- **Caching**: In-memory cache for frequently accessed data (products, payment methods)
- **Image compression**: Before upload to storage
- **Bundle size**: Frontend < 500KB initial load

### Performance Targets
- **Users**: 2-3 concurrent
- **Products**: ~500 catalog items
- **Response time**: Optimize for mobile operators

### Security Requirements
- JWT authentication with refresh tokens
- BCrypt password hashing with salt
- HTTPS required in production
- CORS configured per environment
- Role-based access control (RBAC)
- Pre-signed URLs for storage access

### Data Storage
- **Development**: Local filesystem (`./uploads/`) + PostgreSQL in Docker
- **Production**: S3/Blob Storage + managed PostgreSQL (RDS/Azure Database)
- **Strategy Pattern**: IFileStorageService abstraction for environment switching

---

## External Dependencies

### Cloud Services (Production — AWS)
- **PostgreSQL**: RDS (db.t3.micro, 20GB)
- **Object Storage**: S3 bucket de ficheros (`prod-jpv-files` en pila Terraform)
- **Edge / TLS**: nginx en EC2 (Let’s Encrypt)
- **Container hosting**: EC2 + Docker (imagen ECR con API + SPA)
- **Config / secrets**: SSM Parameter Store (`/jpv/prod/*`)
- **Logging**: CloudWatch Logs

### Third-party Libraries

**Backend:**
- Entity Framework Core (ORM)
- Serilog (logging)
- BCrypt.Net (password hashing)
- ClosedXML (Excel processing)

**Frontend:**
- Metronic React template (UI components, layouts)
- TensorFlow.js or ONNX.js (ML inference)
- xlsx/exceljs (Excel file reading)
- React Router v7 (routing)
- Sonner (toast notifications)
- next-themes (dark mode support)

### Development Tools
- Docker & Docker Compose
- GitHub Actions
- PostgreSQL 15+
- Node.js (for frontend)
- .NET 10 SDK

---

## Key Documentation References

- **Architecture**: `Documentos/arquitectura.md`
- **C4 Model**: `Documentos/modelo-c4.md`
- **Data Model**: `Documentos/modelo-de-datos.md`
- **Epics**: `Documentos/epicas.md`
- **Testing Backend**: `Documentos/testing-backend.md` + `Documentos/Testing/Backend/`
- **Testing Frontend**: `Documentos/testing-frontend.md` + `Documentos/Testing/Frontend/`
- **Metronic Analysis**: `Documentos/Propuestas/analisis-metronic-frontend.md`
- **Technical Clarifications**: `Documentos/Propuestas/aclaraciones-tecnicas.md`
- **AWS Deploy Guide**: `Documentos/Guias/deploy-aws-production.md`
- **AI Model Admin Guide**: `Documentos/Guias/admin-modelo-ia.md`
- **Sales Registration Guide**: `Documentos/Guias/ventas-registro.md`
- **AWS vs Azure Comparison**: `Documentos/Propuestas/comparacion-aws-azure-deploy.md`
- **User Story Procedure**: `Documentos/Procedimientos/Procedimiento-UserStories.md`
- **Work Ticket Procedure**: `Documentos/Procedimientos/Procedimiento-TicketsTrabajo.md`
