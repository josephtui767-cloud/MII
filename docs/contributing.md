# Contributing

## Project Structure

```
mii/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI route handlers
│   │   ├── collectors/     # AWS and GitLab/GitHub data collectors
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Business logic engines
│   │   └── utils/          # Shared utilities
│   ├── alembic/            # Database migrations
│   └── tests/              # pytest test suites
├── frontend/
│   └── src/
│       ├── api/            # API client and TypeScript types
│       ├── components/     # Shared UI components
│       └── features/       # Feature modules (one per tab)
├── infra/                  # Terraform infrastructure code
├── docs/                   # Documentation
└── docker-compose.yml      # Local development
```

## Development Workflow

1. Create a feature branch from `main`
2. Make changes
3. Run tests locally
4. Push and create a merge request
5. CI pipeline runs tests and builds (GitLab CI or GitHub Actions)
6. Merge to main triggers deployment

## Backend Development

```bash
cd backend
pip install -e ".[dev]"
# Run server
uvicorn app.main:app --reload --port 8000
# Run tests
pytest tests/ -v
# Lint
ruff check app/
ruff format app/
```

## Frontend Development

```bash
cd frontend
npm install
# Run dev server
npm run dev
# Run tests
npm run test
# Type check
npx tsc --noEmit
# Build
npm run build
```

## Adding a New Security Check

1. Add the check method to `backend/app/services/findings_engine.py`
2. Call it from `generate_findings()`
3. The finding will automatically appear in the Findings tab

## Adding a New Compliance Policy

1. Add the check method to `backend/app/services/compliance_engine.py`
2. Call it from `run_all_checks()`
3. The policy will automatically appear in the Compliance tab

## Database Migrations

```bash
cd backend
# Create a new migration
alembic revision --autogenerate -m "description"
# Apply migrations
alembic upgrade head
```

## Code Style

- Backend: Python 3.11+, formatted with Ruff, type hints required
- Frontend: TypeScript strict mode, Tailwind CSS for styling
- No emojis in code (only in documentation/UI labels)
