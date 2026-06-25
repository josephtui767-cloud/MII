variable "aws_region" {
  description = "AWS region for deployment"
  default     = "eu-central-1"
}

variable "key_name" {
  description = "SSH key pair name (optional)"
  default     = ""
}

variable "container_image" {
  description = "Docker image for the backend (e.g., ghcr.io/your-org/mii-backend:latest)"
  type        = string
}

variable "container_registry_url" {
  description = "Container registry URL (e.g., ghcr.io)"
  default     = "ghcr.io"
}

variable "container_registry_username" {
  description = "Container registry username"
  type        = string
  sensitive   = true
}

variable "container_registry_password" {
  description = "Container registry password/token"
  type        = string
  sensitive   = true
}

variable "aws_account_ids" {
  description = "Comma-separated AWS account IDs to scan"
  type        = string
  default     = ""
}

variable "openai_api_key" {
  description = "OpenAI API key (optional — for AI features)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "gitlab_token" {
  description = "GitLab personal access token (optional — for GitLab identity discovery)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_token" {
  description = "GitHub token (optional — for GitHub Actions identity discovery)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_org" {
  description = "GitHub organization name (optional — for GitHub Actions identity discovery)"
  type        = string
  default     = ""
}

variable "db_password" {
  description = "PostgreSQL password for MII database"
  type        = string
  default     = "change-me-in-production"
  sensitive   = true
}

variable "project_name" {
  description = "Project name prefix for AWS resources"
  default     = "mii"
}
