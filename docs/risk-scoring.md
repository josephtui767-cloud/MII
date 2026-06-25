# Risk Scoring

## Overview

Every discovered identity receives a risk score from 0 to 100. The score is calculated deterministically based on six weighted factors — no AI is involved in scoring.

## Risk Factors

| Factor | Points | Condition |
|--------|--------|-----------|
| Admin Permissions | +35 | Has AdministratorAccess, PowerUserAccess, or wildcard `*:*` actions |
| Production Access | +25 | Accesses resources classified as "production" |
| Trust Relationship Count | +20 | Trusted by more than 10 other identities |
| Cross-Account Access | +20 | Has Cross_Account_Trust type relationships |
| Staleness | +15 | Not used in 90+ days |
| Unused | +10 | Has never been used (last_used_at is null) |

The final score is capped at 100. If the sum exceeds 100, it is set to 100.

## Scoring Examples

### High Risk Identity (score: 55)
- Admin permissions (+35): Has AdministratorAccess policy
- Cross-account access (+20): Trusted by external account

### Medium Risk Identity (score: 45)
- Admin permissions (+35): Has wildcard action on all resources
- Unused (+10): Has never been used

### Low Risk Identity (score: 10)
- Unused (+10): Has never been used
- No other risk factors

### Zero Risk Identity (score: 0)
- Recently used
- No admin permissions
- No production access
- Low trust count
- No cross-account trust

## Risk Score Colors

| Score Range | Color | Label |
|-------------|-------|-------|
| 60-100 | Red | High Risk |
| 35-59 | Orange | Medium Risk |
| 10-34 | Yellow | Low Risk |
| 0-9 | Green | Minimal Risk |

## When Scores Are Calculated

Risk scores are recalculated:
1. After every discovery scan completes
2. When manually triggered via `POST /api/v1/risk/recalculate`

## Missing Data Handling

If data required for a factor cannot be evaluated (e.g., no policies attached), that factor is skipped and the score is calculated from remaining factors. The `unevaluable_factors` field indicates which factors could not be assessed.
