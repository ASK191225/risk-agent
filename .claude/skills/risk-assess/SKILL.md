---
name: risk-assess
description: Run the full 12-stage agentic cyber risk assessment pipeline on a scenario, context extraction, assumptions, risk generation/review/scoring, prioritization, mitigation planning, residual risk, framework mapping, compliance review, skeptic pass, and final report. Use when the user wants a risk assessment of an org/scenario, invoked as /risk-assess.
---

# risk-assess: pipeline orchestrator runbook

You are the orchestrator for this run. You do not do the analysis yourself
,  every stage is a dedicated subagent (`.claude/agents/*.md`) with its own
detailed instructions and self-validation. Your job is: get the scenario,
scaffold the run, invoke each stage's agent in the correct order with the
right context, verify each output yourself before advancing (do not just
trust an agent's self-report), log everything, retry on failure, and
surface the final report and any human-review flags to the user.

Work from the project root (the directory containing `.claude/`, `schemas/`,
`engine/`, `runs/`), that's `risk-agent/`. If you're not sure you're there,
confirm with `pwd`/`ls` before running any Python command below (all paths
below are relative to that root).

## 0. Get the scenario

If `$ARGUMENTS` (the text passed after `/risk-assess`) is non-empty, treat
it as the scenario: if it looks like a file path that exists, use
`--source file --file-path "<path>"`; otherwise treat it as pasted text
with `--source pasted --text "<text>"`.

If no arguments were given, ask the user directly in chat (plain question,
no tool needed):

> "Give me the scenario to assess, either paste the text directly, or
> give me a file path to read it from."

Once you have it, proceed. Do not overthink this step or use
AskUserQuestion for it, it's free-text input, just ask plainly.

## 1. Initialize the run

Before scaffolding, skim the scenario text yourself and pick a short
organization/subject name (e.g. "Acme Corp", "Northwind Health"), this
doesn't need an agent call, just read it off the text. If the scenario
truly doesn't name an org, use a short descriptive subject instead (e.g.
"fintech-startup-scenario"). Pass it as `--name` so the run folder is
identifiable at a glance instead of a bare timestamp:

```
run_id=$(python engine/run_manager.py init --source <pasted|file> --text "<text>" --name "<org or subject name>")
```
(use `--file-path "<path>"` instead of `--text` for file source; `--name`
is optional, omitting it falls back to a timestamp-only run_id, but
always supply it when you can)

This creates `runs/<run_id>/01_input.json`, an empty `decision_log.json`,
and an empty `prompts_manifest.json`. Capture `run_id`, every stage below
needs `runs/<run_id>` as its `run_dir`. `run_id` will look like
`acme-corp_20260707T235959Z` (slugified name + UTC timestamp) rather than
a bare timestamp.

Tell the user the run has started and give them the run_id.

## 2. Run the pipeline, stage by stage

For each stage below: invoke the Agent tool with the given `subagent_type`,
a prompt telling it the `run_dir` (absolute or relative path is fine, be
consistent), then **independently** verify with
`python schemas/validate.py <stage> "runs/<run_id>/<file>"` yourself before
moving on, the subagent validates its own output per its instructions,
but you re-check because an agent's self-report is not proof.

If validation fails: re-invoke the SAME subagent with a prompt that
includes the exact validator error output and an instruction to fix it.
Retry up to 2 times. If it still fails after 2 retries, STOP the pipeline,
tell the user exactly which stage and error blocked it, and do not
fabricate a workaround.

| # | subagent_type | reads | writes | validate stage key |
|---|---|---|---|---|
| 1 | `context-mapper` | 01_input.json | 02_context.json | `02_context` |
| 2 | `assumption-agent` | 01,02 | 03_assumptions.json | `03_assumptions` |
| 3 | `risk-generator` | 01,02,03 | 04_candidate_risks.json | `04_candidate_risks` |
| 4 | `risk-reviewer` | 04 | 05_reviewed_risks.json | `05_reviewed_risks` |
| 5 | `risk-scorer` | 05 | 06_scored_risks.json | `06_scored_risks` |
| 6 | `prioritizer` | 06 | 07_prioritized_risks.json | `07_prioritized_risks` |
| 7 | `mitigation-planner` | 05,07 | 08_mitigations.json | `08_mitigations` |
| 8 | `residual-estimator` | 06,08 | 09_residuals.json | `09_residuals` |
| 9 | `framework-mapper` | 02,05,08 | 10_framework_mappings.json | `10_framework_mappings` |
| 10 | `compliance-reviewer` | 02,05,08,10 | 11_compliance_review.json | `11_compliance_review` |
| 11 | `skeptic` | 03,05,06,07,08,09,10,11 | 12_skeptic_review.json | `12_skeptic_review` |
| 12 | `report-composer` | all of the above | 13_final_report.md, manifest.json | `manifest` |

Example invocation prompt for stage 1 (adapt the stage name/number for
each row): *"run_dir is `runs/<run_id>`. Execute your stage per your
instructions."*, the subagent's own `.claude/agents/<name>.md` system
prompt already has the full task spec; you don't need to repeat it, just
give it the run_dir.

Stages 4, 5, 7, 8, 9 additionally invoke `engine/policy_engine.py` inside
their own instructions, that already happens as part of the subagent's
self-check. You don't need to re-run it yourself unless you want an extra
sanity pass; if you do, `python engine/policy_engine.py "runs/<run_id>" --through-stage <N>` and treat HARD violations the same as a schema validation failure (retry the responsible stage's agent with the violation text).

## 3. After the pipeline completes

Read `runs/<run_id>/13_final_report.md` and `runs/<run_id>/manifest.json`.
Report back to the user in chat:

- run_id and full path to the final report
- whether the report is marked DRAFT/human-review-required (from the
  skeptic's `blocking` field / manifest `human_review_flags`)
- the top1 risk title and one-line justification
- a short list of what needs human sign-off before this is used for
  anything consequential (pull from `human_review_flags`)

Do not silently summarize away a `blocking: true` skeptic result, always
surface it prominently.

## Notes on scale

This is a single scenario, single run. If the user wants to compare
multiple scenarios, run this whole procedure once per scenario (separate
run_id each time) rather than trying to interleave them, stages are
sequential-dependency chains within one run and shouldn't be parallelized
across runs in the same conversation unless the user explicitly asks for
a batch/compare mode (not built yet, flag it as a stretch-goal option if
asked).
