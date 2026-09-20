## Why

El asistente de venta necesita herramientas antes que decisiones. C32 se partió el 2026-09-20 por la regla 5 del §1 del plan de changes, y ésta es la mitad que **no llama a ningún proveedor**: las seis tools, su registro y sus invariantes. El bucle, los presupuestos y la ruta son C32b.

Partirlo así no es sólo cuestión de tamaño. El §15.8 del diseño declara al mundo que **ningún agente escribe**, y ésa es una de las tres afirmaciones que el README entrega: o se demuestra o no se declara. Un registro sin bucle es exactamente la pieza donde esa garantía se puede comprobar de forma estructural, sin que un modelo intervenga en el resultado.

Y hay una deuda concreta que vence aquí. De las seis tools que la ficha enumeraba, **cinco están servidas por código ya probado y una no tenía servicio detrás**: `consultar_disponibilidad`. El §6.1 del diseño dejaba el esquema de la llamada de vuelta Python → .NET como *«decisión abierta del change del agente de venta»*, y este change es ese change.

## What Changes

- **Seis herramientas de solo lectura**, con nombre, descripción en castellano orientada al modelo, esquema de parámetros tipado y **validación de argumentos antes de ejecutar**: `buscar_catalogo`, `buscar_sustitutos`, `listar_familia`, `consultar_conocimiento`, `consultar_disponibilidad` y `pedir_aclaracion`.
- **Un registro** con el conjunto de nombres **congelado**, resolución por nombre y exportación del esquema de *function calling* de cada herramienta.
- **Los errores viajan como observaciones**, nunca como excepción que escape, con causa de vocabulario cerrado. Una excepción mataría el bucle de C32b en vez de gastarle una vuelta; un `"error"` genérico dejaría ciego al modelo.
- **`consultar_disponibilidad` servida desde `ai.pos_projection`**, con **etiqueta cualitativa sin dígitos**, declaración de la antigüedad de la proyección y un valor propio para «sin ámbito de lectura», distinto de «sin existencias». El endpoint .NET puntual y su esquema de autenticación de vuelta quedan **identificados, acotados y no hechos**.
- **Direccionamiento por `sku` y nunca por identificador interno**, lo que añade **dos lecturas** a `ProductSearchPort`: una pieza por SKU y la disponibilidad de una pieza en un punto de venta.
- **El invariante de solo-lectura comprobado por introspección** del registro construido, no mediante una bandera declarativa en el descriptor.
- **No hay bucle, no hay ruta y no hay contrato nuevo.** `ai-service/openapi.json` queda byte a byte igual y el comportamiento de `POST /v1/assist/sale` es idéntico al que dejó C31.

No es *breaking*: no se retira ni se modifica ningún comportamiento publicado. Las dos lecturas nuevas son adiciones a un `Protocol`, lo que obliga a actualizar los dobles de la suite pero no a ningún consumidor del servicio.

## Capabilities

### New Capabilities

- `sales-assistant-tools`: el catálogo de herramientas de solo lectura del asistente de venta — su registro congelado, la forma de sus argumentos y de sus observaciones, el tratamiento de los fallos como datos, el vocabulario cerrado de disponibilidad y el invariante de que ninguna herramienta escribe.

### Modified Capabilities

Ninguna. Las herramientas **consumen** `vector-retrieval`, `substitutes-retrieval`, `knowledge-corpus`, `pos-projection`, `product-family` y `assist-generation` sin cambiar ningún requisito suyo, y el precedente de C30a confirma el reparto: cuando aquel change añadió `family_roster()` al puerto de búsqueda, el requisito se escribió en la capability **consumidora** y no en la del puerto.

## Impact

- **`ai-service/src/jbg_ai/assist/`** — `tools.py` nuevo; `constants.py` ampliado con los dos vocabularios cerrados (etiquetas de disponibilidad y causas de fallo).
- **`ai-service/src/jbg_ai/retrieval/`** — `ports.py` y `search.py`: dos lecturas nuevas, ninguna modificación de las existentes.
- **`ai-service/tests/`** — suite nueva en `tests/assist/`, más la actualización de los dobles de `ProductSearchPort` que la ampliación del `Protocol` obliga.
- **Sin impacto** en `backend/`, `frontend/`, `terraform/`, `.github/workflows/`, `alembic/` ni `ai-service/openapi.json`. **Sin migración de EF Core** y sin cambios en el modelo de datos de `Documentos/modelo-de-datos.md`: las dos lecturas nuevas van contra tablas que ya existen en el esquema `ai`.
- **Sin variables de entorno ni ajustes nuevos**, y sin credencial de ningún proveedor: esta mitad no llama a ningún modelo de chat.
- **Aguas abajo**: desbloquea **C32b** y, a través de él, **C38** y **C39**.
