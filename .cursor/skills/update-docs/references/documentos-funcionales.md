# Reglas por documento — `Documentos/`

Toda esta carpeta está en **español**. Los identificadores técnicos (endpoints,
clases, campos, nombres de test) van en inglés dentro del texto español.

La tabla *Post-Implementation Documentation Update* de `openspec/project.md` es
el mapeo canónico change → documentos; `config/doc-impact.json` la extiende con
los README y con las rutas de código que la disparan.

---

## Documentos que se actualizan

### `Documentos/epicas.md`

Estructura: `## Bloque 1 — MVP (EP1–EP10)` con una sección por épica, luego
`## Bloque 2 — Proyecto Final de IA (EP11–EP17)`, y al final
`## Resumen de Épicas`, `## Orden de Implementación` y `## Notas`.

Se actualiza cuando cambia el alcance de una épica, se añade o retira una HU, o
cambian dependencias y orden de implementación. Tres puntos que se olvidan:

- la **tabla de resumen** con el recuento de historias por épica;
- el **orden de implementación** si la nueva capability introduce dependencias;
- las HU del Proyecto Final usan la serie plana `HU-AIENG-[NNN]` organizada por
  change (C01–C39), **no** por épica.

### `Documentos/modelo-de-datos.md`

Estructura: Visión General · Diagrama (Mermaid ER) · Descripción de Entidades
Principales · Relaciones y Cardinalidades · Índices y Optimizaciones ·
Consideraciones de Implementación · Migración y Evolución · Optimizaciones
free-tier · Conclusión.

Se actualiza con cualquier cambio en entidades, campos, relaciones, índices o
migraciones. **Si añades una entidad, tócala en cuatro sitios**: el diagrama
Mermaid, su ficha en «Descripción de Entidades», la sección de relaciones y —
si lleva índice nuevo — la de índices. Contrasta siempre con
`backend/src/JoiabagurPV.Domain/Entities/` y la última migración de EF Core, no
con lo que diga la spec.

### `Documentos/modelo-c4.md`

Estructura: Tabla de Contenidos · Nivel 1 Contexto · Nivel 2 Contenedores ·
Nivel 3 Componentes · Notas Desarrollo vs Producción · Resumen de Componentes
por Épica · Consideraciones · Referencias.

Se actualiza cuando aparece un contenedor (p. ej. `jbg-ai`), un componente de
backend/frontend, o un punto de integración nuevo. Mantén sincronizados el
diagrama y la tabla de «Resumen de Componentes por Épica».

### `Documentos/arquitectura.md`

Estructura: Visión General · Stack Tecnológico · Arquitectura Detallada ·
Entorno de Desarrollo · Entorno de Producción · Diferencias Dev/Prod ·
Estructura del Proyecto · Flujos de Datos · Seguridad · Optimizaciones
free-tier · Monitoreo y Logging · CI/CD Pipeline.

Se actualiza con cambios de stack, versiones, patrones transversales,
infraestructura, seguridad o pipeline. Ojo: contiene **bloques de ejemplo de
variables de entorno y Dockerfile** — si cambian los reales, esos bloques
mienten.

### `Documentos/Guias/*.md`

Guías orientadas a la persona que opera el sistema (es-ES, tono de usuario):

- `deploy-aws-production.md` — guía vigente (EC2 + Terraform). Tiene índice
  propio y 8 secciones; si cambian workflows, secretos de GitHub o variables de
  runtime, esta guía es la primera afectada.
- `admin-modelo-ia.md` — administración del modelo de IA.
- `ventas-registro.md` — flujo funcional de venta.
- `aws-production-credentials.example.md` — plantilla: **nunca** metas valores
  reales.
- `deploy-aws-ec2-migration.md` y `deploy-aws-app-runner-legacy.md` — histórico
  de migración y legado deprecado: no se reescriben, como mucho se marca su
  estado.

### `Documentos/testing-backend.md` y `Documentos/testing-frontend.md`

Índices de las series `Documentos/Testing/Backend/01..09` y
`Documentos/Testing/Frontend/01..07`. Se actualizan cuando cambia el stack de
test, la nomenclatura (`Method_Scenario_ExpectedResult` /
`should [behavior] when [condition]`), el umbral de cobertura (70%) o los
workflows de CI que los ejecutan. Si el detalle vive en un fichero de la serie,
actualiza ese fichero, no el índice.

### `Documentos/Proyecto Final AIEng/`

- `joiabagur-ia-especificaciones-funcionales-v2.md` — versión vigente. **La v1
  no se toca**: es histórico.
- `proyecto-final-plan-changes-openspec.md` y su variante `-3devs.md` — plan de
  changes C01–C39. Se actualiza cuando un change se completa, se archiva, se
  parte o cambia de alcance. Si el cambio afecta al reparto entre
  desarrolladores, revisa las dos variantes.
- `proyecto-final-diseno-rag-joiabagur*.md` — diseño de referencia; se actualiza
  solo si la decisión de diseño cambia de verdad.

---

## Documentos que NO se escriben desde esta skill

| Ruta | Motivo |
|---|---|
| `Documentos/Historias/**` | Crear o enriquecer HU es trabajo del comando `enrich-us`. Aquí solo se **reporta** la HU que falta o quedó desalineada. |
| `Documentos/prompts.md` | Registro de conversaciones; lo gestiona el comando `add-prompts`. |
| `Documentos/Sesiones Master AIEng/**` | Apuntes del máster, ajenos al código. |
| `Documentos/Propuestas/**` | Análisis fechados (comparativas, Metronic, Swagger). Son fotos de un momento: no se reescriben retroactivamente. |
| `Documentos/Procedimientos/**` | Solo si cambia el procedimiento en sí, nunca como efecto colateral de un cambio de código. |

Si detectas que uno de estos debería cambiar, va al plan como **nota**, con el
responsable indicado — no como edición.
