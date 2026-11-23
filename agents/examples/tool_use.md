# One-shot tool-use examples
Example (tracker): after `list_tasks` returns `"late": ["T2"]` and `"blocked": {"T3": ["T2"]}`, call
`flag` with {"type": "delay", "title": "T2 is 2 day(s) late: Safety rules v1", "details": "Option: cut scope to the wind-stow rule and keep the W4 date.", "evidence": "board T2"}.

Example (risk_adr): a meeting line "- Decision: the advisor scores 5 fixed angles" becomes `draft_adr` with
{"title": "Advisor scores 5 fixed angles", "context": "...", "decision": "...", "alternatives": "...", "consequences": "...", "source": "2026-11-20_weekly.md"}.

Example (budget): `budget_status` shows {"line": "AI / API usage (EUR)", "actual": 36.5, "plan_max": 50.0, "pct_of_max": 73, "alert": true}; call
`flag` with {"type": "budget", "title": "AI / API usage (EUR) at 73% of max", "details": "36.5 of 50.0 EUR used. Option: cap agent runs to one per week.", "evidence": "budget line AI / API usage (EUR)"}.
