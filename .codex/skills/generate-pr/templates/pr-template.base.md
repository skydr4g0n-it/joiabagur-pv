<!--
  PLANTILLA de cuerpo de PR de joiabagur-pv, usada por la skill `generate-pr`.
  Rellena cada sección con evidencia del diff; borra los comentarios al redactar.
  No dejes secciones vacías: si una no aplica, escríbelo ("Sin impacto de
  despliegue", "Ninguno").
-->

## 📋 Descripción

<!-- 2-3 párrafos: qué cambia y por qué. Técnico, sin marketing. -->

### Tipo de cambio

<!-- Marca [x] solo lo que el diff respalde. -->
- [ ] ✨ feat — funcionalidad nueva
- [ ] 🐛 fix — corrección de bug
- [ ] ♻️ refactor — reestructuración sin cambio de comportamiento
- [ ] ⚡ perf — mejora de rendimiento
- [ ] 📝 docs — documentación
- [ ] 🧪 test — tests
- [ ] 🔧 chore / ci / build
- [ ] 💥 breaking change — rompe compatibilidad

---

## 🎯 Motivación y contexto

<!-- Problema técnico concreto. Change de OpenSpec asociado
     (openspec/changes/<slug>/) y HU de Documentos/Historias/ si existen.
     Issue relacionado (#NN) si aparece en commits. -->

---

## 🔄 Cambios realizados

<!-- Agrupa POR DOMINIO (los del manifest.json: backend-api, frontend-services,
     ai-service, infra, openspec, docs...), no por archivo suelto.
     Cita archivo:símbolo real. -->

---

## 🧪 Testing

<!-- Tests presentes en el diff. Lo no verificable se deja sin marcar.
     Backend: xUnit (Método_Escenario_ResultadoEsperado).
     Frontend: Vitest / RTL (should [comportamiento] when [condición]), Playwright.
     ai-service: pytest. -->

---

## ✅ Checklist pre-merge

- [ ] El código sigue las convenciones de `openspec/project.md` y las capas de `Documentos/modelo-c4.md`
- [ ] Hay tests para el código nuevo (backend ≥70%, frontend ≥70%)
- [ ] Migración de EF Core incluida si cambia el modelo de datos
- [ ] `ai-service/openapi.json` actualizado si cambia el contrato de `jbg-ai`
- [ ] Spec de la capability actualizada en `openspec/` y `openspec validate` en verde
- [ ] Documentación de `Documentos/` actualizada según la tabla de `openspec/project.md`
- [ ] Sin secrets ni credenciales en el diff (van a SSM `/jpv/prod/*`)
- [ ] Revisado el impacto en otros componentes del monorepo

---

## 🚀 Deployment notes

<!-- Variables de entorno, dependencias, pasos post-deploy, rollback.
     Si no hay impacto: "Sin impacto de despliegue". -->

---

## 📝 Notas adicionales

<!-- Breaking changes, decisiones de diseño, deuda técnica, limitaciones
     conocidas y puntos de atención para reviewers. -->
