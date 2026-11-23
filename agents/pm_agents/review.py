"""Human review of agent drafts: shared by the command line and the web interface."""
import json
from datetime import date, datetime
from .tools import DRAFTS, ROOT, list_drafts
from .hooks import audit

OUT = ROOT / "output"


def _append_table(path, header, row):
    OUT.mkdir(exist_ok=True)
    if not path.exists():
        path.write_text(header, encoding="utf-8")
    with open(path, "a", encoding="utf-8") as f:
        f.write(row)


def publish(d):
    """Write an approved draft to the project record in output/."""
    OUT.mkdir(exist_ok=True)
    if d["kind"] == "sprint_log":
        (OUT / "sprint_logs").mkdir(exist_ok=True)
        (OUT / "sprint_logs" / f"{d['title'].split()[-1]}.md").write_text(d["body"], encoding="utf-8")
    elif d["kind"] == "adr":
        (OUT / "adr").mkdir(exist_ok=True)
        n = len(list((OUT / "adr").glob("*.md"))) + 1
        (OUT / "adr" / f"{n:03d}.md").write_text(d["body"].replace("Status: Proposed", "Status: Accepted"), encoding="utf-8")
    elif d["kind"] == "risk":
        _append_table(OUT / "risk_register_additions.md",
                      "| Risk (cause -> event -> effect) | Score | Mitigation | Evidence |\n|---|---|---|---|\n",
                      f"| {d['body']} | P{d['probability']} x I{d['impact']} = {d['score']} | {d['mitigation']} | {d['evidence']} |\n")


def decide(draft_id, approve, by, reason):
    """Record a human decision on a pending draft. Returns the updated draft."""
    p = DRAFTS / f"{draft_id}.json"
    if not p.exists():
        raise ValueError(f"Unknown draft: {draft_id}")
    d = json.loads(p.read_text(encoding="utf-8"))
    if d["status"] != "pending":
        raise ValueError(f"Draft {draft_id} was already {d['status']}.")
    if not by.strip():
        raise ValueError("A reviewer name is required.")
    reason = reason.strip() or "No reason given"
    d.update(status="approved" if approve else "refused", decided_by=by.strip(), reason=reason,
             decided=datetime.now().isoformat(timespec="seconds"))
    p.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    if approve:
        publish(d)
    audit(d["agent"], "human_decision", id=d["id"], decision=d["status"], by=d["decided_by"], reason=reason)
    _append_table(OUT / "decision_log.md", "| Date | Item | Decision | Reason | By | Draft |\n|---|---|---|---|---|---|\n",
                  f"| {date.today():%Y-%m-%d} | {d['title']} | {d['status']} | {reason} | {d['decided_by']} | {d['id']} |\n")
    return d


def review_cli(by):
    pend = list_drafts("pending")
    if not pend:
        print("Nothing to review."); return
    by = by or input("Your name: ").strip()
    for d in pend:
        print(f"\n[{d['kind']}] from {d['agent']} agent, for {d['owner']}\n{d['title']}\n{d['body']}\nEvidence: {d['evidence']}")
        try:
            c = input("Approve? (y)es / (n)o / (s)kip: ").strip().lower()[:1]
            if c not in ("y", "n"):
                continue
            reason = input("Reason: ")
        except EOFError:
            break
        decide(d["id"], c == "y", by, reason)
