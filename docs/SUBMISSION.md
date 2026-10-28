# Devpost submission copy — Nebius × NVIDIA Global AI Hackathon

Track: **Personal AI**

---

## Tagline

While every other agent writes your emails, SHIELD-NHI secures the robots that run your cloud.

---

## Inspiration

Every SOC team is drowning in **non-human identities** — deploy keys, CI runner roles, k8s
service accounts, cloud IAM roles. They have no human to notice when they leak, rot unused, or
overstay their welcome. A leaked GitHub token with `admin:org` sitting in a public repo is a
standing breach; a deploy key unused for 166 days is pure attack surface with zero value. Nobody
notices, because there is no such thing as a "bored" machine identity — until it is used against you.

An "always-on personal AI" is exactly the right shape for this problem: it should watch quietly in
the background, and only interrupt a human when a real decision has to be made.

## What it does

SHIELD-NHI is an always-on, private operations agent for machine identities. It runs a
**DISCOVER → SCORE → GOVERN** loop:

1. **Discover** — pulls service accounts, API keys, IAM roles and workload identities from AWS IAM,
   GitHub and Kubernetes into one inventory.
2. **Score** — a deterministic, audit-friendly risk engine ranks each identity 0–100 using concrete
   evidence: public leak, over-broad permission sets, hardcoded secrets, days since last use,
   expiry windows, missing owner.
3. **Govern** — proposes remediation (rotate, decommission, least-privilege, vault) and **pauses for
   a human** before executing anything destructive.

The human-in-the-loop gate is the whole point: read-only tools run autonomously; the single
destructive tool (`remediate`) is intercepted by a Strands `InterventionHandler` and cannot execute
without explicit human confirmation. The default posture is read-only — the agent can only *propose*.

## How we used Nebius Token Factory + NVIDIA Nemotron

Inference is not a side feature here; **every reasoning step is a runtime call to Nebius Token
Factory** with an NVIDIA Nemotron open model (`nvidia/nemotron-3-super-120b-a12b` by default,
OpenAI-compatible endpoint `api.tokenfactory.nebius.com/v1/`).

- **Per-task model tiers** — `fast` for bulk inventory sweeps, `reason` for risk explanations,
  `deep` for cross-signal correlation, each overridable via `NEBIUS_MODEL_FAST/_REASON/_DEEP`, so
  cheap calls stay cheap and expensive reasoning is spent deliberately.
- **Evidence-backed explanations** — `explain_risk(nhi_id)` takes the engine's own record (perms,
  `last_used`, `public_leak`, expiry, fired rules) and sends it to Nemotron for a grounded,
  plain-language "why this matters / blast radius" for an on-call engineer. The prompt forbids
  inventing facts beyond the evidence, the tool prints which model id served it, and it degrades to
  the deterministic record if the API is unreachable — so a network blip never kills a run and never
  fabricates an answer.
- **Verified wiring** — `tests/test_token_factory.py` spins a local OpenAI-compatible server and
  asserts base path, bearer auth, model id and payload shape (14 checks), so the Token Factory path
  is tested without spending credits.

## What was significantly updated during the submission period

This project started as an entry for the Amazon "Agents for Humans" hackathon (Strands SDK + risk
engine + approval gate, September 2026). During this hackathon's submission period we:

- **Moved primary inference to Nebius Token Factory with NVIDIA Nemotron**, added the OpenAI-compatible
  client, per-task model tiers and the Bedrock path as an optional fallback only.
- **Rewrote `explain_risk` to be evidence-grounded and provider-aware**: live Nemotron call, model id
  reported, deterministic fallback on failure.
- **Added a hosted web console** (`webdemo.py`) over the real engine — inventory, scores, live
  explanations, and a destructive-action endpoint that returns **403 unless a human explicitly
  approved**, with an audit trail.
- **Added Token Factory wiring tests** and refreshed the README with setup, architecture and how
  Nemotron is used.

## Feedback on Nebius Token Factory / NVIDIA tools

- **The OpenAI-compatible surface is the single best decision** — dropping in `openai` with a custom
  `base_url` took minutes; no bespoke SDK, no rewrite of the agent loop.
- **Model-id discovery is the sharp edge.** Model ids are versioned and not guessable
  (`nvidia/nemotron-3-super-120b-a12b`), and a wrong id fails as a generic 400/404 rather than a
  helpful "did you mean". A `GET /v1/models`-driven picker in the console, plus a clear error code
  for an unknown model, would remove the most common onboarding failure. We mitigated it by printing
  `GET /v1/models` from `nhi_models.py` and keeping model ids in env vars, not code.
- **Per-task tiering is where the economics work**: routing bulk sweeps to a small Nemotron and
  reserving the large one for judgment calls is the difference between a demo and something you leave
  running 24/7. Documenting recommended tier mappings per workload type would help builders get there
  faster.
- **What we would use next**: Nebius Serverless Endpoints for the explanation path (so the console
  keeps working when a laptop closes) and Serverless Jobs for scheduled inventory sweeps.

## Built with

`python` · `strands-agents` · `nvidia-nemotron` · `nebius-token-factory` · `openai-sdk` ·
`aws-iam` · `github-api` · `kubernetes` · `html` · `javascript`

---

## Checklist before submitting

- [ ] `NEBIUS_API_KEY` set on the demo host so `/api/explain` shows a **live** Nemotron answer
      (without it the console shows the deterministic record and says so)
- [ ] Demo URL reachable: `https://<host>/` (health: `/healthz`)
- [ ] Public repo with license visible at top: https://github.com/kebostrade/shield-nhi (MIT)
- [ ] Demo video ≤3 min, **public on YouTube**: `~/amazon-hackathon/shield-nhi-demo-v2.mp4` (2:53)
- [ ] Track selected: **Personal AI**
