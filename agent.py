"""SHIELD-NHI — Strands Agents SDK implementation.

An AI agent that governs Non-Human Identities (service accounts, API keys, IAM
roles, workload identities). It discovers NHIs, risk-scores them, and proposes
remediation. Critically, every *destructive* action requires an explicit human
sign-off — implemented as a Strands ``Confirm`` intervention at the tool boundary.

Theme fit ("Agents for Humans"): the agent runs autonomously in the background
and only surfaces when a real decision needs a human. That is the entire pitch.
"""
from __future__ import annotations

import dataclasses
import json
import os

from strands import Agent, tool
from strands.interventions import InterventionHandler
from strands.interventions.actions import Confirm, Deny, Proceed

# Our SDK-free risk engine (pure logic, unit-testable).
from nhi_engine import NHI, ScoredNHI, load_inventory, render_report, score_all

# Model layer: Nebius Token Factory (primary, NVIDIA Nemotron) → Bedrock (fallback).
import nhi_models

# --------------------------------------------------------------------------
# 1) Strands tools the agent can call
# --------------------------------------------------------------------------

@tool(description="Scan the connected sources (AWS IAM / GitHub / K8s) and return the "
                  "raw Non-Human Identity inventory as JSON.")
def scan_inventory() -> str:
    inv = load_inventory()
    return json.dumps([dataclasses.asdict(n) for n in inv], indent=2)


@tool(description="Risk-score the full NHI inventory (0-100) and return the ranked report. "
                  "Ranks CRITICAL first. Read-only, deterministic.")
def risk_report() -> str:
    results = score_all()
    return render_report(results)


@tool(description="Look up the individual risk record for one NHI by its id "
                  "(e.g. 'gh-001'). Returns score, reasons, and proposed actions.")
def get_nhi(nhi_id: str) -> str:
    for r in score_all():
        if r.nhi.id == nhi_id:
            return json.dumps({
                "nhi": dataclasses.asdict(r.nhi), "risk": r.risk, "score": r.score,
                "reasons": r.reasons, "proposed": r.proposed, "approved_id": r.approved_id,
            }, indent=2)
    return f"NHI '{nhi_id}' not found."


# READ-ONLY tool — makes a direct runtime call to Nebius Token Factory (NVIDIA Nemotron)
# to explain *why* a finding matters, grounded in the engine's own evidence.
@tool(description="Explain in plain language WHY one NHI is risky, with the evidence behind "
                  "it. Read-only. Runs a live inference call on Nebius Token Factory "
                  "(NVIDIA Nemotron).")
def explain_risk(nhi_id: str) -> str:
    record = None
    for r in score_all():
        if r.nhi.id == nhi_id:
            record = r
            break
    if record is None:
        return f"NHI '{nhi_id}' not found."

    evidence = {
        "id": record.nhi.id, "source": record.nhi.source, "name": record.nhi.name,
        "scope": record.nhi.scope, "perms": record.nhi.perms, "last_used": record.nhi.last_used,
        "expires_at": record.nhi.expires_at, "public_leak": record.nhi.public_leak,
        "hardcoded": record.nhi.hardcoded, "score": record.score, "risk": record.risk,
        "reasons": record.reasons, "proposed": record.proposed,
    }
    if not nhi_models.token_factory_enabled():
        return ("NEBIUS_API_KEY not set — live explanation unavailable. Deterministic record:\n"
                + json.dumps(evidence, indent=2, ensure_ascii=False))

    prompt = (
        "You are an NHI (non-human identity) security analyst. Explain in under 120 words, "
        "for an on-call engineer, why this machine identity is risky and what the blast "
        "radius is if it leaks. Quote the concrete evidence fields (perms, last_used, "
        "public_leak, expires_at). Do not invent facts beyond the evidence.\n\n"
        f"EVIDENCE:\n{json.dumps(evidence, indent=2, ensure_ascii=False)}"
    )
    try:
        text = nhi_models.chat("reason", [{"role": "user", "content": prompt}])
        return (f"[served by {nhi_models.model_for('reason')} via Nebius Token Factory]\n\n{text}")
    except Exception as exc:  # network/key failure must not kill the agent run
        return (f"Token Factory call failed ({type(exc).__name__}: {exc}). "
                f"Deterministic record:\n{json.dumps(evidence, indent=2, ensure_ascii=False)}")


# DESTRUCTIVE tool — gated by the human-in-the-loop Confirm intervention below.
@tool(description="Remediate an NHI by applying one of its proposed actions (rotate, "
                  "decommission, least-privilege, vault). DESTRUCTIVE: requires human "
                  "approval before execution.")
def remediate(nhi_id: str, action: str) -> str:
    # This body only runs AFTER a human confirms via the Confirm intervention.
    return (f"REMEDIATED {nhi_id}: '{action}' applied. "
            f"Audit trail recorded. (simulated execution for demo)")


# --------------------------------------------------------------------------
# 2) Human-in-the-loop gate: the "Agents for Humans" story.
# --------------------------------------------------------------------------

class HumanApprovalGate(InterventionHandler):
    """Strands intervention that pauses the agent whenever it tries a destructive
    tool call. The agent surfaces the decision; a human confirms or denies."""

    name = "human-approval-gate"

    def before_tool_call(self, event):
        tool_use = getattr(event, "tool_use", None)
        tool_name = getattr(tool_use, "name", None)
        # Only gate destructive tools; everything else runs autonomously.
        if tool_name != "remediate":
            return Proceed()

        input_ = getattr(tool_use, "input", {}) or {}
        nhi_id = input_.get("nhi_id", "?")
        action = input_.get("action", "?")

        # For the public demo we auto-confirm so the video can show an end-to-end
        # run without an interactive TTY. Flip to an interactive prompt for real ops.
        if os.environ.get("SHIELD_NHI_NO_PROMPT") == "1":
            print(f"\n🛑 HUMAN APPROVAL required: remediate {nhi_id} -> '{action}'. "
                  f"(auto-confirmed, SHIELD_NHI_NO_PROMPT=1)\n")
            return Confirm(prompt=f"Approve remediation of {nhi_id}: {action}?",
                           response=True)

        # Interactive confirmation: ask the operator on stdin.
        try:
            ans = input(f"\n🛑 HUMAN APPROVAL required for {nhi_id} -> '{action}'. "
                        f"Approve? [y/N] ")
            ok = ans.strip().lower() in {"y", "yes"}
            return Confirm(prompt=f"Remediate {nhi_id}: {action}?", response=ok)
        except (EOFError, KeyboardInterrupt):
            return Deny(reason="No human available — denying by default. Safe default.")


# --------------------------------------------------------------------------
# 3) Agent assembly
# --------------------------------------------------------------------------

def build_agent() -> Agent:
    # Primary: Nebius Token Factory (NVIDIA Nemotron). Fallback: Bedrock bearer token.
    model = nhi_models.build_model()

    system_prompt = (
        "You are SHIELD-NHI, an operations AI agent that governs Non-Human Identities "
        "(machine identities: service accounts, API keys, cloud IAM roles, workload IDs).\n\n"
        "Your job: DISCOVER * SCORE * GOVERN. You run quietly in the background and only "
        "surface when a REAL decision needs a human.\n\n"
        "Behavior:\n"
        "- Use scan_inventory to see the NHIs, risk_report to rank them.\n"
        "- Use explain_risk to justify *why* a finding matters, grounded in its evidence.\n"
        "- Summarize the top risks and PROPOSE remediation actions.\n"
        "- For any destructive action you must call `remediate` — Strands will pause you "
        "and ask a human to approve. This is by design: safe-agent-ops.\n"
        "- Default read-only. Never fabricate results; report what the tools return.\n"
    )

    return Agent(
        model=model,
        tools=[scan_inventory, risk_report, get_nhi, explain_risk, remediate],
        system_prompt=system_prompt,
        interventions=[HumanApprovalGate()],
        name="SHIELD-NHI",
        description="NHI governance agent with human-in-the-loop approval",
    )


def main() -> None:
    agent = build_agent()
    print("SHIELD-NHI :: Strands Agents SDK (human-in-the-loop NHI governance)")
    print(f"model provider :: {nhi_models.active_provider()}\n")
    demo = (
        "Scan the inventory and give me a ranked risk report. "
        "Explain why the most critical NHI is dangerous, then remediate it."
    )
    print(f">>> {demo}\n")
    result = agent(demo)
    print(f"\n{result.message}\n{'='*60}\n")


if __name__ == "__main__":
    main()