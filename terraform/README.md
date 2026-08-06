# JoiabagurPV — Infrastructure (Terraform)

Production stack for the jewelry POS system on AWS: a single EC2 instance
running the API and the bundled SPA behind nginx, with RDS PostgreSQL, an S3
bucket for files, ECR for the container image, SSM Parameter Store for runtime
configuration, and GitHub OIDC for keyless deploys.

This README documents **what the stack contains**. The step-by-step deployment
and day-to-day operation procedure lives in
[`Documentos/Guias/deploy-aws-production.md`](../Documentos/Guias/deploy-aws-production.md).

> The App Runner + CloudFront workflows (`deploy-backend-aws.yml`,
> `deploy-frontend-aws.yml`) are **deprecated and manual-only**. This stack is
> the current architecture.

## Layout

| File | Contents |
|---|---|
| `main.tf` | Provider `aws ~> 5.0` and `tls ~> 4.0`, region from `var.aws_region`, default tags (`Project=JoiabagurPV`, `Environment=Production`, `ManagedBy=Terraform`) |
| `backend.tf` | Remote state in S3 (`jpv-terraform-state`, key `prod/terraform.tfstate`, encrypted) |
| `ec2.tf` | Security group (80/443 inbound, all outbound), `t3.micro` instance with a 30 GiB encrypted gp3 root volume, Elastic IP |
| `rds.tf` | Security group (5432 from the EC2 SG only), optional migration ingress rules, DB subnet group, `db.t3.micro` PostgreSQL 15 instance |
| `s3.tf` | Bucket `prod-jpv-files` with versioning, SSE, public access block, CORS and a 30-day non-current version expiration rule |
| `ecr.tf` | Repository `jpv-backend` with scan-on-push and a lifecycle policy that keeps the last 5 `sha-` tagged images |
| `iam.tf` | GitHub OIDC provider, `jpv-github-actions-role` (deploy), `jpv-ec2-instance-role` + instance profile (SSM, ECR pull, S3, Parameter Store) |
| `ssm.tf` | SecureString/String parameters under `/jpv/prod/*` consumed by the API at container start |
| `outputs.tf` | Values needed to configure DNS and GitHub Actions |
| `templates/user_data.sh` | First-boot script: Docker, nginx, SSM agent, certbot and the renewal cron |
| `terraform.tfvars.example` | Template for the required variables |

## Prerequisites

- Terraform >= 1.5 and AWS credentials with permissions for the resources above.
- The state bucket **must exist before `terraform init`** — see the commands at
  the top of `backend.tf`.
- A current Amazon Linux 2023 AMI id for the target region (`var.ami_id`); the
  lookup command is in the variable description.

## Variables

| Variable | Type | Default | Notes |
|---|---|---|---|
| `aws_region` | string | `eu-west-3` | |
| `domain_name` | string | — | Domain served by the instance; also used for CORS and the certificate |
| `github_repo` | string | — | `owner/name`, validated; used for the OIDC trust condition |
| `db_password` | string (sensitive) | — | RDS master password; avoid characters that break .NET connection strings |
| `jwt_secret_key` | string (sensitive) | — | Min. 32 characters |
| `jwt_issuer` / `jwt_audience` | string | `JoiabagurPV` | |
| `s3_presigned_url_expiration_minutes` | number | `60` | |
| `ec2_instance_type` | string | `t3.micro` | Free-tier eligible for the first 12 months |
| `db_instance_class` | string | `db.t3.micro` | Free-tier eligible for the first 12 months |
| `rds_publicly_accessible` | bool | `false` | Migration only — set back to `false` afterwards |
| `rds_migration_ingress_cidrs` | list(string) | `[]` | Temporary /32 CIDRs for psql/pgAdmin. Never `0.0.0.0/0` |
| `ami_id` | string | — | Amazon Linux 2023 AMI for the region |
| `key_pair_name` | string | `""` | Optional emergency SSH; empty disables it (deploys go through SSM) |

Copy `terraform.tfvars.example` to `terraform.tfvars` and fill it in.
**`terraform.tfvars` holds secrets: it is never committed and its values are
never documented here.**

## Outputs

| Output | Used for |
|---|---|
| `ec2_public_ip` | DNS `A` record for the domain |
| `rds_endpoint` | Data import through SSM port forwarding |
| `ecr_repository_url` | `ECR_REPOSITORY` in GitHub Actions |
| `github_actions_role_arn` | `DEPLOY_ROLE_ARN` in GitHub Actions (replaces static keys) |
| `ec2_instance_id` | `EC2_INSTANCE_ID` in GitHub Actions |
| `s3_files_bucket` | Files bucket name |

## Runtime configuration (`/jpv/prod/*`)

The API reads these parameters as environment variables injected by the deploy
script. Naming follows the ASP.NET Core convention where `__` replaces `:`.

| Parameter | Type | Source |
|---|---|---|
| `ConnectionStrings__DefaultConnection` | SecureString | Built from the RDS endpoint and `db_password` |
| `Jwt__SecretKey` | SecureString | `jwt_secret_key` |
| `Jwt__Issuer`, `Jwt__Audience` | String | `jwt_issuer`, `jwt_audience` |
| `Aws__S3__BucketName` | String | Files bucket |
| `Aws__S3__PresignedUrlExpirationMinutes` | String | `s3_presigned_url_expiration_minutes` |
| `Cors__AllowedOrigins__0` | String | `https://<domain_name>` |

## Usage

```bash
terraform init
terraform plan  -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

Notes:

- `aws_instance.api` has `ignore_changes = [user_data]`: editing
  `templates/user_data.sh` does **not** re-provision the instance. Re-run the
  relevant part manually over SSM.
- RDS has `deletion_protection = true`, `skip_final_snapshot = false` and 7-day
  backups: destroying it is deliberately awkward.
- TLS certificates are issued on the instance with certbot after the DNS record
  points at the Elastic IP; renewal runs from a cron installed by `user_data.sh`.

## Related documentation

- [Guía de producción en AWS (EC2 + Terraform)](../Documentos/Guias/deploy-aws-production.md) — deployment and operation
- [Migración a EC2](../Documentos/Guias/deploy-aws-ec2-migration.md) — history of the move away from App Runner
- [Arquitectura del sistema](../Documentos/arquitectura.md) — production environment in context
- [`.github/workflows/deploy-aws-ec2.yml`](../.github/workflows/deploy-aws-ec2.yml) — the pipeline that consumes these outputs
