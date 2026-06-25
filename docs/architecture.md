# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                Frontend (React + TypeScript)                      │
│   Overview │ Identities │ Findings │ Compliance │ Trust Debt     │
│   Blast Path │ Trust Graph │ Identity Detail                     │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ REST API (HTTPS via CloudFront)
┌─────────────────────────────────┴───────────────────────────────┐
│                  Backend API (FastAPI + Python 3.11)              │
│   Collectors │ Risk Engine │ Graph Engine │ Trust Parser          │
│   Findings Engine │ Compliance Engine │ Trust Debt Engine         │
│   Blast Path Engine │ AI Advisor                                 │
└──────┬──────────┬───────────────┬──────────────┬────────────────┘
       │          │               │              │
┌──────┴──┐  ┌───┴────┐   ┌─────┴─────┐  ┌────┴─────┐
│PostgreSQL│  │Collectors│  │Trust Graph │  │ OpenAI   │
│(Storage) │  │(AWS/GL)  │  │(NetworkX)  │  │ (LLM)   │
└──────────┘  └──────────┘  └───────────┘  └──────────┘
```

## Component Overview

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React 18, TypeScript, React Flow, TanStack Query | Interactive dashboard and visualizations |
| Backend API | FastAPI, Python 3.11, Pydantic | REST API serving all platform features |
| Database | PostgreSQL 15, SQLAlchemy 2.0 (async) | Persistent storage for identities, trust, and resources |
| Graph Engine | NetworkX | In-memory directed graph for trust chain traversal |
| AI Advisor | OpenAI API (GPT-4o-mini) | Natural language explanations and remediation plans |
| AWS Collector | boto3 | Discovers IAM roles, policies, and trust policies |
| GitLab Collector | python-gitlab | Discovers access tokens and OIDC configurations |
| Infrastructure | Terraform, AWS (EC2, S3, CloudFront) | Hosting and deployment |
| CI/CD | GitLab CI/CD or GitHub Actions | Automated testing, building, and deployment |

## Data Flow

```
1. Discovery Scan Triggered
       │
       ▼
2. AWS Collector ──► Retrieves IAM roles, policies, trust policies
       │
       ▼
3. GitLab Collector ──► Retrieves tokens, OIDC configs (if configured)
       │
       ▼
4. Trust Parser ──► Extracts trust relationships from policies
       │
       ▼
5. Resource Mapper ──► Maps IAM actions to resource access (Read/Write/Admin)
       │
       ▼
6. Risk Engine ──► Calculates risk scores (6 weighted factors)
       │
       ▼
7. Graph Engine ──► Rebuilds in-memory trust graph
       │
       ▼
8. Data Available ──► All tabs render from API
```

## Database Schema

Four core tables:

- **Identity** — Machine identities (IAM roles, GitLab tokens)
- **TrustRelationship** — Directed trust edges between identities
- **Resource** — AWS resources that identities can access
- **IdentityAccess** — Links identities to resources with access type

## Security Model

- Read-only access to AWS (IAMReadOnlyAccess)
- Read-only access to GitLab (read_api scope)
- No source code is read or stored
- No secret values are stored
- No customer data is collected
- AI receives only identity metadata (never credentials)
