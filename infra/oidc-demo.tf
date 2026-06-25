# OIDC Federation Demo — creates trust relationships for MII to discover
# This file creates sample IAM roles with various trust configurations
# that MII will detect, score, and report on.
#
# Customize the OIDC provider and project paths for your environment.

# --- GitHub OIDC Provider ---
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com"
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1"
  ]

  tags = {
    Project = "MII"
    Purpose = "GitHub Actions OIDC Federation"
  }
}

# --- GitLab OIDC Provider (optional — uncomment if using GitLab) ---
# resource "aws_iam_openid_connect_provider" "gitlab" {
#   url = "https://gitlab.com"
#
#   client_id_list = ["https://gitlab.com"]
#   thumbprint_list = ["b3dd7606d2b5a8b4a13771dbecc9ee1cecafa38a"]
#
#   tags = {
#     Project = "MII"
#     Purpose = "GitLab OIDC Federation Demo"
#   }
# }

# IAM Role trusted by GitHub Actions (demo - read only)
resource "aws_iam_role" "ci_deploy" {
  name = "ci-deploy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/*:*"
          }
        }
      }
    ]
  })

  tags = {
    Project   = "MII"
    Purpose   = "CI/CD Deploy Role - OIDC Federation Demo"
    TrustedBy = "GitHub Actions"
  }
}

# Attach a read-only policy to the role (safe for demo)
resource "aws_iam_role_policy_attachment" "ci_readonly" {
  role       = aws_iam_role.ci_deploy.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# Second role - simulating a production deployment role (HIGH RISK - for MII to detect)
resource "aws_iam_role" "ci_production" {
  name = "ci-production-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/mii:ref:refs/heads/main"
          }
        }
      }
    ]
  })

  tags = {
    Project     = "MII"
    Purpose     = "Production Deploy Role - OIDC Federation Demo"
    Environment = "production"
    TrustedBy   = "GitHub Actions - main branch only"
  }
}

# Attach admin policy to production role (to demonstrate high-risk detection by MII)
resource "aws_iam_role_policy_attachment" "ci_prod_admin" {
  role       = aws_iam_role.ci_production.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# Third role - cross-account trust demo
resource "aws_iam_role" "cross_account_demo" {
  name = "cross-account-shared-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::123456789012:root"
        }
        Action = "sts:AssumeRole"
      },
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/*:*"
          }
        }
      }
    ]
  })

  tags = {
    Project     = "MII"
    Purpose     = "Cross-Account Shared Role - Demo"
    Environment = "production"
  }
}

resource "aws_iam_role_policy_attachment" "cross_account_s3" {
  role       = aws_iam_role.cross_account_demo.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}
