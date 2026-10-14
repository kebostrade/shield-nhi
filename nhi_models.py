"""Model layer for SHIELD-NHI.

Primary path — **Nebius Token Factory** (OpenAI-compatible): every reasoning step in
the agent is a runtime call to the Token Factory inference API, serving **NVIDIA
open-source models** (Nemotron family).

Fallback path — Amazon Bedrock bearer-token, kept so the original AWS demo still runs.

Environment:
    NEBIUS_API_KEY      — Token Factory key (https://tokenfactory.nebius.com/)
    NEBIUS_BASE_URL     — optional, default https://api.tokenfactory.nebius.com/v1/
    NEBIUS_MODEL        — optional, default nvidia/nemotron-3-super-120b-a12b
    NEBIUS_MODEL_FAST / _REASON / _DEEP — per-task tier overrides (see MODEL_TIERS)
    BEDROCK_API_KEY     — fallback provider key
"""
from __future__ import annotations

import os
from typing import Any, Iterable

# Verified against the Token Factory docs (OpenAI-compatible inference API).
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"

# Task tiers: cheap model for bulk sweeps, strong model only where reasoning is needed.
# IDs are env-overridable, because the served catalogue changes — see list_models().
TIER_ENV = {"fast": "NEBIUS_MODEL_FAST", "reason": "NEBIUS_MODEL_REASON", "deep": "NEBIUS_MODEL_DEEP"}


def base_url() -> str:
    return (os.environ.get("NEBIUS_BASE_URL") or DEFAULT_BASE_URL).rstrip("/") + "/"


def token_factory_enabled() -> bool:
    return bool(os.environ.get("NEBIUS_API_KEY"))


def model_for(tier: str = "reason") -> str:
    """Model id for a task tier. Unset tier falls back to NEBIUS_MODEL, then the default."""
    env_name = TIER_ENV.get(tier)
    if env_name and os.environ.get(env_name):
        return os.environ[env_name]
    return os.environ.get("NEBIUS_MODEL") or DEFAULT_MODEL


def token_factory_client():
    """OpenAI-compatible client bound to Nebius Token Factory."""
    if not token_factory_enabled():
        raise RuntimeError("NEBIUS_API_KEY is not set — Token Factory is the primary path.")
    from openai import OpenAI

    return OpenAI(base_url=base_url(), api_key=os.environ["NEBIUS_API_KEY"], timeout=60.0)


def chat(tier: str, messages: Iterable[dict[str, Any]], **params: Any) -> str:
    """One runtime call to Token Factory. Returns the assistant text.

    This is the call the hackathon rules look for: it goes over the wire to
    api.tokenfactory.nebius.com on every invocation — not a cached or offline path.
    """
    client = token_factory_client()
    body: dict[str, Any] = {"model": model_for(tier), "messages": list(messages)}
    body.update({"max_tokens": 700, "temperature": 0.2})
    body.update(params)
    resp = client.chat.completions.create(**body)
    choice = resp.choices[0]
    return (choice.message.content or "").strip()


def list_models() -> list[str]:
    """GET /v1/models — the honest way to discover servable ids for this key."""
    return [m.id for m in token_factory_client().models.list().data]


def build_model():
    """Strands model object, or None (Strands then falls back to its own default).

    Order: Nebius Token Factory (primary) → Bedrock bearer token (fallback).
    """
    if token_factory_enabled():
        from strands.models.openai import OpenAIModel

        # NOTE: OpenAIModel takes its config as **kwargs (Unpack[OpenAIConfig]), not as a
        # dict — passing {"model_id": ...} silently lands as an invalid config key and the
        # model id never reaches the request.
        return OpenAIModel(
            client=token_factory_client(),
            model_id=model_for("reason"),
            params={"max_tokens": 2048, "temperature": 0.2},
        )

    if os.environ.get("BEDROCK_API_KEY"):
        from strands.models.bedrock import BedrockModel

        return BedrockModel(
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            api_key=os.environ["BEDROCK_API_KEY"],
            model_id=os.environ.get("BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-6"),
        )

    return None


def active_provider() -> str:
    if token_factory_enabled():
        return f"nebius-token-factory ({base_url()} · {model_for('reason')})"
    if os.environ.get("BEDROCK_API_KEY"):
        return "bedrock (bearer token)"
    return "none (Strands default)"


if __name__ == "__main__":  # tiny self-check: python nhi_models.py
    print("provider :", active_provider())
    print("tiers    :", {t: model_for(t) for t in ("fast", "reason", "deep")})
    if token_factory_enabled():
        ids = list_models()
        print(f"models   : {len(ids)} served")
        for i in ids[:25]:
            print("   ", i)
    else:
        print("models   : set NEBIUS_API_KEY to enumerate")
