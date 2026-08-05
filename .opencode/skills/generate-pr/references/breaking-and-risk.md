# Referencia — Breaking changes y revisión de riesgo

Módulo cargado por `generate-pr` cuando un chunk toca auth, contratos de API,
modelos de datos, permisos o variables de entorno. Cubre dos capacidades:
**detección de breaking changes** y **revisión de riesgo**.

## Detección de breaking changes

Un cambio es *breaking* solo si rompe un consumidor existente. Busca evidencia:

- **Contrato de API**: endpoint eliminado o renombrado; campo de
  request/response eliminado, renombrado o con tipo cambiado; parámetro
  obligatorio nuevo; código de estado distinto.
- **Modelo de datos**: campo eliminado o renombrado en `models.py` / esquema;
  cambio de tipo; índice nuevo que exige migración.
- **Configuración**: variable de entorno **nueva y obligatoria** (sin default), o
  variable renombrada/eliminada.
- **Comportamiento**: cambio en el resultado esperado de una función pública con
  el mismo input.
- **Plugin WooCommerce**: hook/filtro eliminado o con firma cambiada; cambio en
  un parámetro de shortcode o en el contrato de un endpoint AJAX/REST.

Si no hay evidencia de ruptura, **no** marques breaking change. Un campo nuevo
*opcional* o un endpoint *nuevo* no son breaking.

## Revisión de riesgo

Clasifica el riesgo del conjunto y justifícalo:

| Nivel | Señales |
|---|---|
| **Alto** | Toca `auth.py`, `database.py`, `server.py`, `models.py`; breaking change confirmado; migración de datos. |
| **Medio** | Lógica de negocio nueva en services/controllers; cambio en flujo de checkout; dependencia nueva. |
| **Bajo** | Docs, tests, formateo, cambios aislados sin efecto en contratos. |

Revisa además, si el diff lo evidencia:

- **Seguridad**: manejo de secrets, validación/sanitización de inputs, cambios en
  RBAC/permisos, escape de salida (XSS), nonces de WordPress.
- **Multi-tenancy** (backend): toda query a recursos de ecommerce debe filtrar por
  `ecommerce_account_id`. Señala si un cambio lo omite.
- **Performance**: queries nuevas a BD, posible N+1, llamadas a APIs externas sin
  timeout, procesamiento síncrono pesado.
- **Deuda técnica**: `TODO`/`FIXME` introducidos, atajos, falta de tests.

## Salida

Para la Fase C: lista de breaking changes (o "ninguno"), nivel de riesgo con
justificación, y los puntos concretos a destacar en "Notas para reviewers".
