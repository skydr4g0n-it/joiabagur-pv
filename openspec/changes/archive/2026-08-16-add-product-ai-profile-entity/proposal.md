## Why

El catálogo no tiene un solo atributo estructurado que sirva para buscar por semántica: `Product` guarda SKU, nombre, descripción, precio, colección y un booleano, y nada más. Toda la recuperación asistida diseñada para la Ola 2 —filtro por solape de materiales, filtros estructurales por tipo de pieza y talla, sustitutos por materiales coincidentes— presupone unos campos que hoy no existen en ninguna tabla del sistema.

Pero un atributo inferido por un modelo y aprobado por nadie es peor que un atributo ausente: si el sistema afirma que una pieza es de plata y es de acero, la operadora que se fía vende mal. Por eso este change no entrega solo los campos, sino **quién responde de cada uno**: confianza y origen por campo, y revisión humana obligatoria únicamente donde el error tiene consecuencias.

Además hay dos dependientes esperando. **C12** filtra su feed de indexación por estado de aprobación, y sin un predicado claro indexa propuestas sin revisar o no indexa nada. **C28** promete al README la tasa de corrección del extractor y el tiempo medio de revisión, y **no tiene turno de migración**: si este change no le reserva dónde guardar esos datos, esas métricas no se podrán calcular.

## What Changes

- **Entidad `ProductAiProfile`** en el dominio .NET, un perfil por producto, con los valores vigentes, la confianza y el origen (`rule` \| `inferred`) de cada campo, la propuesta original de la IA conservada intacta, y el estado y el origen de la revisión como dos conceptos separados.
- **Una única migración de EF Core** con las columnas `jsonb`, el índice único sobre el producto, los índices de consulta y las reglas de borrado declaradas explícitamente.
- **Política de enrutado híbrido de revisión**: los campos sensibles inferidos exigen revisión humana, los que vienen de una regla determinista no, y las etiquetas comerciales se auto-aprueban por encima de un umbral configurable.
- **Endpoint `POST /api/ai/catalog/enrich-batch`**, solo para administradores, con modo enrutado y modo masivo, tope de lote e idempotencia por hash de las entradas.
- **BREAKING** — **El contrato `POST /v1/enrich/products` se renegocia**: cada valor propuesto pasa a declarar su origen, se añaden `piece_type`, `stone_type` y `size_label`, y el `tags` plano se desglosa en etiquetas de color, estilo y ocasión. Sin el origen por campo, la revisión híbrida no es implementable. La ruta no tiene hoy ningún otro consumidor.
- **BREAKING** — **Aparece un scope de llamada sin punto de venta** para las rutas de catálogo, con dos cierres independientes —uno en el cliente .NET y otro en el servicio Python— que impiden que ese scope alcance una ruta de recuperación.
- **Nueva operación de enriquecimiento en el cliente tipado**, con familia de ruta propia: presupuesto de tiempo generoso, cortacircuitos aislado del de recuperación y sin reintento automático.
- **Almacenamiento reservado para las métricas de revisión humana** que C28 necesitará y no podrá crear por sí mismo.

**Fuera de alcance:** cualquier ruta de lectura, aprobación o métrica (C28); el feed de indexación (C12); el extractor real con su prompt y sus vocabularios cerrados (C09); las familias de producto (C07 y C18); interfaz de usuario; y cualquier escritura sobre `Product`.

## Capabilities

### New Capabilities

- `product-ai-profile`: perfil IA revisable de un producto — persistencia con procedencia por campo, política de enrutado híbrido de revisión, enriquecimiento por lotes idempotente y su superficie HTTP restringida a administradores.

### Modified Capabilities

- `ai-gateway-client`: el scope de llamada deja de exigir un punto de venta en todos los casos — aparece un scope de catálogo, con la garantía de que no puede usarse en rutas de recuperación; y el cliente gana la operación de enriquecimiento con su propia familia de resiliencia.
- `ai-service-auth`: el claim `pos_id` deja de ser obligatorio en todas las rutas `/v1` y pasa a exigirse solo en las que tienen alcance de punto de venta.
- `ai-service-api-contracts`: el contrato de enriquecimiento pasa a declarar el origen de cada valor propuesto, los tres campos sensibles que faltaban y el desglose de etiquetas.

## Impact

**Backend .NET** — entidad, enums y configuración EF nuevos; una migración; `IAiGatewayClient` gana su segunda operación; `AiCallScope` pasa a admitir punto de venta nulo; opciones nuevas de umbrales y de presupuesto de llamada; un controlador nuevo con un solo endpoint.

**`jbg-ai`** — modelos Pydantic de enriquecimiento ampliados, stub determinista coherente con ellos, dependencia de autenticación para rutas de catálogo, y **regeneración de `ai-service/openapi.json`**, que romperá `test_openapi_snapshot_is_stable` hasta actualizarlo.

**Turno de migración** — ocupa el slot único de EF Core que comparte con C07, C19, C27 y C29. No solapar.

**Compatibilidad** — ninguna ruta `/v1` existente cambia de comportamiento: recuperación, asistencia e inventario siguen exigiendo su punto de venta. No cambia ningún contrato REST del backend; el endpoint es nuevo.

**Documentación** — `Documentos/modelo-de-datos.md`, `Documentos/epicas.md`, `backend/README.md`, `ai-service/README.md`, `openspec/project.md` y el registro de revisiones del plan de changes, donde debe anotarse que la zona real de este change son seis carpetas y no las tres que su ficha declaraba.

**Sin cambios** — `frontend/`, `terraform/`.
