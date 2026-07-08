# risk-agent

A constrained, auditable, multi-agent cyber risk assessment and
compliance-alignment pipeline, run entirely through Claude Code (no
separate LLM API key/integration; this project *is* a Claude Code
project, in the same style as this user's other agentic security tools).

## What this is

Given a scenario (a company/org description), the `/risk-assess` skill
runs it through 12 sequential subagents:

context-mapper -> assumption-agent -> risk-generator -> risk-reviewer ->
risk-scorer -> prioritizer -> mitigation-planner -> residual-estimator ->
framework-mapper -> compliance-reviewer -> skeptic -> report-composer

Each stage reads the prior stage's JSON artifact(s), writes its own
schema-validated JSON artifact into `runs/<org-name>_<timestamp>/`, and gets checked
against `schemas/models.py` (Pydantic) and `engine/policy_engine.py`
(semantic rules the schema alone can't express) before the pipeline
advances. The final stage produces a human-readable Markdown report plus a
manifest.

## How to run it

From this project directory, in Claude Code:

```
/risk-assess
```

Then either paste a scenario when asked, or give a file path. Or pass it
inline: `/risk-assess <paste scenario text or a file path here>`.

Output lands in `runs/<org-name>_<timestamp>/13_final_report.md` (plus all
12 JSON artifacts, `decision_log.json`, and `manifest.json` in the same
folder). The folder name is derived from the org/subject the orchestrator
reads off the scenario text, passed as `--name` to `run_manager.py init`
(falls back to a bare timestamp if no name is inferable).

## Key files

- `schemas/models.py`: the contract every stage's output must satisfy.
- `schemas/validate.py`: CLI validator agents/orchestrator call via Bash.
- `engine/run_manager.py`: scaffolds a new run.
- `engine/decision_log.py`: append-only audit trail per run.
- `engine/policy_engine.py`: semantic rules (owner/effort required on
  mitigations, no NIST AI RMF mapping without a real org-deployed AI
  system, Type 2 evidence must read as time-based, etc.) beyond what JSON
  schema shape alone can enforce.
- `engine/build_prompt_registry.py`: regenerate `prompts/registry.json`
  and its snapshots after editing any `.claude/agents/*.md` file.
- `.claude/agents/*.md`: the 12 subagents; each file IS that stage's
  full prompt (role/task/constraints/schema/forbidden behavior/quality
  rubric/output rules). This is the source of truth; `prompts/` is a
  generated, versioned snapshot, not where you edit.
- `.claude/skills/risk-assess/SKILL.md`: the orchestrator runbook.

## Design constraints worth knowing before changing anything

- The core deliverable is **exactly the 5 risks** in
  `07_prioritized_risks.json`'s `top5`. `report-composer.md` scopes
  sections 4/6/7/8/9/11 of the final report to those 5 only. The pipeline
  still scores/mitigates/maps every `accepted` risk internally (useful
  breadth), but anything outside `top5` goes in the report's Appendix B
  as a pointer, not full detail in the main body. Don't let this drift
  back to "all accepted risks in the main sections" without a reason.
- Framework mapping / SOC 2 evidence (Sections 8-9) are explicitly framed
  as a value-add layer, not the core assessment (Sections 4-7 are the
  core). Keep that framing if you touch report-composer.
- `02_context.json` has a `stated_facts` field specifically so no
  scenario fact a downstream stage relies on can go undocumented. Every
  downstream claim must trace to a typed context field, `stated_facts`,
  a registered assumption, or a stated heuristic, never to an ad hoc
  re-read of the raw scenario text. `policy_engine.py::check_context_stated_facts`
  warns (doesn't hard-fail) if a non-trivial scenario produced an empty
  `stated_facts` list.
- Every stage validates its own output AND gets re-validated by the
  orchestrator before the pipeline advances. An agent claiming success
  is never sufficient on its own.
- `nist_ai_rmf` mappings are only valid when `02_context.json` has
  `deployed_ai_systems: true` for that specific risk. This is enforced by
  `policy_engine.py::check_ai_rmf_usage` and is a HARD violation if
  broken, by design (the framework mapping agent maps ordinary customer
  risk to NIST CSF / ISO 27001 / SOC 2, and only maps the AI system's own
  governance to NIST AI RMF).
- SOC 2 Type 1 vs Type 2 evidence is treated as a real distinction, not
  interchangeable. Type 1 is point-in-time design evidence; Type 2 is
  operating-effectiveness evidence over an observation window. See
  `compliance-reviewer.md` and `policy_engine.py::check_type2_evidence_is_time_based`.
- The system deliberately never claims exact breach probabilities, legal
  compliance determinations, or audit certification. See each report's
  "AI governance and trust boundaries" section and the skeptic's
  `blocking` flag.
- If the skeptic's `blocking` is `true`, the final report must carry a
  visible DRAFT/human-review-required marker. This is enforced in
  `report-composer.md`; don't remove it when editing that agent.
