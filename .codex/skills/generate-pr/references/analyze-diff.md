# Referencia — Análisis de un chunk de diff

Módulo cargado por `generate-pr` en la Fase B. Se aplica **a un chunk cada vez**.

## Entrada

Un archivo `.pr/<rama>/chunks/NN-<dominio>.diff` y su entrada en `manifest.json`
(dominio, archivos, líneas, `truncated`).

## Procedimiento

Para el chunk en curso, extrae y anota:

1. **Qué cambió** — por archivo: funciones/clases/métodos/endpoints añadidos,
   modificados o eliminados. Cita `archivo:símbolo`. Distingue `status`:
   `A` añadido, `M` modificado, `D` eliminado, `R` renombrado.
2. **Intención** — qué problema resuelve o qué capacidad introduce. Apóyate en los
   mensajes de commit, pero la evidencia manda sobre el commit.
3. **Impacto** — qué otras partes del sistema dependen de lo que cambió
   (contrato de API, esquema de datos, comportamiento observable).
4. **Señales** que disparan otros módulos:
   - auth / permisos / DTOs / entidades de dominio / schemas de `jbg-ai` /
     `appsettings*.json` → marca el chunk para `breaking-and-risk.md`.
   - Docker / Terraform / deps / migraciones de EF Core / workflows de CI
     → marca el chunk para `deployment-impact.md`.
   - dominios de más de un componente (`backend-*` + `frontend-*` + `ai-*`)
     → marca la PR para `cross-component.md`.
5. **Ruido a descartar** — reordenado de imports, formato, espacios: menciónalo de
   forma agregada ("formateo automático en N archivos"), no archivo por archivo.

## Chunk truncado (`truncated: true`)

El `.diff` solo contiene cabeceras de hunk (`@@`), no el contenido completo.
Limita el análisis a "se modificaron N regiones de `archivo`" y dilo
explícitamente. No infieras la lógica concreta de un archivo truncado.

## Salida

Una nota de trabajo breve por dominio (no por archivo), que la Fase C consumirá.
No redactes aún el body: solo recopila hechos verificados.
