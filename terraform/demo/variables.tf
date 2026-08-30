variable "aws_region" {
  description = "AWS region for the demo environment"
  type        = string
  default     = "eu-west-1"
}

variable "github_repo" {
  description = "GitHub repository in owner/name format, used for the OIDC trust condition (e.g. skydr4g0n-it/joiabagur-pv)"
  type        = string

  validation {
    condition = (
      can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repo)) &&
      var.github_repo != "your-org/joiabagur-pv"
    )
    error_message = "github_repo must be the real GitHub repository in owner/name format, for example skydr4g0n-it/joiabagur-pv."
  }
}

variable "github_environment" {
  description = <<-EOT
    Name of the GitHub Environment the deploy workflow declares. The role's trust
    policy is scoped to it, so a workflow that does not run under this environment
    cannot assume the role — stricter than the production role, whose condition is
    `repo:<org>/<repo>:*` and therefore accepts any branch and any workflow.
  EOT
  type        = string
  default     = "demo"
}

variable "deployment_branch" {
  description = "Branch the demo environment is deployed from, and the branch whose archive the host retrieves at first boot"
  type        = string
  default     = "demo"
}

variable "deployment_bundle_url" {
  description = <<-EOT
    HTTPS URL of a gzipped tarball whose single top-level directory contains
    `compose.demo.yaml` and `deploy/`. Retrieved once by host provisioning and
    refreshed by every deployment. Empty means "derive it from github_repo and
    deployment_branch", which works for a public repository; for a private one,
    stage the tarball in S3 and put its URL here. See deploy/demo/README.md.
  EOT
  type        = string
  default     = ""
}

variable "docker_compose_version" {
  description = <<-EOT
    Version of the Compose plugin installed on the host, pinned on purpose. A
    moving tag here would mean the same commit provisions a different host
    depending on the day. Bump it deliberately, in a commit, like a dependency.
  EOT
  type        = string
  default     = "v2.32.4"
}

variable "instance_type" {
  description = <<-EOT
    Instance type for the demo host. `t3.small` is the starting point for four
    containers with a 512 MiB cap on the AI service; the definitive size is
    decided WITH the measurement of the first deployment, not before it.
  EOT
  type        = string
  default     = "t3.small"
}

variable "root_volume_size_gb" {
  description = "Root volume size. AL2023 images use a snapshot that requires at least 30 GiB."
  type        = number
  default     = 30
}

variable "demo_hostname" {
  description = <<-EOT
    Hostname the environment is served under, and the name the reverse proxy
    requests a certificate for. It is configuration rather than a build-time
    constant, so the environment can start on a name derived from its elastic IP
    — which is a real, certifiable DNS name — and migrate to a purchased domain
    by changing this value and redeploying, with no image rebuilt.

    Leave empty to derive `<dashed-elastic-ip>.sslip.io` automatically.
  EOT
  type        = string
  default     = ""
}

variable "key_pair_name" {
  description = "EC2 key pair for emergency SSH access. Empty disables SSH entirely; deployments use the systems management service."
  type        = string
  default     = ""
}
