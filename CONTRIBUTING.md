# Contributing to MII

Thank you for your interest in contributing to Machine Identity Intelligence! This document provides guidelines and information for contributors.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/MII.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Follow the [SETUP.md](./SETUP.md) to get the platform running locally

## Development Setup

```bash
cp .env.example .env
docker-compose up --build
```

## How to Contribute

### Reporting Bugs
- Use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)
- Include steps to reproduce, expected vs actual behavior, and environment details

### Suggesting Features
- Use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)
- Describe the problem, proposed solution, and alternatives considered

### Submitting Code

1. Ensure your code follows the existing patterns in the codebase
2. Write clear commit messages
3. Keep PRs focused — one feature or fix per PR
4. Update documentation if your change affects user-facing behavior

### Code Style

**Backend (Python):**
- Follow PEP 8
- Use type hints
- Line length: 120 characters
- Run `ruff check` before committing

**Frontend (TypeScript/React):**
- Follow existing component patterns
- Use functional components with hooks
- Tailwind CSS for styling
- Run `npm run build` to verify no TypeScript errors

## Good First Issues

Looking for something to work on? Check issues labeled [`good first issue`](https://github.com/josephtui767-cloud/MII/labels/good%20first%20issue).

Some ideas:
- Add a GitHub Actions collector (discover GitHub OIDC federations)
- Add Slack/Teams webhook notifications for critical findings
- Add export to CSV format
- Add dark mode to the frontend
- Add pagination to the Trust Graph
- Add finding acknowledgement (mark as accepted risk)
- Add identity tagging/grouping

## Architecture Overview

```
backend/
├── app/
│   ├── api/           → FastAPI route handlers
│   ├── collectors/    → AWS and GitLab data collection
│   ├── models/        → SQLAlchemy database models
│   ├── schemas/       → Pydantic request/response schemas
│   ├── services/      → Business logic engines
│   └── utils/         → Shared utilities
frontend/
├── src/
│   ├── api/           → API client and types
│   ├── components/    → Shared React components
│   └── features/      → Page components by feature
infra/
├── backend.tf         → EC2 + Docker deployment
├── main.tf            → S3 + CloudFront
├── oidc-demo.tf       → Demo OIDC roles for testing
└── variables.tf       → All configurable variables
```

## Questions?

Open a [Discussion](https://github.com/josephtui767-cloud/MII/discussions) for questions that aren't bugs or feature requests.

## License

By contributing to MII, you agree that your contributions will be licensed under the MIT License.
