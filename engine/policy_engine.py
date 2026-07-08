"""
Semantic / policy validation, layered on top of (not instead of) schema
validation from schemas/validate.py.

Schema validation only proves the JSON has the right shape. This proves the
content obeys the project's actual rules: the stuff a human reviewer would
flag even if every field were technically present. Run this once a run
directory has all 12 stage files (or pass --through-stage to check a
partial run).

Usage:
    python engine/policy_engine.py <run_dir> [--through-stage 12]

Exit code 0 if no HARD violations (WARN-level findings do not fail the run
but are always printed and always carried into human_review_flags).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

Violation = tuple[str, str, str]  # (level, rule, detail)   level: HARD | WARN


def load(run_dir: Path, name: str):
    p = run_dir / name
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def check_context_stated_facts(scenario_input: dict | None, context: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not scenario_input or not context:
        return out
    raw_len = len((scenario_input.get("raw_text") or "").strip())
    if raw_len > 200 and not context.get("stated_facts"):
        out.append((
            "WARN",
            "context_stated_facts_empty",
            "02_context.json has an empty stated_facts list despite a non-trivial scenario. "
            "verify no material fact (staffing, budget, org maturity, incident history) was "
            "dropped instead of captured",
        ))
    return out


def check_risks_complete(reviewed: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not reviewed:
        return out
    for r in reviewed.get("risks", []):
        if r.get("review_status") != "accepted":
            continue
        for field in ("threat_source", "asset", "exposure"):
            if not (r.get(field) or "").strip():
                out.append(("HARD", "risk_completeness", f"{r.get('risk_id')} missing {field}"))
    return out


def check_scores_have_rationale(scored: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not scored:
        return out
    for r in scored.get("risks", []):
        if not (r.get("rationale") or "").strip():
            out.append(("HARD", "score_rationale", f"{r.get('risk_id')} has no scoring rationale"))
    return out


def check_mitigations_have_owner_effort(mitigations: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not mitigations:
        return out
    for plan in mitigations.get("plans", []):
        for m in plan.get("mitigations", []):
            if not (m.get("owner") or "").strip():
                out.append(("HARD", "mitigation_owner", f"{plan.get('risk_id')}: '{m.get('control_name')}' has no owner"))
            if not m.get("effort"):
                out.append(("HARD", "mitigation_effort", f"{plan.get('risk_id')}: '{m.get('control_name')}' has no effort estimate"))
    return out


def check_residuals_have_assumptions(residuals: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not residuals:
        return out
    for e in residuals.get("estimates", []):
        if not e.get("assumptions"):
            out.append(("HARD", "residual_assumptions", f"{e.get('risk_id')} residual estimate has no stated assumptions"))
    return out


def check_assumption_ids_registered(reviewed: dict | None, assumptions: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not reviewed or not assumptions:
        return out
    known_ids = {a["assumption_id"] for a in assumptions.get("assumptions", [])}
    for r in reviewed.get("risks", []):
        for aid in r.get("assumptions_used", []):
            if aid not in known_ids:
                out.append(("HARD", "unregistered_assumption", f"{r.get('risk_id')} references unknown assumption_id '{aid}'"))
    return out


def check_ai_rmf_usage(context: dict | None, mappings: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not context or not mappings:
        return out
    if context.get("deployed_ai_systems"):
        return out
    for m in mappings.get("mappings", []):
        if m.get("nist_ai_rmf"):
            out.append((
                "HARD",
                "ai_rmf_misuse",
                f"{m.get('risk_id')} maps to NIST AI RMF but context.deployed_ai_systems is false",
            ))
    return out


def check_type2_evidence_is_time_based(mappings: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not mappings:
        return out
    time_markers = (
        "over time", "recurring", "period", "history", "log", "review", "monitor",
        "ticket", "alert", "trend", "sample", "quarterly", "monthly", "continuous",
    )
    for m in mappings.get("mappings", []):
        for ev in m.get("type2_evidence", []):
            if not any(marker in ev.lower() for marker in time_markers):
                out.append((
                    "WARN",
                    "type2_evidence_shape",
                    f"{m.get('risk_id')}: Type 2 evidence item '{ev}' doesn't read as time-based/operating-effectiveness evidence",
                ))
    return out


def check_framework_mapping_basis(mappings: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not mappings:
        return out
    for m in mappings.get("mappings", []):
        if not m.get("mapping_basis"):
            out.append(("HARD", "mapping_basis_missing", f"{m.get('risk_id')} mapping has no direct/inferred basis"))
    return out


def check_top_risk_has_human_review(prioritized: dict | None, compliance: dict | None, skeptic: dict | None) -> list[Violation]:
    out: list[Violation] = []
    if not prioritized:
        return out
    top1 = prioritized.get("top1")
    if not top1:
        return out
    flagged = False
    if compliance:
        flagged = flagged or any(
            c.get("risk_id") == top1 and c.get("human_review_required") for c in compliance.get("reviews", [])
        )
    if skeptic:
        flagged = flagged or any(f.get("risk_id") in (top1, "global") for f in skeptic.get("findings", []))
        flagged = flagged or skeptic.get("blocking") is True
    if not flagged:
        out.append(("WARN", "top_risk_human_review", f"top risk {top1} has no explicit human-review flag from compliance or skeptic review"))
    return out


CHECKS_BY_MAX_STAGE = [
    # (min stage number required to run this check, fn, args-as-file-names)
    (2, check_context_stated_facts, ["01_input.json", "02_context.json"]),
    (5, check_risks_complete, ["05_reviewed_risks.json"]),
    (6, check_scores_have_rationale, ["06_scored_risks.json"]),
    (5, check_assumption_ids_registered, ["05_reviewed_risks.json", "03_assumptions.json"]),
    (8, check_mitigations_have_owner_effort, ["08_mitigations.json"]),
    (9, check_residuals_have_assumptions, ["09_residuals.json"]),
    (10, check_ai_rmf_usage, ["02_context.json", "10_framework_mappings.json"]),
    (10, check_type2_evidence_is_time_based, ["10_framework_mappings.json"]),
    (10, check_framework_mapping_basis, ["10_framework_mappings.json"]),
    (12, check_top_risk_has_human_review, ["07_prioritized_risks.json", "11_compliance_review.json", "12_skeptic_review.json"]),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--through-stage", type=int, default=12)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"error: run dir not found: {run_dir}", file=sys.stderr)
        return 2

    all_violations: list[Violation] = []
    for min_stage, fn, files in CHECKS_BY_MAX_STAGE:
        if min_stage > args.through_stage:
            continue
        loaded = [load(run_dir, f) for f in files]
        all_violations.extend(fn(*loaded))

    hard = [v for v in all_violations if v[0] == "HARD"]
    warn = [v for v in all_violations if v[0] == "WARN"]

    for level, rule, detail in all_violations:
        print(f"[{level}] {rule}: {detail}")

    print(f"\n{len(hard)} hard violation(s), {len(warn)} warning(s)")
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
