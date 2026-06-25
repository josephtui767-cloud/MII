# Deployment Guide

## Production Architecture

```
Users ──► CloudFront (HTTPS) ──► S3 (Frontend static files)
                │
                └──► /api/* ──► EC2 (Backend API + PostgreSQL)
```

## Infrastructure Components

| Component | Service | Purpose |
|-----------|---------|---------|
| Frontend Hosting | S3 + CloudFront | Static React app served over HTTPS |
| Backend API | EC2 (t3.micro/t3.small) | FastAPI application |
| Database | PostgreSQL (Docker on EC2) | Identity and relationship storage |
| Container Registry | GitLab Container Registry or GitHub Container Registry | Docker image storage |
| CI/CD | GitLab CI/CD or GitHub Actions | Automated build and deploy |

## CI/CD Pipeline

The CI/CD pipeline (GitLab CI or GitHub Actions) has three stages:

### 1. Test
- Backend: installs dependencies, runs Alembic migrations against test PostgreSQL
- Frontend: installs dependencies, runs Vitest

### 2. Build
- Backend: builds Docker image, pushes to container registry (GitLab or GitHub)
- Frontend: builds with Vite, syncs to S3, invalidates CloudFront cache

### 3. Deploy
- Frontend automatically deploys on changes to `frontend/**/*`
- Backend requires manual image pull on EC2 (or EC2 recreation)

## Terraform Resources

Infrastructure is defined in `infra/`:

- `backend.tf` — EC2 instance, security group, IAM role, instance profile
- `main.tf` — S3 bucket, CloudFront distribution, OAC
- `oidc-demo.tf` — Demo OIDC federation roles (for testing)

## Environment Variables

Required on the EC2 backend:

| Variable | Description |
|----------|-------------|
| DATABASE_URL | PostgreSQL connection string |
| AWS_REGION | AWS region for IAM discovery |
| AWS_ACCOUNT_IDS | Comma-separated AWS account IDs to scan |
| GITLAB_URL | GitLab instance URL |
| GITLAB_TOKEN | GitLab personal access token (read_api scope) |
| OPENAI_API_KEY | OpenAI API key for AI features |
| OPENAI_MODEL | Model name (default: gpt-4o-mini) |

## Scaling Considerations

- **Frontend**: CloudFront handles global distribution and caching
- **Backend**: EC2 t3.micro supports ~10K identities; upgrade to t3.small for heavy workloads
- **Database**: PostgreSQL on EC2 is sufficient up to 50K identities; move to RDS for production scale
- **Graph Engine**: NetworkX handles 10K+ nodes in-memory efficiently

## Monitoring

- Backend logs are output to stdout (viewable via `docker logs`)
- CloudFront access logs can be enabled for traffic analysis
- CloudTrail monitors IAM API calls made by the discovery process

## Security Hardening for Production

1. Restrict EC2 security group to CloudFront IP ranges only
2. Enable HTTPS on EC2 (currently HTTP behind CloudFront HTTPS)
3. Add API authentication (API keys or OAuth2)
4. Move PostgreSQL to RDS with encryption at rest
5. Store secrets in AWS Secrets Manager instead of environment variables
6. Enable VPC isolation for the EC2 instance
