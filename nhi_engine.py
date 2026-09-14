"""NHI risk engine (Python port of the Go prototype) — pure logic, no Strands.

Kept dependency-free so the risk scoring is unit-testable on its own.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# --- domain model ---

@dataclass
class NHI:
    """Non-Human Identity (machine identity in the cloud)."""
    id: str
    source: str                # aws | github | k8s | gcp | azure
    name: str
    scope: str
    perms: list[str] = field(default_factory=list)
    last_used: str = ""        # RFC3339
    owner: str = ""
    expires_at: str = ""       # RFC3339 (empty = never)
    public_leak: bool = False  # leaked key/token in a public repo
    hardcoded: bool = False    # secret hardcoded in config

@dataclass
class ScoredNHI:
    nhi: NHI
    risk: str = "LOW"         # CRITICAL | HIGH | MEDIUM | LOW
    score: int = 0            # 0-100
    reasons: list[str] = field(default_factory=list)
    proposed: list[str] = field(default_factory=list)
    approved_id: str = ""     # set when a human approves

RISK_LEVELS = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}

# --- connectors (mock inventory for the demo, matches the Go prototype) ---
def load_inventory() -> list[NHI]:
    # Mirrors the Go prototype's mockInventory so the demo stays deterministic.
    return [
        NHI(id="aws-001", source="aws", name="deploy-key-prod", scope="prod",
            perms=["s3:PutObject", "ec2:RunInstances"], owner="team-deploy",
            last_used="2026-04-01T00:00:00Z"),
        NHI(id="aws-002", source="aws", name="ci-runner-role", scope="ci",
            perms=["eks:Describe*", "iam:List*", "s3:PutObject", "ssm:PutParameter", "ecr:*"],
            owner="platform", last_used="2026-08-29T00:00:00Z"),
        NHI(id="gh-001", source="github", name="github-app-billing-tokens", scope="org",
            perms=["repo", "admin:org"], public_leak=True, last_used="2026-08-20T00:00:00Z"),
        NHI(id="k8s-001", source="k8s", name="payment-svc-serviceaccount", scope="payment",
            perms=["secrets:get"], owner="team-payment", last_used="2026-08-30T00:00:00Z",
            expires_at="2026-09-15T00:00:00Z"),
        NHI(id="aws-003", source="aws", name="backup-role", scope="backups",
            perms=["s3:ListBucket", "s3:GetObject"], owner="team-ops",
            last_used="2026-08-28T00:00:00Z", hardcoded=True),
        NHI(id="k8s-002", source="k8s", name="grafana-dashboard-sa", scope="monitoring",
            perms=["get:deployments"], owner="team-observ", last_used="2026-08-31T00:00:00Z"),
    ]

# --- risk engine ---
def _days_since(ts: str) -> int:
    try:
        return int((datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).days)
    except Exception:
        return 0

def _days_until(ts: str) -> int:
    if not ts:
        return 1 << 30
    try:
        return int((datetime.fromisoformat(ts.replace("Z", "+00:00")) - datetime.now(timezone.utc)).days)
    except Exception:
        return 1 << 30

# document-classes for the score:
UNUSED_90 = "unused %d days"
UNUSED_30 = "low activity %d days"
OVERPRIV = "over-privileged (broad permission set)"
LEAKED = "key/token leaked in public repo (CRITICAL)"
HARDCODED = "secret hardcoded in config"
EXPIRING = "credential expires in %d days"
ORPHANED = "orphaned (no owner)"

def score(n: NHI) -> ScoredNHI:
    s = ScoredNHI(nhi=n)
    score = 0

    # Unused
    d = _days_since(n.last_used)
    if d > 90:
        score += 40
        s.reasons.append(UNUSED_90 % d)
        s.proposed.append("decommission (human approval)")
    elif d > 30:
        score += 15
        s.reasons.append(UNUSED_30 % d)

    # Over-privileged (heuristic: >=5 broad write/admin perms)
    if len(n.perms) >= 5:
        score += 25
        s.reasons.append(OVERPRIV)
        s.proposed.append("apply least-privilege policy patch")

    # Public leak -> critical
    if n.public_leak:
        score += 60
        s.reasons.append(LEAKED)
        s.proposed.append("rotate token immediately + revoke+audit")

    # Hardcoded secret
    if n.hardcoded:
        score += 35
        s.reasons.append(HARDCODED)
        s.proposed.append("move to secrets manager / vault")

    # Expiring
    d = _days_until(n.expires_at)
    if 0 < d < 30:
        score += 45
        s.reasons.append(EXPIRING % d)
        s.proposed.append("rotate before %s" % n.expires_at[:10])

    # Orphaned (no owner)
    if not n.owner:
        score += 20
        s.reasons.append(ORPHANED)
        s.proposed.append("assign owner or decommission")

    if score >= 80:
        s.risk = "CRITICAL"
    elif score >= 50:
        s.risk = "HIGH"
    elif score >= 25:
        s.risk = "MEDIUM"
    else:
        s.risk = "LOW"
    s.score = min(100, score)
    return s

def score_all(inventory: list[NHI] | None = None) -> list[ScoredNHI]:
    inventory = inventory or load_inventory()
    results = [score(n) for n in inventory]
    results.sort(key=lambda r: r.score, reverse=True)
    return results

def render_report(results: list[ScoredNHI]) -> str:
    out = ["ARCHIVE: NHI-Governance Risk Report", "Generated: %s" % datetime.now(timezone.utc).isoformat(),
           "-" * 54, ""]
    for r in results:
        icon = RISK_LEVELS.get(r.risk, "·")
        out.append(f"{icon} [{r.risk}] {r.nhi.name} ({r.nhi.source}/{r.nhi.scope}) score={r.score}")
        for why in r.reasons:
            out.append(f"    - {why}")
        for p in r.proposed:
            status = "APPROVED" if r.approved_id == r.nhi.id else "PENDING"
            out.append(f"    • PROPOSE:{p} [{status}]")
        out.append("")
    return "\n".join(out)

def to_json(results: list[ScoredNHI]) -> str:
    return json.dumps([dict({"nhi": asdict(r.nhi), "risk": r.risk, "score": r.score,
                             "reasons": r.reasons, "proposed": r.proposed,
                             "approved_id": r.approved_id}) for r in results], indent=2)