"""Hooks: deterministic host-side functions at fixed points of the agent lifecycle.
pre_tool_use is the security gate where the allow-list is applied; post_tool_use writes the audit trail.
Authorisation lives here, never in the prompt."""
import json
from datetime import datetime
from .tools import LOGS

RIGHTS = {
    "tracker":  {"tools": {"list_tasks", "read_meeting_notes", "draft_sprint_log", "flag"}, "flags": {"delay", "dependency"}},
    "risk_adr": {"tools": {"read_doc", "read_meeting_notes", "list_tasks", "list_drafts", "draft_risk", "draft_adr"}, "flags": set()},
    "budget":   {"tools": {"budget_status", "flag"}, "flags": {"budget"}},
}
WRITE_TOOLS = {"draft_sprint_log", "draft_risk", "draft_adr", "flag"}
MAX_WRITES_PER_RUN = 8


def audit(agent, event, **data):
    LOGS.mkdir(exist_ok=True)
    rec = {"ts": datetime.now().isoformat(timespec="seconds"), "agent": agent, "event": event, **data}
    with open(LOGS / "agent_activity.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def pre_tool_use(agent, tool, args, state):
    r = RIGHTS[agent]
    if tool not in r["tools"]:
        return f"Denied: the {agent} agent has no right to use '{tool}'."
    if tool == "flag" and args.get("type") not in r["flags"]:
        return f"Denied: the {agent} agent cannot raise '{args.get('type')}' flags."
    if tool in WRITE_TOOLS and state["writes"] >= MAX_WRITES_PER_RUN:
        return "Denied: write limit for this run reached. Stop and let the owner review."
    return None


def post_tool_use(agent, tool, args, result, denied):
    if denied:
        audit(agent, "tool_denied", tool=tool, reason=denied)
    elif tool in WRITE_TOOLS:
        audit(agent, "draft", tool=tool, id=result["created"], goes_to=result["goes_to"])
