# ============================================================================
# terraform/demo — infrastructure for the ISOLATED DEMO environment (C17)
#
# This module targets a DIFFERENT AWS ACCOUNT from the one in `terraform/`,
# which hosts the shop's production system. It shares nothing with it: not a
# resource, not a permission, not a deployment path, and — critically — not a
# state file. See `backend.tf`.
#
# What lives here:
#
#   iam.tf   OIDC trust, deploy role scoped to the `demo` environment, and the
#            instance role
#   ecr.tf   the two image repositories, each with its own lifecycle policy
#   ec2.tf   security group (80/443 only), instance, elastic IP
#   ssm.tf   the non-secret parameters. Secrets are created by hand, out of
#            state — see deploy/demo/README.md
#
# Everything specific to the application lives in `compose.demo.yaml`, in the
# images, and in the parameter store. Nothing here knows what the application
# is (C17 D17).
# ============================================================================

terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "JoiabagurPV"
      Environment = "Demo"
      ManagedBy   = "Terraform"
      Module      = "terraform/demo"
    }
  }
}

data "aws_caller_identity" "current" {}

# The base operating system image, resolved from the provider's own published
# parameter rather than a variable somebody has to update by hand before every
# apply — which is what `terraform/variables.tf` does for production, with a
# comment telling the operator to go and look the identifier up.
#
# ASSUMPTION, written down because it is invisible otherwise: this module uses
# the account's DEFAULT VPC and its default subnets. It declares no VPC, no
# subnet and no route table. In an account without a default VPC the instance
# and the security group will fail to create, and the fix is to add a VPC and
# pass its subnet — not to hunt for a missing permission.
data "aws_ssm_parameter" "amazon_linux_2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}
