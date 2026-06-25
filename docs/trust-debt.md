# Trust Debt

## Concept

Trust debt is the accumulation of unnecessary, overprivileged, or stale trust relationships in your identity landscape. Like technical debt in code, trust debt grows over time as permissions are granted but never reviewed or removed.

Trust debt increases attack surface, complicates audits, and creates implicit access paths that are invisible without analysis.

## How It's Measured

Trust debt is measured as a point score. Each identified debt item contributes points:

| Category | Points | Description |
|----------|--------|-------------|
| Admin on CI/CD Role | 50 | OIDC-trusted role has AdministratorAccess |
| Unused OIDC Federation | 40 | GitLab OIDC trusts a role that's never been used |
| Cross-Account No ExternalId | 35 | Cross-account trust without confused deputy protection |
| No Branch Restriction | 30 | OIDC trust allows assumption from any branch |
| Stale Trusted Identity | 25 | Role hasn't been used in 90+ days but still has active trust |
| Unused Trust Relationship | 20 | Trust relationship targets a role that's never been used |
| Wildcard Resource Access | 15 | Actions are scoped but resources target everything (*) |
| Overprivileged Service Role | 10 | Service role has more permissions than needed |

## Grading Scale

| Grade | Score Range | Meaning |
|-------|-------------|---------|
| A | 0 | No trust debt — clean environment |
| B | 1-50 | Minimal debt — minor cleanup needed |
| C | 51-150 | Moderate debt — scheduled cleanup recommended |
| D | 151-300 | Significant debt — prioritize remediation |
| F | 301+ | Critical debt — immediate action required |

## Top Contributors

The platform identifies the top 5 identities contributing the most trust debt points. These are the highest-value targets for remediation — fixing them reduces the most debt in the least effort.

## Reducing Trust Debt

1. **Remove unused OIDC federations** — Delete trust to roles that are never assumed
2. **Scope down admin on CI/CD roles** — Replace AdministratorAccess with deployment-specific policies
3. **Add branch restrictions** — Restrict OIDC trust to main/production branches only
4. **Delete stale identities** — Remove roles that haven't been used in 90+ days
5. **Add ExternalId to cross-account trust** — Prevent confused deputy attacks

## Trend Tracking

Future versions will track trust debt score over time to show whether your environment is getting cleaner or accumulating more debt.
