"""SHIELD-NHI — hosted web demo (stdlib only HTTP layer).

Serves a small operations console over the REAL risk engine:
  GET  /                      -> dashboard (single page)
  GET  /api/state             -> inventory + scores + audit trail + provider status
  GET  /api/explain?id=...    -> live Nemotron explanation via Nebius Token Factory
                                 (falls back to the deterministic evidence record)
  POST /api/remediate         -> {"id": "...", "action": "...", "approved": true}
                                 Destructive action — refuses unless a human approved.

Run:  .venv/bin/python webdemo.py [--port 8100]
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import nhi_engine
import nhi_models

PORT = 8100
for i, a in enumerate(sys.argv):
    if a == "--port" and i + 1 < len(sys.argv):
        PORT = int(sys.argv[i + 1])

AUDIT: list[dict] = []


def state() -> dict:
    results = nhi_engine.score_all()
    items = []
    for r in results:
        items.append({
            "id": r.nhi.id, "source": r.nhi.source, "name": r.nhi.name,
            "scope": r.nhi.scope, "perms": r.nhi.perms, "owner": r.nhi.owner,
            "last_used": r.nhi.last_used, "expires_at": r.nhi.expires_at,
            "public_leak": r.nhi.public_leak, "hardcoded": r.nhi.hardcoded,
            "risk": r.risk, "score": r.score, "reasons": r.reasons,
            "proposed": r.proposed,
        })
    return {
        "count": len(items),
        "items": items,
        "audit": AUDIT[-20:],
        "provider": {
            "token_factory": nhi_models.token_factory_enabled(),
            "active": nhi_models.active_provider(),
            "model": nhi_models.model_for("reason") if nhi_models.token_factory_enabled() else None,
        },
    }


def explain(nhi_id: str) -> dict:
    record = next((r for r in nhi_engine.score_all() if r.nhi.id == nhi_id), None)
    if record is None:
        return {"error": f"NHI '{nhi_id}' not found"}
    evidence = {
        "id": record.nhi.id, "source": record.nhi.source, "name": record.nhi.name,
        "scope": record.nhi.scope, "perms": record.nhi.perms,
        "last_used": record.nhi.last_used, "expires_at": record.nhi.expires_at,
        "public_leak": record.nhi.public_leak, "hardcoded": record.nhi.hardcoded,
        "score": record.score, "risk": record.risk, "reasons": record.reasons,
        "proposed": record.proposed,
    }
    if not nhi_models.token_factory_enabled():
        return {"source": "deterministic", "model": None,
                "text": "NEBIUS_API_KEY not set on this instance — showing the deterministic "
                        "evidence record instead of a live model call.\n\n"
                        + json.dumps(evidence, indent=2, ensure_ascii=False),
                "evidence": evidence}
    prompt = (
        "You are an NHI (non-human identity) security analyst. Explain in under 120 words, "
        "for an on-call engineer, why this machine identity is risky and what the blast "
        "radius is if it leaks. Quote the concrete evidence fields (perms, last_used, "
        "public_leak, expires_at). Do not invent facts beyond the evidence.\n\n"
        f"EVIDENCE:\n{json.dumps(evidence, indent=2, ensure_ascii=False)}"
    )
    model = nhi_models.model_for("reason")
    try:
        text = nhi_models.chat("reason", [{"role": "user", "content": prompt}])
        return {"source": "nebius", "model": model, "text": text, "evidence": evidence}
    except Exception as exc:
        return {"source": "fallback", "model": model,
                "text": f"Token Factory call failed ({type(exc).__name__}: {exc}). "
                        f"Deterministic record:\n" + json.dumps(evidence, indent=2, ensure_ascii=False),
                "evidence": evidence}


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHIELD-NHI — NHI Governance Console</title>
<style>
:root{--bg:#0b0f14;--panel:#121a23;--line:#1e2a36;--txt:#dce6f2;--dim:#7d93aa;
--crit:#ff4d5e;--high:#ff9f43;--med:#ffd166;--low:#3ddc97;--acc:#4ea1ff}
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(1200px 600px at 20% -10%,#16222e 0%,var(--bg) 60%);
color:var(--txt);font:14px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
header{display:flex;align-items:center;gap:14px;padding:18px 26px;border-bottom:1px solid var(--line);
background:rgba(10,15,20,.7);backdrop-filter:blur(6px);position:sticky;top:0;z-index:5}
h1{font-size:17px;margin:0;letter-spacing:.3px}
.sub{color:var(--dim);font-size:12px}
.badge{margin-left:auto;font-size:12px;padding:5px 10px;border-radius:999px;border:1px solid var(--line);
background:var(--panel);color:var(--dim)}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:7px;vertical-align:1px}
main{padding:22px 26px;max-width:1180px;margin:0 auto}
.summary{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:18px}
.pill{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px 14px;font-size:13px}
.pill b{font-size:19px;display:block;margin-top:2px}
table{width:100%;border-collapse:separate;border-spacing:0 8px}
th{text-align:left;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim);
padding:0 12px 4px;font-weight:600}
td{background:var(--panel);padding:12px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);
vertical-align:top}
td:first-child{border-left:1px solid var(--line);border-radius:10px 0 0 10px}
td:last-child{border-right:1px solid var(--line);border-radius:0 10px 10px 0}
.sc{font-variant-numeric:tabular-nums;font-weight:700;font-size:17px}
.r-CRITICAL{color:var(--crit)}.r-HIGH{color:var(--high)}.r-MEDIUM{color:var(--med)}.r-LOW{color:var(--low)}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px}
.why{color:var(--dim);font-size:12px;margin-top:4px}
button{font:inherit;font-size:12px;padding:7px 11px;border-radius:8px;border:1px solid var(--line);
background:#16222e;color:var(--txt);cursor:pointer}
button:hover{border-color:var(--acc);color:#fff}
button.danger{border-color:#4b2028;background:#1e1216;color:#ff8f9b}
button:disabled{opacity:.45;cursor:not-allowed}
.actions{display:flex;gap:8px;flex-wrap:wrap}
pre{white-space:pre-wrap;font-size:12px;color:var(--dim);margin:8px 0 0}
.explain{grid-column:1/-1;background:#0e161f;border:1px dashed var(--line);border-radius:10px;
padding:12px;margin-top:10px;display:none}
.explain.on{display:block}
.explain b{color:var(--acc);font-size:12px;letter-spacing:.04em}
.audit{margin-top:26px}
.audit h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--dim)}
.audit li{margin:6px 0;color:var(--dim);font-size:12.5px}
footer{color:#54677a;font-size:11.5px;padding:26px;text-align:center}
</style></head><body>
<header>
  <div><h1>🛡️ SHIELD-NHI</h1>
  <div class="sub">Non-Human Identity governance · Strands agent + NVIDIA Nemotron on Nebius Token Factory</div></div>
  <div class="badge" id="prov">checking provider…</div>
</header>
<main>
  <div class="summary" id="summary"></div>
  <table><thead><tr><th>Risk</th><th>Identity</th><th>Source / scope</th><th>Evidence</th><th>Action</th></tr></thead>
  <tbody id="rows"></tbody></table>
  <div class="audit"><h2>Human approval audit trail</h2><ul id="audit"><li>no actions yet</li></ul></div>
</main>
<footer>Read-only by default · every destructive action requires explicit human approval ·
demo inventory is synthetic</footer>
<script>
const esc = s => (s??'').toString().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let DATA = null;

async function load() {
  const r = await fetch('/api/state'); DATA = await r.json();
  const p = DATA.provider;
  const badge = document.getElementById('prov');
  if (p.token_factory) {
    badge.innerHTML = '<span class="dot" style="background:#3ddc97"></span>Nebius Token Factory · ' + esc(p.model);
  } else {
    badge.innerHTML = '<span class="dot" style="background:#ffd166"></span>deterministic mode · set NEBIUS_API_KEY for live Nemotron';
  }
  const crit = DATA.items.filter(i => i.risk === 'CRITICAL').length;
  const high = DATA.items.filter(i => i.risk === 'HIGH').length;
  document.getElementById('summary').innerHTML =
    `<div class="pill">Identities discovered<b>${DATA.count}</b></div>
     <div class="pill">Critical<b class="r-CRITICAL">${crit}</b></div>
     <div class="pill">High<b class="r-HIGH">${high}</b></div>
     <div class="pill">Awaiting approval<b>${DATA.items.filter(i=>i.proposed.length).length}</b></div>`;
  document.getElementById('rows').innerHTML = DATA.items.map(i => `
    <tr data-id="${esc(i.id)}">
      <td><span class="sc r-${esc(i.risk)}">${i.score}</span><div class="why">${esc(i.risk)}</div></td>
      <td><div class="mono">${esc(i.id)}</div><div>${esc(i.name)}</div>
          <div class="why">owner: ${esc(i.owner || '— none —')}</div></td>
      <td><div>${esc(i.source)} · ${esc(i.scope)}</div>
          <div class="why mono">${esc((i.perms||[]).join(' '))}</div></td>
      <td>${(i.reasons||[]).slice(0,3).map(x=>`<div class="why">• ${esc(x)}</div>`).join('')}</td>
      <td><div class="actions">
        <button onclick="why('${esc(i.id)}', this)">Why risky?</button>
        ${(i.proposed||[]).slice(0,1).map(a=>`<button class="danger" onclick="fix('${esc(i.id)}','${esc(a)}')">Remediate</button>`).join('')}
      </div><div class="explain" id="ex-${esc(i.id)}"></div></td>
    </tr>`).join('');
  renderAudit();
}
function renderAudit(){
  const ul = document.getElementById('audit');
  ul.innerHTML = (!DATA.audit || !DATA.audit.length) ? '<li>no actions yet</li>' :
    DATA.audit.slice().reverse().map(a =>
      `<li>✅ <b>${esc(a.id)}</b> — ${esc(a.action)} · approved by human · ${esc(a.at)}</li>`).join('');
}
async function why(id, btn){
  const box = document.getElementById('ex-' + id);
  box.classList.add('on'); box.innerHTML = '<b>EXPLAINING…</b>';
  btn.disabled = true;
  try {
    const r = await fetch('/api/explain?id=' + encodeURIComponent(id));
    const j = await r.json();
    const tag = j.source === 'nebius' ? `NVIDIA Nemotron via Nebius Token Factory · ${esc(j.model)}`
              : j.source === 'deterministic' ? 'deterministic evidence record (no API key on this instance)'
              : 'fallback — Token Factory unreachable';
    box.innerHTML = `<b>WHY THIS MATTERS — ${tag}</b><pre>${esc(j.text)}</pre>`;
  } catch(e) { box.innerHTML = '<b>ERROR</b><pre>' + esc(e) + '</pre>'; }
  btn.disabled = false;
}
async function fix(id, action){
  // The human-in-the-loop gate, in the browser: nothing happens without an explicit click.
  if (!confirm('DESTRUCTIVE ACTION\n\nRemediate ' + id + '\nAction: ' + action + '\n\nApprove as the human operator?')) {
    document.getElementById('ex-' + id).classList.add('on');
    document.getElementById('ex-' + id).innerHTML =
      '<b>DENIED BY HUMAN</b><pre>No change applied. Safe default preserved.</pre>';
    return;
  }
  const r = await fetch('/api/remediate', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({id, action, approved: true})});
  const j = await r.json();
  const box = document.getElementById('ex-' + id);
  box.classList.add('on');
  box.innerHTML = `<b>${j.ok ? 'REMEDIATED (human-approved)' : 'REFUSED'}</b><pre>${esc(j.message)}</pre>`;
  if (j.ok) { AUDIT_PUSH(j.audit); }
}
function AUDIT_PUSH(a){ DATA.audit.push(a); renderAudit(); }
load();
setInterval(async () => { const r = await fetch('/api/state'); DATA = await r.json(); renderAudit(); }, 15000);
</script></body></html>
"""


class H(BaseHTTPRequestHandler):
    server_version = "SHIELD-NHI-demo"

    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), format % args))

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if u.path == "/api/state":
            return self._send(200, json.dumps(state()).encode())
        if u.path == "/api/explain":
            q = parse_qs(u.query)
            return self._send(200, json.dumps(explain(q.get("id", [""])[0])).encode())
        if u.path == "/healthz":
            return self._send(200, b'{"ok":true}')
        return self._send(404, b'{"error":"not found"}')

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/remediate":
            return self._send(404, b'{"error":"not found"}')
        try:
            n = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return self._send(400, b'{"ok":false,"message":"bad json"}')
        nhi_id = str(payload.get("id", ""))
        action = str(payload.get("action", ""))
        if payload.get("approved") is not True:
            return self._send(403, json.dumps({"ok": False,
                "message": "REFUSED: destructive action requires explicit human approval."}).encode())
        record = next((r for r in nhi_engine.score_all() if r.nhi.id == nhi_id), None)
        if record is None:
            return self._send(404, json.dumps({"ok": False, "message": "unknown NHI"}).encode())
        entry = {"id": nhi_id, "action": action,
                 "at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                        .strftime("%Y-%m-%d %H:%M:%SZ")}
        AUDIT.append(entry)
        return self._send(200, json.dumps({"ok": True, "audit": entry,
            "message": f"REMEDIATED {nhi_id}: '{action}' applied. Audit trail recorded. "
                       f"(simulated execution for demo)"}).encode())


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), H)
    print(f"SHIELD-NHI web demo on :{PORT} · token_factory={nhi_models.token_factory_enabled()} · "
          f"provider={nhi_models.active_provider()}", flush=True)
    srv.serve_forever()
