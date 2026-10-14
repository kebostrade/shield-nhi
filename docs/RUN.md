# SHIELD-NHI — environment setup

The primary inference path is **Nebius Token Factory** (NVIDIA Nemotron, OpenAI-compatible):

```bash
export NEBIUS_API_KEY=<your-token-factory-key>   # https://tokenfactory.nebius.com/
# optional overrides:
# export NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
# export NEBIUS_MODEL=nvidia/nemotron-3-super-120b-a12b
# export NEBIUS_MODEL_FAST=...  # bulk sweeps
# export NEBIUS_MODEL_DEEP=...  # cross-signal reasoning
```

Fallback path — Amazon Bedrock with a bearer-token API key (no AWS creds needed):

```bash
export BEDROCK_API_KEY=<your-bedrock-api-key>
export AWS_REGION=us-east-1            # or your region
export BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6   # optional override
```

`nhi_models.py` picks the provider in this order: **Token Factory → Bedrock → Strands default**.
Run `python nhi_models.py` to print the resolved provider, the per-tier model ids, and the model
list your key actually serves.

Check the wiring without spending a key — a local OpenAI-compatible server captures the real
request (path, bearer auth, model id, message payload):

```bash
python tests/test_token_factory.py     # 14 checks
```

There are two run modes:

| Mode | Env | Behavior |
|---|---|---|
| **Interactive** | *(none)* | The human-approval gate prompts `Approve? [y/N]` on stdin for each destructive `remediate` call |
| **Demo / video** | `SHIELD_NHI_NO_PROMPT=1` | Gate auto-confirms so a scripted end-to-end demo runs unattended |

Example:

```bash
# Interactive (real ops)
python agent.py

# Demo (for the hackathon video)
SHIELD_NHI_NO_PROMPT=1 python agent.py
```

If you'd rather use AWS credentials (SigV4) instead of an API key, just unset
`BEDROCK_API_KEY` and configure a boto3 session / AWS CLI profile. The agent falls
back to Strands' default Bedrock model in that case.