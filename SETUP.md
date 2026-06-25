# MII Platform — Complete Setup Guide

This guide walks you through setting up the Machine Identity Intelligence platform from scratch.

---

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Node.js** 20+ and **npm**
- **Python** 3.11+
- **AWS Account** with IAM read permissions
- **Terraform** 1.5+ (for production deployment)
- **Git**

---

## Connecting Your Accounts

MII discovers machine identities from your AWS account and (optionally) GitLab CI/CD. Here's how to configure each.

### AWS Setup (Required)

MII needs **read-only** IAM access to discover identities. It uses the [boto3 credential chain](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html) — pick one method:

#### Method A: Environment Variables (local dev)

Add to your `.env` file:
```bash
AWS_REGION=eu-central-1
AWS_ACCOUNT_IDS=123456789012           # Your AWS account ID
AWS_ACCESS_KEY_ID=AKIA...              # IAM user access key
AWS_SECRET_ACCESS_KEY=wJalrX...        # IAM user secret key
```

**Create an IAM user with read-only access:**
1. Go to AWS Console → IAM → Users → Create User
2. Name: `mii-reader`
3. Attach policy: `IAMReadOnlyAccess`
4. Create access key → Copy the key ID and secret into `.env`

#### Method B: EC2 Instance Role (production)

When running on EC2, the Terraform config automatically creates an instance profile with `IAMReadOnlyAccess`. No env vars needed — boto3 picks up the role automatically.

#### Method C: AWS CLI Profile (local dev alternative)

If you have `~/.aws/credentials` configured:
```bash
AWS_REGION=eu-central-1
AWS_ACCOUNT_IDS=123456789012
# No AWS_ACCESS_KEY_ID/SECRET needed — boto3 reads ~/.aws/credentials
```

#### Cross-Account Discovery (multiple AWS accounts)

To scan 2+ AWS accounts, create the same read-only role in each account and set:
```bash
AWS_ACCOUNT_IDS=111111111111,222222222222,333333333333
AWS_ASSUME_ROLE_ARN=arn:aws:iam::111111111111:role/MIIReadOnly
```

MII automatically swaps the account ID in the role ARN for each account. So it will assume:
- `arn:aws:iam::111111111111:role/MIIReadOnly`
- `arn:aws:iam::222222222222:role/MIIReadOnly`
- `arn:aws:iam::333333333333:role/MIIReadOnly`

**Requirement:** Each target account needs an IAM role named `MIIReadOnly` (or whatever you choose) with:
- Policy: `IAMReadOnlyAccess`
- Trust: allows your source account/role to assume it

```json
{
  "Effect": "Allow",
  "Principal": { "AWS": "arn:aws:iam::SOURCE_ACCOUNT:role/mii-ec2-role" },
  "Action": "sts:AssumeRole"
}
```

If you only have **one account**, you don't need `AWS_ASSUME_ROLE_ARN` — just set credentials directly.

#### Enterprise: AWS Organizations Auto-Discovery (100+ accounts)

For large organizations, manually listing account IDs is impractical. Set `AWS_ACCOUNT_IDS=auto` and MII will automatically discover all active accounts via the AWS Organizations API:

```bash
AWS_ACCOUNT_IDS=auto
AWS_ASSUME_ROLE_ARN=arn:aws:iam::000000000000:role/MIIReadOnly
# Optional: if your Organizations management account is separate
AWS_ORG_ROLE_ARN=arn:aws:iam::MANAGEMENT_ACCOUNT:role/MIIOrgReader
```

**How it works:**
1. MII calls `organizations:ListAccounts` to find all active accounts
2. For each account, it assumes `MIIReadOnly` role (swapping the account ID)
3. Discovers all IAM roles across your entire organization

**Setup:**
1. In your **management account** (or delegated admin), create a role with `organizations:ListAccounts` permission
2. In **every member account**, deploy the `MIIReadOnly` role via CloudFormation StackSets:

```yaml
# stackset-mii-role.yml
Resources:
  MIIReadOnlyRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: MIIReadOnly
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal:
              AWS: arn:aws:iam::SOURCE_ACCOUNT:role/mii-ec2-role
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/IAMReadOnlyAccess
```

3. Deploy the StackSet to all accounts in your organization
4. Set `AWS_ACCOUNT_IDS=auto` — MII handles the rest

---

### GitLab Setup (Optional)

To discover GitLab CI/CD identities (OIDC federations, pipeline tokens):

1. Go to GitLab → Settings → Access Tokens
2. Create a token with `read_api` scope
3. Add to `.env`:
```bash
GITLAB_URL=https://gitlab.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
```

MII will discover which GitLab projects have OIDC trust to your AWS roles.

---

### OpenAI Setup (Optional)

For AI-powered risk explanations and remediation plans:

1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Add $5 credit (each MII call costs ~$0.001)
4. Add to `.env`:
```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxx
OPENAI_MODEL=gpt-4o-mini
```

The platform works fully without OpenAI — AI features just won't appear on identity detail pages.

---

## Option 1: Local Development (Docker Compose)

The fastest way to get MII running locally.

### 1. Clone and Configure

```bash
git clone https://github.com/YOUR_ORG/mii.git
cd mii
cp .env.example .env
```

Edit `.env` with your values (see [Connecting Your Accounts](#connecting-your-accounts) above):
- `AWS_REGION` — your AWS region
- `AWS_ACCOUNT_IDS` — comma-separated AWS account IDs to scan
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — IAM user with `IAMReadOnlyAccess`
- `OPENAI_API_KEY` — (optional) for AI features

### 2. Start Services

```bash
docker-compose up --build
```

This starts:
- PostgreSQL 15 on port 5432
- Backend API on port 8000
- Frontend on port 3000

### 3. Run Migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Access the Platform

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v1/health

### 5. Run First Discovery

Click "Run Discovery" in the UI, or:
```bash
curl -X POST http://localhost:8000/api/v1/discovery/run
```

---

## Option 2: Manual Development Setup

For active development with hot-reloading.

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Start PostgreSQL (Docker)
docker run -d --name mii-db -e POSTGRES_DB=mii -e POSTGRES_USER=mii -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15

# Run migrations
export DATABASE_URL="postgresql+asyncpg://mii:password@localhost:5432/mii"
alembic upgrade head

# Start the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at http://localhost:5173 (Vite dev server).

---

## Option 3: Production Deployment (AWS)

Deploy to AWS using Terraform — EC2 for backend, S3+CloudFront for frontend.

### Architecture

```
Users → CloudFront (HTTPS) → S3 (frontend static files)
                           → EC2:8000 (backend API via /api/* proxy)
```

### 1. Build and Push Docker Image

```bash
# Build backend image
cd backend
docker build -t ghcr.io/YOUR_ORG/mii-backend:latest .
docker push ghcr.io/YOUR_ORG/mii-backend:latest
```

Or let GitHub Actions build it automatically on push to main.

### 2. Configure Terraform

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:
```hcl
container_image              = "ghcr.io/YOUR_ORG/mii-backend:latest"
container_registry_username  = "YOUR_GITHUB_USERNAME"
container_registry_password  = "ghp_YOUR_PERSONAL_ACCESS_TOKEN"
aws_region                   = "eu-central-1"
aws_account_ids              = "123456789012"
openai_api_key               = "sk-..."   # optional
db_password                  = "a-strong-random-password"
github_org                   = "YOUR_ORG"
```

### 3. Deploy Infrastructure

```bash
cd infra
terraform init
terraform plan
terraform apply
```

Terraform creates:
- EC2 instance (t3.micro) running the backend in Docker
- S3 bucket for frontend static files
- CloudFront distribution with API proxy
- IAM roles for EC2 (read-only IAM access for discovery)
- Demo OIDC roles (for MII to discover and report on)

### 4. Deploy Frontend

```bash
cd frontend
npm ci && npm run build

# Upload to S3
aws s3 sync dist/ s3://$(terraform -chdir=../infra output -raw s3_bucket_name) --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id $(terraform -chdir=../infra output -raw cloudfront_distribution_id) \
  --paths "/*"
```

### 5. Configure CloudFront API Proxy

After Terraform applies, add a second origin to the CloudFront distribution for the backend API:

1. Go to CloudFront → Distribution → Origins → Create Origin
2. Origin domain: `ec2-<IP-WITH-HYPHENS>.<region>.compute.amazonaws.com`
3. Protocol: HTTP only, Port: 8000
4. Create a behavior: Path pattern `/api/*` → Origin: EC2 backend
5. Allow methods: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE
6. Cache policy: CachingDisabled
7. Origin request policy: AllViewer

### 6. Verify

```bash
curl https://YOUR_CLOUDFRONT_DOMAIN/api/v1/health
# → {"status":"healthy","service":"mii-backend","version":"0.1.0"}
```

---

## GitHub Actions CI/CD

The included `.github/workflows/ci.yml` automates:
- Backend tests + Docker build/push to ghcr.io
- Frontend tests + build + S3 deploy

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3 deploy |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 deploy |
| `AWS_REGION` | AWS region (e.g., `eu-central-1`) |
| `S3_BUCKET_NAME` | S3 bucket name for frontend |

The `GITHUB_TOKEN` is automatically available for pushing to ghcr.io.

---

## GitLab CI/CD Alternative

If you prefer GitLab instead of GitHub:

### 1. Use GitLab Container Registry

Replace `ghcr.io` references with `registry.gitlab.com/YOUR_GROUP/mii/backend:latest`.

### 2. Create `.gitlab-ci.yml`

```yaml
stages:
  - test
  - build
  - deploy

backend:test:
  stage: test
  image: python:3.11-slim
  services:
    - name: postgres:15
      alias: postgres
  variables:
    POSTGRES_DB: mii_test
    POSTGRES_USER: mii
    POSTGRES_PASSWORD: password
    DATABASE_URL: "postgresql+asyncpg://mii:password@postgres:5432/mii_test"
  script:
    - cd backend
    - pip install --no-cache-dir -e ".[dev]"
    - alembic upgrade head
    - pytest tests/ -v || echo "No tests to run yet"
  rules:
    - changes:
        - backend/**/*

backend:build:
  stage: build
  image: docker:24
  services:
    - docker:24-dind
  variables:
    DOCKER_TLS_CERTDIR: "/certs"
    IMAGE_TAG: $CI_REGISTRY_IMAGE/backend:$CI_COMMIT_SHORT_SHA
    IMAGE_LATEST: $CI_REGISTRY_IMAGE/backend:latest
  before_script:
    - docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY
  script:
    - docker build -t $IMAGE_TAG -t $IMAGE_LATEST ./backend
    - docker push $IMAGE_TAG
    - docker push $IMAGE_LATEST
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      changes:
        - backend/**/*

frontend:test:
  stage: test
  image: node:20-slim
  script:
    - cd frontend
    - npm ci
    - npm run test
  rules:
    - changes:
        - frontend/**/*

frontend:build:
  stage: build
  image: node:20-slim
  script:
    - cd frontend
    - npm ci
    - npm run build
  artifacts:
    paths:
      - frontend/dist/
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      changes:
        - frontend/**/*
```

### 3. GitLab OIDC (for demo identities)

Uncomment the GitLab OIDC provider in `infra/oidc-demo.tf` and update the project paths to match your GitLab group/project.

### 4. Terraform Variables

Update `terraform.tfvars`:
```hcl
container_image              = "registry.gitlab.com/YOUR_GROUP/mii/backend:latest"
container_registry_url       = "registry.gitlab.com"
container_registry_username  = "gitlab-ci-token"
container_registry_password  = "YOUR_GITLAB_DEPLOY_TOKEN"
```

---

## AWS Permissions Required

### For Discovery (EC2 Instance Role)

The platform needs **read-only** IAM access to discover identities:
- `IAMReadOnlyAccess` (managed policy)

This is automatically configured by Terraform via the `mii-ec2-role`.

### For Deployment (CI/CD or manual)

Your deployment credentials need:
- `s3:PutObject`, `s3:DeleteObject` on the frontend bucket
- `cloudfront:CreateInvalidation`
- `ec2:*` (for Terraform to manage the instance)
- `iam:*` (for Terraform to create demo roles)

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `APP_ENV` | No | `development` or `production` (default: development) |
| `LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: INFO) |
| `AWS_REGION` | Yes | AWS region for discovery |
| `AWS_ACCOUNT_IDS` | Yes | Comma-separated account IDs |
| `GITLAB_URL` | No | GitLab instance URL |
| `GITLAB_TOKEN` | No | GitLab PAT for CI/CD identity discovery |
| `GITHUB_TOKEN` | No | GitHub PAT for Actions identity discovery |
| `GITHUB_ORG` | No | GitHub organization to scan |
| `OPENAI_API_KEY` | No | For AI-powered features (~$0.001/call) |
| `OPENAI_MODEL` | No | Model name (default: gpt-4o-mini) |

---

## Troubleshooting

### Backend won't start
- Check `DATABASE_URL` is correct and PostgreSQL is running
- Run `alembic upgrade head` to ensure migrations are applied
- Check logs: `docker-compose logs backend`

### Discovery returns no identities
- Verify `AWS_ACCOUNT_IDS` is set correctly
- Ensure the EC2 instance role (or local AWS credentials) has `IAMReadOnlyAccess`
- Check AWS region matches where your roles exist

### AI features not working
- Set `OPENAI_API_KEY` in environment
- Ensure you have credits on your OpenAI account
- The platform works fully without AI — these are optional enhancements

### Report export fails
- Ensure `reportlab` and `openpyxl` are installed (included in pyproject.toml)
- Check backend logs for specific error messages

### CloudFront returns 502
- Verify the EC2 instance is running and healthy: `curl http://<EC2_IP>:8000/api/v1/health`
- Ensure CloudFront origin uses the correct EC2 hostname format: `ec2-<IP-WITH-HYPHENS>.<region>.compute.amazonaws.com`
- Wait 3–5 minutes after EC2 creation for user_data to finish
