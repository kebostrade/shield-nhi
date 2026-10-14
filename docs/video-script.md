# 🎬 SHIELD-NHI — demo video script (≤ 3:00, hard cap)

Rules say: **under three minutes**, must show the project actually running on the device it was
built for, must be publicly visible on YouTube. Judges are not required to watch past 3:00 — so the
proof must land before 2:40.

## Pre-flight (before you hit record)

```bash
cd ~/amazon-hackathon/shield-nhi
export NEBIUS_API_KEY=<your-key>
python nhi_models.py          # confirm: provider = nebius-token-factory, and note a REAL model id
```
- Terminal font ≥ 16 pt, dark theme, window resized so nothing needs scrolling.
- Close notifications/Telegram.
- Have a second terminal pane ready for the raw API proof (below).
- `SHIELD_NHI_NO_PROMPT=1` only for the unattended segment; the gate segment must be interactive.

---

## Shot list

### 0:00 – 0:18 — The problem (voice over a static slide or a terminal)
> "Every company now has more machine identities than people — service accounts, CI keys, cloud
> roles. Nobody notices when they leak, because there's no human attached to them."

Show the line: `gh-001 · github-app-billing-tokens · public leak · admin:org`

### 0:18 – 0:40 — What SHIELD-NHI is
> "SHIELD-NHI is an always-on agent that discovers those identities, risk-scores them, and fixes
> them — but it can only *propose*. Destructive actions stop and wait for a human."

Show the four tools list on screen (`scan_inventory`, `risk_report`, `get_nhi`, `explain_risk`,
`remediate` — last one marked DESTRUCTIVE).

### 0:40 – 1:15 — Live run: discover + score
```bash
SHIELD_NHI_NO_PROMPT=1 python agent.py
```
Let the first lines show:
```
SHIELD-NHI :: Strands Agents SDK (human-in-the-loop NHI governance)
model provider :: nebius-token-factory (https://api.tokenfactory.nebius.com/v1/ · nvidia/nemotron-...)
```
Say: *"That line is the point — the agent's reasoning runs on Nemotron through Nebius Token
Factory, live, on every call."* Then show the ranked risk report as it prints.

### 1:15 – 1:50 — Evidence, not opinion (`explain_risk`)
In the second pane, prove the call is real:
```bash
# the same request the tool makes, on camera
.venv/bin/python - <<'PY'
import nhi_models, json
print("base_url:", nhi_models.base_url())
print("model   :", nhi_models.model_for("reason"))
print(nhi_models.chat("reason", [{"role":"user","content":"In one sentence: why is a public admin:org token dangerous?"}]))
PY
```
> "The explanation isn't a template — it comes back from Nemotron, grounded in the finding's own
> evidence record: permissions, last use, leak flag."

Then in the agent output show the same: `[served by <model-id> via Nebius Token Factory]`.

### 1:50 – 2:25 — The human gate (the whole pitch)
Re-run interactively and **let the prompt appear on screen**:
```bash
python agent.py
```
```
🛑 HUMAN APPROVAL required for gh-001 -> 'rotate'. Approve? [y/N]
```
Type `y` on camera. Say: *"Everything else ran autonomously. This one stopped, because the agent
is not allowed to destroy anything without a person."*
Then type `n` once on a second remediation and show: `denied by default — safe default`.

### 2:25 – 2:45 — What's new in this submission
> "Since the submission window opened: inference moved to Nebius Token Factory running NVIDIA
> Nemotron; a new `explain_risk` tool that justifies every finding with its evidence; per-task model
> tiers so bulk sweeps run cheap; and a wiring test that asserts the real HTTP call."

Show `python tests/test_token_factory.py` → `14/14 checks passed`.

### 2:45 – 3:00 — Close
Show the repo URL on screen and read it once: `github.com/kebostrade/shield-nhi` (MIT).

---

## Absolute musts

- [ ] The phrase **Nebius Token Factory** and the **live call** appear on screen (not just in text)
- [ ] A **NVIDIA Nemotron model id** is visible in the output
- [ ] The **human approval prompt** is visible and answered on camera
- [ ] Runtime under **3:00** — trim the report scrolling, never the proof shots
- [ ] Upload to YouTube as **Public** (unlisted does not count), paste the link into the Devpost form
- [ ] Repo is **public + MIT visible in the About section**
- [ ] Devpost text description uses §4a/§4b/§4c/§4d from `~/money/hackathon-pack-2026-10-14.md`

## If something breaks on camera
`explain_risk` falls back to the deterministic record with a visible reason string — that is honest
behaviour and worth showing rather than hiding, but the video still needs at least one successful
live Nemotron answer to prove the integration.
