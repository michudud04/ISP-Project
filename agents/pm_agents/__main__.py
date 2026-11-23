"""Command-line interface. Each agent is a CLI with a stable invocation shape (Turtle pattern):

  python3 -m pm_agents <agent> ["task"]                    start a new session
  python3 -m pm_agents <agent> <session-id> "next task"    continue a session
  python3 -m pm_agents <agent> --list-sessions
  python3 -m pm_agents <agent> <session-id> --replay       print the recorded trace of a session
  python3 -m pm_agents review [--by NAME]                  human approval of pending drafts
  python3 -m pm_agents log                                 audit trail
  python3 -m pm_agents ui                                  local web interface (http://127.0.0.1:8765)

Agents: tracker (Sprint & Task Tracker), risk_adr (Risk & ADR Logger), budget (Budget & Token Monitor).
Options: --offline (deterministic rules, no API key), --json (structured output with tool trace),
--model MODEL, --today YYYY-MM-DD.
"""
import argparse, json, re, sys
from datetime import date
from . import loop
from .tools import LOGS
from .review import review_cli

AGENTS = ["tracker", "risk_adr", "budget"]
SESSION_RE = re.compile(r"^(tracker|risk_adr|budget)-\d{8}-\d{6}-[0-9a-f]{4}$")


# ---------- agent CLI ----------
def agent_cli(argv):
    ap = argparse.ArgumentParser(prog="python3 -m pm_agents", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("agent", choices=AGENTS)
    ap.add_argument("args", nargs="*", help="[session-id] [task]")
    ap.add_argument("--list-sessions", action="store_true")
    ap.add_argument("--replay", action="store_true", help="print the recorded turns and tool trace of a session")
    ap.add_argument("--offline", action="store_true", help="deterministic rules instead of the model (no API key)")
    ap.add_argument("--json", action="store_true", help="structured output: response, session id, drafts, tool trace")
    ap.add_argument("--model", default=loop.DEFAULT_MODEL)
    ap.add_argument("--today", default=date.today().isoformat())
    a = ap.parse_args(argv)
    if a.list_sessions:
        rows = loop.list_sessions(a.agent)
        print(json.dumps(rows, indent=2) if a.json else "\n".join(f"{r['id']}  {r['mode']}  {r['turns']} turn(s)  {r['created']}" for r in rows) or "No sessions.")
        return
    sid = a.args[0] if a.args and SESSION_RE.match(a.args[0]) else None
    task = " ".join(a.args[1:] if sid else a.args) or None
    if a.replay:
        if not sid:
            ap.error("--replay needs a session id")
        s = loop.load_session(sid)
        if a.json:
            print(json.dumps(s["turns"], indent=2, ensure_ascii=False)); return
        for i, t in enumerate(s["turns"], 1):
            print(f"--- turn {i} ({t['at']}, data date {t['today']})\ntask: {t['task']}")
            for step in t["trace"]:
                print(f"  {step['tool']}({json.dumps(step['input'], ensure_ascii=False)[:120]})" + (f"  DENIED: {step['denied']}" if step["denied"] else ""))
            print(f"response: {t['response']}")
        return
    out = loop.run(a.agent, task, sid, a.offline, a.model, a.today)
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    else:
        print(out["response"])
        print(f"\nsession: {out['session_id']}")
        if out["drafts"]:
            print("drafts for review: " + ", ".join(out["drafts"]))


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["review"]:
        ap = argparse.ArgumentParser(prog="python3 -m pm_agents review"); ap.add_argument("--by")
        review_cli(ap.parse_args(argv[1:]).by)
    elif argv[:1] == ["ui"]:
        from .ui import serve
        ap = argparse.ArgumentParser(prog="python3 -m pm_agents ui"); ap.add_argument("--port", type=int, default=8765)
        ap.add_argument("--no-browser", action="store_true")
        a = ap.parse_args(argv[1:]); serve(a.port, not a.no_browser)
    elif argv[:1] == ["log"]:
        p = LOGS / "agent_activity.jsonl"
        print(p.read_text(encoding="utf-8") if p.exists() else "The audit log is empty.")
    else:
        agent_cli(argv)


main()
