# Parameters for the demo environment, all under one prefix — `/jbg-demo/` —
# which is the prefix the instance role can read, and the only one.
#
# ONLY THE NON-SECRET PARAMETERS ARE DECLARED HERE, and that is deliberate. A
# value passed to Terraform is written to the state file in clear; declaring the
# database password, the shared token secret, the index feed credential or the
# provider API key here would move six secrets out of the encrypted parameter
# store and into a state file, which is the opposite of what the store is for.
# They are created once, by hand, with the command line — see the runbook in
# `deploy/demo/README.md`.
#
# Class C settings — the embedding model, the retrieval threshold and stub mode
# — are ABSENT on purpose, and not by oversight: they are versioned literals in
# `compose.demo.yaml`. The parameter store is a place where a value can change
# without code review, and each of those three fails silently when wrong
# (C17 D8).

resource "aws_ssm_parameter" "demo_hostname" {
  name        = "/jbg-demo/DEMO_HOSTNAME"
  description = "Hostname served by the reverse proxy and named on its certificate"
  type        = "String"
  value       = local.demo_hostname

  tags = { Name = "jbg-demo-hostname" }
}

resource "aws_ssm_parameter" "ecr_registry" {
  name        = "/jbg-demo/ECR_REGISTRY"
  description = "Registry host the two demo images are pulled from"
  type        = "String"
  # Derived from a repository URL so it cannot drift from the repositories this
  # module actually creates.
  value = split("/", aws_ecr_repository.api.repository_url)[0]

  tags = { Name = "jbg-demo-ecr-registry" }
}

resource "aws_ssm_parameter" "deployment_bundle_url" {
  name        = "/jbg-demo/DEPLOYMENT_BUNDLE_URL"
  description = "Archive holding compose.demo.yaml and deploy/; refreshed on the host before every deployment"
  type        = "String"
  # Same value host provisioning used at first boot, so a deployment and a fresh
  # instance always start from the same bundle.
  value = local.deployment_bundle_url

  tags = { Name = "jbg-demo-bundle-url" }
}

resource "aws_ssm_parameter" "image_tag" {
  name        = "/jbg-demo/IMAGE_TAG"
  description = "Tag of the last image the pipeline deployed; what an unattended restart brings back up"
  type        = "String"
  # A placeholder only for the first apply, before anything has been published.
  value = "bootstrap"

  lifecycle {
    # The deployment workflow owns this value from the first deployment onward.
    # Without this, every apply would propose to roll the environment back to
    # the placeholder.
    ignore_changes = [value]
  }

  tags = { Name = "jbg-demo-image-tag" }
}
