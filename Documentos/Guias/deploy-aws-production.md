# Guía de producción en AWS — JoiabagurPV (EC2 + Terraform)

Esta guía describe la **arquitectura actual**: una instancia **EC2** con **nginx** (TLS), contenedor **Docker** con API .NET + SPA React embebida, **RDS PostgreSQL**, **S3** solo para ficheros, **ECR**, **SSM Parameter Store** y despliegue con **GitHub Actions (OIDC)**.

**Migración desde App Runner + CloudFront + S3 frontend:** [deploy-aws-ec2-migration.md](deploy-aws-ec2-migration.md).  
**Referencia histórica App Runner / CloudFront:** [deploy-aws-app-runner-legacy.md](deploy-aws-app-runner-legacy.md).

---

## Índice

1. [Arquitectura](#1-arquitectura)
2. [Infraestructura (Terraform)](#2-infraestructura-terraform)
3. [CI/CD y secretos en GitHub](#3-cicd-y-secretos-en-github)
4. [DNS y HTTPS (nginx + Let’s Encrypt)](#4-dns-y-https-nginx--lets-encrypt)
5. [Variables de entorno en runtime](#5-variables-de-entorno-en-runtime)
6. [Operación habitual](#6-operación-habitual)
7. [Costes y backups (resumen)](#7-costes-y-backups-resumen)
8. [Troubleshooting breve](#8-troubleshooting-breve)

---

## 1. Arquitectura

```
Internet → HTTPS → EC2 (nginx :443 / :80) → localhost:8080 (Docker: API + wwwroot SPA)
                    ├── RDS PostgreSQL (solo desde VPC / SG EC2)
                    ├── S3 bucket prod-jpv-files (fotos, modelos ML)
                    ├── ECR jpv-backend (imágenes)
                    └── SSM /jpv/prod/* (cadena BD, JWT, bucket S3, etc.)
```

| Componente | Rol |
|------------|-----|
| **EC2** | nginx + Docker; único punto de entrada HTTP(S) para app y `/api/*` |
| **RDS** | PostgreSQL (p. ej. `db.t3.micro`), sin acceso público por defecto |
| **S3 `prod-jpv-files`** | Objetos de negocio (no frontend estático) |
| **ECR** | Imagen construida con `Dockerfile.bundled` (repo + frontend build) |
| **SSM** | Sustituye Secrets Manager para parámetros de aplicación |
| **GitHub OIDC** | Rol IAM sin access keys de larga duración en GitHub |

El entrenamiento ML sigue siendo **en el navegador** (TensorFlow.js); la API no ejecuta training en servidor.

---

## 2. Infraestructura (Terraform)

Código en `terraform/`.

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # si aún no existe
terraform init
terraform plan
terraform apply
```

Outputs útiles:

- `ec2_public_ip` / Elastic IP → DNS `A` para `pv.joiabagur.com`
- `ec2_instance_id` → secret `EC2_INSTANCE_ID` en GitHub
- `rds_endpoint` → migraciones / restore (túnel SSM o acceso temporal restringido)
- `github_actions_role_arn` → secret `DEPLOY_ROLE_ARN`
- `ecr_repository_url` → referencia para pull en la instancia

**Acceso temporal al RDS desde tu IP** (solo migración): variables opcionales `rds_publicly_accessible` y `rds_migration_ingress_cidrs` en `terraform.tfvars` (o regla manual en consola); **revocar** tras importar datos.

---

## 3. CI/CD y secretos en GitHub

Workflow activo: **`.github/workflows/deploy-aws-ec2.yml`** — nombre en GitHub: *Deploy to AWS EC2 (nueva arquitectura)*.

Disparadores habituales: `push` a `main` o `master` (y `workflow_dispatch` manual).

### Secrets del repositorio (Actions)

| Secret | Origen / uso |
|--------|----------------|
| `DEPLOY_ROLE_ARN` | `terraform output -raw github_actions_role_arn` |
| `EC2_INSTANCE_ID` | `terraform output -raw ec2_instance_id` (sin espacios) |
| `PRODUCTION_DOMAIN` | P. ej. `pv.joiabagur.com` (sin `https://`) |

OIDC: el workflow usa `aws-actions/configure-aws-credentials` con `role-to-assume`; **no** hace falta `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` para este deploy.

### Workflows desactivados en push (legado)

| Archivo | Estado |
|---------|--------|
| `deploy-backend-aws.yml` | **Deprecated** — solo `workflow_dispatch` (App Runner) |
| `deploy-frontend-aws.yml` | **Deprecated** — solo `workflow_dispatch` (S3 + CloudFront) |

---

## 4. DNS y HTTPS (nginx + Let’s Encrypt)

Tras el `terraform apply`, apunta el registro **A** de `pv.joiabagur.com` al Elastic IP.

En la EC2: certificados Let’s Encrypt, nginx en **443** haciendo `proxy_pass` a `http://127.0.0.1:8080` y cabeceras `X-Forwarded-*` (la API confía forwarded headers). El `user_data` de Terraform programa el cron de renovación (`/usr/local/bin/certbot`, no `certbot` a secas). Detalle, primer certificado y ejemplo de bloque nginx: sección **§9** de [deploy-aws-ec2-migration.md](deploy-aws-ec2-migration.md).

---

## 5. Variables de entorno en runtime

El contenedor obtiene configuración desde **SSM** (ruta `/jpv/prod/...`), generada por Terraform: cadena de conexión, JWT, `Aws__S3__BucketName` (`prod-jpv-files`), CORS, etc.

Tras cambiar parámetros en SSM, suele hacer falta **reiniciar** el contenedor (nuevo deploy o `docker restart` en la instancia).

---

## 6. Operación habitual

- **Desplegar nueva versión:** push a `master`/`main` o *Run workflow* en Actions sobre `deploy-aws-ec2.yml`.
- **Ver logs en servidor:** SSM Session Manager → `docker logs jpv-api` (o el nombre del contenedor que uséis).
- **Migración BD / S3:** [deploy-aws-ec2-migration.md](deploy-aws-ec2-migration.md) §5 y §6.
- **Salud:** `https://<PRODUCTION_DOMAIN>/api/health`

---

## 7. Costes y backups (resumen)

- RDS: backups automáticos (p. ej. retención 7 días) según Terraform.
- S3 versionado en bucket de ficheros según `terraform/s3.tf`.
- Estimación orientativa de la pila EC2 + RDS + S3 + SSM: tabla en [deploy-aws-ec2-migration.md](deploy-aws-ec2-migration.md) §11.

---

## 8. Troubleshooting breve

| Síntoma | Comprobación |
|---------|----------------|
| 502 en nginx | `docker ps`, logs del contenedor, puerto 8080 |
| 404 en `/` y API OK | `wwwroot/index.html` en imagen; forwarded headers / HTTPS redirect |
| Deploy Actions falla SSM | Instancia *Online* en Systems Manager; rol IAM instancia |
| 403 / errores S3 | Bucket `prod-jpv-files`, política IAM instancia, nombre en SSM |
| Certificado SSL caducado | `/var/log/cron` con `certbot: command not found` → ver §12 en [deploy-aws-ec2-migration.md](deploy-aws-ec2-migration.md) |

Más detalle: [deploy-aws-ec2-migration.md](deploy-aws-ec2-migration.md) §12.

---

## Documentos relacionados

- [deploy-aws-ec2-migration.md](deploy-aws-ec2-migration.md) — migración de cuenta, BD, S3, SSL
- [deploy-aws-app-runner-legacy.md](deploy-aws-app-runner-legacy.md) — arquitectura anterior (referencia)
- [aws-production-credentials.example.md](aws-production-credentials.example.md) — plantilla en repo; copiar a `aws-production-credentials.md` (gitignored) para notas locales
- [Documentos/arquitectura.md](../arquitectura.md) — visión de conjunto del sistema
- [Documentos/Propuestas/comparacion-aws-azure-deploy.md](../Propuestas/comparacion-aws-azure-deploy.md) — comparativa cloud (puede citar servicios genéricos)

*Última actualización: julio 2026 — arquitectura EC2 + Terraform.*
