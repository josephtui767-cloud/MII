# Configuration

## Environment Variables

All configuration is via environment variables. Copy `.env.example` to `.env` for local development.

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| DATABASE_URL | postgresql+asyncpg://mii:password@localhost:5432/mii | PostgreSQL connection string |

### AWS

| Variable | Default | Description |
|----------|---------|-------------|
| AWS_REGION | eu-central-1 | AWS region for API calls |
| AWS_ACCOUNT_IDS | (empty) | Comma-separated account IDs to scan |
| AWS_ASSUME_ROLE_ARN | (empty) | Role ARN to assume for cross-account access |

### GitLab

| Variable | Default | Description |
|----------|---------|-------------|
| GITLAB_URL | https://gitlab.com | GitLab instance URL (for GitLab identity discovery) |
| GITLAB_TOKEN | (empty) | Personal access token with read_api scope (for GitLab identity discovery) |

### OpenAI (AI Features)

| Variable | Default | Description |
|----------|---------|-------------|
| OPENAI_API_KEY | (empty) | OpenAI API key for AI explanations |
| OPENAI_MODEL | gpt-4o-mini | Model to use for AI generation |
| OPENAI_BASE_URL | https://api.openai.com/v1 | API endpoint (override for Azure) |

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| APP_ENV | development | Environment (development/production) |
| LOG_LEVEL | INFO | Logging level |
| DISCOVERY_SCHEDULE_HOURS | 24 | Auto-discovery interval in hours |

## AWS IAM Permissions Required

The platform needs read-only IAM access:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "iam:ListRoles",
      "iam:GetRole",
      "iam:ListRolePolicies",
      "iam:GetRolePolicy",
      "iam:ListAttachedRolePolicies",
      "iam:GetPolicy",
      "iam:GetPolicyVersion"
    ],
    "Resource": "*"
  }]
}
```

Or use the managed policy: `arn:aws:iam::aws:policy/IAMReadOnlyAccess`

## GitLab Token Scopes

Required scope: `read_api`

The token should have access to the groups and projects you want to scan.

## OpenAI Setup

AI features power two capabilities:
- **Explain Risk** — Natural language explanation of why an identity is risky
- **AI Remediation Plan** — Step-by-step fix with AWS CLI commands and Terraform code

### Step 1: Get an API Key

1. Go to https://platform.openai.com
2. Sign up or log in (you can use your existing ChatGPT account)
3. Add a payment method at https://platform.openai.com/settings/organization/billing/overview
4. Load minimum $5 credit (each AI call costs ~$0.001 with gpt-4o-mini)
5. Create an API key at https://platform.openai.com/api-keys
6. Copy the key (starts with `sk-...`)

### Step 2: Configure

Set the environment variable on your backend:

```bash
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini    # cheapest, recommended
```

### Step 3: Use

- Go to any identity with risk score > 0
- Click **"Explain Risk"** for a natural language explanation
- Click **"AI Remediation Plan"** for a structured fix plan with commands

### Supported Models

| Model | Cost per call | Best for |
|-------|--------------|----------|
| gpt-4o-mini | ~$0.001 | Recommended — fast and cheap |
| gpt-4o | ~$0.01-0.03 | More detailed explanations |

### Alternative Providers

The platform supports any OpenAI-compatible API by changing `OPENAI_BASE_URL`:

```bash
# Azure OpenAI
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment

# Self-hosted (e.g., vLLM, Ollama)
OPENAI_BASE_URL=http://localhost:11434/v1
```

### Without AI

AI features are completely optional. Without an API key:
- Risk scores, findings, compliance, trust debt, blast path — all work normally
- The "Explain Risk" and "AI Remediation Plan" buttons are hidden for risk-0 identities
- If clicked without a key, they show a message saying AI is not configured

No data is sent to OpenAI until you explicitly click an AI button.
