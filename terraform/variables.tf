variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-3"
}

variable "domain_name" {
  description = "Primary domain name served by the EC2 instance (e.g. joiabagur.com)"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository in owner/name format used for OIDC trust (e.g. my-org/joiabagur-pv)"
  type        = string

  validation {
    condition = (
      can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repo)) &&
      var.github_repo != "your-org/joiabagur-pv"
    )
    error_message = "github_repo must be the real GitHub repository in owner/name format, for example skydr4g0n-it/joiabagur-pv."
  }
}

variable "db_password" {
  description = "RDS master user (postgres) password — min 8 chars; avoid characters that break connection strings in .NET"
  type        = string
  sensitive   = true
}

variable "jwt_secret_key" {
  description = "JWT signing secret (min 32 characters)"
  type        = string
  sensitive   = true
}

variable "jwt_issuer" {
  description = "JWT issuer claim"
  type        = string
  default     = "JoiabagurPV"
}

variable "jwt_audience" {
  description = "JWT audience claim"
  type        = string
  default     = "JoiabagurPV"
}

variable "s3_presigned_url_expiration_minutes" {
  description = "Pre-signed URL expiration in minutes for S3 file downloads"
  type        = number
  default     = 60
}

variable "ec2_instance_type" {
  description = "EC2 instance type (t3.micro is free-tier eligible for the first 12 months)"
  type        = string
  default     = "t3.micro"
}

variable "db_instance_class" {
  description = "RDS instance class (db.t3.micro is free-tier eligible for the first 12 months)"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_publicly_accessible" {
  description = <<-EOT
    If true, RDS gets a public DNS name and can be reached from the Internet when combined with
    rds_migration_ingress_cidrs on the security group. Use only briefly for migration (pgAdmin/psql),
    then set back to false. Requires DB subnets that route to an Internet Gateway (default VPC subnets usually do).
  EOT
  type        = bool
  default     = false
}

variable "rds_migration_ingress_cidrs" {
  description = <<-EOT
    IPv4 CIDRs allowed to connect to PostgreSQL (5432) on RDS — e.g. ["203.0.113.50/32"] for your home IP.
    Leave empty for no extra rules (only EC2 security group access). Remove or empty after migration.
    Never use 0.0.0.0/0 for production databases.
  EOT
  type        = list(string)
  default     = []
}

variable "ami_id" {
  description = <<-EOT
    Amazon Linux 2023 AMI for eu-west-3. Update before applying.
    Find latest: aws ec2 describe-images --owners amazon \
      --filters "Name=name,Values=al2023-ami-*-x86_64" \
      --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
      --output text --region eu-west-3
  EOT
  type        = string
}

variable "key_pair_name" {
  description = "EC2 key pair for emergency SSH access. Leave empty to disable SSH (SSM is used for deployments)."
  type        = string
  default     = ""
}
