# API Reference

Base URL: `/api/v1`

## Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service health check |

## Identity Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/identities` | List identities (paginated, filterable) |
| GET | `/identities/{id}` | Get identity detail with trusts and access |

### GET /identities Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 25 | Items per page (max 100) |
| type | string | - | Filter by identity type |
| source | string | - | Filter by source (AWS, GitLab) |
| min_risk_score | int | - | Minimum risk score (0-100) |
| has_admin | bool | - | Has admin/wildcard permissions |
| has_production_access | bool | - | Accesses production resources |
| unused_days | int | - | Unused for N+ days |
| trusted_by_gitlab | bool | - | Has OIDC/Pipeline trust from GitLab |
| cross_account | bool | - | Has cross-account trust |
| sort_by | string | risk_score | Sort field |
| sort_order | string | desc | Sort direction (asc/desc) |

## Discovery Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/discovery/run` | Trigger a discovery scan |
| GET | `/discovery/status` | Get scan status |

## Graph Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/graph/full` | Get all nodes and edges |
| GET | `/graph/traverse` | Traverse from a starting identity |
| GET | `/graph/path` | Find path between two identities |
| GET | `/graph/blast-radius/{id}` | Get blast radius for an identity |
| GET | `/graph/stats` | Graph statistics |

## Risk Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/risk/scores` | List risk scores |
| GET | `/risk/scores/{id}` | Get risk breakdown for an identity |
| POST | `/risk/recalculate` | Trigger risk recalculation |

## Security Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/security/findings` | All security findings |
| GET | `/security/compliance` | Compliance check results |
| GET | `/security/recommendations` | Prioritized recommendations |
| GET | `/security/trust-debt` | Trust debt score and breakdown |
| GET | `/security/blast-path/{id}` | Blast path from specific identity |
| GET | `/security/blast-path-gitlab` | Blast path from GitLab CI/CD |
| GET | `/security/executive-summary` | Executive dashboard data |

## AI Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ai/explain-risk` | AI risk explanation |
| POST | `/ai/explain-path` | AI trust path explanation |
| POST | `/ai/blast-radius` | AI blast radius summary |
| POST | `/ai/remediation-plan` | AI remediation plan generation |

## Report Export Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reports/identities` | Export identity inventory |
| GET | `/reports/findings` | Export security findings |
| GET | `/reports/compliance` | Export compliance report |
| GET | `/reports/trust-debt` | Export trust debt report |
| GET | `/reports/blast-path/{id}` | Export blast path simulation |

### Report Query Parameters

| Parameter | Type | Values | Description |
|-----------|------|--------|-------------|
| format | string | `pdf`, `markdown`, `excel` | Output format (default: `pdf`) |

### Response

All report endpoints return a binary file download with the appropriate Content-Type:
- PDF: `application/pdf`
- Markdown: `text/markdown`
- Excel: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

### Example

```bash
# Download findings report as Excel
curl -o findings.xlsx "http://<backend-url>:8000/api/v1/reports/findings?format=excel"

# Download compliance report as PDF
curl -o compliance.pdf "http://<backend-url>:8000/api/v1/reports/compliance?format=pdf"

# Download identity inventory as Markdown
curl -o identities.md "http://<backend-url>:8000/api/v1/reports/identities?format=markdown"
```

### POST /ai/explain-risk Request Body

```json
{
  "identity_id": "uuid"
}
```

## Interactive API Documentation

Full OpenAPI/Swagger documentation is available at:
- Swagger UI: `http://<backend-url>:8000/docs`
- ReDoc: `http://<backend-url>:8000/redoc`
