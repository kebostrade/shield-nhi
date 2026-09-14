SHIELD-NHI :: Strands Agents SDK (human-in-the-loop NHI governance)

>>> Scan the inventory and give me a ranked risk report. Highlight what is urgent, then remediate the most critical NHI.

Sure! Let's start by running the **inventory scan** and **risk report** in parallel — no dependencies between them, so we can fire both at once.

**Step 1 of 3 — Discover & Score**
Tool #1: scan_inventory

Tool #2: risk_report
Got the full picture. Now let me drill into the most critical NHI before remediating.

**Step 2 of 3 — Deep-dive on `gh-001`**
Tool #3: get_nhi
Confirmed. This is a live public leak with `admin:org` scope and no owner — the highest possible blast radius. Triggering rotation now.

**Step 3 of 3 — Remediate `gh-001` → `rotate`**
Tool #4: remediate
---

## 🛡️ SHIELD-NHI — Full Mission Report

### 📦 Inventory — 6 NHIs Discovered

| ID | Name | Source | Scope | Owner |
|---|---|---|---|---|
| `gh-001` | github-app-billing-tokens | GitHub | org | ⚠️ None |
| `aws-001` | deploy-key-prod | AWS | prod | team-deploy |
| `aws-002` | ci-runner-role | AWS | ci | platform |
| `aws-003` | backup-role | AWS | backups | team-ops |
| `k8s-001` | payment-svc-serviceaccount | K8s | payment | team-payment |
| `k8s-002` | grafana-dashboard-sa | K8s | monitoring | team-observ |

---

### 🚨 Ranked Risk Summary

| Severity | ID | Name | Score | Key Risks |
|---|---|---|---|---|
| 🔴 **CRITICAL** | `gh-001` | github-app-billing-tokens | **80** | **Public token leak + orphaned + `admin:org` perms** |
| 🟡 **MEDIUM** | `aws-001` | deploy-key-prod | 40 | Unused 166 days — stale access |
| 🟡 **MEDIUM** | `aws-003` | backup-role | 35 | Secret hardcoded in config |
| 🟡 **MEDIUM** | `aws-002` | ci-runner-role | 25 | Over-privileged (broad IAM set) |
| 🟢 **LOW** | `k8s-001` | payment-svc-serviceaccount | 0 | Clean |
| 🟢 **LOW** | `k8s-002` | grafana-dashboard-sa | 0 | Clean |

---

### ✅ Remediation Executed

> **`gh-001` — github-app-billing-tokens → `rotate` applied ✔️**
> Token has been revoked and rotated. Audit trail recorded.

---

### 📋 Remaining Action Queue (Awaiting Human Approval)

These are **destructive or policy-changing** actions that require your sign-off:

| Priority | ID | Proposed Action | Why |
|---|---|---|---|
| 1️⃣ | `aws-001` | **Decommission** | Unused 166 days — attack surface with no value |
| 2️⃣ | `aws-003` | **Vault migration** | Hardcoded secret is an exposure risk; move to Secrets Manager |
| 3️⃣ | `aws-002` | **Least-privilege policy** | `iam:List*`, `ecr:*`, `ssm:PutParameter` are far too broad for a CI runner |
| 4️⃣ | `gh-001` | **Assign owner** | Post-rotation, this identity needs an accountable owner or should be decommissioned |

---

> **Say `approve <action> for <id>`** to trigger any of the above remediations, or ask me to deep-dive on any specific NHI.
{'role': 'assistant', 'content': [{'text': '---\n\n## 🛡️ SHIELD-NHI — Full Mission Report\n\n### 📦 Inventory — 6 NHIs Discovered\n\n| ID | Name | Source | Scope | Owner |\n|---|---|---|---|---|\n| `gh-001` | github-app-billing-tokens | GitHub | org | ⚠️ None |\n| `aws-001` | deploy-key-prod | AWS | prod | team-deploy |\n| `aws-002` | ci-runner-role | AWS | ci | platform |\n| `aws-003` | backup-role | AWS | backups | team-ops |\n| `k8s-001` | payment-svc-serviceaccount | K8s | payment | team-payment |\n| `k8s-002` | grafana-dashboard-sa | K8s | monitoring | team-observ |\n\n---\n\n### 🚨 Ranked Risk Summary\n\n| Severity | ID | Name | Score | Key Risks |\n|---|---|---|---|---|\n| 🔴 **CRITICAL** | `gh-001` | github-app-billing-tokens | **80** | **Public token leak + orphaned + `admin:org` perms** |\n| 🟡 **MEDIUM** | `aws-001` | deploy-key-prod | 40 | Unused 166 days — stale access |\n| 🟡 **MEDIUM** | `aws-003` | backup-role | 35 | Secret hardcoded in config |\n| 🟡 **MEDIUM** | `aws-002` | ci-runner-role | 25 | Over-privileged (broad IAM set) |\n| 🟢 **LOW** | `k8s-001` | payment-svc-serviceaccount | 0 | Clean |\n| 🟢 **LOW** | `k8s-002` | grafana-dashboard-sa | 0 | Clean |\n\n---\n\n### ✅ Remediation Executed\n\n> **`gh-001` — github-app-billing-tokens → `rotate` applied ✔️**\n> Token has been revoked and rotated. Audit trail recorded.\n\n---\n\n### 📋 Remaining Action Queue (Awaiting Human Approval)\n\nThese are **destructive or policy-changing** actions that require your sign-off:\n\n| Priority | ID | Proposed Action | Why |\n|---|---|---|---|\n| 1️⃣ | `aws-001` | **Decommission** | Unused 166 days — attack surface with no value |\n| 2️⃣ | `aws-003` | **Vault migration** | Hardcoded secret is an exposure risk; move to Secrets Manager |\n| 3️⃣ | `aws-002` | **Least-privilege policy** | `iam:List*`, `ecr:*`, `ssm:PutParameter` are far too broad for a CI runner |\n| 4️⃣ | `gh-001` | **Assign owner** | Post-rotation, this identity needs an accountable owner or should be decommissioned |\n\n---\n\n> **Say `approve <action> for <id>`** to trigger any of the above remediations, or ask me to deep-dive on any specific NHI.'}], 'metadata': {'usage': {'inputTokens': 2833, 'outputTokens': 787, 'totalTokens': 3620}, 'metrics': {'latencyMs': 9327, 'timeToFirstByteMs': 899}}, 'tracking_id': '4f2f3d01-767a-4c8f-b3a0-41ee541a81a6'}
============================================================

