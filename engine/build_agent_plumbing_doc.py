"""
Builds PLUMBING.md at the project root: a single submission-ready document
exposing the actual prompts, schemas, orchestration logic, tool access, and
validation/escalation rules behind every stage of the pipeline.

This exists specifically to satisfy "show the plumbing, not just the
output"; a run's `13_final_report.md` is the assessment; this file is the
system design artifact that goes alongside it.

Not per-run. Regenerate after editing any `.claude/agents/*.md`,
`.claude/skills/risk-assess/SKILL.md`, `schemas/models.py`, or
`engine/policy_engine.py`:

    python engine/build_agent_plumbing_doc.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_prompt_registry import STAGE_ORDER, AGENTS_DIR, parse_agent_file  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SKILL_PATH = ROOT / ".claude" / "skills" / "risk-assess" / "SKILL.md"
MODELS_PATH = ROOT / "schemas" / "models.py"
VALIDATE_PATH = ROOT / "schemas" / "validate.py"
POLICY_PATH = ROOT / "engine" / "policy_engine.py"
OUTPUT_PATH = ROOT / "PLUMBING.md"


def build() -> str:
    parts: list[str] = []

    parts.append(
        "# risk-agent: Agent Prompts, Configuration, and Tool Definitions\n\n"
        "This is the design/implementation artifact for the risk-agent pipeline: "
        "the actual system prompts, JSON schemas, tool access, validation rules, "
        "and orchestration logic behind every one of the 12 stages. Nothing here "
        "is a summary or a description of behavior. Every prompt and schema "
        "below is the literal source used at runtime, generated directly from "
        "`.claude/agents/*.md`, `.claude/skills/risk-assess/SKILL.md`, "
        "`schemas/models.py`, and `engine/policy_engine.py` by "
        "`engine/build_agent_plumbing_doc.py`. Regenerate after editing any of "
        "those files. Do not hand-edit this file.\n\n"
        "For a specific run's actual output, see `runs/<run_id>/13_final_report.md`. "
        "This document is the system design, not a result.\n\n"
        "---\n"
    )

    # --- pipeline overview table -------------------------------------------------
    parts.append("## Pipeline overview\n\n")
    parts.append("| Stage | Agent | Model | Tools |\n|---|---|---|---|\n")
    agent_meta = []
    for i, agent_name in enumerate(STAGE_ORDER, start=1):
        agent_path = AGENTS_DIR / f"{agent_name}.md"
        fm, body = parse_agent_file(agent_path)
        agent_meta.append((i, agent_name, fm, body))
        parts.append(f"| {i} | `{agent_name}` | {fm.get('model', 'inherit')} | {fm.get('tools', '')} |\n")
    parts.append("\n---\n")

    # --- orchestration runbook ----------------------------------------------------
    parts.append("\n## Orchestration runbook (`.claude/skills/risk-assess/SKILL.md`)\n\n")
    parts.append("This is what sequences the 12 agents, validates each handoff, "
                  "retries on failure, and assembles the final report.\n\n")
    parts.append("```markdown\n")
    parts.append(SKILL_PATH.read_text(encoding="utf-8"))
    parts.append("\n```\n\n---\n")

    # --- per-agent full prompts ----------------------------------------------------
    parts.append("\n## Agent prompts (full, verbatim)\n\n")
    parts.append(
        "Each block below is the complete, unmodified content of that agent's "
        "`.claude/agents/<name>.md` file: role, task, constraints, schema, "
        "forbidden behavior, quality rubric, and output/validation rules "
        "(including the exact `schemas/validate.py` and `engine/policy_engine.py` "
        "invocations each agent runs on its own output before reporting done).\n\n"
    )
    for i, agent_name, fm, body in agent_meta:
        parts.append(f"### Stage {i}: `{agent_name}`\n\n")
        parts.append(f"**Description:** {fm.get('description', '')}\n\n")
        parts.append(f"**Tools:** {fm.get('tools', '')}  \n**Model:** {fm.get('model', 'inherit')}\n\n")
        parts.append("```markdown\n")
        parts.append(body)
        parts.append("\n```\n\n")

    parts.append("---\n")

    # --- schemas --------------------------------------------------------------------
    parts.append("\n## Schemas (`schemas/models.py`, full source)\n\n")
    parts.append(
        "The Pydantic contract every stage's output must satisfy. This is what "
        "`schemas/validate.py` checks each artifact against before the pipeline "
        "is allowed to advance.\n\n"
    )
    parts.append("```python\n")
    parts.append(MODELS_PATH.read_text(encoding="utf-8"))
    parts.append("\n```\n\n---\n")

    parts.append("\n## Schema validator CLI (`schemas/validate.py`, full source)\n\n")
    parts.append("```python\n")
    parts.append(VALIDATE_PATH.read_text(encoding="utf-8"))
    parts.append("\n```\n\n---\n")

    # --- policy engine ----------------------------------------------------------------
    parts.append("\n## Semantic policy rules (`engine/policy_engine.py`, full source)\n\n")
    parts.append(
        "Rules the JSON schema alone can't express. Examples: every mitigation "
        "needs an owner and effort estimate, NIST AI RMF can't be cited unless "
        "the scenario has a real org-deployed AI system, SOC 2 Type 2 evidence "
        "claims must read as time-based, every assumption_id a risk cites must "
        "actually exist in the assumption registry.\n\n"
    )
    parts.append("```python\n")
    parts.append(POLICY_PATH.read_text(encoding="utf-8"))
    parts.append("\n```\n")

    return "".join(parts)


def main() -> int:
    doc = build()
    OUTPUT_PATH.write_text(doc, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({len(doc)} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
