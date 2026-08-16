## Why

El catálogo no tiene forma de saber que dos productos son la misma pieza en tallas distintas. `Product` guarda SKU, nombre, descripción, precio, colección y un booleano; la única agrupación que existe es `Collection`, que es editorial —«Verano 2024»— y por tanto responde a otra pregunta. Tres anillos con la misma foto y tallas S, M y L producen tres resultados indistinguibles en cualquier buscador, y el error de venta no se detecta hasta que el cliente vuelve.

Ese es el caso de negocio crítico del proyecto, y la recuperación semántica no lo arregla: los tres productos son legítimamente parecidos y devolverlos los tres es lo correcto. Lo que falta es que el sistema **sepa que son variantes** y pueda exigir que se confirme cuál. Las especificaciones v2 lo resolvían con `VariantGroupKey`, una cadena dentro del perfil de IA; la **decisión 2 de la revisión** la elimina porque se rompe por un guion, no la puede corregir un administrador —y si la corrige, el siguiente enriquecimiento la machaca— y, sin una entidad con identidad propia, no hay contra qué comparar para detectar productos huérfanos.

Hay tres dependientes esperando. **C12** debe emitir la familia en su feed de indexación y hoy no tiene qué emitir. **C18** implementa el flujo mixto del §7.5 —la IA propone, el administrador aprueba, la familia queda editable después— y necesita que exista lo que se aprueba; además **no tiene turno de migración**, así que si este change no le reserva dónde registrar esa aprobación, tendrá que abrir una séptima en plena Ola 3. **C30** agrupa por familia los candidatos de la venta asistida.

## What Changes

- **Entidades `ProductFamily` y `ProductFamilyMember`** en el dominio .NET: la familia con nombre y descripción, y el miembro con su producto, su etiqueta de variante y su orden dentro de la familia.
- **Una única migración de EF Core** con tres índices únicos, dos índices de cursor y las dos reglas de borrado declaradas explícitamente.
- **El invariante «un producto pertenece como máximo a una familia» garantizado por la base de datos**, no por una comprobación aplicativa: una comprobación deja la carrera abierta y un segundo miembro no produce ningún error, sino documentos incoherentes en el índice vectorial.
- **Repositorio específico** con las dos lecturas del change: familia con sus miembros ordenados, y familia de un producto.
- **Cinco endpoints**: crear familia —opcionalmente con miembros—, leerla, editar sus metadatos, **reemplazar su lista de miembros de forma declarativa**, y consultar la familia de un producto. Escritura solo para administradores.
- **Distinción explícita entre producto huérfano y producto inexistente** en la consulta por producto: el generador de C06 introduce un 15 % de huérfanos a propósito, así que es uno de cada siete productos y no un caso borde.
- **Almacenamiento reservado para el flujo asistido de C18**: origen de la familia, quién la aprobó y cuándo, los tres nulables y sin usar por este change.

**Fuera de alcance:** toda la inteligencia —propuesta de familias por similitud, detección automática de la etiqueta de variante y alerta de huérfanos (C18)—; la pantalla de revisión por lotes (C18); el feed de indexación (C12); la agrupación en la venta asistida y la confirmación de variante (C30, C36); el listado paginado y el borrado de familias; cualquier escritura sobre `Product`; y cualquier cambio en el contrato de `jbg-ai`, que ya transporta familia y variante desde C02.

## Capabilities

### New Capabilities

- `product-family`: familias de producto como entidad de negocio editable — pertenencia excluyente garantizada por la base de datos, miembros con etiqueta de variante y orden declarados de forma idempotente, y su superficie HTTP con escritura restringida a administradores y lectura abierta a cualquier usuario autenticado.

### Modified Capabilities

Ninguna. `product-management` describe `Collection`, que es el otro eje de agrupación y no cambia; `product-ai-profile` ya declara que ignora la familia a propósito; y `ai-vector-schema` ya reserva `family_id`, `family_name` y `variant_label` desde C05, sin que este change escriba en el esquema `ai`.

## Impact

**Backend .NET** — dos entidades, un enum y dos configuraciones EF nuevas; una migración; un repositorio específico; un servicio de aplicación con el reemplazo declarativo, su cortocircuito de no-operación y la detección de conflicto por doble pertenencia; un controlador nuevo con cuatro rutas y una quinta añadida a `ProductsController`.

**Turno de migración** — ocupa el slot único de EF Core que comparte con C19, C27 y C29. C08 lo liberó al mergearse. No solapar.

**Compatibilidad** — sin breaking changes. Los cinco endpoints son nuevos, `Product` no gana ninguna columna ni ninguna propiedad de navegación, ninguna spec viva se modifica y `ai-service/openapi.json` no se regenera.

**Obligaciones que quedan adjudicadas a C12** — un producto que sale de una familia pierde su fila de miembro, así que el cursor `since` no puede verlo; y renombrar una familia obliga a reindexar a todos sus miembros, porque el índice denormaliza el nombre. Ninguna de las dos se resuelve aquí: el §6.3 ya diseña el mecanismo —la invalidación que .NET empuja cuando cambia una familia— y ese mecanismo es de C12.

**Documentación** — `Documentos/modelo-de-datos.md` (las dos entidades, sus índices, sus reglas de borrado y la distinción explícita frente a `Collection`), `Documentos/epicas.md` (EP13), `openspec/project.md` (*Key Entities* y la regla de negocio nueva), `backend/README.md` (endpoints y matriz de autorización), y el registro de revisiones del plan de changes, donde debe anotarse que la zona real son cinco carpetas y no las tres que su ficha declara.

**Sin cambios** — `frontend/`, `ai-service/`, `terraform/`, `Documentos/modelo-c4.md`, cuya sección EP13 ya nombra estas dos entidades en el backend.
