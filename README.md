# risk-agent

A scenario-agnostic, agentic cyber risk assessment system: ingest a scenario, identify **5 distinct security risks** (threat source, asset, exposure), run an explicit agentic prioritization workflow to pick the single highest and explain why, generate a mitigation for each (control,  
owner, effort), estimate residual likelihood reduction, flag what needs  
human review before anyone trusts the output. As a value-add layer beyond  
the core assessment, map everything to NIST CSF / ISO 27001 / SOC 2 (and  
NIST AI RMF only where the scenario itself involves a deployed AI system).

It runs as a Claude Code project: a pipeline of 12 custom subagents
orchestrated by one skill, not a standalone app with its own LLM API key.
Agent prompts are in `.claude/agents/`. JSON schemas are in
`schemas/models.py`. Semantic validation rules are in
`engine/policy_engine.py`. The orchestrator runbook is
`.claude/skills/risk-assess/SKILL.md`.

## Requirements

- [Claude Code](https://claude.com/claude-code) CLI
- Python 3.10+ with `pydantic>=2.6` (`pip install -r requirements.txt`)

## Usage

```
cd risk-agent
claude
```

Then, inside the Claude Code session:

```
/risk-assess
```

You'll be asked for a scenario: paste text directly, or give a file path.
You can also pass it inline: `/risk-assess <scenario text or file path>`.

The pipeline runs all 12 stages, validating and logging as it goes. Each
run gets its own folder named from the organization/subject in the
scenario plus a UTC timestamp (e.g. `runs/acme-corp_20260707T235959Z/`),
so runs are identifiable at a glance instead of bare timestamps:

```
runs/<org-name>_<timestamp>/
  01_input.json ... 12_skeptic_review.json   # every stage's artifact
  13_final_report.md                          # the human-facing report (see below)
  manifest.json                                # run summary + validation status
  decision_log.json                            # full audit trail
```

`13_final_report.md`'s core sections (the 5 risks, why #1 beat #2,
mitigations, residual likelihood reduction, human-review checklist) cover
**exactly the top 5 prioritized risks**. That's the deliverable. The
pipeline internally reviews/scores/mitigates every accepted risk (often
more than 5), but anything outside the top 5 is relegated to an appendix
in the report (risk_id, title, score, plus a pointer to the JSON artifacts
for full detail), not blended into the main body. Framework mapping and SOC 2
evidence sections are explicitly framed in the report as a value-add layer
on top of the core assessment, not the heart of it.

## Pipeline

```
scenario
  -> context-mapper          (org/security context, unknowns)
  -> assumption-agent        (explicit, rated assumptions)
  -> risk-generator          (8-10 candidate risk scenarios)
  -> risk-reviewer           (dedupe, reject weak scenarios)
  -> risk-scorer             (transparent likelihood x impact scoring)
  -> prioritizer             (rank, top 5, top 1 + why)
  -> mitigation-planner      (owner/effort/timeline per risk)
  -> residual-estimator      (heuristic residual likelihood reduction)
  -> framework-mapper        (NIST CSF / ISO 27001 / SOC 2 / NIST AI RMF)
  -> compliance-reviewer     (adversarial check on the framework mapping)
  -> skeptic                 (challenges the whole run, sets human-review flags)
  -> report-composer         (assembles final_report.md + manifest)
```

Each arrow is a schema-validated handoff (`schemas/models.py` +
`schemas/validate.py`), with semantic rules layered on top
(`engine/policy_engine.py`). Examples: every mitigation needs an owner,
every residual estimate needs stated assumptions, NIST AI RMF can't be used
unless the scenario has a real org-deployed AI system, SOC 2 Type 2
evidence claims must actually read as time-based.

## Project layout

```
risk-agent/
  .claude/
    agents/          # the 12 subagents; each file is that stage's full prompt
    skills/risk-assess/SKILL.md   # orchestrator runbook
  schemas/
    models.py         # Pydantic contract for every stage
    validate.py        # CLI validator
  engine/
    run_manager.py      # scaffolds a new run
    decision_log.py     # audit trail
    policy_engine.py    # semantic/policy rules beyond schema shape
    build_prompt_registry.py       # regenerate prompts/ snapshot + registry.json
  prompts/             # versioned, generated snapshot of each agent's prompt
  runs/<org-name>_<timestamp>/   # per-run artifacts (gitignored; may
                                  # contain sensitive scenario text)
  reports/               # (reserved for stretch: copying/exporting reports)
```

## What this system does NOT claim

- Exact breach probabilities (`09_residuals.json` is explicitly labeled a
heuristic comparative estimate).
- Legal compliance determinations or audit certification (framework
mapping shows *alignment and expected evidence*, not a pass/fail audit
result; that's `compliance-reviewer`'s whole job: catching overclaims).
- Precise financial exposure.

Every run's skeptic stage decides whether the report needs mandatory human
sign-off before being used for anything consequential (`blocking: true` in
`12_skeptic_review.json`, surfaced as a DRAFT marker on the final report).

## Extending it

- Edit a stage's behavior by editing its `.claude/agents/<name>.md` file,
then run `python engine/build_prompt_registry.py` to refresh the
versioned prompt snapshot under `prompts/`.
- Add a new semantic rule in `engine/policy_engine.py` (see the existing
`check_`* functions for the pattern) and wire it into
`CHECKS_BY_MAX_STAGE`.
- Add a new stage output field by editing the relevant model in
`schemas/models.py`. `schemas/validate.py` picks it up automatically.

