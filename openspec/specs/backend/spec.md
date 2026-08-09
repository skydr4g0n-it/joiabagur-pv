# backend Specification

## Purpose
TBD - created by archiving change init-backend-structure. Update Purpose after archive.
## Requirements
### Requirement: Layered Architecture

The backend SHALL implement a layered architecture following the C4 model with clear separation of concerns: Domain (core business logic), Infrastructure (external dependencies), Application (use cases), and API (HTTP interface).

#### Scenario: Domain Layer Isolation
- **WHEN** business rules change
- **THEN** only Domain layer code requires modification
- **AND** Infrastructure and API layers remain unchanged

#### Scenario: Infrastructure Abstraction
- **WHEN** switching from PostgreSQL to another database
- **THEN** only Infrastructure layer requires changes
- **AND** Domain, Application, and API layers remain unaffected

### Requirement: Entity Framework Core Integration

The backend SHALL use Entity Framework Core as the ORM with PostgreSQL as the database provider, supporting migrations, connection pooling, and optimized queries for free-tier constraints.

#### Scenario: Database Connection Pooling
- **WHEN** system handles multiple concurrent requests
- **THEN** connection pool is limited to 5-10 connections maximum
- **AND** connections are reused efficiently

#### Scenario: Migration Management
- **WHEN** deploying database schema changes
- **THEN** EF Core migrations are applied automatically
- **AND** migration scripts are version-controlled

### Requirement: Repository Pattern Implementation

The backend SHALL implement the repository pattern for data access abstraction, providing consistent CRUD operations and query capabilities across all entities.

#### Scenario: Generic Repository Operations
- **WHEN** creating a new entity type
- **THEN** standard CRUD operations are available without custom implementation
- **AND** LINQ queries are supported for complex filtering

#### Scenario: Unit of Work Pattern
- **WHEN** performing multiple related database operations
- **THEN** changes can be committed atomically
- **AND** rollback occurs if any operation fails

### Requirement: Password Security

The backend SHALL use BCrypt hashing for password storage with salt, ensuring secure credential management.

#### Scenario: Password Hashing
- **WHEN** user sets or changes password
- **THEN** password is hashed using BCrypt with appropriate work factor
- **AND** salt is automatically generated and stored

#### Scenario: Password Verification
- **WHEN** user attempts authentication
- **THEN** provided password is verified against stored hash
- **AND** timing attack prevention is implemented

### Requirement: Structured Logging

The backend SHALL implement structured logging using Serilog, capturing relevant context and supporting multiple output targets. The rendering of those events SHALL depend on the deployment environment: a human-readable console rendering under a development profile, and one JSON object per event under a production profile, so that emitted events are ingestible by an observability platform without parsing free text. Named properties of a log event MUST be emitted as fields rather than embedded in a rendered sentence. Correlation SHALL cover outbound calls to other services, not only inbound requests: a call the backend makes to another service MUST be attributable to the same correlation identifier as the request that caused it.

#### Scenario: Request Logging
- **WHEN** API request is processed
- **THEN** request details are logged with correlation ID
- **AND** response status and duration are captured

#### Scenario: Error Logging
- **WHEN** exception occurs
- **THEN** full exception details and context are logged
- **AND** sensitive information is redacted

#### Scenario: Environment-dependent rendering
- **WHEN** the application emits a log event under a development profile
- **THEN** the output is the human-readable console rendering
- **AND** under a production profile the same event is emitted as a single-line JSON object
- **AND** the event's named properties appear as fields, not embedded in a rendered sentence

#### Scenario: Outbound Call Logging
- **WHEN** the backend calls another service on behalf of an inbound request
- **THEN** the outbound call is logged with the same correlation ID as that request
- **AND** its outcome and duration are captured

### Requirement: Input Validation

The backend SHALL use FluentValidation for comprehensive input validation across all API endpoints and service operations.

#### Scenario: API Input Validation
- **WHEN** invalid data is submitted to API endpoint
- **THEN** validation errors are returned with specific field details
- **AND** appropriate HTTP status codes are used

#### Scenario: Business Rule Validation
- **WHEN** business rule is violated
- **THEN** domain exception is thrown with descriptive message
- **AND** validation is consistent across all layers

### Requirement: File Storage Abstraction

The backend SHALL provide an abstraction layer for file storage, supporting both local filesystem (development) and AWS S3 (production), with secure pre-signed URL generation and configurable storage providers.

#### Scenario: Storage Provider Switching
- **WHEN** deploying to different environments
- **THEN** storage implementation can be changed via configuration (`FileStorage:Type` = "Local" or "S3")
- **AND** no code changes are required

#### Scenario: Pre-signed URLs for S3
- **WHEN** client needs to access files stored in S3
- **THEN** pre-signed URLs are generated with configurable expiration (default 60 minutes)
- **AND** URLs provide temporary read access without exposing AWS credentials

#### Scenario: S3 Upload with Server-Side Encryption
- **WHEN** file is uploaded to S3
- **THEN** file is stored with AES-256 server-side encryption
- **AND** unique filename is generated with timestamp and GUID

#### Scenario: S3 Folder Organization
- **WHEN** files are uploaded to S3
- **THEN** files are organized in folders: `/product-photos`, `/sale-photos`, `/ml-models`
- **AND** folder structure mirrors local development environment

### Requirement: Health Monitoring

The backend SHALL expose health check endpoints for monitoring system status and dependencies.

#### Scenario: Database Health Check
- **WHEN** health endpoint is called
- **THEN** database connectivity is verified
- **AND** response indicates healthy/unhealthy status

#### Scenario: Application Health Check
- **WHEN** monitoring system polls health endpoint
- **THEN** application responsiveness is confirmed
- **AND** relevant metrics are returned

### Requirement: API Documentation

The backend SHALL provide interactive API documentation via Swagger/OpenAPI specification.

#### Scenario: Swagger UI Access
- **WHEN** developer accesses documentation endpoint
- **THEN** interactive API explorer is available
- **AND** all endpoints are documented with examples

#### Scenario: OpenAPI Specification
- **WHEN** API spec is requested
- **THEN** complete OpenAPI 3.0 specification is returned
- **AND** can be used for client code generation

### Requirement: CORS Configuration

The backend SHALL configure CORS policies appropriate for each environment, allowing frontend access while maintaining security.

#### Scenario: Development CORS
- **WHEN** running in development environment
- **THEN** CORS allows all origins for frontend development
- **AND** appropriate headers are set

#### Scenario: Production CORS
- **WHEN** running in production environment
- **THEN** CORS is restricted to allowed domains
- **AND** credentials are properly handled

### Requirement: Configuration Management

The backend SHALL use environment-based configuration with strongly-typed options, supporting different settings per deployment environment.

#### Scenario: Environment Configuration
- **WHEN** application starts
- **THEN** configuration is loaded from appropriate environment files
- **AND** sensitive values are protected

#### Scenario: Options Pattern
- **WHEN** configuration values are needed
- **THEN** strongly-typed options classes are injected
- **AND** validation ensures required values are present

### Requirement: Docker Development Environment

The backend SHALL provide Docker configuration for consistent development environment setup.

#### Scenario: Docker Compose Setup
- **WHEN** developer runs docker-compose
- **THEN** PostgreSQL database is started
- **AND** application connects successfully

#### Scenario: Hot Reload Development
- **WHEN** code changes are made
- **THEN** application automatically restarts
- **AND** changes are reflected immediately

### Requirement: AWS Secrets Manager Integration

The backend SHALL integrate with AWS Secrets Manager for secure credential management in production environments, supporting automatic configuration loading and environment-based fallback.

#### Scenario: Production Secrets Loading
- **WHEN** application starts in Production environment
- **THEN** configuration is loaded from AWS Secrets Manager secret "jpv-prod"
- **AND** secrets are merged with appsettings.json configuration

#### Scenario: Development Environment Fallback
- **WHEN** application starts in Development environment
- **THEN** configuration is loaded from local appsettings.Development.json and environment variables
- **AND** AWS Secrets Manager is not accessed

#### Scenario: Required Secrets Validation
- **WHEN** production application starts
- **THEN** required secrets are validated: ConnectionStrings:DefaultConnection, Jwt:SecretKey
- **AND** application fails fast with descriptive error if secrets are missing

### Requirement: Production Database Configuration

The backend SHALL connect to AWS RDS PostgreSQL in production with optimized connection pooling and SSL encryption.

#### Scenario: RDS Connection with SSL
- **WHEN** connecting to RDS PostgreSQL in production
- **THEN** connection uses SSL/TLS encryption
- **AND** connection string includes `SSL Mode=Require`

#### Scenario: Connection Pool Optimization
- **WHEN** application handles concurrent requests
- **THEN** connection pool is limited to 5-10 connections (free-tier optimization)
- **AND** connections are reused efficiently with proper timeout handling

#### Scenario: Database Health Check
- **WHEN** health endpoint is called
- **THEN** RDS connectivity is verified
- **AND** response indicates healthy/unhealthy status with latency metrics

### Requirement: Production Deployment Configuration

The backend SHALL support production deployment via Docker container with environment-based configuration and health monitoring.

#### Scenario: Docker Production Build
- **WHEN** Docker image is built for production
- **THEN** multi-stage build creates optimized runtime image (~200MB)
- **AND** non-root user is used for security
- **AND** image contains only .NET runtime (no Python or ML dependencies)

#### Scenario: Health Check Endpoint
- **WHEN** the load balancer or process supervisor performs a health check (e.g. nginx/Docker/App Runner)
- **THEN** `/api/health` (or configured health path) responds within timeout
- **AND** includes database and storage connectivity status where applicable

#### Scenario: CORS Production Configuration
- **WHEN** running in production environment
- **THEN** CORS is restricted to the production web origin (e.g. `https://pv.joiabagur.com`) and any configured custom domains
- **AND** credentials are properly handled

### Requirement: Automated Backup Verification

The backend infrastructure SHALL maintain automated database backups with configurable retention and verification capabilities.

#### Scenario: Daily Automated Backups
- **WHEN** backup window time is reached (03:00-04:00 UTC)
- **THEN** RDS creates automated snapshot
- **AND** previous backups are retained for 7 days

#### Scenario: Point-in-Time Recovery Capability
- **WHEN** data recovery is needed
- **THEN** database can be restored to any point within retention period
- **AND** recovery creates new database instance (non-destructive)

### Requirement: ML Model Storage and Distribution

The backend SHALL store and serve ML models uploaded by administrators, supporting version management and metadata tracking.

#### Scenario: Store uploaded model
- **WHEN** administrator uploads trained model via dashboard or CLI
- **THEN** model files are stored in S3 at `/ml-models/v{version}/`
- **AND** model.json and .bin shard files are validated before storing
- **AND** ModelMetadata table is updated with version, upload date, and accuracy metrics

#### Scenario: Serve model metadata
- **WHEN** frontend requests GET /api/image-recognition/model/metadata
- **THEN** backend returns latest model version, upload date, and download URL
- **AND** response includes model size for download progress estimation

#### Scenario: Serve model files
- **WHEN** frontend requests model files
- **THEN** backend serves files from S3 via pre-signed URL or proxy
- **AND** appropriate cache headers are set for CDN optimization

#### Scenario: Preserve model history
- **WHEN** new model version is uploaded
- **THEN** previous model versions are NOT deleted
- **AND** ModelMetadata maintains history of all versions
- **AND** admin can view training history in dashboard

### Requirement: Dashboard Aggregation Service

The backend SHALL provide a DashboardService that computes pre-aggregated KPIs by querying Sales, Returns, and Inventory data, with optional POS scoping and IMemoryCache for expensive aggregations.

#### Scenario: Compute global KPIs for administrator
- **WHEN** DashboardService is called without posId
- **THEN** service queries Sales table for today's count and total across all POS
- **AND** queries Sales for current month's total revenue
- **AND** queries Sales for same month of previous year's revenue (nullable if no data)
- **AND** queries Returns for current month's count and total amount
- **AND** returns all KPIs in a single response DTO

#### Scenario: Compute POS-scoped KPIs for operator
- **WHEN** DashboardService is called with a posId
- **THEN** service queries Sales table for today's count and total filtered by posId
- **AND** queries Sales for current natural week (Mon-Sun) revenue filtered by posId
- **AND** queries Returns for today's count filtered by posId
- **AND** does not compute donut chart aggregations

#### Scenario: Cache donut chart aggregations
- **WHEN** DashboardService computes payment method distribution or return category distribution
- **THEN** service checks IMemoryCache for cached result
- **AND** if cache hit, returns cached data without querying database
- **AND** if cache miss, queries database, stores result in IMemoryCache with AbsoluteExpirationRelativeToNow = 24 hours, and returns fresh data

#### Scenario: Validate POS access for operator
- **WHEN** DashboardService is called with posId by an operator
- **THEN** service validates the operator is assigned to the POS via UserPointOfSale
- **AND** returns 403 Forbidden if not assigned

### Requirement: Dashboard API Controller

The backend SHALL expose a DashboardController with a GET /api/dashboard/stats endpoint that delegates to DashboardService, enforcing authentication and role-based response shaping.

#### Scenario: GET /api/dashboard/stats returns 200 for authenticated users
- **WHEN** authenticated user calls GET /api/dashboard/stats
- **THEN** controller delegates to DashboardService
- **AND** returns 200 OK with DashboardStatsDto

#### Scenario: Reject unauthenticated requests
- **WHEN** unauthenticated user calls GET /api/dashboard/stats
- **THEN** controller returns 401 Unauthorized

#### Scenario: Admin receives full response including distributions
- **WHEN** authenticated administrator calls GET /api/dashboard/stats
- **THEN** response includes paymentMethodDistribution and returnCategoryDistribution arrays

#### Scenario: Operator receives scoped response without distributions
- **WHEN** authenticated operator calls GET /api/dashboard/stats?posId={id}
- **THEN** response includes POS-scoped KPIs
- **AND** paymentMethodDistribution and returnCategoryDistribution are null

