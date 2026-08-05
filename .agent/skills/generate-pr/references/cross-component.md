# Referencia — Awareness entre componentes del monorepo

Módulo cargado por `generate-pr` en la Fase B/C cuando el `manifest.json` lista
dominios de **más de un componente**.

## Contexto

`joiabagur-pv` es un **monorepo**: no hay repos hermanos ni PRs coordinadas entre
repositorios. Una PR puede tocar varios componentes a la vez, y ahí es donde
aparecen los acoplamientos que el body debe dejar explícitos:

| Componente | Dominios del manifest | Tecnología |
|---|---|---|
| Backend | `backend-auth`, `backend-data`, `backend-domain`, `backend-api`, `backend-application`, `backend-infrastructure`, `backend-misc` | .NET 10, ASP.NET Core, EF Core, PostgreSQL |
| Frontend | `frontend-services`, `frontend-pages`, `frontend` | React 19, TypeScript, Vite, Metronic |
| Servicio de IA | `ai-contracts`, `ai-service` | Python, FastAPI, `jbg_ai`, pgvector |
| Infra / CI | `infra`, `ci` | Terraform, Docker, nginx, GitHub Actions |
| Especificación | `openspec`, `docs` | OpenSpec, `Documentos/` |

## Acoplamientos que hay que señalar

1. **Backend ↔ Frontend.** Si el diff cambia un DTO o un endpoint en
   `backend-api` y también `frontend-services`, verifica que los tipos
   TypeScript acompañen al cambio. Si el contrato cambia y el frontend **no**
   está en el diff, dilo: es un desajuste pendiente, no un olvido del reviewer.
2. **Backend ↔ ai-service.** La frontera es JWT interno HS256: .NET emite el
   token, `jbg-ai` lo valida y el `pos_id` del token manda sobre el body. Un
   cambio en los claims de un lado sin el otro es un breaking change operativo.
3. **`ai-service/openapi.json`.** Es un snapshot congelado con test de igualdad.
   Si el diff toca `ai-contracts` sin actualizar `openapi.json` (o al revés), el
   test de snapshot falla: señálalo en riesgos.
4. **Migraciones EF Core.** Un cambio en `backend-data` con migración nueva
   condiciona el orden de despliegue y el rollback.
5. **Código ↔ especificación.** Si el diff toca código de una capability pero no
   su spec en `openspec/`, o al revés, indícalo: el flujo del repo es
   propose → apply → verify → archive.

## Qué añadir al body

1. En **"Motivación y contexto"**, nombra el change de OpenSpec asociado
   (`openspec/changes/<slug>/`) y la HU de `Documentos/Historias/` si existe.
2. En **"Deployment notes"**, el orden concreto si importa. La imagen de
   producción empaqueta API + SPA juntas, así que backend y frontend se
   despliegan a la vez; `jbg-ai` es un contenedor aparte y **el proveedor de un
   contrato se despliega antes que su consumidor**.
3. En **"Notas adicionales"**, el impacto cruzado: qué componente queda
   pendiente de alinear, si lo hay.

Agrupa siempre por dominio, no por componente entero: un cambio de 3 líneas en
`frontend-services` no merece el mismo espacio que un endpoint nuevo.
