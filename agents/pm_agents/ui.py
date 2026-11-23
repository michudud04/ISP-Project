"""Local web interface to run the agents, review their drafts and inspect the project record.

Start with: python3 -m pm_agents ui   (serves http://127.0.0.1:8765 on this machine only)
Uses the Python standard library only. The interface calls the same functions as the CLI,
so every run, decision and denial goes through the same hooks and audit log."""
import json, os, re, subprocess, sys, threading, webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from . import loop, tools
from .review import OUT, decide

CODE = Path(__file__).resolve().parent.parent
PAGE = Path(__file__).with_name("ui.html")
AGENTS = {"tracker": "Sprint & Task Tracker", "budget": "Budget & Token Monitor", "risk_adr": "Risk & ADR Logger"}
DATA_FILES = ["board.csv", "hours.csv", "budget_plan.csv", "api_usage.csv", "risk_register.md"]
MEETING_RE = re.compile(r"^meetings/\d{4}-\d{2}-\d{2}_[A-Za-z0-9_-]+\.md$")
LOCK = threading.Lock()  # one agent run or decision at a time


def _text(p):
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _editable(name):
    return name in DATA_FILES or bool(MEETING_RE.match(name))


def state():
    drafts = tools.list_drafts("all") if tools.DRAFTS.exists() else []
    return {"agents": AGENTS, "drafts": drafts, "sessions": loop.list_sessions() if (tools.ROOT / "sessions").exists() else [],
            "model": loop.DEFAULT_MODEL, "api_key": bool(os.environ.get("ANTHROPIC_API_KEY")), "today": date.today().isoformat()}


def outputs():
    def folder(name):
        d = OUT / name
        return {p.name: _text(p) for p in sorted(d.glob("*.md"))} if d.exists() else {}
    return {"decision_log": _text(OUT / "decision_log.md"), "risks": _text(OUT / "risk_register_additions.md"),
            "sprint_logs": folder("sprint_logs"), "adr": folder("adr")}


def audit_log(limit=300):
    p = tools.LOGS / "agent_activity.jsonl"
    lines = _text(p).splitlines()[-limit:]
    return [json.loads(l) for l in reversed(lines) if l.strip()]


def data_files():
    names = DATA_FILES + [f"meetings/{p.name}" for p in sorted((tools.DATA / "meetings").glob("*.md"))]
    return {n: _text(tools.DATA / n) for n in names}


def run_scenarios():
    r = subprocess.run([sys.executable, str(CODE / "run_scenarios.py"), "--offline"], cwd=CODE,
                       capture_output=True, text=True, timeout=600, env={k: v for k, v in os.environ.items() if k != "PM_AGENTS_HOME"})
    report = tools.LOGS / "scenario_report.json"
    return {"output": r.stdout + r.stderr, "report": json.loads(_text(report)) if report.exists() else []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path == "/":
                return self._send(200, PAGE.read_bytes(), "text/html")
            if u.path == "/api/state":
                return self._send(200, state())
            if u.path == "/api/output":
                return self._send(200, outputs())
            if u.path == "/api/log":
                return self._send(200, audit_log())
            if u.path == "/api/data":
                return self._send(200, data_files())
            if u.path == "/api/session":
                return self._send(200, loop.load_session(parse_qs(u.query)["id"][0]))
            self._send(404, {"error": "Not found"})
        except (Exception, SystemExit) as e:
            self._send(400, {"error": str(e)})

    def do_POST(self):
        if self.headers.get("Origin") not in (None, f"http://{self.headers.get('Host')}"):
            return self._send(403, {"error": "Cross-origin requests are not allowed."})
        u = urlparse(self.path)
        try:
            b = self._body()
            with LOCK:
                if u.path == "/api/run":
                    if b["agent"] not in AGENTS:
                        raise ValueError("Unknown agent.")
                    return self._send(200, loop.run(b["agent"], b.get("task") or None, None, bool(b.get("offline", True)),
                                                    b.get("model") or loop.DEFAULT_MODEL, b.get("today") or None))
                if u.path == "/api/decide":
                    return self._send(200, decide(b["id"], bool(b["approve"]), b.get("by", ""), b.get("reason", "")))
                if u.path == "/api/data":
                    name = b["name"]
                    if not _editable(name):
                        raise ValueError("This file cannot be edited from the interface.")
                    p = tools.DATA / name
                    p.parent.mkdir(exist_ok=True)
                    p.write_text(b["text"], encoding="utf-8")
                    return self._send(200, {"saved": name})
                if u.path == "/api/scenarios":
                    return self._send(200, run_scenarios())
            self._send(404, {"error": "Not found"})
        except (Exception, SystemExit) as e:
            self._send(400, {"error": str(e)})


def serve(port=8765, open_browser=True):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Project management agents: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
