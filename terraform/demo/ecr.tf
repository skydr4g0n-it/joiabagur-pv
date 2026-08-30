# Two repositories, one per image. Production has a single one (`jpv-backend`)
# because it ships a single bundled image; the demo runs the AI service as its
# own container, so it publishes two.
#
# Each gets its OWN lifecycle policy. A lifecycle policy is attached per
# repository, so a second repository without one is a repository that grows
# without limit — quietly, and in an account created precisely to be cheap.

locals {
  # Same expiry rules for both, declared once. Five tagged images is roughly a
  # week of deployments, which is as far back as a demo ever needs to roll.
  image_lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep the last 5 commit-tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["sha-"]
          countType     = "imageCountMoreThan"
          countNumber   = 5
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Remove untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      }
    ]
  })
}

resource "aws_ecr_repository" "api" {
  name                 = "jbg-demo-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "jbg-demo-api" }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy     = local.image_lifecycle_policy
}

resource "aws_ecr_repository" "ai" {
  name                 = "jbg-demo-ai"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = { Name = "jbg-demo-ai" }
}

resource "aws_ecr_lifecycle_policy" "ai" {
  repository = aws_ecr_repository.ai.name
  policy     = local.image_lifecycle_policy
}
