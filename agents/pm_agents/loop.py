"""Agent loop (P2) folded with a pre-tool-use hook and a session store (P4).

Prompt layout follows the cacheable prefix order: tools (fixed at init) -> system (fixed per
session) -> messages (append-only). Per-turn context such as the date goes in messages.
--offline runs the same tools, hooks and logs with deterministic rules instead of the model."""
import csv, json, re, uuid
from datetime import date, datetime
from pathlib import Path
from . import tools
from .hooks import RIGHTS, WRITE_TOOLS, pre_tool_use, post_tool_use, audit

DEFAULT_MODEL = "claude-opus-5-5"
PRICE_EUR_PER_MTOK = (4.0, 20.0)  # approximate input / output price, used by the token monitor
CODE = Path(__file__).resolve().parent.parent
SKILLS = {"tracker": ["replanning"], "risk_adr": ["risk-scoring", "adr"], "budget": []}
DEFAULT_TASK = "Run your weekly check and end with a three-line summary."


def _read(*parts):
    return (CODE.joinpath(*parts)).read_text(encoding="utf-8")


def system_prompt(agent):
    """System = persona, domain knowledge, directives, skills, one-shot tool-use examples."""
    sections = [_read("characters", f"{agent}.md"), _read("knowledge", "project.md"), _read("instructions", f"{agent}.md")]
    sections += [_read("skills", s, "SKILL.md") for s in SKILLS[agent]]
    sections.append(_read("examples", "tool_use.md"))
    return "\n\n".join(sections)


def tool_definitions(agent):
    return [tools.SCHEMAS[t] for t in sorted(RIGHTS[agent]["tools"])]


# ---------- session store ----------
def _session_path(sid):
    return tools.ROOT / "sessions" / f"{sid}.json"


def load_session(sid):
    p = _session_path(sid)
    if not p.exists():
        raise SystemExit(f"Unknown session: {sid}")
    return json.loads(p.read_text(encoding="utf-8"))


def save_session(s):
    p = _session_path(s["id"])
    p.parent.mkdir(exist_ok=True)
    p.write_text(json.dumps(s, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def list_sessions(agent=None):
    out = []
    for p in sorted((tools.ROOT / "sessions").glob("*.json")):
        s = json.loads(p.read_text(encoding="utf-8"))
        if agent in (None, s["agent"]):
            out.append({"id": s["id"], "agent": s["agent"], "mode": s["mode"], "created": s["created"], "turns": len(s["turns"])})
    return out


# ---------- tool dispatch ----------
def dispatch(agent, name, args, today, state):
    denied = pre_tool_use(agent, name, args, state)
    result = None
    if not denied:
        if name == "list_tasks":
            result = tools.list_tasks(today)
        elif name == "read_meeting_notes":
            result = tools.read_meeting_notes()
        elif name == "read_doc":
            result = tools.read_doc(args["name"])
        elif name == "budget_status":
            result = tools.budget_status()
        elif name == "list_drafts":
            result = tools.list_drafts(args.get("status", "pending"))
        else:
            result = getattr(tools, name)(agent, **args)
            state["drafts"].append(result["created"])
        if name in WRITE_TOOLS:
            state["writes"] += 1
    post_tool_use(agent, name, args, result, denied)
    state["trace"].append({"tool": name, "input": args, "denied": denied,
                           "created": result.get("created") if isinstance(result, dict) else None})
    return result, denied


def _log_tokens(agent, usage):
    cost = (usage.input_tokens * PRICE_EUR_PER_MTOK[0] + usage.output_tokens * PRICE_EUR_PER_MTOK[1]) / 1e6
    with open(tools.DATA / "api_usage.csv", "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([date.today().isoformat(), f"{agent} agent", usage.input_tokens, usage.output_tokens, f"{cost:.4f}"])


def _model_turn(agent, session, task, today, state, max_turns=12):
    import anthropic
    client = anthropic.Anthropic()  # the API key is read from the environment, never from prompts or logs
    messages = session["messages"]
    messages.append({"role": "user", "content": f"Today is {today}. {task}"})
    for _ in range(max_turns):
        resp = client.beta.messages.create(
            model=session["model"], max_tokens=16000,
            tools=tool_definitions(agent), system=system_prompt(agent), messages=messages,
            cache_control={"type": "ephemeral"}, output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        _log_tokens(agent, resp.usage)
        if resp.stop_reason == "refusal":
            audit(agent, "refusal")
            return "The model declined this request. The human owner performs the check manually."
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
        uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not uses:
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        results = []
        for u in uses:
            out, denied = dispatch(agent, u.name, u.input, today, state)
            results.append({"type": "tool_result", "tool_use_id": u.id, "is_error": bool(denied),
                            "content": denied or json.dumps(out, ensure_ascii=False, default=str)})
        messages.append({"role": "user", "content": results})
    audit(agent, "turn_limit")
    return "Stopped at the turn limit. The human owner has been notified through the audit log."


def _short_title(text, limit=70):
    """First clause of a decision, cut at a word boundary."""
    t = text.split(",")[0].strip().rstrip(".")
    return t if len(t) <= limit else t[:limit].rsplit(" ", 1)[0] + "..."


def _rules_turn(agent, today, state):
    """Deterministic version of each agent, used offline and as a baseline in tests."""
    def call(name, **a):
        return dispatch(agent, name, a, today, state)[0]
    if agent == "tracker":
        b, notes = call("list_tasks"), call("read_meeting_notes")
        t = {x["id"]: x for x in b["tasks"]}
        lines = [f"# Sprint log, week of {today}", "", "## Done"] + [f"- {i}: {x['title']}" for i, x in t.items() if x["status"] == "done"]
        lines += ["", "## In progress / to do"] + [f"- {i}: {x['title']} ({x['owner']}, due {x['due']})" for i, x in t.items() if x["status"] != "done"]
        lines += ["", "## Late"] + [f"- {i}: {t[i]['days_late']} day(s) late" for i in b["late"]]
        lines += ["", "## Blocked"] + [f"- {i} waits for {', '.join(d)}" for i, d in b["blocked"].items()]
        lines += ["", "## Decisions and actions from meetings"]
        for n in notes:
            lines += [f"- {l.strip('- ').strip()} ({n['file']})" for l in n["text"].splitlines() if re.match(r"-\s*(Decision|Action):", l)]
        call("draft_sprint_log", week=today, markdown="\n".join(lines))
        for i in b["late"]:
            if t[i]["critical_path"] == "yes":
                call("flag", type="delay", title=f"{i} is {t[i]['days_late']} day(s) late: {t[i]['title']}",
                     details="Option: cut scope to what the next milestone needs and keep the milestone date.", evidence=f"board {i}")
        chain = [i for i, d in b["blocked"].items() if set(d) & set(b["late"])]
        if chain:
            call("flag", type="dependency", title=f"Late tasks block {', '.join(chain)}",
                 details="Downstream tasks cannot start until the late task is done.", evidence=f"board depends_on {', '.join(chain)}")
    elif agent == "budget":
        for l in call("budget_status")["lines"]:
            if l["alert"]:
                call("flag", type="budget", title=f"{l['line']} at {l['pct_of_max']}% of max",
                     details=f"{l['actual']} of {l['plan_max']} used. Option: cap usage or move contingency.", evidence=f"budget line {l['line']}")
    elif agent == "risk_adr":
        b, notes = call("list_tasks"), call("read_meeting_notes")
        for i in b["late"]:
            x = next(t for t in b["tasks"] if t["id"] == i)
            if x["critical_path"] == "yes":
                call("draft_risk", cause=f"{i} ({x['title']}) is {x['days_late']} day(s) late", event="the W4 prototype is not ready",
                     effect="the pitch has no working evidence", probability=2, impact=3,
                     mitigation="cut scope of the late task; review at the weekly meeting", evidence=f"board {i}")
        for n in notes:
            for l in n["text"].splitlines():
                m = re.match(r"-\s*Decision:\s*(.+)", l)
                if m:
                    call("draft_adr", title=_short_title(m.group(1)), context="Recorded in the weekly meeting.", decision=m.group(1),
                         alternatives="Not recorded in the meeting notes; the decision owner completes this section before approval.",
                         consequences="Not recorded in the meeting notes; the decision owner adds at least one trade-off before approval.",
                         source=n["file"])
    n = len(state["drafts"])
    return f"{agent}: {n} draft(s) created for human review." if n else f"{agent}: nothing to report this week."


def run(agent, task=None, session_id=None, offline=False, model=DEFAULT_MODEL, today=None):
    """One stateless invocation. Returns the response, the session id, the drafts created and the tool trace."""
    today = today or date.today().isoformat()
    task = task or DEFAULT_TASK
    if session_id:
        session = load_session(session_id)
        if session["agent"] != agent:
            raise SystemExit(f"Session {session_id} belongs to the {session['agent']} agent.")
    else:
        session = {"id": f"{agent}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}", "agent": agent,
                   "mode": "rules" if offline else "model", "model": None if offline else model,
                   "created": datetime.now().isoformat(timespec="seconds"), "turns": [], "messages": []}
    state = {"writes": 0, "drafts": [], "trace": []}
    audit(agent, "run_start", session=session["id"], mode=session["mode"], model=session["model"])
    if session["mode"] == "rules":
        response = _rules_turn(agent, today, state)
    else:
        try:
            response = _model_turn(agent, session, task, today, state)
        except Exception as e:  # API or network failure: logged, the human owner takes over
            audit(agent, "run_failed", session=session["id"], error=type(e).__name__)
            response = f"The {agent} agent could not complete ({type(e).__name__}). {tools.OWNERS[agent]} performs the check manually."
    session["turns"].append({"at": datetime.now().isoformat(timespec="seconds"), "today": today, "task": task,
                             "response": response, "drafts": state["drafts"], "trace": state["trace"]})
    save_session(session)
    audit(agent, "run_done", session=session["id"], drafts=state["drafts"])
    return {"agent": agent, "session_id": session["id"], "response": response, "drafts": state["drafts"], "trace": state["trace"]}
