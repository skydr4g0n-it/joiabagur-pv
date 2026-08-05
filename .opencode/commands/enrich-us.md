---
name: "Enrich: Ticket"
description: Transforma un ticket o descripción funcional en una especificación técnica completa adaptada a la arquitectura de Adresles 2.0
category: Documentation
tags: [documentation, specs, planning]
---

Actúa como Senior Engineer experto en Adresles 2.0. Tu objetivo es transformar el ticket o descripción en `$ARGUMENTS` en una especificación técnica completa y precisa, usando como fuente de verdad el `memory-bank/`.

### FLUJO DE EJECUCIÓN OBLIGATORIO:

1. **Fase de Ingesta:** Lee el archivo `$ARGUMENTS`. Luego carga el contexto necesario:
   - `memory-bank/README.md` → determina qué secciones son relevantes para esta petición
   - `memory-bank/projectbrief.md` → verifica que la petición encaje en la visión del producto
   - `memory-bank/activeContext.md` → estado actual del proyecto y posibles bloqueos
   - `memory-bank/systemPatterns.md` → patrones arquitecturales aplicables
   - `memory-bank/techContext.md` → stack, versiones y restricciones técnicas
   - `memory-bank/interfaces/api.md` → contratos de API existentes a respetar
   - `memory-bank/domains/domain-model.md` → modelo de dominio afectado

2. **Fase de Análisis:** Evalúa si el ticket es técnicamente completo ("Definition of Ready"): descripción clara, alcance bien delimitado, alineado con la arquitectura (ADR-0002: monolito modular) y coherente con los patrones de `systemPatterns.md`. Detecta también si hay solapamiento con funcionalidad existente en `openspec/specs/`.

3. **Fase de Escritura (CRÍTICO):** No respondas el contenido en el chat. Usa tu capacidad de edición de archivos para **SOBREESCRIBIR** el archivo `$ARGUMENTS` con la versión enriquecida.

### ESTRUCTURA DEL TICKET ENRIQUECIDO (salida exclusivamente en español):

Actualiza el archivo `$ARGUMENTS` siguiendo estrictamente este esquema:

- **Título**: ID y nombre descriptivo del ticket.
- **Contexto y Problema**: Por qué es necesario este cambio según el estado actual del sistema, citando archivos de `memory-bank/` relevantes y el impacto en el producto.
- **Componentes Afectados**: Lista los componentes impactados (Adresles son 3 repositorios separados):
  - `backend/` (repo `adresles-platform-2.0`) — API Python/FastAPI/MongoDB
  - `frontend/` (repo `adresles-platform-2.0`) — Frontend React/CRA
  - Plugin WooCommerce (repo `adresles-woocommerce`, en la raíz del repo) — Plugin PHP para WordPress/WooCommerce
  - `memory-bank/` — documentación que debe actualizarse
- **Especificaciones Técnicas** (incluir únicamente las secciones aplicables al ticket):
  - **Backend**: Endpoints a crear/modificar (URL/Método/Auth requerida), modelos Pydantic nuevos o modificados, servicios afectados en `backend/services/`, colecciones MongoDB involucradas, filtros multi-tenant obligatorios (`ecommerce_account_id`), audit logs si aplica.
  - **Plugin WooCommerce**: Clases PHP a modificar (Admin/Api/Checkout/Helpers/Listeners/Logger/Webhooks) en `includes/`, hooks WordPress/WooCommerce, REST endpoints, módulos JS en `assets/js/adresles/`, cambios en opciones de WordPress (`wp_options`).
- **Arquitectura**: ADRs afectados (ver `memory-bank/decisions/`), patrones de diseño aplicados (controller/service, jobs, webhooks, demonios A/B, etc.), impacto en multi-tenancy, breaking changes potenciales.
- **Definición de Hecho (DoD)**:
  - [ ] Código implementado siguiendo los patrones de `memory-bank/systemPatterns.md`
  - [ ] Tests con pytest (backend, cobertura ≥80%) o PHPUnit (plugin)
  - [ ] Documentación actualizada en `memory-bank/`
  - [ ] Sin TODO/FIXME sin issue de seguimiento asociado
  - [ ] Backward compatibility verificada (contratos de API no rotos)
  - [ ] Internacionalización incluida si aplica (en/es/fr/pt)
- **Requisitos No Funcionales**: Seguridad (autenticación/RBAC/nonces WP), rendimiento (async/caché transients 1h/TTL MongoDB), observabilidad (logging estructurado, audit_logs para acciones críticas).
- **Preguntas Abiertas**: Decisiones pendientes o información que necesita confirmación del usuario antes de implementar.

### REGLA DE ORO:

Si el ticket carece de detalles técnicos, infiere la solución más coherente con la arquitectura vigente a partir del `memory-bank/`. No uses tecnologías, patrones ni dependencias que no estén documentados en `memory-bank/techContext.md` o `memory-bank/systemPatterns.md`.
