"""
Schema validator CLI.

Every agent in the pipeline MUST run this on its own output before reporting
"done" to the orchestrator, and the orchestrator MUST run it again itself
before advancing to the next stage (belt and suspenders: an agent claiming
success is not evidence of success).

Usage:
    python schemas/validate.py <stage> <path/to/output.json>

Exit code 0 + "VALID" on stdout if it validates.
Exit code 1 + "INVALID" + pydantic error detail if it does not.

<stage> is one of the keys in STAGE_MODELS below (matches the numbered
filenames used in runs/<run_id>/).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.models import (  # noqa: E402
    AssumptionSet,
    CandidateRiskSet,
    ComplianceReviewSet,
    ContextModel,
    FinalReportManifest,
    FrameworkMappingSet,
    MitigationPlanSet,
    PrioritizedRiskSet,
    ResidualRiskSet,
    ReviewedRiskSet,
    ScenarioInput,
    ScoredRiskSet,
    SkepticReview,
)

STAGE_MODELS = {
    "01_input": ScenarioInput,
    "02_context": ContextModel,
    "03_assumptions": AssumptionSet,
    "04_candidate_risks": CandidateRiskSet,
    "05_reviewed_risks": ReviewedRiskSet,
    "06_scored_risks": ScoredRiskSet,
    "07_prioritized_risks": PrioritizedRiskSet,
    "08_mitigations": MitigationPlanSet,
    "09_residuals": ResidualRiskSet,
    "10_framework_mappings": FrameworkMappingSet,
    "11_compliance_review": ComplianceReviewSet,
    "12_skeptic_review": SkepticReview,
    "manifest": FinalReportManifest,
}


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: python {sys.argv[0]} <stage> <path/to/output.json>")
        print(f"stages: {', '.join(STAGE_MODELS)}")
        return 2

    stage, path_str = sys.argv[1], sys.argv[2]
    model = STAGE_MODELS.get(stage)
    if model is None:
        print(f"INVALID: unknown stage '{stage}'. Known stages: {', '.join(STAGE_MODELS)}")
        return 1

    path = Path(path_str)
    if not path.exists():
        print(f"INVALID: file not found: {path}")
        return 1

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"INVALID: not valid JSON: {e}")
        return 1

    try:
        model.model_validate(data)
    except Exception as e:  # pydantic ValidationError
        print(f"INVALID: schema violation for stage '{stage}':\n{e}")
        return 1

    print(f"VALID: {path} conforms to {model.__name__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
