# Referencia — Resumen de commits

Módulo cargado por `generate-pr` al inicio de la Fase B.

## Entrada

El array `commits` de `manifest.json` (`hash`, `subject`).

## Procedimiento

1. Lee los `subject` de todos los commits de la rama.
2. Agrúpalos por intención (feature, fix, refactor, docs...), no los transcribas
   uno a uno.
3. Úsalos como **hipótesis de intención**, que luego confirmas o corriges con la
   evidencia del diff en la Fase B. Si un commit dice una cosa y el diff muestra
   otra, **manda el diff**.
4. Detecta referencias a issues (`#123`, `closes #45`) y consérvalas para la
   sección "Motivación y contexto" del body.

## Salida

- Una o dos frases de intención global del conjunto de commits.
- Lista de issues referenciados (si los hay).

No incluyas el historial de commits crudo en el body de la PR: GitHub ya lo
muestra. El body explica el *qué* y el *porqué*, no el log.
