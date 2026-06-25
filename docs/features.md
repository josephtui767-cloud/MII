# Features Guide

MII provides seven main features accessible via the sidebar navigation.

## Overview (Executive Dashboard)

**Purpose:** Security posture at a glance for leadership and security managers.

**What it shows:**
- Total identities discovered
- High risk identity count
- Unused identity count
- Compliance score (percentage)
- Trust relationships and OIDC federations count
- Average risk score
- Critical and high findings count
- Top priority actions (critical findings requiring immediate attention)
- Health status badge (Healthy / Needs Attention / Critical)

**When to use:** Daily check-in, executive reporting, quick status assessment.

---

## Identities

**Purpose:** Complete inventory of all discovered machine identities with risk scores.

**What it shows:**
- Paginated table of all identities (25 per page)
- Name, type, source, account ID, risk score, last used date
- Sortable by risk score (highest first)
- Filterable by: type, source, admin privileges, production access, unused 90+ days, trusted by GitLab, cross-account

**Actions:**
- Click any row to view identity detail
- Click "Run Discovery" to scan AWS/GitLab/GitHub
- Use filters to answer specific questions

**When to use:** Investigating specific identities, finding risky roles, answering "what exists?"

**Export:** Click "Export" to download the full identity inventory as PDF, Markdown, or Excel.

---

## Findings

**Purpose:** Actionable security issues with severity, blast radius, and remediation commands.

**What it shows:**
- Total findings count by severity (Critical/High/Medium/Low)
- Each finding includes:
  - Severity badge
  - Category (Excessive Permissions, Trust Configuration, Stale Identity, etc.)
  - Description of the issue
  - Affected identity (clickable link to detail)
  - Blast radius (impact if exploited)
  - Remediation steps with copy-paste CLI commands

**Finding types:**
| Finding | Severity | Description |
|---------|----------|-------------|
| Admin on OIDC role | Critical | CI/CD pipeline can get full admin access |
| Admin without constraints | Critical | Unrestricted admin with no trust conditions |
| OIDC without branch restriction | High | Any branch can assume the role |
| Cross-account trust | High | External account can assume the role |
| Wildcard trust | Critical | Any AWS identity can assume the role |
| Unused identity | Medium | Role not used in 90+ days |
| Production without MFA | Medium | Production access without MFA requirement |

**When to use:** Prioritizing remediation work, creating security tickets, sprint planning.

**Export:** Click "Export" to download all findings as PDF, Markdown, or Excel — ready for stakeholder reporting or ticket creation.

---

## Compliance

**Purpose:** Policy checks against security best practices with pass/fail status.

**What it shows:**
- Compliance score (percentage ring)
- 8 policy checks with pass/fail/warning status
- Progress bars showing pass rate per check
- Failing identities listed (clickable for critical/high severity)
- Recommendations for failing checks

**Policy checks:**
1. No Unrestricted Admin Access (critical)
2. Least Privilege Principle (high)
3. No Stale Identities (medium)
4. OIDC Branch Restriction (high)
5. No Wildcard Trust (critical)
6. MFA for Production Access (medium)
7. Identity Ownership (low)
8. Cross-Account ExternalId (high)

**When to use:** Audit preparation, compliance reporting, tracking security hygiene over time.

**Export:** Click "Export" to download the compliance report as PDF, Markdown, or Excel — ideal for audit evidence packages.

---

## Trust Debt

**Purpose:** Measures accumulated unnecessary or overprivileged trust relationships.

**What it shows:**
- Trust debt grade (A through F)
- Total debt score (points)
- Debt by category (bar chart)
- Top 5 debt contributors (clickable to identity detail)
- All debt items with descriptions and fix recommendations

**Categories:**
| Category | Points | Description |
|----------|--------|-------------|
| Admin on CI/CD Role | 50 | OIDC role with AdministratorAccess |
| Unused OIDC Federation | 40 | OIDC trust to a role that's never used |
| No Branch Restriction | 30 | OIDC trust allows any branch |
| Stale Trusted Identity | 25 | Trusted role unused 90+ days |
| Unused Trust Relationship | 20 | Trust to a role that's never used |
| Wildcard Resource Access | 15 | Actions scoped but resources are wildcard |

**Grading:**
- A: 0 points (no debt)
- B: 1-50 points
- C: 51-150 points
- D: 151-300 points
- F: 301+ points

**When to use:** Tracking trust hygiene over time, identifying where to focus cleanup, measuring improvement.

**Export:** Click "Export" to download the trust debt breakdown as PDF, Markdown, or Excel.

---

## Blast Path

**Purpose:** Simulates what happens when an identity is compromised — traces the full attack chain.

**What it shows:**
- Attack scenario description
- Severity assessment (Critical/High/Medium/Low)
- Summary cards: identities compromised, resources accessible, production resources, max hops
- Step-by-step attack chain with numbered steps
- Compromised identities (clickable to detail)
- Compromised resources with access type and classification
- Impact analysis narrative

**Simulation modes:**
- **GitLab/GitHub CI/CD Compromise** — Simulates an attacker gaining access to your CI/CD pipeline
- **Custom Identity** — Select any identity to simulate its compromise

**When to use:** Risk assessment, incident response planning, justifying security investments, demonstrating attack impact to stakeholders.

**Export:** Click "Export" to download the blast path simulation as PDF, Markdown, or Excel — useful for incident response documentation.

---

## Trust Graph

**Purpose:** Visual map of ALL identities and trust relationships.

**What it shows:**
- All identities as nodes (color-coded by risk score)
- All trust relationships as edges (color-coded by type)
- Connected nodes in hierarchical layout, disconnected nodes in grid
- Legend explaining colors and edge types
- Click any node to navigate to identity detail

**Color coding:**
- Node border: Red = high risk, Orange = medium, Yellow = low, Green = safe
- Edge color: Purple = OIDC Federation, Red = Cross Account, Blue = AssumeRole
- Animated edges = OIDC Federation (GitLab to AWS)

**When to use:** Understanding the big picture, presenting trust landscape to teams, identifying unexpected connections.

---

## Identity Detail

**Purpose:** Deep-dive into a specific identity with all relationships, risk factors, and AI tools.

**What it shows:**
- Identity metadata (name, ARN, type, source, owner, last used, created)
- Risk score with factor breakdown (each factor's contribution)
- Trusted By list (who can assume this identity)
- Can Access list (what resources this identity reaches)

**AI Actions (requires OpenAI credits):**
- **Explain Risk** — Natural language explanation of why it's risky
- **AI Remediation Plan** — Step-by-step fix with CLI commands and Terraform code

**When to use:** Investigating a specific finding, understanding an identity's full context, generating remediation plans.
