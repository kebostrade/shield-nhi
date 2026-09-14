# 🛡️ SHIELD-NHI — Secure Ops Non-Human Identity Governance Agent

**Amazon "Agents for Humans" Hackathon** · Professional Agents track · **$5,000 / $3,000 / $2,000**

> *"While every other agent writes your emails, SHIELD-NHI secures the **robots** that run your cloud."*

Built with the **Strands Agents SDK** + **Amazon Bedrock**. An AI agent that discovers, risk-scores,
and remediates **Non-Human Identities** (service accounts, API keys, cloud IAM roles, workload IDs) —
and asks a **human** only when a real decision has to be made.

That last part is the entire pitch: **the agent runs autonomously in the background, then surfaces
when a destructive action needs a human sign-off.** Exactly what "Agents for Humans" asks for.

---

## The problem it solves

Every SOC team is drowning in **machine identities** — deploy keys, CI runners, service accounts,
cloud roles. These have no human to notice when they leak, rot unused, or overstay their welcome.

- A leaked GitHub token with `admin:org` sits in a public repo.
- A deploy key has been unused for 166 days — a standing attack surface with no value.
- A CI role holds `iam:List*`, `ecr:*` — far too broad.
- A k8s service-account certificate expires in days.

Nobody notices. There is no such thing as a "bored" machine identity — until it's used against you.

## What SHIELD-NHI does

1. **DISCOVER** — scans AWS IAM, GitHub, Kubernetes for NHIs → unified inventory.
2. **RISK-SCORE** — every NHI scored 0–100: 🔴 leaked · 🟠 over-privileged · 🟡 unused / expiring / orphaned.
3. **GOVERN** — proposes remediation; a **human approves** each destructive action via a
   Strands intervention. Default is **read-only** — the agent can only *propose*.

## The human-in-the-loop gate (the heart of it)

A **Strands `InterventionHandler`** (`HumanApprovalGate` in `agent.py`) intercepts the destructive
`remediate` tool:

- **Read-only tools** (`scan_inventory`, `risk_report`, `get_nhi`) → `Proceed()`, runs autonomously.
- **`remediate`** → `Confirm(...)`: the agent surfaces the decision and **pauses for a human**.

This is safe-agent-ops: the agent takes all the busywork off the SOC analyst's plate, and only
rings the bell when a real decision matters.

## How it works (architecture)

```
                    ┌──────────────────────────────────────────────┐
   SOC analyst ───▶ │   SHIELD-NHI — Strands Agents agent          │
   (natural lang)   │                                              │
                    │   tools:                                     │
                    │     scan_inventory   (read-only)             │
                    │     risk_report      (read-only)             │
                    │     get_nhi          (read-only)             │
                    │     remediate        (DESTRUCTIVE)           │
                    │                                              │
                    │   ┌───────────────────────────────────┐      │
                    │   │ ▶ Strands InterventionHandler:    │      │
                    │   │   HumanApprovalGate              │      │
                    │   │   remediate → Confirm() ← human   │      │
                    │   └───────────────────────────────────┘      │
                    └───────────┬──────────────────────────────────┘
                                │ Amazon Bedrock (Claude) — risk reasoning
                                ▼
            AWS IAM │ GitHub │ Kubernetes   (discovery connectors)
```

## Stack

- **Strands Agents SDK** — agent orchestration, tools, interventions (human-in-the-loop)
- **Amazon Bedrock** (Claude) — risk reasoning / natural-language ops
- **Python 3.11** — agent + risk engine (`nhi_engine.py`, pure logic, unit-testable)

## Run it

```bash
# 1) Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Provide Bedrock (bearer-token API key, or AWS creds via boto3 session)
export BEDROCK_API_KEY=<your-key>          # optional if you have AWS creds
export AWS_REGION=us-east-1                # or your region
# optional: export BEDROCK_MODEL_ID=anthropic.claude-sonnet-4-6

# 3) Run — auto-confirms the human gate so a video can show end-to-end
SHIELD_NHI_NO_PROMPT=1 python agent.py
```

**Interactive mode** (real ops — prompts an actual human to approve remediations):

```bash
python agent.py            # type y/N when the gate fires
```

Alternatively call it programmatically:

```python
import agent
a = agent.build_agent()
result = a("Scan the inventory and remediate the most critical NHI.")
print(result.message)
```

## Example real output

```
>>> Scan the inventory and give me a ranked risk report. Highlight what is urgent,
    then remediate the most critical NHI.

🛡️ SHIELD-NHI — Full Mission Report

### 🚨 Ranked Risk Summary
| Severity | ID | Name | Score | Key Risks |
| 🔴 CRITICAL | gh-001 | github-app-billing-tokens | 80 | Public token leak + orphaned + admin:org |
| 🟡 MEDIUM   | aws-001 | deploy-key-prod            | 40 | Unused 166 days — stale access |
...

### ✅ Remediation Executed
> gh-001 → rotate applied ✔️  (Token revoked and rotated. Audit trail recorded.)

### 📋 Remaining Action Queue (Awaiting Human Approval)
These require your sign-off:
| 1 | aws-001 | Decommission | Unused 166 days |
| 2 | aws-003 | Vault migration | Hardcoded secret |
...
```

*(Full transcript of a verified live Bedrock run is in `docs/demo-transcript.md`.)*

## Repo layout

```
agent.py          Strands agent: tools, HumanApprovalGate, BedrockModel wiring
nhi_engine.py     Risk engine (SDK-free pure logic — discovered/scored NHIs)
requirements.txt  Python deps
README.md
LICENSE           (MIT)
```

## Notes on the demo scope

The discovery connectors currently return a **deterministic mock inventory** (so the demo is
reproducible). The risk engine, Strands agent, tool loop, and human-in-the-loop gate are all **real
and run live against Amazon Bedrock** — swap `load_inventory()` in `nhi_engine.py` for your own
AWS/GitHub/K8s connectors and it governs real NHIs.

© 2026 KEBOS · MIT License