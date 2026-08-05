# Referencia — Impacto de despliegue

Módulo cargado por `generate-pr` cuando un chunk toca infra, Docker, dependencias,
configuración o migraciones. Alimenta la sección "Deployment Notes" del body.

## Qué buscar en el diff

- **Variables de entorno**: altas/bajas/renombrados en `.env.example` o en
  `os.getenv(...)` / `getenv(...)`. Marca cuáles son obligatorias y cuáles tienen
  default.
- **Dependencias**: cambios en `requirements*.txt`, `package.json`, `yarn.lock`,
  `composer.json`. Indica paquete y versión; señala saltos de versión mayor.
- **Infraestructura**: `Dockerfile`, `docker-compose*`, `buildspec*`, scripts de
  `aws-migration/`, IaC. Describe el efecto (nueva imagen base, puerto, comando).
- **Base de datos**: colecciones nuevas, índices nuevos (incluido TTL), cambios de
  esquema que requieran migración o backfill.
- **Build del plugin**: cambios en `webpack.config.js` o `build-client-zip.ps1`
  que alteren los artefactos distribuibles.

## Qué redactar

1. **Variables de entorno nuevas/modificadas** — nombre, si es obligatoria, default.
2. **Pasos post-deploy** — orden concreto y verificable (p. ej. "verificar índice
   TTL: `db.refresh_tokens.getIndexes()`").
3. **Plan de rollback** — qué revertir y qué efectos colaterales tiene (sesiones
   invalidadas, datos ya migrados que no se revierten).
4. **Orden de despliegue** — si backend y plugin deben desplegarse en cierto orden,
   dilo (ver `multi-repo.md`).

Si el diff no toca despliegue, escribe explícitamente "Sin impacto de despliegue"
en esa sección — no la dejes vacía ni inventes pasos.
