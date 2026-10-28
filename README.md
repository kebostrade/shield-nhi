# 🛡️ SHIELD-NHI — Secure Ops Non-Human Identity Governance Agent

**Nebius × NVIDIA Global AI Hackathon** · **Personal AI** track · built on **Nebius Token Factory**
*(original entry: Amazon "Agents for Humans" Hackathon, Professional Agents track)*

> *"While every other agent writes your emails, SHIELD-NHI secures the **robots** that run your cloud."*

Built with the **Strands Agents SDK** and **NVIDIA Nemotron open-source models served through
Nebius Token Factory** — every reasoning step is a runtime call to the Token Factory inference API.
The agent discovers, risk-scores, and remediates **Non-Human Identities** (service accounts, API
keys, cloud IAM roles, workload IDs) — and asks a **human** only when a real decision has to be made.

That last part is the entire pitch: **the agent runs autonomously in the background, then surfaces
when a destructive action needs a human sign-off.** Always-on, private, and read-only by default.

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

- **Read-only tools** (`scan_inventory`, `risk_report`, `get_nhi`, `explain_risk`) → `Proceed()`, runs autonomously.
- **`remediate`** → `Confirm(...)`: the agent surfaces the decision and **pauses for a human**.

This is safe-agent-ops: the agent takes all the busywork off the SOC analyst's plate, and only
rings the bell when a real decision matters.

## Evidence-backed reasoning (`explain_risk`)

A finding is only useful if you can audit it. `explain_risk(nhi_id)` takes the engine's own record —
scope, permissions, `last_used`, `public_leak`, expiry, the rules that fired — and sends it to
**NVIDIA Nemotron on Nebius Token Factory** for a grounded, plain-language explanation of why the
identity is dangerous and what the blast radius is. The tool prints the model id that served it,
and falls back to the deterministic record if the API is unreachable — so a network blip never
kills a run and never fabricates an answer.

## How it works (architecture)

```
                    ┌──────────────────────────────────────────────┐
   SOC analyst ───▶ │   SHIELD-NHI — Strands Agents agent          │
   (natural lang)   │                                              │
                    │   tools:                                     │
                    │     scan_inventory   (read-only)             │
                    │     risk_report      (read-only)             │
                    │     get_nhi          (read-only)             │
                    │     explain_risk     (read-only, live LLM)   │
                    │     remediate        (DESTRUCTIVE)           │
                    │                                              │
                    │   ┌───────────────────────────────────┐      │
                    │   │ ▶ Strands InterventionHandler:    │      │
                    │   │   HumanApprovalGate              │      │
                    │   │   remediate → Confirm() ← human   │      │
                    │   └───────────────────────────────────┘      │
                    └───────────┬──────────────────────────────────┘
                                │ Nebius Token Factory → NVIDIA Nemotron
                                │ (per-task tiers: Nano / Super / Ultra)
                                ▼
            AWS IAM │ GitHub │ Kubernetes   (discovery connectors)
```

## Stack

- **Strands Agents SDK** — agent orchestration, tools, interventions (human-in-the-loop)
- **Nebius Token Factory** — OpenAI-compatible inference; **every** agent reasoning step is a
  runtime call to `api.tokenfactory.nebius.com`
- **NVIDIA Nemotron** (open-source) — risk explanations and ops reasoning, with per-task model
  tiers (`NEBIUS_MODEL_FAST` / `_REASON` / `_DEEP`)
- **Amazon Bedrock** — optional fallback provider (bearer token), so the original run path still works
- **Python 3.11** — agent + risk engine (`nhi_engine.py`, pure logic, unit-testable)

## Live demo (hosted console)

A zero-dependency web console over the **real** risk engine — no mock UI: it loads the
inventory, scores it with `nhi_engine`, calls Nemotron through Token Factory for the
"why risky?" explanations, and enforces the same human-approval gate before any
destructive action:

```bash
.venv/bin/python webdemo.py --port 8100     # http://localhost:8100
```

- `GET /api/state` — inventory, scores, reasons, audit trail, provider status
- `GET /api/explain?id=gh-001` — live Nemotron call (falls back to the deterministic record)
- `POST /api/remediate` — **refuses with 403 unless `"approved": true`**, then writes the audit entry

## Run it

```bash
# 1) Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2) Provide the primary inference key — Nebius Token Factory
export NEBIUS_API_KEY=<your-token-factory-key>   # https://tokenfactory.nebius.com/
# optional overrides:
# export NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
# export NEBIUS_MODEL_FAST=...   NEBIUS_MODEL_DEEP=...

# 2b) Fallback (optional): Amazon Bedrock bearer token
# export BEDROCK_API_KEY=<your-key>

# 3) Run — auto-confirms the human gate so a video can show end-to-end
SHIELD_NHI_NO_PROMPT=1 python agent.py
```

Check your key and see which Nemotron ids it actually serves:

```bash
python nhi_models.py        # prints provider, tiers, and GET /v1/models
```

Verify the Token Factory wiring without spending a key (spins a local OpenAI-compatible
server and asserts path, bearer auth, model id and payload):

```bash
python tests/test_token_factory.py     # 14 checks
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
agent.py          Strands agent: tools, HumanApprovalGate, model wiring
nhi_models.py     Model layer: Nebius Token Factory (primary) → Bedrock (fallback)
nhi_engine.py     Risk engine (SDK-free pure logic — discovered/scored NHIs)
tests/            Wiring proof for the Token Factory runtime call
requirements.txt  Python deps
README.md
LICENSE           (MIT)
```

## Significant updates during the submission period

SHIELD-NHI existed before this submission window; this is what was **added** for it:

1. **Inference moved to Nebius Token Factory.** `nhi_models.py` now routes the agent's model
   through Token Factory's OpenAI-compatible API, serving **NVIDIA Nemotron** open-source models.
   The previous Bedrock path remains as an explicit fallback provider.
2. **`explain_risk` — evidence-backed decisions.** Every risk finding can now be justified in
   plain language from the engine's own evidence, with the serving model id printed in the output.
3. **Per-task model tiers.** `NEBIUS_MODEL_FAST` / `_REASON` / `_DEEP` let bulk inventory sweeps run
   on a small model while only the reasoning-heavy calls hit the large one.
4. **Wiring proof + graceful degradation.** `tests/test_token_factory.py` asserts the real HTTP
   call (path, bearer auth, model id, payload) against a local stand-in; `explain_risk` returns the
   deterministic record instead of failing when the API is unreachable.

## Notes on the demo scope

The discovery connectors currently return a **deterministic mock inventory** (so the demo is
reproducible). The risk engine, Strands agent, tool loop, and human-in-the-loop gate are all **real
and run live against NVIDIA Nemotron on Nebius Token Factory** — swap `load_inventory()` in
`nhi_engine.py` for your own AWS/GitHub/K8s connectors and it governs real NHIs.

© 2026 KEBOS · MIT License