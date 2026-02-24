# -----------------------------------------------------------------------------
# ECR Repositories — container image storage
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "puzzleboss" {
  name                 = "${var.project_name}/puzzleboss"
  image_tag_mutability = "MUTABLE" # allows :latest tag updates
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-puzzleboss"
  }
}

resource "aws_ecr_repository" "mediawiki" {
  name                 = "${var.project_name}/mediawiki"
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project_name}-mediawiki"
  }
}

# -----------------------------------------------------------------------------
# Lifecycle policies — keep images from accumulating forever
# Keeps the 10 most recent tagged images and cleans up untagged after 7 days.
# -----------------------------------------------------------------------------

resource "aws_ecr_lifecycle_policy" "puzzleboss" {
  repository = aws_ecr_repository.puzzleboss.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep only 10 most recent tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPatternList = ["*"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "mediawiki" {
  repository = aws_ecr_repository.mediawiki.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images after 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep only 10 most recent tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPatternList = ["*"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
