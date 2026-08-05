<!--
  PLANTILLA BASE de cuerpo de PR (fallback).
  La usa la skill `generate-pr` cuando no hay plantilla especializada del repo
  (`pr-template.repo.md`). Rellena cada sección con evidencia del diff; borra los
  comentarios <!-- ... --> al redactar. No dejes secciones vacías: si una no aplica,
  escríbelo ("Sin impacto de despliegue", "Ninguno").
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

<!-- Problema técnico concreto. Issue relacionado (#NN) si aparece en commits. -->

---

## 🔄 Cambios realizados

<!-- Agrupa POR DOMINIO (los del manifest.json), no por archivo suelto.
     Cita archivo:símbolo real. -->

---

## 🧪 Testing

<!-- Tests presentes en el diff. Lo no verificable se deja sin marcar. -->

---

## ✅ Checklist pre-merge

- [ ] El código sigue las convenciones del repo
- [ ] Hay tests para el código nuevo
- [ ] La documentación está actualizada
- [ ] Sin secrets ni credenciales en el diff
- [ ] Revisado el impacto en otros módulos

---

## 🚀 Deployment notes

<!-- Variables de entorno, dependencias, pasos post-deploy, rollback.
     Si no hay impacto: "Sin impacto de despliegue". -->

---

## 📝 Notas adicionales

<!-- Breaking changes, decisiones de diseño, deuda técnica, limitaciones
     conocidas y puntos de atención para reviewers. -->
