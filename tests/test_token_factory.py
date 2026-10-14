"""Proof that SHIELD-NHI's primary path really does make a runtime HTTP call to the
Nebius Token Factory inference API — verified without needing a real key.

Spins a local OpenAI-compatible server, points the model layer at it via
NEBIUS_BASE_URL, and asserts what actually goes over the wire: path, bearer auth,
model id, and message payload. Run:

    .venv/bin/python tests/test_token_factory.py
"""
from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CAPTURED: list[dict] = []
SERVED = {"id": "chatcmpl-local", "object": "chat.completion", "created": 0,
          "model": "nvidia/nemotron-3-super-120b-a12b",
          "choices": [{"index": 0, "finish_reason": "stop",
                       "message": {"role": "assistant",
                                   "content": "gh-001 is critical because the token is public."}}],
          "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the test output clean
        pass

    def do_GET(self):
        if self.path.startswith("/v1/models"):
            body = json.dumps({"object": "list", "data": [
                {"id": "nvidia/nemotron-3-super-120b-a12b", "object": "model"},
                {"id": "nvidia/nemotron-3-nano-30b-a3b", "object": "model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode()
        CAPTURED.append({"path": self.path, "auth": self.headers.get("Authorization"),
                         "body": json.loads(raw)})
        body = json.dumps(SERVED).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> int:
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    os.environ["NEBIUS_API_KEY"] = "test-key-not-real"
    os.environ["NEBIUS_BASE_URL"] = f"http://127.0.0.1:{port}/v1/"
    os.environ.pop("BEDROCK_API_KEY", None)

    import nhi_models

    checks = []

    def check(label, cond, detail=""):
        checks.append(cond)
        print(f"{'ok  ' if cond else 'FAIL'} {label}{(' — ' + str(detail)) if detail and not cond else ''}")

    check("provider resolves to token factory", nhi_models.token_factory_enabled())
    check("base_url honours NEBIUS_BASE_URL", nhi_models.base_url() == f"http://127.0.0.1:{port}/v1/",
          nhi_models.base_url())
    check("default model is the verified Nemotron id",
          nhi_models.model_for("reason") == "nvidia/nemotron-3-super-120b-a12b",
          nhi_models.model_for("reason"))

    text = nhi_models.chat("reason", [{"role": "user", "content": "explain gh-001"}])
    check("chat() returns assistant text", "critical" in text, text)

    check("exactly one HTTP call captured", len(CAPTURED) == 1, len(CAPTURED))
    if CAPTURED:
        c = CAPTURED[0]
        check("path is /v1/chat/completions", c["path"] == "/v1/chat/completions", c["path"])
        check("bearer auth header sent", c["auth"] == "Bearer test-key-not-real", c["auth"])
        check("model id in payload", c["body"].get("model") == "nvidia/nemotron-3-super-120b-a12b",
              c["body"].get("model"))
        check("messages forwarded", c["body"]["messages"][0]["content"] == "explain gh-001")

    ids = nhi_models.list_models()
    check("list_models() reads /v1/models", len(ids) == 2, ids)

    os.environ["NEBIUS_MODEL_FAST"] = "nvidia/nemotron-3-nano-30b-a3b"
    check("tier override via env", nhi_models.model_for("fast") == "nvidia/nemotron-3-nano-30b-a3b")
    os.environ.pop("NEBIUS_MODEL_FAST")

    try:
        model = nhi_models.build_model()
        check("build_model() returns a Strands OpenAIModel",
              type(model).__name__ == "OpenAIModel", type(model).__name__)
        cfg = getattr(model, "config", {}) or {}
        check("Strands model carries the Nemotron model_id",
              cfg.get("model_id") == "nvidia/nemotron-3-super-120b-a12b", cfg)
    except Exception as exc:
        check("build_model() returns a Strands OpenAIModel", False, f"{type(exc).__name__}: {exc}")

    # agent wiring: explain_risk must be registered as a tool
    import agent as agent_mod
    names = [getattr(t, "tool_name", None) or getattr(t, "__name__", "?") for t in
             agent_mod.build_agent().tool_registry.registry.values()] if hasattr(
                 agent_mod.build_agent(), "tool_registry") else []
    check("explain_risk registered on the agent", any("explain_risk" in str(n) for n in names),
          names[:8])

    srv.shutdown()
    ok = all(checks)
    print(f"\n{sum(checks)}/{len(checks)} checks passed")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
