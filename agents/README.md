# Project management agents

Three custom agents support the weekly management of the ISP agrivoltaic project. They **draft, compute and flag**; the team members (Malak, Mario, Michal, Arkadiusz) **approve** every plan change. Nothing an agent produces enters the project record without a human decision.

| Agent | Reads | Drafts for review | Approved by |
|---|---|---|---|
| `tracker`: Sprint & Task Tracker | task board (`data/board.csv`), weekly meeting notes (`data/meetings/`) | Markdown sprint log; delay flags for late critical-path tasks; dependency flags for blocked tasks | Arkadiusz (Product Owner) |
| `risk_adr`: Risk & ADR Logger | risk register, meeting notes, task board, pending drafts | risks written as *cause → event → effect* scored probability × impact (1–9, escalation at 6); Architectural Decision Records (status Proposed) for every decision recorded in a meeting | Michal (risks), Mario (ADRs) |
| `budget`: Budget & Token Monitor | developer hours (`data/hours.csv`), LLM API usage (`data/api_usage.csv`), plan (`data/budget_plan.csv`) | an alert for every budget line at or above **70 %** of its maximum | Michal |

## Quick start
```bash
cd agents
bash weekly.sh --offline                       # the three agents with deterministic rules (no API key)
python3 -m pm_agents review                    # a human approves (y) or refuses (n) each draft, with a reason
python3 -m pm_agents log                       # audit trail of agent actions and human decisions
python3 run_scenarios.py --offline             # behavioural scenario suite
```
With the language model:
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...                   # read from the environment only
bash weekly.sh                                 # same agents; Claude reasons over the data and writes the drafts
python3 run_scenarios.py --judge               # scenarios graded criterion by criterion by an evaluating agent
python3 run_scenarios.py --judge --model claude-sonnet-5-5   # same suite on a second backbone
```
Approved drafts are written to `output/`: `sprint_logs/`, `adr/`, `risk_register_additions.md` and `decision_log.md`.

### Web interface
```bash
python3 -m pm_agents ui               # opens http://127.0.0.1:8765 (local only, standard library, no install)
```
Run each agent or the weekly sequence, approve or refuse each draft with a reason, read the project record (decision log, risks, sprint logs, ADRs), edit the input data, browse the audit log and run the behavioural scenarios. The interface calls the same functions as the CLI, so every action goes through the same hooks and audit log.

### Agent CLI
```bash
python3 -m pm_agents tracker "Check the sprint"              # new session; prints the response and the session id
python3 -m pm_agents tracker <session-id> "Why is T3 blocked?"   # continue the session
python3 -m pm_agents tracker --list-sessions
python3 -m pm_agents tracker <session-id> --replay           # recorded turns and tool trace
python3 -m pm_agents budget --json                           # structured output: response, session id, drafts, tool trace
python3 -m pm_agents --help
```

## Weekly routine
1. Add the meeting notes as `data/meetings/YYYY-MM-DD_weekly.md`, with decisions and actions on their own lines (`- Decision: ...`, `- Action: ...`).
2. Update `data/board.csv` (dependencies in `depends_on`, separated by `;`) and log hours in `data/hours.csv`.
3. Run `bash weekly.sh`, then `python3 -m pm_agents review` during the weekly meeting.

## Layout
```
agents/
  characters/     persona of each agent (voice, stance, register)
  knowledge/      project knowledge shared by all agents
  instructions/   directives of each agent (must-dos and must-not-dos)
  skills/         reusable domain procedures (risk scoring, ADR format, re-planning)
  examples/       one-shot tool-use examples
  pm_agents/      tools.py (tools), hooks.py (hooks), loop.py (agent loop, session store), review.py (human review),
                  __main__.py (CLI), ui.py + ui.html (local web interface)
  weekly.sh       orchestration by CLI composition
  scenarios/      behavioural scenarios with rubrics, and the brief for a driving agent
  run_scenarios.py
  data/           project state read by the agents
  drafts/ sessions/ logs/ output/   generated at run time
```

## Governance and safeguards
- **Draft-only writes.** Agents create drafts and flags. They cannot edit the board, the budget, the register or an accepted ADR.
- **Authorisation in code, not in the prompt.** Each agent has an allow-list of tools and flag types, enforced by the pre-tool-use hook before any side effect; denials are logged.
- **Facts computed by code.** Days late, blocked dependencies, totals and percentages are computed in Python; the model reasons and writes.
- **Human approval.** `review` records who decided, what, and why, in the audit log and the decision log.
- **Failure handling.** API errors, model refusals and the turn limit are logged and hand the check back to the human owner; a per-run write limit stops runaway output.
- **Untrusted input.** Meeting notes and task titles are data; a scenario checks that an instruction hidden in a task title has no effect.
- **Secrets.** The API key is read from the environment and never appears in prompts, sessions or logs.
- **Cost transparency.** Every model call appends its token usage and estimated cost to `data/api_usage.csv`, which the budget agent monitors.

## Relation to *Agents All the Way Down* (Alier, Pereira, García-Peñalvo and Casañ, 2026, arXiv:2606.11869)
| Methodology element | Implementation |
|---|---|
| **P1 Substrate**: cacheable prefix ordered tools → system → messages; tools fixed at init, system fixed per session, messages append-only; dynamic context kept out of the system prompt | `loop.py` sends tools (sorted, fixed per agent), then the system prompt, then messages, with prompt caching; the date and the task go in messages; token usage is logged per call |
| System prompt content: persona, worldview / domain knowledge, directives, one-shot tool-use examples | `characters/`, `knowledge/`, `instructions/`, `skills/`, `examples/`, assembled by `system_prompt()` |
| **P2 Function calling** | `tools.py`: a small registry per agent (2 to 6 tools) with strict schemas |
| **P2 Agent loop**, written without a framework | `loop.py`, `_model_turn` |
| **P2 Skills, characters, instruction sets** | `skills/*/SKILL.md`, `characters/`, `instructions/` |
| **P2 Hooks**: deterministic gate before tool execution | `hooks.py`: `pre_tool_use` (allow-list, write limit), `post_tool_use` (audit) |
| **P2 CLI orchestration / scaffolding** | each agent is a command; dispatch, session store and security live in host code |
| P2 MCP and liteshell | not used: the agents run locally with a host shell and small tool registries, so a CLI is the lower-overhead surface and no in-process facade is needed |
| **P3 Prototype with a general-purpose agent** | the agents were prototyped with a general-purpose coding agent against the real project files |
| **P4 Harvest, fold, ship as CLI (Turtle pattern)**: stateless invocation, session-keyed continuation, `--list-sessions`, `--replay`, structured output, working `--help` | `python3 -m pm_agents <agent> [session-id] "task"`, `--list-sessions`, `--replay` (a recorded trace, not a deterministic re-run), `--json`, `--help` |
| **P5 Agent-tests-agent**: a scenario, the CLI invocation and a rubric; pass/fail per criterion with evidence; backbone comparison; continuous re-runs | `run_scenarios.py` drives each agent through its CLI, checks invariants and, with `--judge`, grades each rubric criterion with quoted evidence; `--model` compares backbones; `scenarios/P5_BRIEF.md` for a general-purpose driving agent |
| **Turtle corollary**: multi-agent orchestration is CLI composition | `weekly.sh` composes the three agent commands; the risk agent reads the other agents' drafts from disk |
| Prompt rules that keep being violated are promoted to code | decision rights, write limits and all calculations are in host code |
