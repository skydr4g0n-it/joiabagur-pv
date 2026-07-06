# Guía de Migración a Nueva Cuenta AWS — Arquitectura EC2

## Decisiones de naming (coherentes con producción actual)

| Recurso | Cuenta antigua (App Runner / legado) | Cuenta nueva (EC2 + Terraform) |
|---------|--------------------------------------|----------------------------------|
| **Bucket de ficheros** | `jpv-files-prod` | **`prod-jpv-files`** (nombre global único en S3; evita conflicto con el bucket ya existente en la cuenta antigua) |
| **PostgreSQL** | Base `jpv`, usuario `postgres` | **Misma convención:** base **`jpv`**, usuario **`postgres`** — el `pg_dump` y el `psql` usan los mismos nombres en origen y destino |

La cadena de conexión en SSM (`ConnectionStrings__DefaultConnection`) la genera Terraform con `Database=jpv` y `Username=postgres`.

> **Si ya ejecutaste `terraform apply` en la nueva cuenta** con la plantilla anterior (`joiabagur_admin` / `joiabagur_prod`), cambiar usuario o nombre de base en Terraform suele **forzar recreación del recurso RDS**. Revisa `terraform plan` y haz copia de seguridad antes de aplicar.

---

## Índice

1. [Arquitectura nueva](#1-arquitectura-nueva)
2. [Prerrequisitos](#2-prerrequisitos)
3. [Paso 1 — Preparar nueva cuenta AWS](#3-paso-1--preparar-nueva-cuenta-aws)
4. [Paso 2 — Desplegar infraestructura con Terraform](#4-paso-2--desplegar-infraestructura-con-terraform)
5. [Paso 3 — Migrar la base de datos](#5-paso-3--migrar-la-base-de-datos)
6. [Paso 4 — Migrar ficheros S3](#6-paso-4--migrar-ficheros-s3)
7. [Paso 5 — Configurar GitHub Actions](#7-paso-5--configurar-github-actions)
8. [Paso 6 — Primer despliegue](#8-paso-6--primer-despliegue)
9. [Paso 7 — Configurar SSL y cambiar DNS](#9-paso-7--configurar-ssl-y-cambiar-dns)
10. [Paso 8 — Verificación y cierre del entorno antiguo](#10-paso-8--verificación-y-cierre-del-entorno-antiguo)
11. [Costes estimados](#11-costes-estimados)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Arquitectura nueva

```
Internet
    │ HTTPS
    ▼
EC2 t3.micro — nginx (SSL/TLS + Let's Encrypt)
    │
    └── Docker: .NET 10 API + React SPA (puerto 8080)
         │
         ├── RDS PostgreSQL db.t3.micro (acceso solo desde EC2)
         ├── S3 prod-jpv-files (fotos + modelos ML)
         ├── ECR jpv-backend (imágenes Docker)
         └── SSM Parameter Store /jpv/prod/* (credenciales)
```

**Mejoras incorporadas respecto a la arquitectura anterior:**

| Mejora | Detalle |
|--------|---------|
| Sin credenciales en GitHub | OIDC federation: GitHub Actions asume IAM Role directamente |
| SSM Parameter Store | Sustituye Secrets Manager (~$1.50/mes de ahorro) |
| Frontend bundled | React SPA incluida en imagen Docker — elimina CloudFront + S3-frontend |

---

## 2. Prerrequisitos

- AWS CLI v2 configurado con credenciales de la **nueva cuenta**
- Terraform >= 1.5 instalado
- Docker instalado localmente
- Acceso al repositorio de GitHub para actualizar Secrets

---

## 3. Paso 1 — Preparar nueva cuenta AWS

### 3.1 Crear usuario IAM para Terraform (solo para el apply inicial)

```bash
# Crear usuario solo para terraform apply
aws iam create-user --user-name jpv-terraform-admin

aws iam attach-user-policy \
  --user-name jpv-terraform-admin \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess

aws iam create-access-key --user-name jpv-terraform-admin
# Guardar las credenciales — se eliminarán tras el terraform apply
```

### 3.2 Crear bucket S3 para estado de Terraform (prerequisito de terraform init)

```bash
aws s3api create-bucket \
  --bucket jpv-terraform-state \
  --region eu-west-3 \
  --create-bucket-configuration LocationConstraint=eu-west-3

aws s3api put-bucket-versioning \
  --bucket jpv-terraform-state \
  --versioning-configuration Status=Enabled

aws s3api put-public-access-block \
  --bucket jpv-terraform-state \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

---

## 4. Paso 2 — Desplegar infraestructura con Terraform

### 4.1 Crear fichero de variables

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
# Editar terraform.tfvars con los valores reales
```

Obtener el AMI más reciente de Amazon Linux 2023:

```bash
aws ec2 describe-images \
  --owners amazon \
  --filters "Name=name,Values=al2023-ami-*-x86_64" \
  --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
  --output text \
  --region eu-west-3
```

### 4.2 Aplicar Terraform

```bash
terraform init
terraform plan   # Revisar los recursos que se crearán
terraform apply
```

El apply crea: EC2, Elastic IP, RDS, S3, ECR, SSM parameters, IAM roles (con OIDC).

### 4.3 Anotar los outputs

```bash
terraform output
# ec2_public_ip          → para actualizar DNS
# rds_endpoint           → para importar datos
# ecr_repository_url     → para GitHub Actions
# github_actions_role_arn → para GitHub Actions
# ec2_instance_id        → para GitHub Actions
```

---

## 5. Paso 3 — Migrar la base de datos

RDS en la nueva cuenta no es accesible públicamente. Se usa SSM port forwarding para tunelizar la conexión desde el equipo local.

### 5.1 Exportar la base de datos actual (cuenta antigua)

La instancia legada usa la base **`jpv`** y el usuario **`postgres`** (misma convención que la nueva RDS).

```bash
# Obtener endpoint RDS antiguo
OLD_RDS=$(aws rds describe-db-instances \
  --db-instance-identifier jpv-db-prod \
  --query 'DBInstances[0].Endpoint.Address' \
  --output text \
  --profile cuenta-antigua)

PGPASSWORD=TU_PASSWORD_ANTIGUA pg_dump \
  -h $OLD_RDS -U postgres -d jpv \
  --no-owner --no-acl \
  -f backup_prod.sql

echo "Backup: $(wc -l backup_prod.sql) líneas"
```

### 5.2 Abrir túnel SSM al nuevo RDS (desde el equipo local)

En una terminal aparte:

```bash
# Obtener EC2 instance ID e RDS endpoint de los outputs de terraform
EC2_ID=$(cd terraform && terraform output -raw ec2_instance_id)
NEW_RDS=$(cd terraform && terraform output -raw rds_endpoint)

aws ssm start-session \
  --target $EC2_ID \
  --document-name AWS-StartPortForwardingSessionToRemoteHost \
  --parameters "{\"host\":[\"$NEW_RDS\"],\"portNumber\":[\"5432\"],\"localPortNumber\":[\"5432\"]}"
# Dejar esta terminal abierta durante la importación
```

### 5.3 Importar datos al nuevo RDS (a través del túnel)

En otra terminal:

```bash
# Con el túnel activo, localhost:5432 apunta al nuevo RDS
# TU_PASSWORD_NUEVA = db_password en terraform.tfvars
PGPASSWORD=TU_PASSWORD_NUEVA psql \
  -h localhost -p 5432 \
  -U postgres -d jpv \
  -f backup_prod.sql

echo "Importación completada."
```

---

## 6. Paso 4 — Migrar ficheros S3

Origen (**cuenta antigua**): bucket `jpv-files-prod`. Destino (**cuenta nueva**): bucket **`prod-jpv-files`** creado por Terraform. Los nombres son distintos a propósito: los nombres de bucket S3 son únicos a nivel global y el nombre antiguo ya está ocupado por la cuenta legada.

### 6.1 Sincronizar los ficheros (recomendado: disco local)

No hace falta política en el bucket antiguo: primero descargás con credenciales de la **cuenta antigua** y subís con la **nueva** (perfil por defecto o `--profile cuenta-nueva`).

```bash
mkdir -p s3-migrate-tmp
aws s3 sync s3://jpv-files-prod s3-migrate-tmp --profile cuenta-antigua --region eu-west-3 --no-progress
aws s3 sync s3-migrate-tmp s3://prod-jpv-files --profile cuenta-nueva --region eu-west-3 --no-progress
rm -rf s3-migrate-tmp

echo "Sync completado."
```

### 6.2 Opcional — política cross-account en el bucket origen

Solo si necesitás que un principal de la **nueva** cuenta lea `jpv-files-prod` **sin** usar el perfil de la cuenta antigua (p. ej. copia directa entre buckets con un rol concreto). Si usaste el flujo de 6.1, podés omitir este paso.

```bash
# Obtener Account ID de la nueva cuenta
NEW_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# En la cuenta antigua — añadir política temporal al bucket
aws s3api put-bucket-policy \
  --bucket jpv-files-prod \
  --profile cuenta-antigua \
  --policy "{
    \"Version\": \"2012-10-17\",
    \"Statement\": [{
      \"Effect\": \"Allow\",
      \"Principal\": { \"AWS\": \"arn:aws:iam::$NEW_ACCOUNT_ID:root\" },
      \"Action\": [\"s3:GetObject\", \"s3:ListBucket\"],
      \"Resource\": [
        \"arn:aws:s3:::jpv-files-prod\",
        \"arn:aws:s3:::jpv-files-prod/*\"
      ]
    }]
  }"
```

Tras usarla, eliminá la política:

### 6.3 Eliminar la política temporal (cuenta antigua), si aplicó 6.2

```bash
aws s3api delete-bucket-policy \
  --bucket jpv-files-prod \
  --profile cuenta-antigua
```

---

## 7. Paso 5 — Configurar GitHub Actions

### 7.1 Actualizar GitHub Secrets del repositorio

Ir a **Settings → Secrets and variables → Actions** y crear/actualizar:

| Secret | Valor (de terraform output) |
|--------|-----------------------------|
| `DEPLOY_ROLE_ARN` | `terraform output -raw github_actions_role_arn` |
| `EC2_INSTANCE_ID` | `terraform output -raw ec2_instance_id` |
| `PRODUCTION_DOMAIN` | `pv.joiabagur.com` |

> Los secrets `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` **no se necesitan** para el workflow EC2 (OIDC). Los workflows **App Runner** y **S3/CloudFront** están **deprecated** y ya **no se ejecutan en push** (solo ejecución manual si hiciera falta en la cuenta legada).

### 7.2 Workflows en el repositorio

| Workflow | Uso |
|----------|-----|
| **Deploy to AWS EC2 (nueva arquitectura)** (`deploy-aws-ec2.yml`) | **Producción** — push a `main`/`master` o manual |
| `deploy-backend-aws.yml` / `deploy-frontend-aws.yml` | **Deprecated** — solo `workflow_dispatch` |

---

## 8. Paso 6 — Primer despliegue

Tras configurar secrets, el despliegue puede ejecutarse **automáticamente** en cada push a `main`/`master`. También puedes lanzarlo a mano:

```
GitHub → Actions → "Deploy to AWS EC2 (nueva arquitectura)" → Run workflow
```

O desde la CLI:

```bash
gh workflow run deploy-aws-ec2.yml
```

Verificar que el contenedor está corriendo:

```bash
# Via SSM
aws ssm start-session --target $EC2_ID

# Dentro de la sesión SSM:
docker ps
docker logs jpv-api --tail 50
```

---

## 9. Paso 7 — Configurar SSL y cambiar DNS

### 9.1 Obtener el Elastic IP

```bash
EC2_IP=$(cd terraform && terraform output -raw ec2_public_ip)
echo "Elastic IP: $EC2_IP"
```

### 9.2 Actualizar el registro DNS

En el proveedor DNS actual, cambiar el registro A de `pv.joiabagur.com` de la IP antigua a `$EC2_IP`. Esperar propagación (entre 5 min y 1 hora dependiendo del TTL).

Verificar propagación:

```bash
dig pv.joiabagur.com +short
# Debe mostrar el Elastic IP nuevo
```

### 9.3 Certificado Let's Encrypt y renovación automática

Los certificados obtenidos con `certbot certonly --manual` **no se renuevan solos**: hace falta repetir el TXT a mano o usar otra autenticación. Para que `certbot renew` funcione sin intervención, usa **una** de estas dos vías.

#### Opción A (recomendada tras el corte DNS): HTTP-01 con nginx

Cuando el registro **A** de `pv.joiabagur.com` apunte ya al **Elastic IP del EC2** (puerto 80 accesible como ahora):

```bash
# SSM en la instancia
sudo certbot certonly --nginx -d pv.joiabagur.com --force-renewal
```

Eso **sustituye** el certificado “manual” por uno renovable. Luego certbot guarda en `/etc/letsencrypt/renewal/` la configuración adecuada.

Comprueba la renovación simulada:

```bash
sudo /usr/local/bin/certbot renew --dry-run
```

#### Cron de renovación automática

Certbot se instala con **pip** en `user_data` → el binario queda en `/usr/local/bin/certbot`. **No** uses `certbot` a secas en cron: el PATH de cron es mínimo y el job falla con `certbot: command not found` (el certificado caduca sin renovarse).

Las instancias nuevas creadas por Terraform ya incluyen `/etc/cron.d/certbot-jpv` con la ruta absoluta. En una instancia **ya existente** (p. ej. tras la migración), créalo o corrígelo a mano:

```bash
echo '0 3,15 * * * root /usr/local/bin/certbot renew -q --deploy-hook "systemctl reload nginx" >> /var/log/certbot-cron.log 2>&1' | sudo tee /etc/cron.d/certbot-jpv
sudo chmod 644 /etc/cron.d/certbot-jpv
sudo /usr/local/bin/certbot renew --dry-run
```

Comprueba en `/var/log/cron` o `/var/log/certbot-cron.log` que no aparece `command not found`.

#### Opción B (renovación automática sin esperar al corte DNS): plugin DNS OVH

Si el **A** sigue apuntando al sistema antiguo pero quieres certificado en el EC2 nuevo **renovable por API** (sin TXT manual cada 90 días):

1. En OVH, crea credenciales de **API** con permisos sobre la zona DNS del dominio ([documentación API OVH](https://help.ovhcloud.com/csm/es-es-api-getting-started-ovhcloud-api?id=kb_article_view&sysparm_article=KB0042789)).
2. En el EC2 (SSM):

```bash
sudo pip3 install certbot-dns-ovh
sudo mkdir -p /root/.secrets
sudo nano /root/.secrets/certbot-ovh.ini   # o vi
```

Contenido del fichero (valores reales de OVH):

```ini
dns_ovh_endpoint = ovh-eu
dns_ovh_application_key = TU_APPLICATION_KEY
dns_ovh_application_secret = TU_APPLICATION_SECRET
dns_ovh_consumer_key = TU_CONSUMER_KEY
```

```bash
sudo chmod 600 /root/.secrets/certbot-ovh.ini
sudo certbot certonly \
  --authenticator dns-ovh \
  --dns-ovh-credentials /root/.secrets/certbot-ovh.ini \
  -d pv.joiabagur.com \
  --cert-name pv.joiabagur.com \
  --force-renewal
```

3. Mismo **cron** de renovación que en la opción A (`certbot renew` usará el plugin según `/etc/letsencrypt/renewal/pv.joiabagur.com.conf`).

> **Seguridad:** el `.ini` con claves OVH es sensible; no lo copies al repositorio. Opcional: mover secretos a SSM y generar el `.ini` en un hook (más trabajo).

#### Antes del corte: certificado solo con TXT manual

Si aún usas `certbot certonly --manual --preferred-challenges dns`, ejecuta certbot con **`sudo`**. Tras obtener el cert, configura nginx (siguiente apartado) y **migra a la opción A o B** cuanto antes para no depender de renovación manual cada 90 días.

### 9.4 nginx con HTTPS (certificados ya en `/etc/letsencrypt/live/`)

Si certbot **no** modificó nginx (p. ej. solo `certonly`), añade un `server` en **443** que reutilice el mismo `proxy_pass` que en el bloque `:80`, y opcionalmente redirige HTTP → HTTPS. Ejemplo mínimo (ajusta `server_name` si difiere):

```nginx
# /etc/nginx/conf.d/jpv.conf — ejemplo: mantener el server :80 y añadir uno :443 + redirect
server {
    listen 80;
    server_name pv.joiabagur.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name pv.joiabagur.com;

    ssl_certificate     /etc/letsencrypt/live/pv.joiabagur.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pv.joiabagur.com/privkey.pem;

    location / {
        proxy_pass         http://localhost:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        client_max_body_size 50M;
        proxy_read_timeout   120s;
    }
}
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Hasta que no quieras forzar HTTPS para todos, puedes dejar **solo** el `server` en 443 y mantener el :80 actual sin redirección (útil mientras pruebas por IP).

---

## 10. Paso 8 — Verificación y cierre del entorno antiguo

### 10.1 Checklist de verificación

```bash
# Health check
curl -sf https://pv.joiabagur.com/api/health | jq .

# Frontend carga correctamente
curl -sf -o /dev/null -w "%{http_code}" https://pv.joiabagur.com
# Debe retornar 200
```

Pruebas funcionales:
- [ ] Login con usuario admin
- [ ] Listar productos y fotos
- [ ] Subir una foto de producto
- [ ] Inventario por punto de venta
- [ ] Acceso desde móvil

### 10.2 Apagar entorno antiguo

Solo después de confirmar que todo funciona correctamente en la nueva cuenta:

```bash
# Con credenciales de la cuenta ANTIGUA
# Pausar App Runner (no eliminar — por si acaso)
aws apprunner pause-service \
  --service-arn $APP_RUNNER_SERVICE_ARN \
  --profile cuenta-antigua

# Tras unos días de margen, eliminar recursos:
# - App Runner service
# - S3 frontend bucket (jpv-frontend-prod)
# - CloudFront distribution
# - ECR repository (antigua cuenta)
# Conservar: RDS (hasta confirmar backup migrado), usuario IAM antigua
```

---

## 11. Costes estimados (nueva arquitectura, post free tier)

| Servicio | €/mes |
|----------|-------|
| EC2 t3.micro + EBS 20GB | ~9–10 |
| RDS PostgreSQL db.t3.micro | ~15–18 |
| S3 prod-jpv-files | ~0.5–2 |
| ECR jpv-backend | ~0 |
| SSM Parameter Store (7 params) | ~0.35 |
| Data transfer | ~1–3 |
| **Total** | **~26–33 €/mes** |

> Durante los primeros 12 meses de la nueva cuenta, EC2 t3.micro y RDS db.t3.micro son free tier: **~1–3 €/mes** (solo S3 + SSM + data transfer).

---

## 12. Troubleshooting

### Contenedor no arranca

```bash
# Via SSM
aws ssm start-session --target $EC2_ID
docker logs jpv-api
# Error común: SSM parameter no encontrado → verificar /jpv/prod/* en AWS Console
```

### Error en SSM send-command

```bash
# Ver output del comando
aws ssm get-command-invocation \
  --command-id $COMMAND_ID \
  --instance-id $EC2_INSTANCE_ID \
  --query 'StandardErrorContent' \
  --output text
```

### nginx devuelve 502 Bad Gateway

El contenedor no está corriendo en el puerto 8080:

```bash
# Via SSM
docker ps -a
docker start jpv-api  # Si está parado
```

### Certbot falla (DNS no propagado)

```bash
# Verificar que el DNS apunta al EC2
dig pv.joiabagur.com +short
# Debe coincidir con: terraform output -raw ec2_public_ip
```

### Certificado SSL caducado o cron no renueva

Síntoma en `/var/log/cron`: `certbot: command not found` en las líneas de `CROND ... CMD (certbot renew ...)`.

```bash
# Renovar ya
sudo /usr/local/bin/certbot renew --force-renewal
sudo nginx -t && sudo systemctl reload nginx

# Corregir cron (ruta absoluta + log)
echo '0 3,15 * * * root /usr/local/bin/certbot renew -q --deploy-hook "systemctl reload nginx" >> /var/log/certbot-cron.log 2>&1' | sudo tee /etc/cron.d/certbot-jpv
sudo chmod 644 /etc/cron.d/certbot-jpv
sudo /usr/local/bin/certbot renew --dry-run
```

### Importación de datos falla (acceso denegado)

Verificar que el túnel SSM está activo y que las credenciales de la nueva cuenta tienen acceso a RDS:

```bash
# El túnel SSM debe estar corriendo en otra terminal
# Verificar conectividad:
psql -h localhost -p 5432 -U postgres -d jpv -c "SELECT 1;"
```

---

*Última actualización: Julio 2026*
