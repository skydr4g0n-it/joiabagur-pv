# ─── Security group ─────────────────────────────────────────────────────────
#
# The first of the three independent layers that keep the AI service — and with
# it the embedding provider credential — off the Internet. The other two are in
# `compose.demo.yaml`: only the reverse proxy declares published ports, and the
# AI service declares none at all. A mistake in any one layer is not enough to
# expose the credential (C17 D7).
#
# There is deliberately NO ingress rule for 8000 (the AI service), 8080 (the
# business API) or 5432 (the database). Adding one to "debug something" removes
# the guarantee this group exists for; use the systems management service, which
# needs no inbound rule at all.

resource "aws_security_group" "host" {
  name        = "jbg-demo-sg"
  description = "Demo host: HTTP and HTTPS inbound only, all outbound"

  ingress {
    description = "HTTP, redirected to HTTPS by the proxy"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound is open: the host pulls images, reads parameters, reaches the
  # systems management service, and the AI service calls the embedding provider.
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "jbg-demo-sg" }
}

# ─── Host ───────────────────────────────────────────────────────────────────

locals {
  # Empty means "derive it from the elastic IP". `sslip.io` resolves any
  # dotted-or-dashed address embedded in the name to that address, so
  # `1-2-3-4.sslip.io` is a real DNS name a certificate authority will issue
  # for — which is what lets the environment have valid TLS before a domain is
  # bought (C17 D6).
  demo_hostname = var.demo_hostname != "" ? var.demo_hostname : "${replace(aws_eip.host.public_ip, ".", "-")}.sslip.io"

  deployment_bundle_url = (
    var.deployment_bundle_url != ""
    ? var.deployment_bundle_url
    : "https://codeload.github.com/${var.github_repo}/tar.gz/refs/heads/${var.deployment_branch}"
  )
}

resource "aws_instance" "host" {
  # Resolved from the provider's published parameter — no identifier to look up
  # and paste before an apply. See the note in main.tf.
  ami                    = data.aws_ssm_parameter.amazon_linux_2023.value
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.host.name
  vpc_security_group_ids = [aws_security_group.host.id]
  key_name               = var.key_pair_name != "" ? var.key_pair_name : null

  root_block_device {
    volume_type = "gp3"
    volume_size = var.root_volume_size_gb
    encrypted   = true
  }

  metadata_options {
    http_tokens   = "required"
    http_endpoint = "enabled"
  }

  user_data = templatefile("${path.module}/templates/user_data.sh", {
    compose_plugin_version = var.docker_compose_version
    bundle_url             = local.deployment_bundle_url
  })

  # NOTE the ABSENCE of `lifecycle { ignore_changes = [user_data] }`, which the
  # production module declares. That is why editing production's provisioning
  # script propagates nothing, and why the script that actually deploys the shop
  # lives only inside an instance booted months ago. Here the repository is the
  # source of truth from the first minute: changing provisioning replaces the
  # instance, which is the honest consequence and is affordable because the data
  # is restored from a dump and the environment is disposable by design.

  tags = { Name = "jbg-demo-host" }
}

# ─── Elastic IP ─────────────────────────────────────────────────────────────
#
# A stable address, so the derived hostname and the certificate issued for it
# survive a stop/start of the instance. Without it, restarting the host changes
# the name, and the new name needs a new certificate — against an authority that
# rate-limits issuance.

resource "aws_eip" "host" {
  instance = aws_instance.host.id
  domain   = "vpc"
  tags     = { Name = "jbg-demo-eip" }
}
