# ─── Federated identity for the deployment pipeline ─────────────────────────
#
# Declared as a `resource` because this module targets a VIRGIN account, where
# the provider does not exist yet.
#
# READ THIS BEFORE REUSING THIS MODULE IN ANOTHER ACCOUNT: an OpenID Connect
# provider registration is a SINGLETON PER ACCOUNT AND ISSUER URL. There can be
# exactly one for `token.actions.githubusercontent.com` in a given account. In
# an account that already has one — because something else already deploys from
# GitHub Actions — this resource must be replaced by a data source:
#
#   data "aws_iam_openid_connect_provider" "github" {
#     url = "https://token.actions.githubusercontent.com"
#   }
#
# and every `aws_iam_openid_connect_provider.github.arn` below changed to
# `data.aws_iam_openid_connect_provider.github.arn`. Without that, the apply
# fails with `EntityAlreadyExists`, which reads like a name collision and is
# not one. Written down because it is exactly the class of detail that bites
# months later, in a hurry.
resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # Empty on purpose: since 2023 the trust is anchored in the issuer's TLS
  # certificate chain, not in a pinned thumbprint that expires and has to be
  # chased. Same choice as the production module.
  thumbprint_list = []
}

# ─── Deploy role ────────────────────────────────────────────────────────────
#
# The trust condition is the point of this resource. Production's role trusts
# `repo:<org>/<repo>:*` — ANY branch, ANY workflow, ANY event of that
# repository. This one trusts a single subject:
#
#   repo:<org>/<repo>:environment:demo
#
# which is only issued to a job that declares `environment: demo`. A pull
# request from a fork, a workflow on another branch, or a job that forgets the
# environment declaration cannot assume it. It costs nothing to be strict in a
# module that starts from scratch.
resource "aws_iam_role" "deploy" {
  name        = "jbg-demo-deploy-role"
  description = "Assumed by the demo deployment workflow via OIDC, scoped to the ${var.github_environment} environment"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = aws_iam_openid_connect_provider.github.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        # StringEquals, not StringLike: there is no wildcard to accommodate.
        StringEquals = {
          "token.actions.githubusercontent.com:sub" = "repo:${var.github_repo}:environment:${var.github_environment}"
          "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "deploy" {
  name = "jbg-demo-deploy-policy"
  role = aws_iam_role.deploy.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # The authorisation token call takes no resource; the push permissions
        # below are what actually scope this role, and they name the two demo
        # repositories and nothing else.
        Sid      = "RegistryAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "PushDemoImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage",
          "ecr:DescribeRepositories"
        ]
        Resource = [
          aws_ecr_repository.api.arn,
          aws_ecr_repository.ai.arn
        ]
      },
      {
        # Deployment and post-deployment verification both run INSIDE the host
        # through the systems management service, because the AI service is not
        # reachable from a pipeline runner by design (C17 D21).
        #
        # `GetCommandInvocation` is authorised against
        # `arn:aws:ssm:<region>:<account>:*` rather than the instance ARN — that
        # is how the service evaluates it, and scoping it to the instance
        # produces an access denial that looks like a bug in the workflow.
        Sid    = "RunDeploymentCommands"
        Effect = "Allow"
        Action = [
          "ssm:SendCommand",
          "ssm:GetCommandInvocation",
          "ssm:ListCommandInvocations"
        ]
        Resource = [
          "arn:aws:ec2:${var.aws_region}:${data.aws_caller_identity.current.account_id}:instance/${aws_instance.host.id}",
          "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:*"
        ]
      },
      {
        # So the workflow can confirm the host is registered before sending it a
        # command, instead of timing out on a command nobody will ever collect.
        #
        # `ec2:DescribeInstances` lets it find the host by tag instead of being
        # handed an instance id, which would otherwise have to live in a secret
        # and would go stale the first time the instance is replaced. Neither
        # action supports resource-level permissions, so both are `*` — in an
        # account that holds this environment and nothing else, that is a list
        # of one machine.
        Sid    = "InstanceDiscoveryAndRegistrationStatus"
        Effect = "Allow"
        Action = [
          "ssm:DescribeInstanceInformation",
          "ec2:DescribeInstances"
        ]
        Resource = "*"
      },
      {
        # The tag just deployed, so an unattended restart of the host redeploys
        # the same image rather than whatever was there before. One parameter,
        # named explicitly.
        Sid      = "RecordDeployedTag"
        Effect   = "Allow"
        Action   = "ssm:PutParameter"
        Resource = aws_ssm_parameter.image_tag.arn
      }
    ]
  })
}

# ─── Instance role ──────────────────────────────────────────────────────────
#
# Two permissions and no more: read this environment's parameters, and pull
# this environment's images.

resource "aws_iam_role" "host" {
  name        = "jbg-demo-host-role"
  description = "Instance role for the demo host"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# Without this the host never registers with the systems management service,
# and every deployment times out waiting for a command it cannot receive.
resource "aws_iam_role_policy_attachment" "host_ssm_core" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "host" {
  name = "jbg-demo-host-policy"
  role = aws_iam_role.host.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # One prefix, decrypted. The deploy script reads these into its own
        # process environment and nothing else on this host ever reads them.
        Sid    = "ReadDemoParameters"
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/jbg-demo/*"
      },
      {
        Sid      = "DecryptDemoParameters"
        Effect   = "Allow"
        Action   = "kms:Decrypt"
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${var.aws_region}.amazonaws.com"
          }
        }
      },
      {
        Sid      = "RegistryAuth"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*"
      },
      {
        Sid    = "PullDemoImages"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = [
          aws_ecr_repository.api.arn,
          aws_ecr_repository.ai.arn
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "host" {
  name = "jbg-demo-host-profile"
  role = aws_iam_role.host.name
}
