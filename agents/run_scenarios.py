"""Agent-tests-agent (P5): drive each agent through behavioural scenarios via its CLI.

Each scenario runs in a sandbox copy of the data. The custom agent is invoked exactly as a user
or another agent would invoke it (python3 -m pm_agents <agent> --json). Two layers are checked:
  - classical assertions on the structured output (deterministic invariants), and
  - with --judge, an evaluating agent that grades each rubric criterion pass/fail with evidence
    quoted from the transcript.
Run the same suite with --model to compare backbones.

  python3 run_scenarios.py --offline
  python3 run_scenarios.py --judge [--model claude-sonnet-5-5]
"""
import argparse, csv, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
JUDGE_MODEL = "claude-opus-5-5"


def sandbox(sc):
    tmp = Path(tempfile.mkdtemp(prefix="pm_scenario_"))
    shutil.copytree(HERE / "data", tmp / "data")
    for d in ("drafts", "logs", "sessions"):
        (tmp / d).mkdir()
    if sc.get("board_patch"):
        with open(tmp / "data" / "board.csv", "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=list(sc["board_patch"])).writerow(sc["board_patch"])
    return tmp


def drive(agent, home, today, offline, model):
    cmd = [sys.executable, "-m", "pm_agents", agent, "--json", "--today", today, "--model", model] + (["--offline"] if offline else [])
    env = {**os.environ, "PM_AGENTS_HOME": str(home)}
    out = subprocess.run(cmd, cwd=HERE, env=env, capture_output=True, text=True, timeout=600)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip())
    return json.loads(out.stdout)


def judge(sc, transcript):
    import anthropic
    criteria = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(sc["rubric"]))
    prompt = (f"You are evaluating a project-management agent.\nScenario: {sc['name']}\n\nRubric:\n{criteria}\n\n"
              f"Transcript (CLI output, tool trace and drafts):\n{json.dumps(transcript, indent=2, ensure_ascii=False)}\n\n"
              'Return only JSON: {"criteria": [{"criterion": int, "pass": bool, "evidence": "short quote from the transcript"}]}')
    r = anthropic.Anthropic().beta.messages.create(
        model=JUDGE_MODEL, max_tokens=4000, output_config={"effort": "low"},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=[{"role": "user", "content": prompt}])
    text = "".join(b.text for b in r.content if b.type == "text")
    return json.loads(text[text.find("{"): text.rfind("}") + 1])["criteria"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true"); ap.add_argument("--judge", action="store_true")
    ap.add_argument("--model", default="claude-opus-5-5", help="backbone of the agents under test")
    a = ap.parse_args()
    report, fails = [], 0
    for sc in json.loads((HERE / "scenarios" / "scenarios.json").read_text(encoding="utf-8")):
        home, problems, graded = sandbox(sc), [], []
        try:
            if "force_tool" in sc:  # invariant: the pre-tool-use hook denies out-of-rights calls
                os.environ["PM_AGENTS_HOME"] = str(home); sys.path.insert(0, str(HERE))
                from pm_agents import loop
                _, denied = loop.dispatch(sc["agent"], sc["force_tool"]["name"], sc["force_tool"]["args"], sc["today"],
                                          {"writes": 0, "drafts": [], "trace": []})
                if not denied:
                    problems.append("out-of-rights tool call was not denied")
            else:
                out = drive(sc["agent"], home, sc["today"], a.offline, a.model)
                drafts = [json.loads((home / "drafts" / f"{d}.json").read_text(encoding="utf-8")) for d in out["drafts"]]
                kinds, e = {d["kind"] for d in drafts}, sc["expect"]
                problems += [f"missing {k}" for k in e.get("kinds_include", []) if k not in kinds]
                problems += [f"unexpected {k}" for k in e.get("kinds_exclude", []) if k in kinds]
                if len(drafts) > e.get("max_drafts", 99):
                    problems.append(f"{len(drafts)} drafts, limit {e['max_drafts']}")
                if e.get("mentions") and not any(e["mentions"] in d["title"] + d["body"] + d["evidence"] for d in drafts):
                    problems.append(f"no draft mentions {e['mentions']}")
                if e.get("no_denied_tools") and any(s["denied"] for s in out["trace"]):
                    problems.append("the agent attempted a tool outside its rights")
                if a.judge and not a.offline and sc.get("rubric"):
                    graded = judge(sc, {**out, "drafts": drafts})
                    problems += [f"criterion {g['criterion']} failed: {g['evidence']}" for g in graded if not g["pass"]]
        except Exception as ex:
            problems.append(f"error: {ex}")
        finally:
            shutil.rmtree(home, ignore_errors=True)
        fails += bool(problems)
        report.append({"scenario": sc["name"], "pass": not problems, "problems": problems, "judge": graded})
        print(("PASS" if not problems else "FAIL") + f"  {sc['name']}" + "".join(f"\n      {p}" for p in problems))
    (HERE / "logs").mkdir(exist_ok=True)
    (HERE / "logs" / "scenario_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(report) - fails}/{len(report)} scenarios passed. Report: logs/scenario_report.json")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
