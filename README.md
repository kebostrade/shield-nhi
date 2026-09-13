# 🛡 SHIELD-NHI — Secure Ops Non-Human Identity Governance Agent

**Amazon "Agents for Humans" Hackathon** · $10,000 Grand Prize target · deadline 14 Sep 2026

> "While every other agent writes your emails, SHIELD-NHI secures the **robots** that run your cloud."

## What it does
An AI agent that **governs Non-Human Identities** (service accounts, API keys, cloud IAM roles,
workload identities) — discovers them, risk-scores them, and proposes remediation **with
human-in-the-loop approval**. Built for SOC teams drowning in machine identities.

## Core capabilities
1. **DISCOVER** — scan AWS IAM, GitHub, Kubernetes for NHIs → unified inventory.
2. **RISK-SCORE** — every NHI scored 0–100: 🔴 leaked / 🟠 over-privileged / 🟡 unused / expiring / orphaned.
3. **GOVERN** — agent proposes remediation; human approves via a gate (rotate, decommission, least-privilege, vault).

## Security principle
**Default read-only.** The agent can only *propose* actions — any destructive step (rotate, delete,
disable) requires explicit human sign-off. This is the "safe agent ops" story enterprises want.

## Stack
- **Strands Agents SDK** (Amazon) — agent orchestration (bonus points)
- **AWS Bedrock AgentCore** — deployment (bonus)
- **Go** — backend services / connectors (Dima's native stack)
- Bedrock LLM — risk reasoning

## Build & run (current scaffold)
```bash
go mod tidy
go build -o shield-nhi .    # or: go run .

# 1) Generate risk report
./shield-nhi report

# 2) Human-in-the-loop approval (agent proposes, human approves an NHI)
./shield-nhi approve gh-001
```

## Example output
```
🔴 [CRITICAL] github-app-billing-tokens (github/org) score=80
    - key/token leaked in public repo (CRITICAL)
    - orphaned (no owner)
    • PROPOSE:rotate token immediately + revoke+audit [PENDING]   → after approve: [APPROVED]

🟡 [MEDIUM] payment-svc-serviceaccount (k8s/payment) score=45
    - credential expires in 13 days
    • PROPOSE:rotate before 2026-09-15 [PENDING]
```

## Roadmap → 14 Sep
- [x] **D1–2** Go scaffold + risk engine + mock inventory (E2E works)
- [ ] **D3–4** AWS IAM connector (read-only) — real inventory
- [ ] **D5–6** GitHub secret-scan connector
- [ ] **D7–8** Report generator (SOC2-style PDF/markdown)
- [ ] **D9** Approval gate → Slack/chat/UI
- [ ] **D10** K8s service-account connector (stretch)
- [ ] **D11–12** Dashboard + Loom demo + Devpost write-up
- [ ] **D13** QA + submit

**MVP shipped:** AWS connector + risk-score + report + approval gate.

## License / owner
© 2026 KEBOS · Dima Hlushchenko