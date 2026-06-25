# Getting Started

## Prerequisites

- Docker and Docker Compose
- AWS account with IAM read-only access
- GitLab account (optional, for GitLab identity discovery)
- OpenAI API key (optional, for AI explanations)

## Quick Start (Local Development)

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_ORG/mii.git
# or: git clone https://gitlab.com/YOUR_ORG/mii.git
cd mii
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Start services

```bash
docker-compose up --build
```

### 4. Run database migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 5. Access the platform

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### 6. Run your first discovery scan

Click "Run Discovery" on the Identities page, or call the API:

```bash
curl -X POST http://localhost:8000/api/v1/discovery/run
```

## Development Setup (without Docker)

### Backend

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Next Steps

- [Features Guide](./features.md) — Learn about each platform feature
- [Configuration](./configuration.md) — Configure AWS, GitLab/GitHub, and OpenAI
- [Deployment Guide](./deployment.md) — Deploy to production
