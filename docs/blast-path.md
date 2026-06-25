# Blast Path Simulation

## Concept

Blast Path Simulation answers: "What happens if this identity is compromised?"

It traces the complete attack chain from a starting identity through all trust relationships, identifying every reachable identity and resource. This provides a concrete understanding of the blast radius — the total impact of a single identity compromise.

## How It Works

1. **Start** — Select an identity (or use the GitLab CI/CD compromise preset)
2. **Trace Trust Chains** — BFS traversal through outgoing trust relationships (max 10 hops)
3. **Enumerate Resources** — For each compromised identity, find all accessible resources
4. **Calculate Severity** — Based on production resources, admin access, and high-risk identities reached
5. **Generate Narrative** — Human-readable impact summary

## Simulation Modes

### GitLab CI/CD Compromise
Simulates an attacker gaining access to your CI/CD pipeline (via compromised credentials, malicious merge request, or supply chain attack). The simulation starts from the GitLab OIDC identity with the most outgoing trust connections.

### Custom Identity
Select any identity from the dropdown to simulate its compromise. Useful for:
- Testing "what if" scenarios
- Validating that high-risk roles are properly isolated
- Demonstrating impact to stakeholders

## Output

### Attack Steps
Numbered sequence showing each hop in the attack chain:
- Step action (e.g., "Assume role via OIDC token")
- Source and target identities
- Trust type used
- Risk level of each step

### Compromised Identities
All identities reachable from the starting point, with:
- Name and type
- Risk score
- Hop count (distance from starting identity)

### Compromised Resources
All resources accessible through the attack chain:
- Resource name and type
- Access level (Read/Write/Admin)
- Classification (production/unclassified)
- Which identity provides access

### Severity Calculation

| Condition | Severity |
|-----------|----------|
| Admin access to resources OR >3 production resources OR >2 high-risk identities | Critical |
| Any production resources OR >5 identities compromised | High |
| Any identities compromised | Medium |
| No identities reachable | Low |

## Use Cases

- **Risk Assessment** — Quantify the impact of a potential compromise
- **Incident Response Planning** — Know which resources to monitor after a breach
- **Security Investment Justification** — Show concrete attack paths to justify remediation budget
- **Architecture Review** — Validate that trust relationships are properly scoped
