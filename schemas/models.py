"""
Pydantic schemas for every artifact produced by the risk-agent pipeline.

These are the contract between stages. Every agent MUST produce output that
validates against the model listed here for its stage (see schemas/validate.py
and prompts/registry.json for the stage -> model mapping). Nothing downstream
should ever have to guess at a missing field.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high"]
Confidence = Literal["low", "medium", "high"]
Effort = Literal["low", "medium", "high"]
EvidenceTag = Literal[
    "scenario_fact",
    "inferred_assumption",
    "heuristic_estimate",
    "framework_inference",
    "human_review_required",
]
MappingBasis = Literal["direct", "inferred"]


# ---------------------------------------------------------------------------
# Stage 1: input / context
# ---------------------------------------------------------------------------


class ScenarioInput(BaseModel):
    raw_text: str
    source: Literal["pasted", "file"]
    file_path: Optional[str] = None
    received_at: str  # ISO-8601, stamped by engine/run_manager.py, not the LLM


class ContextModel(BaseModel):
    company_size: str
    industry: str
    cloud_stack: list[str] = Field(default_factory=list)
    identity_stack: list[str] = Field(default_factory=list)
    app_stack: list[str] = Field(default_factory=list)
    critical_assets: list[str]
    workforce_model: str
    compliance_posture: list[str] = Field(default_factory=list)
    stated_controls: list[str] = Field(default_factory=list)
    # Catch-all for material scenario facts that don't fit any typed field
    # above (staffing/security-org maturity, budget, growth stage, etc.).
    # Exists so nothing a downstream stage relies on can sit undocumented
    # between "typed fact" and "assumption". Every such fact must land
    # here verbatim if it doesn't have a dedicated field.
    stated_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    deployed_ai_systems: bool
    ai_system_notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Stage 2: assumptions
# ---------------------------------------------------------------------------


class Assumption(BaseModel):
    assumption_id: str
    text: str
    category: str
    severity: Severity
    reason_needed: str
    impacts_scoring: bool


class AssumptionSet(BaseModel):
    assumptions: list[Assumption]


# ---------------------------------------------------------------------------
# Stage 3/4: risk generation + review
# ---------------------------------------------------------------------------


class RiskScenario(BaseModel):
    risk_id: str
    title: str
    threat_source: str
    asset: str
    exposure: str
    attack_path: str
    loss_type: list[str]
    business_impact: str
    scenario_facts: list[str] = Field(default_factory=list)
    assumptions_used: list[str] = Field(default_factory=list)


class CandidateRiskSet(BaseModel):
    risks: list[RiskScenario]


class ReviewedRisk(RiskScenario):
    review_status: Literal["accepted", "merged", "rejected"]
    rejection_reason: Optional[str] = None
    merged_from: list[str] = Field(default_factory=list)


class ReviewedRiskSet(BaseModel):
    risks: list[ReviewedRisk]


# ---------------------------------------------------------------------------
# Stage 5: scoring
# ---------------------------------------------------------------------------


class LikelihoodFactors(BaseModel):
    threat_activity: int = Field(ge=1, le=5)
    exposure_strength: int = Field(ge=1, le=5)
    exploit_ease: int = Field(ge=1, le=5)
    control_weakness: int = Field(ge=1, le=5)


class ImpactFactors(BaseModel):
    data_sensitivity: int = Field(ge=1, le=5)
    operational_disruption: int = Field(ge=1, le=5)
    customer_revenue_harm: int = Field(ge=1, le=5)
    compliance_contractual_harm: int = Field(ge=1, le=5)


class ScoredRisk(BaseModel):
    risk_id: str
    likelihood_factors: LikelihoodFactors
    impact_factors: ImpactFactors
    likelihood_score: float
    impact_score: float
    risk_score: float
    confidence: Confidence
    rationale: str
    evidence_tags: list[EvidenceTag]


class ScoredRiskSet(BaseModel):
    risks: list[ScoredRisk]


# ---------------------------------------------------------------------------
# Stage 6: prioritization
# ---------------------------------------------------------------------------


class PrioritizedRiskSet(BaseModel):
    ranked_risk_ids: list[str]
    top5: list[str]
    top1: str
    justification: str  # explicit "why #1 beat #2" narrative


# ---------------------------------------------------------------------------
# Stage 7: mitigations
# ---------------------------------------------------------------------------


class Mitigation(BaseModel):
    control_name: str
    control_type: str
    owner: str
    effort: Effort
    timeline: str
    dependency: Optional[str] = None
    implementation_notes: str


class MitigationPlan(BaseModel):
    risk_id: str
    mitigations: list[Mitigation]


class MitigationPlanSet(BaseModel):
    plans: list[MitigationPlan]


# ---------------------------------------------------------------------------
# Stage 8: residual risk
# ---------------------------------------------------------------------------


class ResidualRiskEstimate(BaseModel):
    risk_id: str
    baseline_likelihood: float = Field(ge=0, le=1)
    control_effectiveness: float = Field(ge=0, le=1)
    residual_likelihood: float = Field(ge=0, le=1)
    delta: float
    assumptions: list[str]
    disclaimer: str = (
        "Heuristic comparative estimate, not an actuarial breach probability."
    )


class ResidualRiskSet(BaseModel):
    estimates: list[ResidualRiskEstimate]
    aggregate_delta: float


# ---------------------------------------------------------------------------
# Stage 9: framework mapping
# ---------------------------------------------------------------------------


class FrameworkMapping(BaseModel):
    risk_id: str
    nist_csf: list[str] = Field(default_factory=list)
    iso_27001: list[str] = Field(default_factory=list)
    soc2_tsc: list[str] = Field(default_factory=list)
    nist_ai_rmf: list[str] = Field(default_factory=list)
    type1_evidence: list[str] = Field(default_factory=list)
    type2_evidence: list[str] = Field(default_factory=list)
    mapping_basis: MappingBasis
    mapping_confidence: Confidence
    notes: list[str] = Field(default_factory=list)


class FrameworkMappingSet(BaseModel):
    mappings: list[FrameworkMapping]


# ---------------------------------------------------------------------------
# Stage 10: compliance review
# ---------------------------------------------------------------------------


class ComplianceReview(BaseModel):
    risk_id: str
    mapping_valid: bool
    findings: list[str]
    overclaims: list[str] = Field(default_factory=list)
    human_review_required: bool


class ComplianceReviewSet(BaseModel):
    reviews: list[ComplianceReview]


# ---------------------------------------------------------------------------
# Stage 11: skeptic
# ---------------------------------------------------------------------------


class SkepticFinding(BaseModel):
    risk_id: str  # or "global" for cross-cutting findings
    category: Literal[
        "assumption",
        "control_effectiveness",
        "ranking",
        "owner_feasibility",
        "compliance_claim",
    ]
    concern: str
    severity: Severity
    recommendation: str


class SkepticReview(BaseModel):
    findings: list[SkepticFinding]
    overall_confidence_in_report: Confidence
    blocking: bool  # True => report must not ship without human sign-off


# ---------------------------------------------------------------------------
# Stage 12: final manifest
# ---------------------------------------------------------------------------


class FinalReportManifest(BaseModel):
    run_id: str
    created_stages: list[str]
    validation_status: dict[str, str]
    human_review_flags: list[str]
    report_path: str
