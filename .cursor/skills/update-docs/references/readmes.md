# Reglas por README — joiabagur-pv

Los **cinco** README del monorepo se revisan en cada ejecución de `update-docs`,
aunque la matriz de impacto no los haya disparado. Para cada uno el plan debe
llevar un veredicto explícito: `actualizar`, `sin cambios` o `no aplica`.

Regla común: un README describe **cómo se usa y cómo está montado su
componente**. No duplica las guías de `Documentos/Guias/` ni las specs de
`openspec/specs/`: las enlaza.

---

## `README.md` (raíz) — es-ES · política `frozen-sections`

**No es un README técnico al uso: es el entregable del máster.** Su estructura
está fijada por la plantilla de la entrega y no se reorganiza.

Secciones **editables** por esta skill:

| Sección | Se actualiza cuando… |
|---|---|
| `### 1.4. Instrucciones de instalación` | Cambian pasos de arranque, requisitos, puertos, `docker-compose*.yml` o scripts de setup |
| `## 2. Arquitectura del sistema` (2.1–2.6) | Cambia el diagrama, un componente, la estructura de carpetas, la infraestructura, la seguridad o el stack de tests |
| `## 3. Modelo de datos` (3.1–3.2) | Cambian entidades, campos o relaciones — debe cuadrar con `Documentos/modelo-de-datos.md` |
| `## 4. Especificación de la API` | Cambian los endpoints documentados (hoy `POST /api/sales`, `GET /api/sales`, `GET /api/dashboard/low-stock`): request, response, códigos o roles |
| `## Documentación adicional` | Se crea, mueve o renombra un documento enlazado |

Secciones **congeladas** (se reportan en el plan, no se editan sin mención
expresa del usuario):

- `## 0. Ficha del proyecto` — datos de la entrega.
- `### 1.1`, `### 1.2`, `### 1.3` — narrativa de producto de la entrega. Si una
  funcionalidad nueva debería aparecer en 1.2, propón el texto en el plan y
  espera aprobación explícita.
- `## 5. Historias de usuario` y `## 6. Tickets de trabajo` — ejemplos
  seleccionados para la entrega. Las HU vivas están en `Documentos/Historias/`.

Detalles: el `## Índice` de la cabecera enlaza a los anclajes de las secciones —
si tocas un encabezado, actualiza el índice. Los diagramas son Mermaid.

---

## `backend/README.md` — inglés · política `editable`

Documento operativo largo del backend .NET. Secciones y su fuente de verdad:

| Sección | Fuente de verdad a verificar |
|---|---|
| `## Stack` | `backend/src/**/*.csproj`, `JoiabagurPV.sln` |
| `## Project Structure` | árbol real de `backend/src/` |
| `## Getting Started` | `docker-compose.yml`, `appsettings*.json`, scripts `setup-dev-certificates.*` |
| `## Authentication` (flow, endpoints, token config, security features) | `AuthController`, servicios JWT, `RefreshToken`, `appsettings.json` (`Jwt:*`) |
| `## Authorization` (RBAC y **Authorization Matrix**) | atributos `[Authorize(Roles = ...)]` de los controladores y la lógica de `UserPointOfSale` |
| `## User Management`, `## Inventory Management` | controladores y servicios correspondientes; tipos de movimiento desde el enum real |
| `## Testing` | `JoiabagurPV.Tests`, umbral de cobertura, uso de Testcontainers |
| `## API Documentation` / `Response Codes` | configuración de Scalar y los códigos que devuelven los controladores |
| `## Configuration` / `Environment Variables` | `appsettings*.json` + `terraform/ssm.tf` (nombres `/jpv/prod/*`) |
| `## Database Migrations` | carpeta `Migrations/` |

Las **tablas de endpoints y la matriz de autorización** son lo primero que se
desincroniza: si el rango toca `Controllers/**`, verifícalas fila a fila.

---

## `frontend/README.md` — inglés · política `editable`

| Sección | Fuente de verdad a verificar |
|---|---|
| `## Tech Stack` | `frontend/package.json` (versiones reales, no aproximadas) |
| `## Getting Started` | scripts de `package.json`, `vite.config.ts`, variables `VITE_*` |
| `## Testing` (unit, E2E, estructura, convenciones) | `vitest.config`/`vite.config.ts`, `playwright.config.ts`, `frontend/src/test/`, `frontend/e2e/` |
| `## Scripts` | tabla de scripts: debe coincidir exactamente con `package.json` |

Si aparece un módulo nuevo bajo `frontend/src/pages/` o `frontend/src/services/`,
el impacto suele ser mayor en `Documentos/modelo-c4.md` (módulos del frontend)
que en este README: no dupliques el catálogo de módulos aquí.

---

## `ai-service/README.md` — inglés · política `editable`

README del microservicio `jbg-ai`. **Está versionado por change**: hoy se titula
`# jbg-ai (C01 skeleton)` y varias secciones llevan el marcador `(C01)`.

Reglas propias:

- Cuando el change en curso avance (C02, C03…), **el marcador del título y el de
  las secciones deben avanzar con él**. No dejes `(C01)` describiendo lo que ya
  es C02.
- `## Explicit non-goals (C01)` es una lista que **encoge** conforme los changes
  entregan funcionalidad. Al archivar un change, comprueba qué non-goal ha
  dejado de serlo.
- `## Required environment` debe coincidir con `ai-service/src/jbg_ai/config/settings.py`
  (pydantic-settings): nombres, obligatoriedad y valores por defecto.
- `## Layout` debe reflejar el árbol real de `ai-service/src/jbg_ai/`.
- `## Run with Docker Compose` y la nota del volumen de pgvector deben cuadrar
  con el `docker-compose.yml` que levanta el servicio.
- `## Tests` describe `uv run pytest`: sin llamadas reales a LLM, embeddings ni RDS.

La frontera arquitectónica (**Python solo vectorial/LLM; .NET manda en precio,
stock y permisos; el navegador nunca llama a Python**) se documenta en
`Documentos/arquitectura.md` y `openspec/project.md`. Aquí solo se enuncia y se
enlaza.

---

## `terraform/README.md` — inglés · política `editable`

README de la pila de infraestructura AWS. Fuente de verdad: los propios `.tf`.

| Sección | Fuente de verdad a verificar |
|---|---|
| Tabla de recursos por fichero | `resource`/`data` de `ec2.tf`, `rds.tf`, `s3.tf`, `ecr.tf`, `iam.tf`, `ssm.tf` |
| Tabla de variables | `variables.tf` (tipo, valor por defecto, si es `sensitive`) |
| Tabla de outputs | `outputs.tf` (y su correspondencia con los secretos de GitHub Actions) |
| Parámetros SSM | nombres literales `/jpv/prod/*` de `ssm.tf` |
| Estado remoto | `backend.tf` (bucket y prerequisito de creación manual) |
| Arranque de la instancia | `templates/user_data.sh` |

Reglas propias:

- **Nunca** incluyas valores de secretos, contraseñas, ARN de cuenta ni IPs
  reales. Los `.tfvars` no se documentan con valores: se referencia
  `terraform.tfvars.example`.
- El **procedimiento** de despliegue vive en
  `Documentos/Guias/deploy-aws-production.md`. Este README documenta *qué hay en
  la pila*; la guía documenta *cómo se opera*. Enlázalos, no los dupliques.
- Los workflows App Runner + CloudFront están **deprecados y son manuales**: si
  los mencionas, mantén esa marca.
