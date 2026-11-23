# Project knowledge

- Course: ISP (UPC FIB), 2026-2027. Seven weekly milestones: W2 proposal, W3 design review, W4 video + pitch, W5 progress checkpoint, W6 final preparation, W7 final presentation.
- Product: a decision-support tool for agrivoltaic farms (solar panels above crops). It recommends a panel position, explains the crop/energy trade-off, and a person always decides. Deterministic safety rules (wind stow, stale-sensor fallback) sit outside the AI.
- Team and decision rights: Arkadiusz (Product Owner: scope, priorities, plan changes), Mario (Tech lead: architecture, safety rules, ADR approval), Malak (UX and user tests), Michal (data, risk register, budget, weekly rituals).
- Critical path: data model -> safety rules -> advisor scoring -> role screens -> user validation.
- Budget (Week 2 proposal): team effort 100-140 h at EUR 30/h; hosting EUR 0-20; AI/API EUR 0-50; 20% contingency; total about EUR 3,600-5,100.
- Governance rule: agents draft logs, compute metrics and flag delays; humans approve all plan changes.
