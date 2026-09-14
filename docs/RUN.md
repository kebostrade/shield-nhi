# SHIELD-NHI — environment setup

Run the agent against Amazon Bedrock with a bearer-token API key (no AWS creds needed):

```bash
export BEDROCK_API_KEY=<your-bedrock-api-key>
export AWS_REGION=us-east-1            # or your region
export BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6   # optional override
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