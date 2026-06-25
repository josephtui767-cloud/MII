# Launch Posts — Copy & Paste

Pre-written posts for announcing MII. Customize as needed.

---

## Hacker News (Show HN)

**Title:** Show HN: MII — Open-source machine identity security (IAM roles outnumber humans 82:1)

**Text:**
Hi HN,

I built MII (Machine Identity Intelligence) — an open-source platform that discovers, maps, and risk-scores machine identities across AWS and CI/CD pipelines.

The problem: Machine identities (IAM roles, service accounts, OIDC federations, CI/CD tokens) outnumber human identities 82:1 in modern cloud environments (CyberArk 2025 report). They're the #1 attack vector for cloud breaches, yet most organizations have zero visibility into them.

What MII does:
- Discovers all IAM roles, trust policies, and OIDC federations across AWS accounts
- Builds a directed trust graph showing who can assume whom
- Scores every identity 0-100 based on 6 risk factors
- Simulates "blast path" — what happens if an identity is compromised
- Measures "trust debt" (like tech debt, but for permissions) graded A-F
- 8 automated compliance checks with pass/fail evidence
- AI-powered remediation plans with exact CLI commands
- Export reports as PDF/Markdown/Excel

Tech stack: FastAPI + React + PostgreSQL + NetworkX + Terraform

Supports AWS Organizations (auto-discover 100+ accounts), any OpenAI-compatible AI provider (including Ollama for free local inference).

GitHub: https://github.com/josephtui767-cloud/MII

Would love feedback from anyone dealing with cloud identity sprawl.

---

## Reddit — r/netsec

**Title:** [Open Source] MII: Machine Identity Intelligence — discover and risk-score IAM roles, OIDC federations, and CI/CD tokens across AWS

**Text:**
Released an open-source tool for a problem I kept hitting: no visibility into machine identities.

CyberArk's 2025 report found machine identities outnumber humans 82:1. Every IAM role, every OIDC federation from CI/CD to AWS, every service account — they pile up with no one monitoring them.

MII connects to your AWS account (read-only) and:

1. **Discovers** every IAM role and trust relationship
2. **Maps** them into a directed trust graph
3. **Scores** each one 0-100 (admin permissions, cross-account trust, staleness, etc.)
4. **Simulates** blast paths — "if this identity is compromised, what's the damage?"
5. **Measures** trust debt — unnecessary permissions accumulated over time
6. **Generates** remediation plans with specific AWS CLI commands

Also supports GitLab CI/CD identity discovery (finds OIDC federations to AWS).

Docker Compose for local dev, Terraform for AWS deployment (EC2 + CloudFront).

MIT licensed: https://github.com/josephtui767-cloud/MII

Happy to answer questions about the architecture or methodology.

---

## Reddit — r/aws

**Title:** [Open Source] Built a tool to discover and risk-score all IAM roles + OIDC trust relationships across AWS accounts

**Text:**
If you're running multiple AWS accounts, you probably have hundreds of IAM roles with trust policies you've never audited. I built MII to solve this.

What it does:
- Scans all IAM roles across your AWS accounts (read-only, uses IAMReadOnlyAccess)
- Parses trust policies to find OIDC federations, cross-account trust, wildcard principals
- Builds a graph of "who can assume whom"
- Scores every role based on risk factors (admin access + OIDC = critical)
- Simulates attack paths through the trust chain
- Supports AWS Organizations for auto-discovering all accounts

Findings it catches:
- OIDC role with AdministratorAccess (any CI/CD pipeline = full admin)
- Cross-account trust without ExternalId (confused deputy)
- Wildcard principals in trust policies (any AWS identity worldwide can assume)
- Unused roles with active trust policies (dormant backdoors)

Self-hosted, MIT licensed, Docker Compose to get started in 5 minutes.

https://github.com/josephtui767-cloud/MII

---

## Reddit — r/devsecops

**Title:** [Open Source] MII — machine identity security platform with trust graph, blast path simulation, and AI remediation

**Text:**
Built this for DevSecOps teams dealing with identity sprawl in AWS + CI/CD.

The unique parts:
- **Trust Debt scoring** — measures accumulated unnecessary permissions like you'd measure tech debt. Graded A through F.
- **Blast Path Simulation** — pick any identity, simulate compromise, see every resource reachable through the trust chain
- **Trust Graph** — visual directed graph of all trust relationships (OIDC, AssumeRole, Cross-Account)
- **Report Export** — PDF/Markdown/Excel for audit evidence

Works with AWS (IAM roles, OIDC) and GitLab (CI/CD identities). Supports AWS Organizations for large-scale environments.

Stack: FastAPI, React, PostgreSQL, NetworkX, Terraform. AI remediation via any OpenAI-compatible API (or Ollama for free local inference).

Setup: `docker-compose up --build` + set your AWS account ID.

MIT: https://github.com/josephtui767-cloud/MII

---

## LinkedIn

**Post:**

Machine identities outnumber human identities 82:1 in modern cloud environments.

Every IAM role, every OIDC federation from your CI/CD pipeline to AWS, every service account — they accumulate silently. No one monitors them. No one audits them. Each one is a potential attack vector.

I built MII (Machine Identity Intelligence) to solve this blind spot.

It's an open-source platform that:
- Discovers all machine identities across AWS accounts
- Maps trust relationships into a visual graph
- Scores every identity 0-100 for risk
- Simulates "what if this identity is compromised?"
- Measures trust debt (like tech debt, but for permissions)
- Generates AI-powered remediation plans

For security teams: prioritized findings with copy-paste remediation commands.
For managers: executive dashboard with compliance scores.
For auditors: automated policy checks with exportable evidence.

Self-hosted. MIT licensed. No vendor lock-in.

GitHub: https://github.com/josephtui767-cloud/MII

#CloudSecurity #IAM #DevSecOps #OpenSource #MachineIdentity #CyberSecurity

---

## Twitter/X Thread

**Tweet 1:**
Machine identities outnumber humans 82:1 in cloud environments.

They're the #1 attack vector — yet most orgs have ZERO visibility into them.

I built an open-source platform to fix this. Thread 🧵

**Tweet 2:**
MII (Machine Identity Intelligence) discovers, maps, and risk-scores every IAM role, OIDC federation, and CI/CD token across your AWS accounts.

One command to start:
```
docker-compose up --build
```

**Tweet 3:**
What makes it different:

- Trust Graph — visual map of who can assume whom
- Blast Path — "if compromised, what's the damage?"
- Trust Debt — like tech debt, but for permissions (A-F grading)
- AI Remediation — exact CLI commands to fix issues

**Tweet 4:**
Real findings it catches:

- OIDC role + AdministratorAccess = any CI/CD pipeline becomes AWS admin
- Cross-account trust without ExternalId = confused deputy attack
- Unused roles with active trust = dormant backdoors

**Tweet 5:**
MIT licensed. Self-hosted. No vendor lock-in.

Works with AWS Organizations (100+ accounts).
AI via OpenAI, Azure, or free local Ollama.
Export reports as PDF/Excel for audits.

GitHub: https://github.com/josephtui767-cloud/MII

---

## Dev.to / Medium Blog Post Title Ideas

1. "How Machine Identities Became the Biggest Blind Spot in Cloud Security (and How I'm Fixing It)"
2. "I Built an Open-Source Trust Graph for AWS IAM — Here's What I Found"
3. "Trust Debt: Why Your AWS Account Has More Permission Bloat Than You Think"
4. "Blast Path Simulation: Tracing Attack Chains Through IAM Trust Relationships"
5. "From 0 to Visibility: Scanning 100+ AWS Accounts for Machine Identity Risk"
