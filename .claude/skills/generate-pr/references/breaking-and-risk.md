# Referencia — Breaking changes y revisión de riesgo

Módulo cargado por `generate-pr` cuando un chunk toca auth, contratos de API,
modelos de datos, permisos o variables de entorno. Cubre dos capacidades:
**detección de breaking changes** y **revisión de riesgo**.

## Detección de breaking changes

Un cambio es *breaking* solo si rompe un consumidor existente. Busca evidencia:

- **Contrato de API (.NET)**: endpoint eliminado o renombrado en
  `JoiabagurPV.API/Controllers/**`; propiedad de un DTO
  (`JoiabagurPV.Application/DTOs/**`) eliminada, renombrada o con tipo cambiado;
  parámetro obligatorio nuevo; código de estado distinto. El consumidor es el
  frontend (`frontend/src/services/**` + `frontend/src/types/**`).
- **Contrato de `jbg-ai`**: cambio en los schemas Pydantic de `/v1/*` o en los
  claims del JWT interno (`user_id`, `role`, `pos_id`, `trace_id`). Si
  `ai-service/openapi.json` no se actualiza en el mismo diff, el test de snapshot
  falla — es breaking de facto.
- **Modelo de datos**: propiedad eliminada o renombrada en
  `JoiabagurPV.Domain/Entities/**`, cambio de tipo, o migración de EF Core que
  exige backfill o no es reversible.
- **Configuración**: variable de entorno o clave de `appsettings*.json` **nueva y
  obligatoria** (sin default), renombrada o eliminada; parámetro nuevo en SSM
  (`/jpv/prod/*`).
- **Comportamiento**: cambio en el resultado esperado de un método público con el
  mismo input; cambio en una regla de negocio documentada en
  `openspec/project.md` (validación de stock, snapshot de precio, ventana de
  devolución, atomicidad del checkout masivo).

Si no hay evidencia de ruptura, **no** marques breaking change. Un campo nuevo
*opcional* o un endpoint *nuevo* no son breaking.

## Revisión de riesgo

Clasifica el riesgo del conjunto y justifícalo:

| Nivel | Señales |
|---|---|
| **Alto** | Toca autenticación/JWT, `JoiabagurPVDbContext`, entidades de dominio, `Program.cs`, migraciones de EF Core, `terraform/`, `ai-service/openapi.json`; breaking change confirmado; migración de datos. |
| **Medio** | Lógica de negocio nueva en `JoiabagurPV.Application/Services/**`; cambios en el flujo de venta, carrito/checkout masivo o devoluciones; dependencia nueva; cambios en inferencia de imagen (embeddings/umbrales). |
| **Bajo** | Docs, tests, formateo, cambios aislados sin efecto en contratos. |

Revisa además, si el diff lo evidencia:

- **Seguridad**: manejo de secretos (nunca en el repo; van a SSM), validación de
  entrada con FluentValidation / Zod, cambios en RBAC y en los atributos
  `[Authorize]`, hashing BCrypt, configuración de CORS.
- **Control de acceso por punto de venta**: un Operador solo puede ver y operar
  sobre sus POS asignados (`UserPointOfSale`). Toda consulta de inventario,
  ventas o devoluciones debe filtrar por el POS del usuario. En `jbg-ai`, el
  `pos_id` del token manda sobre el body. **Señala si un cambio lo omite.**
- **Integridad de datos**: stock que pueda quedar negativo, precio de venta que
  deje de ser snapshot, pérdida de atomicidad en venta/devolución/importación,
  idempotencia del checkout masivo.
- **Performance y free-tier**: queries nuevas sin índice, posible N+1 en EF Core,
  listados sin paginación (máx. 50/página), llamadas externas sin timeout,
  crecimiento del bundle del frontend (< 500 KB inicial).
- **Deuda técnica**: `TODO`/`FIXME` introducidos, atajos, falta de tests.

## Salida

Para la Fase C: lista de breaking changes (o "ninguno"), nivel de riesgo con
justificación, y los puntos concretos a destacar en "Notas para reviewers".
