# Referencia — Estándares de redacción de PR

Módulo cargado por `generate-pr` en la Fase C. Define **cómo se escribe** el cuerpo.

## Principio: cero alucinación

Cada frase del body debe poder rastrearse a una línea de un chunk del diff.

- ✅ Analizar: archivos presentes en `manifest.json`.
- ❌ No describir: archivos que no aparecen en el diff.
- ❌ No inventar: efectos, métricas o mejoras no observables en el código.
- Si no se puede verificar → `UNKNOWN` o ítem de checklist sin marcar. Nunca asumas.

## Estilo

- **Técnico y específico**: nombres reales de archivos, funciones, clases, endpoints.
  Usa la forma `Archivo.cs:Método()`, `archivo.tsx:componente` o `archivo.py:42`.
- **Objetivo**: sin adjetivos de marketing ("potente", "robusto", "increíble").
- **Conciso**: una idea por frase; sin repetir lo que ya dice otra sección.
- **Idioma**: prosa en español; identificadores de código en su idioma original.

### Bien vs mal

❌ "Se mejoró la autenticación para hacerla más robusta y segura."
✅ "Se añadió validación del claim `exp` en
   `JoiabagurPV.Application/Services/AuthService.cs:ValidateToken()`; los
   endpoints con `[Authorize]` rechazan ahora tokens expirados con HTTP 401."

❌ "Se actualizó la documentación."
✅ "Se documentó el flujo de renovación de tokens en
   `Documentos/arquitectura.md` (sección 'Flujo de Autenticación')."

## Agrupación de cambios

Agrupa la sección "Cambios realizados" **por dominio** (los del `manifest.json`:
`backend-auth`, `backend-api`, `frontend-services`, `ai-service`, `infra`,
`openspec`, `docs`...), no por archivo suelto. Cada grupo: qué cambió y por qué,
con referencias concretas.

## Checklist

- Marca `[x]` **solo** lo verificable desde el diff (p. ej. "se añadieron tests"
  si hay archivos de test en el diff).
- Deja `[ ]` lo que exige acción humana (QA manual, revisión de seguridad, deploy).
- No inventes un resultado de test que no esté en el diff.

## Tipo de cambio

Marca las casillas de "Tipo de cambio" según evidencia: `feat` si hay capacidades
nuevas, `fix` si corrige un bug identificable, `breaking` solo si el análisis de
`breaking-and-risk.md` lo confirma, etc.
