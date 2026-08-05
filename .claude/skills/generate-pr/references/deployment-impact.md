# Referencia — Impacto de despliegue

Módulo cargado por `generate-pr` cuando un chunk toca infra, Docker, dependencias,
configuración o migraciones. Alimenta la sección "Deployment Notes" del body.

## Qué buscar en el diff

- **Configuración y variables de entorno**: altas/bajas/renombrados en
  `appsettings*.json`, en variables con doble guion bajo (`ConnectionStrings__*`,
  `JWT__*`, `Storage__*`, `CORS__*`), en el entorno de `jbg-ai` (`APP_ENV`,
  `SERVICE_VERSION`, `LOG_LEVEL`, `JWT_SECRET`, `STUB_MODE`) o en parámetros de
  SSM (`/jpv/prod/*`). Marca cuáles son obligatorias y cuáles tienen default.
- **Dependencias**: cambios en `*.csproj` / `packages.lock.json` (NuGet),
  `package.json` / `package-lock.json` (npm) y `pyproject.toml` / `uv.lock` (uv).
  Indica paquete y versión; señala saltos de versión mayor.
- **Infraestructura**: `Dockerfile`, `backend/docker-compose.yml`, `terraform/**`
  (EC2, RDS, S3, ECR, IAM, SSM), configuración de nginx. Describe el efecto
  concreto (nueva imagen base, puerto, comando, recurso creado o destruido).
- **Base de datos**: migraciones de EF Core en
  `JoiabagurPV.Infrastructure/**/Migrations/**`, índices nuevos, cambios de
  esquema que requieran backfill. Para `jbg-ai`, esquema `ai` y extensión
  `vector` (pgvector).
- **Build del frontend**: cambios en `vite.config.ts` o en el Dockerfile que
  alteren el bundle embebido en la imagen (`wwwroot`) o el tamaño inicial.
- **CI/CD**: cambios en `.github/workflows/**` que alteren cuándo o cómo se
  despliega (`deploy-aws-ec2.yml`, `test-backend.yml`, `test-frontend.yml`).

## Qué redactar

1. **Variables/parámetros nuevos o modificados** — nombre, si es obligatoria,
   default, y dónde hay que darla de alta (Compose local, SSM en producción).
2. **Pasos post-deploy** — orden concreto y verificable (p. ej. "aplicar
   migración `dotnet ef database update`", "verificar `GET /health`").
3. **Plan de rollback** — qué revertir y qué efectos colaterales tiene
   (migraciones no reversibles, sesiones invalidadas, datos ya migrados).
4. **Orden de despliegue** — la imagen de producción empaqueta API + SPA, así que
   backend y frontend salen juntos; `jbg-ai` es un contenedor aparte. Si el
   cambio cruza componentes, ver `cross-component.md`.

Si el diff no toca despliegue, escribe explícitamente "Sin impacto de despliegue"
en esa sección — no la dejes vacía ni inventes pasos.
