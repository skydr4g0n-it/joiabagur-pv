# Verificación antes de escribir

El manifiesto dice **qué ficheros cambiaron**; no dice qué es verdad ahora. Antes
de reescribir una frase, comprueba el estado actual en la fuente de verdad. Si no
puedes comprobarlo, no lo escribas: al plan como pendiente.

| Afirmación a verificar | Dónde se comprueba |
|---|---|
| Entidades, campos, tipos, relaciones | `backend/src/JoiabagurPV.Domain/Entities/*.cs`, enums en `Domain/Enums/`, configuración en `Infrastructure/Data/`, y la migración más reciente de `Migrations/` |
| Índices y restricciones | `Infrastructure/Data/` (`HasIndex`, `HasConstraint`) y la migración correspondiente |
| Endpoints, verbos, rutas | `backend/src/JoiabagurPV.API/Controllers/**` (atributos `[HttpGet]`, `[Route]`) |
| Rol requerido por endpoint | atributos `[Authorize(Roles = ...)]` del controlador o de la acción |
| Forma de request/response | DTOs de `backend/src/JoiabagurPV.Application/DTOs/**` y sus validadores FluentValidation |
| Reglas de negocio | servicio de aplicación correspondiente, no la spec |
| Variables de entorno del backend | `backend/src/**/appsettings*.json` + `terraform/ssm.tf` (nombres `/jpv/prod/*`) |
| Stack y versiones del backend | `backend/src/**/*.csproj` |
| Stack, versiones y scripts del frontend | `frontend/package.json` |
| Rutas y páginas del frontend | `frontend/src/routing/**`, `frontend/src/pages/**` |
| Servicios y tipos que consumen la API | `frontend/src/services/**`, `frontend/src/types/**` |
| Configuración de tests | `frontend/vite.config.ts`, `frontend/playwright.config.ts`, `backend/src/JoiabagurPV.Tests/**` |
| Settings y variables de `jbg-ai` | `ai-service/src/jbg_ai/config/settings.py` (pydantic-settings) |
| Endpoints y contrato de `jbg-ai` | `ai-service/src/jbg_ai/api/**` y, si existe, el snapshot `ai-service/openapi.json` |
| Dependencias de `jbg-ai` | `ai-service/pyproject.toml` (`uv.lock` para versiones exactas) |
| Recursos, variables y outputs de AWS | `terraform/*.tf` — nunca los valores de `*.tfvars` |
| Arranque de la instancia EC2 | `terraform/templates/user_data.sh` |
| Pasos de despliegue y secretos de CI | `.github/workflows/*.yml` |
| Comportamiento ya especificado | `openspec/specs/<capability>/spec.md` |
| Decisiones de arquitectura ya tomadas | `openspec/changes/archive/*/design.md` (hacen de ADR en este repo) |

## Cómo citar la evidencia en el plan

- Preferible: `backend/src/JoiabagurPV.API/Controllers/SalesController.cs:88`.
- Aceptable: la ruta del fichero tal y como aparece en `manifest.json`.
- No vale: «según el change», «se ha implementado», «debería estar».

## Señales de que **no** hay que tocar el documento

- El cambio es refactor interno sin efecto observable (renombrar un privado,
  extraer un método, mover un fichero dentro de la misma capa).
- Solo cambian tests que no alteran convenciones ni cobertura documentada.
- El change está **activo con tareas pendientes** y la parte que documentarías
  aún no está en el código.
- El documento ya venía modificado en el rango (`changedInRange: true`) y su
  texto ya cuadra con el código: en ese caso, veredicto `sin cambios`.

## Conflictos entre fuentes

Si el código y una spec sincronizada se contradicen, **manda el código** para
documentar el estado actual, y la discrepancia va al plan como nota para
`opsx:sync`. Nunca documentes el punto medio entre las dos.
