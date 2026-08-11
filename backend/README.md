# JoiabagurPV Backend

![Backend Tests](https://github.com/marcello-clearcust/jpv/actions/workflows/test-backend.yml/badge.svg)

Backend API for the JoiabagurPV jewelry point of sale management system.

## Stack

| Component | Technology | Version |
|-----------|------------|---------|
| **Framework** | ASP.NET Core | 10.0 |
| **Database** | PostgreSQL | 15+ |
| **ORM** | Entity Framework Core | 10.0 |
| **Logging** | Serilog | Latest |
| **Authentication** | JWT Bearer | Built-in |
| **Validation** | FluentValidation | 11.x |
| **HTTP resilience** | Microsoft.Extensions.Http.Resilience (Polly v8) | 10.8.0 |

## Project Structure

```
backend/
├── src/
│   ├── JoiabagurPV.API/          # Web API layer (controllers, middleware)
│   ├── JoiabagurPV.Application/  # Application layer (services, DTOs)
│   ├── JoiabagurPV.Domain/       # Domain layer (entities, interfaces)
│   ├── JoiabagurPV.Infrastructure/ # Infrastructure layer (EF Core, repositories)
│   └── JoiabagurPV.Tests/        # Unit and integration tests
├── docker-compose.yml            # Development Docker configuration
└── scripts/                      # Database initialization scripts
```

## Prerequisites

- [.NET 10 SDK](https://dotnet.microsoft.com/download/dotnet/10.0)
- [Docker Desktop](https://www.docker.com/products/docker-desktop) (for PostgreSQL)
- IDE: Visual Studio 2022, VS Code, or JetBrains Rider

## Getting Started

### 1. Start the local services

```bash
docker-compose up -d
```

This starts three services: `postgres` (image `pgvector/pgvector:pg15`, published on **5433**), `pgadmin` (8080) and `jbg-ai`, the Python AI microservice (8001) — see [`ai-service/README.md`](../ai-service/README.md). To start only the database, run `docker-compose up -d postgres`.

### 2. Install Dependencies

```bash
cd src/JoiabagurPV.API
dotnet restore
```

### 3. Configure Application

**Nothing to create.** `appsettings.json` already ships working development defaults — database on port 5433, a development JWT key, and the `AiGateway` section pointing at the port Compose publishes for `jbg-ai`. `appsettings.Development.json` also exists and is versioned: it carries the readable console logging profile, so do not overwrite it.

To change something on your own machine, create `appsettings.Local.json` in `src/JoiabagurPV.API/` — it is gitignored — and override only what you need:

```json
{
  "ConnectionStrings": {
    "DefaultConnection": "Host=localhost;Port=5433;Database=joiabagur_pv;Username=postgres;Password=yours"
  }
}
```

For anything genuinely secret, prefer .NET user-secrets (`dotnet user-secrets set`), which stores values in your user profile instead of the working tree. See [Configuration](#configuration).

### 4. Setup HTTPS Certificates (Development)

```bash
# Windows PowerShell
.\setup-dev-certificates.ps1

# Linux/Mac
./setup-dev-certificates.sh
```

### 5. Run the Application

```bash
cd src/JoiabagurPV.API
dotnet run --launch-profile https
```

The API will be available at:
- **API**: `https://localhost:7169`
- **Scalar API Reference**: `https://localhost:7169/scalar/v1`
- **OpenAPI document**: `https://localhost:7169/openapi/v1.json`

## Authentication

### Overview

The system uses JWT-based authentication with HTTP-only cookies for token storage.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Client App    │────▶│   Auth API      │────▶│   Database      │
│                 │     │   (JWT tokens)  │     │   (PostgreSQL)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Authentication Flow

#### Login Flow

1. Client sends credentials to `POST /api/auth/login`
2. Server validates username and password (BCrypt)
3. Server generates JWT access token (1 hour) and refresh token (8 hours)
4. Tokens are set as HTTP-only cookies
5. Server returns user information

```mermaid
sequenceDiagram
    Client->>+Server: POST /api/auth/login {username, password}
    Server->>+Database: Validate credentials
    Database-->>-Server: User found
    Server->>Server: Verify password (BCrypt)
    Server->>Server: Generate JWT + Refresh Token
    Server-->>-Client: 200 OK + Set-Cookie (tokens)
```

#### Token Refresh Flow

1. Client calls `POST /api/auth/refresh` (refresh token sent automatically via cookie)
2. Server validates refresh token
3. Server revokes old refresh token and issues new tokens
4. New tokens are set as cookies

#### Logout Flow

1. Client calls `POST /api/auth/logout`
2. Server revokes refresh token in database
3. Cookies are cleared

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/auth/login` | POST | No | Authenticate with username/password |
| `/api/auth/refresh` | POST | No* | Refresh access token |
| `/api/auth/logout` | POST | No | Revoke tokens and clear cookies |
| `/api/auth/me` | GET | Yes | Get current user information |

*Requires valid refresh token cookie

### Token Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `AccessTokenExpirationMinutes` | 60 | JWT access token validity |
| `RefreshTokenExpirationHours` | 8 | Refresh token validity (work shift) |

### Security Features

- **HTTP-only cookies**: Tokens are stored in HTTP-only cookies, preventing XSS attacks
- **Secure cookies**: Cookies require HTTPS in production
- **SameSite strict**: Prevents CSRF attacks
- **Token rotation**: Refresh tokens are rotated on each use
- **Token revocation**: Refresh tokens can be revoked immediately
- **Rate limiting**: Login endpoint is rate-limited (30 attempts per 10 minutes per IP)

## Authorization

### Role-Based Access Control (RBAC)

The system has two roles:

| Role | Description | Permissions |
|------|-------------|-------------|
| **Admin** | System administrator | Full access to all features |
| **Operator** | Point of sale operator | Access to assigned points of sale only |

### Authorization Matrix

| Endpoint | Admin | Operator |
|----------|-------|----------|
| `GET /api/auth/me` | ✅ | ✅ |
| `GET /api/users` | ✅ | ❌ |
| `POST /api/users` | ✅ | ❌ |
| `PUT /api/users/{id}` | ✅ | ❌ |
| `PUT /api/users/{id}/password` | ✅ | ❌ |
| `GET /api/users/{id}/point-of-sales` | ✅ | ❌ |
| `POST /api/users/{id}/point-of-sales/{posId}` | ✅ | ❌ |
| `DELETE /api/users/{id}/point-of-sales/{posId}` | ✅ | ❌ |
| `GET /api/inventory` | ✅ | ✅* |
| `GET /api/inventory/assigned` | ✅ | ✅* |
| `GET /api/inventory/centralized` | ✅ | ❌ |
| `GET /api/inventory/movements` | ✅ | ✅* |
| `POST /api/inventory/assign` | ✅ | ❌ |
| `POST /api/inventory/unassign` | ✅ | ❌ |
| `POST /api/inventory/import` | ✅ | ❌ |
| `POST /api/inventory/adjustment` | ✅ | ❌ |
| `GET /api/inventory/import-template` | ✅ | ❌ |

*Operators see only their assigned points of sale

### Point of Sale Access Control

Operators are assigned to specific points of sale. When accessing data:

1. **Admin**: Access to all points of sale
2. **Operator**: Filtered to assigned points of sale only
3. **Ownership is a separate axis**: the admin bypass covers point-of-sale access, not ownership of a record. Recording the selection on a search event (`POST /api/ai/search-events/{id}/selection`) answers 403 to anyone who does not own that event, administrators included — the row is the record of what one specific person did, and letting anyone else complete it would corrupt the data without leaving a trace.

## User Management

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/users` | GET | List all users |
| `/api/users/{id}` | GET | Get user by ID |
| `/api/users` | POST | Create new user |
| `/api/users/{id}` | PUT | Update user |
| `/api/users/{id}/password` | PUT | Change user password |
| `/api/users/{id}/point-of-sales` | GET | Get user's point of sale assignments |
| `/api/users/{id}/point-of-sales/{posId}` | POST | Assign user to point of sale |
| `/api/users/{id}/point-of-sales/{posId}` | DELETE | Unassign user from point of sale |

## Inventory Management

### Overview

The inventory management system tracks product stock across multiple points of sale with full audit trails.

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Point of Sale │────▶│    Inventory    │────▶│   Movements     │
│   (Location)    │     │   (Stock)       │     │   (Audit Trail) │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Key Features

- **Product Assignment**: Assign products to points of sale before stock can be tracked
- **Stock Import**: Bulk import stock from Excel files with validation
- **Manual Adjustments**: Adjust stock quantities with mandatory reason tracking
- **Movement History**: Complete audit trail of all inventory changes
- **Centralized View**: Admin-only aggregated stock view across all locations

### Inventory Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/inventory` | GET | Yes | Get stock for a point of sale |
| `/api/inventory/assigned` | GET | Yes | Get products assigned to a point of sale |
| `/api/inventory/centralized` | GET | Admin | Get aggregated stock view |
| `/api/inventory/product/{id}` | GET | Yes | Get stock breakdown for a product |
| `/api/inventory/assign` | POST | Admin | Assign product to point of sale |
| `/api/inventory/assign/bulk` | POST | Admin | Bulk assign products |
| `/api/inventory/unassign` | POST | Admin | Unassign product (requires 0 stock) |
| `/api/inventory/import` | POST | Admin | Import stock from Excel |
| `/api/inventory/import/validate` | POST | Admin | Validate Excel file without importing |
| `/api/inventory/import-template` | GET | Admin | Download Excel import template |
| `/api/inventory/adjustment` | POST | Admin | Manual stock adjustment |
| `/api/inventory/movements` | GET | Yes | Get movement history with filters |

### Excel Import Format

The stock import feature uses Excel files with the following format:

| Column | Required | Description |
|--------|----------|-------------|
| `SKU` | Yes | Product SKU (must exist in catalog) |
| `Quantity` | Yes | Quantity to add (≥ 0) |

**Important Notes:**
- Column names must match exactly (case-sensitive)
- Quantities are **added** to existing stock
- Products not assigned to the point of sale will be **automatically assigned**
- Download the template from `GET /api/inventory/import-template`

### Stock Adjustment

Manual adjustments require:
- Product must be assigned to the point of sale
- Reason is mandatory (max 500 characters)
- Resulting stock cannot be negative

### Movement Types

| Type | Description |
|------|-------------|
| `Sale` | Stock decreased by sales (automatic) |
| `Return` | Stock increased by returns (automatic) |
| `Adjustment` | Manual adjustment with reason |
| `Import` | Stock added via Excel import |

### Default Admin User

On first run, a default admin user is created:

- **Username**: `admin`
- **Password**: `Admin123!`

> ⚠️ **Important**: Change the default password immediately after first login!

### Password Requirements

- Minimum 8 characters
- Must contain at least one uppercase letter
- Must contain at least one lowercase letter
- Must contain at least one digit
- Must contain at least one special character

## Testing

### Run All Tests

```bash
cd src/JoiabagurPV.Tests
dotnet test
```

> **The suite comes back red, and it is not you.** Around fifty failures predate any
> given change. They are defects in the tests and dependency drift, not in the
> application — and most went unnoticed for weeks because the integration tree only
> runs when Docker is up, while CI only fires on `main` and `develop`.
>
> Judge a change by the failing test **names** against a stashed baseline
> (`git stash push -u`, run, `git stash pop`), never by the count: a handful of the
> failures are order-dependent, so two runs of identical code disagree.
>
> Inventory, root causes and what it would take to close them: *Estado de la suite:
> fallos conocidos* in [../Documentos/testing-backend.md](../Documentos/testing-backend.md).

### Run with Coverage

```bash
# Run tests with coverage collection
dotnet test --collect:"XPlat Code Coverage" --results-directory ./TestResults

# Generate HTML report (requires ReportGenerator)
dotnet tool install --global dotnet-reportgenerator-globaltool
reportgenerator -reports:"./TestResults/**/coverage.cobertura.xml" -targetdir:"./TestResults/CoverageReport" -reporttypes:Html

# Open the report
start ./TestResults/CoverageReport/index.html  # Windows
open ./TestResults/CoverageReport/index.html   # macOS
xdg-open ./TestResults/CoverageReport/index.html  # Linux
```

### Coverage Requirements

| Metric | Minimum Threshold |
|--------|-------------------|
| Line Coverage | 70% |

The CI pipeline enforces a minimum **70% line coverage**. Pull requests that reduce coverage below this threshold will fail the build.

### Test Structure

```
JoiabagurPV.Tests/
├── UnitTests/
│   ├── Application/           # Service unit tests
│   │   ├── AuthenticationServiceTests.cs
│   │   ├── UserServiceTests.cs
│   │   ├── UserPointOfSaleServiceTests.cs
│   │   └── JwtTokenServiceTests.cs
│   └── Domain/               # Entity unit tests
├── IntegrationTests/         # API integration tests
│   ├── ApiWebApplicationFactory.cs
│   ├── AuthControllerTests.cs
│   ├── UsersControllerTests.cs
│   ├── AuthorizationTests.cs
│   └── RateLimitingTests.cs
└── TestHelpers/
    ├── TestBase.cs
    └── TestDataGenerator.cs
```

### Integration Tests

Integration tests use **Testcontainers** to spin up a real PostgreSQL instance:

```bash
# Requires Docker running
dotnet test --filter "FullyQualifiedName~IntegrationTests"
```

## API Documentation

OpenAPI documentation is served with Scalar (not Swagger UI) at `/scalar/v1` when running in development mode; the raw document is at `/openapi/v1.json`.

### Response Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (not authenticated) |
| 403 | Forbidden (not authorized) |
| 404 | Not Found |
| 409 | Conflict (duplicate resource) |
| 429 | Too Many Requests (rate limited) |
| 500 | Internal Server Error |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ConnectionStrings__DefaultConnection` | PostgreSQL connection string | Required |
| `Jwt__SecretKey` | JWT signing key (min 32 chars) | Required |
| `Jwt__Issuer` | JWT issuer | JoiabagurPV |
| `Jwt__Audience` | JWT audience | JoiabagurPV |
| `Jwt__AccessTokenExpirationMinutes` | Access token expiry | 60 |
| `Jwt__RefreshTokenExpirationHours` | Refresh token expiry | 8 |
| `AiGateway__BaseUrl` | Address of the `jbg-ai` service | Required |
| `AiGateway__JwtSecret` | HS256 secret for the internal service token — must match the service's `JWT_SECRET` literally | Required |

`AiGateway` is validated at start-up, not on first use: if the base address is missing or is not an absolute http/https URI, or the secret is absent or shorter than 32 characters, **the API does not start** and the error names the offending key. That is deliberate — a mismatched secret makes `jbg-ai` answer 401 without disclosing why, so the fault is caught at boot instead of during a request. Set `AiGateway__Enabled=false` to skip registering the client altogether.

The address differs by environment and neither value is the obvious one: `http://localhost:8001` in development, because the API runs on the host and only sees the port Compose publishes, and `http://jbg-ai:8000` in production, where both containers share a Docker network.

### Configuration files and secrets

| File | Tracked | Purpose |
|------|---------|---------|
| `appsettings.json` | yes | Configuration and development placeholders |
| `appsettings.Development.json` | yes | Readable console logging profile |
| `appsettings.Production.json` | yes | JSON logging profile |
| `appsettings.Local.json`, `appsettings.*.Local.json` | **no** | Your machine-specific overrides |

`appsettings*.json` are **configuration** and belong in version control, development placeholders included. Real secrets never live in the repository: use .NET user-secrets locally, and SSM Parameter Store (`/jpv/prod/*`) in production, where the deploy script injects them as `__`-separated environment variables.

### Rate Limiting

Login endpoint is rate limited to prevent brute force attacks:

- **Limit**: 30 requests per 10 minutes per IP
- **Response**: 429 Too Many Requests

## Database Migrations

### Apply Migrations

```bash
cd src/JoiabagurPV.API
dotnet ef database update --project ../JoiabagurPV.Infrastructure
```

### Add New Migration

```bash
dotnet ef migrations add MigrationName --project ../JoiabagurPV.Infrastructure
```

## Production Deployment

Production does **not** use Docker Compose. The active path is `.github/workflows/deploy-aws-ec2.yml`: it builds the bundled image (API + SPA) from `src/JoiabagurPV.API/Dockerfile.bundled`, pushes it to ECR, and triggers `jpv-deploy.sh` on the EC2 instance through SSM. That script reads configuration from SSM Parameter Store and starts the container with `docker run`, injecting each value as a `__`-separated environment variable. The database is RDS, outside the instance.

```bash
# Deployment is triggered by pushing to main/master, or manually:
gh workflow run deploy-aws-ec2.yml
```

> `docker-compose.prod.yml` is **not** the production deployment: no workflow, terraform template or script invokes it, it builds the wrong Dockerfile, and it declares its own Postgres container where production uses RDS. It survived the move to the bundled-image path and is pending removal.

### Security Checklist

- [ ] Change default admin password
- [ ] Use strong JWT secret key (32+ characters)
- [ ] Configure HTTPS
- [ ] Set appropriate CORS origins
- [ ] Enable rate limiting
- [ ] Configure proper logging
- [ ] Set up database backups
