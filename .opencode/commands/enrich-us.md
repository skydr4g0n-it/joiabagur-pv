---
name: "Enrich: User Story / Ticket"
description: Transforma una historia de usuario, ticket o descripción funcional en una especificación técnica completa adaptada a la arquitectura de JoiaBagur PV (backend .NET, frontend React/Metronic, ai-service Python)
category: Documentation
tags: [documentation, specs, planning, user-stories, openspec]
---

Actúa como Senior Engineer experto en **JoiaBagur PV** (sistema de gestión de puntos de venta para joyería). Tu objetivo es transformar la historia de usuario, ticket o descripción funcional en `$ARGUMENTS` en una especificación técnica completa y precisa.

> **Memoria de largo plazo de este repo:** no existe `memory-bank/`. La fuente de verdad son `Documentos/` (documentación funcional, arquitectura y procedimientos) y `openspec/` (contexto de proyecto, specs vivas y changes). Cita siempre rutas reales de esos árboles.

### FLUJO DE EJECUCIÓN OBLIGATORIO

**1. Fase de Ingesta.** Lee el archivo `$ARGUMENTS` y clasifica el destino:

- **Historia de usuario** → `Documentos/Historias/HU-EP[X]-[NNN].md`, o `Documentos/Historias/AI-Eng/HU-AIENG-[NNN].md` para el Proyecto Final de IA.
- **Ticket de trabajo** → `openspec/changes/<change>/ticket.md` (práctica vigente del PF) o `Tickets/EP[X]/HU-EP[X]-[NNN]/T-EP[X]-[NNN]-[MMM].md` (convención del procedimiento).

Carga después **solo el contexto relevante** a la petición:

| Fuente | Para qué |
|---|---|
| `openspec/project.md` | **Empieza siempre aquí.** Stack, convenciones, capas, entidades clave, reglas de negocio y constraints. |
| `openspec/config.yaml` | Contexto condensado y reglas para proposal / specs / design / tasks. |
| `Documentos/epicas.md` | Épicas EP1–EP10, alcance, HU existentes, dependencias y orden de implementación. |
| `Documentos/arquitectura.md` | Stack, entornos dev/prod, seguridad, optimizaciones free-tier y decisiones de arquitectura. |
| `Documentos/modelo-c4.md` | Niveles 1–3: contenedores, componentes backend/frontend y mapeo por épica. |
| `Documentos/modelo-de-datos.md` | Entidades, relaciones, índices y consideraciones de implementación. |
| `openspec/specs/<capability>/spec.md` | Comportamiento ya especificado: fuente de verdad de lo que existe. |
| `openspec/changes/` | Changes activos (trabajo en curso) y `archive/*/design.md` (decisiones ya tomadas: aquí hacen de ADR). |
| `Documentos/Procedimientos/Procedimiento-UserStories.md` | Esquema obligatorio si el destino es una HU. |
| `Documentos/Procedimientos/Procedimiento-TicketsTrabajo.md` | Esquema obligatorio si el destino es un ticket de trabajo. |
| `Documentos/testing-backend.md` / `testing-frontend.md` (+ `Documentos/Testing/`) | Stack, nomenclatura y tipo de test aplicable. |
| `Documentos/Propuestas/analisis-metronic-frontend.md` | Componentes Metronic reutilizables **antes** de proponer UI nueva. |
| `Documentos/Proyecto Final AIEng/` | Solo para historias del servicio de IA: diseño RAG, plan de changes (C01, C02…) y especificaciones funcionales. |
| `ai-service/openapi.json` | Contrato congelado de `jbg-ai`, cuando exista. |
| Código real (`backend/src/`, `frontend/src/`, `ai-service/src/`) | Verificar qué está implementado antes de afirmarlo. |

**2. Fase de Análisis (Definition of Ready).** Evalúa y deja constancia en el documento:

- Alcance delimitado, con lista explícita de **qué entra y qué no** (patrón de las HU de AI-Eng).
- Encaje en una épica de `Documentos/epicas.md`, respetando el orden de implementación y las dependencias entre historias.
- Solapamiento con capabilities ya cubiertas en `openspec/specs/` o con changes activos en `openspec/changes/`: si existe, **referencia en vez de duplicar**.
- Coherencia con las capas de `Documentos/modelo-c4.md` (Domain → Infrastructure → Application → API → Frontend) y con las reglas de negocio de `openspec/project.md`.
- Impacto en el modelo de datos y si requiere migración de EF Core.
- Ambigüedades que cambiarían el diseño: no las resuelvas en silencio, recógelas en «Preguntas Abiertas» indicando la opción por defecto que asumes.

**3. Fase de Escritura (CRÍTICO).** No respondas el contenido en el chat. Usa tu capacidad de edición de archivos para **SOBREESCRIBIR** `$ARGUMENTS` con la versión enriquecida. Si el fichero ya tiene contenido válido, consérvalo y amplíalo: nunca lo reduzcas.

---

### ESTRUCTURA A — Historia de usuario

Sigue estrictamente `Procedimiento-UserStories.md`, con el nivel de detalle de `Documentos/Historias/AI-Eng/HU-AIENG-002.md`:

- **Título**: `# HU-EP[X]-[NNN]: <nombre descriptivo>` (o `HU-AIENG-[NNN]`).
- **Formato estándar**: *Como* `[Administrador | Operador | desarrollador del proyecto]`, *quiero* `[acción]` *para* `[beneficio]`.
- **Descripción**: contexto de negocio, encaje en el flujo y en la épica; **Alcance de esta historia (sí)** / **Fuera de alcance (no)**; tabla de **Decisiones de diseño ya acordadas**; **Referencias** con enlaces relativos a `Documentos/`, `openspec/specs/` y al change asociado.
- **Criterios de Aceptación**: escenarios `### Escenario N: <nombre>` en formato **Dado que / Cuando / Entonces / Y**. Mínimo 2–3 happy path y 1–2 de error o borde (permisos, validaciones, estados inválidos). Añade un escenario final de *fuera de alcance explícito* cuando la historia sea habilitadora.
- **Notas adicionales**: actor, matices funcionales, limitaciones conocidas, change de OpenSpec por el que se implementa.
- **Tareas**: lista numerada de alto nivel, ordenada por capa, que luego se pueda descomponer en tickets.
- **Estimaciones y atributos de priorización**: puntos, impacto, urgencia, complejidad y **Riesgos y dependencias**. Deja `_Pendiente_` lo que no esté acordado — el procedimiento pide no estimar en el primer borrador.

### ESTRUCTURA B — Ticket de trabajo

Sigue `Procedimiento-TicketsTrabajo.md`, con el formato ya validado en `openspec/changes/add-ai-service-contracts-and-auth/ticket.md`:

**Título** · **Contexto y Problema** (incluye tabla de *estado actual del código* verificado en el repo) · **Componentes Afectados** · **Especificaciones Técnicas** · **Arquitectura** · **Definición de Hecho (DoD)** · **Requisitos No Funcionales** · **Preguntas Abiertas** · **Prioridad / Estimación / Tags** · **Enlaces o Referencias** (HU origen, change, procedimientos) · **Historial de Cambios**.

---

### COMPONENTES AFECTADOS (monorepo)

Lista solo los que el cambio toca realmente:

- **`backend/`** — .NET 10 / ASP.NET Core Web API / EF Core / PostgreSQL. Capas: `src/JoiabagurPV.Domain` → `.Infrastructure` → `.Application` → `.API`; tests en `src/JoiabagurPV.Tests`.
- **`frontend/`** — React 19 + TypeScript + Vite + Metronic (Layout 8). `src/{pages,components,services,hooks,providers,routing,types}`; E2E en `frontend/e2e/`.
- **`ai-service/`** — microservicio Python `jbg_ai` (FastAPI + `uv`). Frontera estrecha: **Python solo vectorial/LLM, .NET conserva la lógica de negocio**.
- **`terraform/` y `.github/workflows/`** — infraestructura AWS (EC2 + Docker + nginx, RDS, S3, ECR, SSM) y CI/CD.
- **`openspec/`** — spec de la capability y change asociado.
- **`Documentos/`** — documentación que debe actualizarse.

### ESPECIFICACIONES TÉCNICAS (incluir solo las secciones aplicables)

- **Backend**: endpoints a crear/modificar (ruta / método / rol requerido), DTOs y validación con FluentValidation, servicios de aplicación afectados, entidades y configuración EF Core, migración necesaria, índices, paginación obligatoria (máx. 50 ítems), **scoping por rol** (Admin acceso total; Operador restringido a sus POS vía `UserPointOfSale`), movimientos de inventario y campos de auditoría cuando apliquen.
- **Frontend**: páginas y módulos afectados, **componentes Metronic reutilizados** (verifica el análisis antes de proponer componentes nuevos), servicios `*.service.ts`, tipos TypeScript de los DTOs, formularios con React Hook Form + Zod, tablas con TanStack Table, estados de carga y error, formato es-ES y moneda EUR (€).
- **ai-service (`jbg-ai`)**: routers `/v1/*`, modelos Pydantic de request/response, validación del JWT interno HS256 (claims `user_id`, `role`, `pos_id`, `trace_id`; **el token manda sobre el body**), comportamiento con `STUB_MODE`, impacto en el snapshot `ai-service/openapi.json` y settings de `pydantic-settings`.
- **Datos**: entidades, campos e índices nuevos o modificados, y su reflejo en `Documentos/modelo-de-datos.md`.

### ARQUITECTURA

Decisiones previas aplicables (`openspec/changes/archive/*/design.md` y la tabla de decisiones de `Documentos/arquitectura.md`), patrones en uso (Repository, Service Layer, Dependency Injection, Strategy en `IFileStorageService`), impacto en el control de acceso por rol y punto de venta, y **breaking changes** potenciales en contratos REST del backend o en el snapshot OpenAPI de `jbg-ai`.

### DEFINICIÓN DE HECHO (DoD)

- [ ] Código implementado según las capas de `Documentos/modelo-c4.md` y las convenciones de `openspec/project.md`
- [ ] Backend: xUnit + Moq + FluentAssertions + Bogus (integración con Testcontainers/PostgreSQL), nomenclatura `Método_Escenario_ResultadoEsperado`, cobertura ≥70%
- [ ] Frontend: Vitest + React Testing Library + MSW (Playwright si el flujo es crítico), nomenclatura `should [comportamiento] when [condición]`, queries accesibles, cobertura ≥70%
- [ ] `ai-service`: `uv run pytest` en verde sin llamadas reales a LLM, embeddings ni RDS; `openapi.json` actualizado si cambia el contrato
- [ ] Migración de EF Core creada y aplicable si cambia el modelo de datos
- [ ] Spec de la capability actualizada en `openspec/changes/<change>/specs/` y `openspec validate` en verde
- [ ] Documentación actualizada en `Documentos/` según la tabla *Post-Implementation Documentation Update* de `openspec/project.md`
- [ ] Compatibilidad hacia atrás verificada (contratos REST y snapshot OpenAPI)
- [ ] Sin TODO/FIXME sin issue o tarea de seguimiento asociada
- [ ] UI en español (es-ES) y moneda EUR (€) — este proyecto **no** es multi-idioma

### REQUISITOS NO FUNCIONALES

- **Seguridad**: JWT con refresh tokens, contraseñas con BCrypt, RBAC Admin/Operador, operador limitado a sus puntos de venta asignados, HTTPS y CORS por entorno, secretos en SSM Parameter Store (`/jpv/prod/*`) y nunca en el repositorio.
- **Rendimiento y free-tier**: pool de 5–10 conexiones, paginación obligatoria (máx. 50/página), caché en memoria para datos frecuentes, bundle inicial < 500 KB, compresión de imágenes antes de subirlas.
- **Observabilidad**: logging estructurado con Serilog, `trace_id` propagado en `jbg-ai`, endpoint `/health`, CloudWatch Logs en producción.
- **Integridad de datos**: stock no negativo validado a nivel de aplicación, `Sale.Price` como snapshot (no referencia al precio vigente), atomicidad transaccional en venta/devolución/importación e idempotencia en el checkout masivo.

### PREGUNTAS ABIERTAS

Decisiones pendientes o información que requiere confirmación antes de implementar. Para cada una, indica la **opción por defecto** que se aplicará si no hay respuesta antes del apply.

---

### REGLA DE ORO

Si la petición carece de detalle técnico, infiere la solución más coherente con la arquitectura vigente a partir de `openspec/project.md`, `Documentos/arquitectura.md` y `Documentos/modelo-c4.md`. **No uses tecnologías, patrones ni dependencias que no estén documentados** en `openspec/project.md`, `openspec/config.yaml` o `Documentos/arquitectura.md`; si crees que hace falta una nueva, decláralo en «Preguntas Abiertas» en lugar de darlo por hecho. No inventes endpoints, entidades ni campos: cítalos desde `openspec/specs/`, `Documentos/modelo-de-datos.md` o el código real.

### IDIOMA

- **Historias de usuario**: íntegramente en español.
- **Tickets de trabajo**: `Procedimiento-TicketsTrabajo.md` los pide en inglés; el precedente vigente del Proyecto Final (`openspec/changes/add-ai-service-contracts-and-auth/ticket.md`) usa **título e identificadores en inglés y cuerpo en español** por coherencia con las HU. Respeta el idioma que ya tenga el fichero; si es nuevo, aplica esa regla e indícalo en la cabecera.
- **Identificadores técnicos** (endpoints, clases, campos, nombres de test, tags): siempre en inglés.

### ENTORNO

Repositorio en Windows: si necesitas ejecutar comandos, usa PowerShell (regla `.cursor/rules/use-powershell.mdc`).
