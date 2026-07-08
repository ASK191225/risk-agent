"""
Builds the versioned prompt registry from the canonical subagent definitions
in .claude/agents/*.md.

.claude/agents/*.md is the single source of truth (it's what Claude Code
actually executes). This script snapshots each agent's prompt body into
prompts/<agent>.md and records metadata in prompts/registry.json, so the
project has an explicit, versioned prompt registry artifact as required by
the project spec (prompt name, version, agent, model, stage, raw text)
without hand-duplicating and risking drift.

Re-run this after editing any .claude/agents/*.md to refresh the registry:
    python engine/build_prompt_registry.py

Bumps version automatically only if content changed since the last snapshot.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"
PROMPTS_DIR = ROOT / "prompts"
REGISTRY_PATH = PROMPTS_DIR / "registry.json"

# stage number, matching the pipeline order in the risk-assess skill
STAGE_ORDER = [
    "context-mapper",
    "assumption-agent",
    "risk-generator",
    "risk-reviewer",
    "risk-scorer",
    "prioritizer",
    "mitigation-planner",
    "residual-estimator",
    "framework-mapper",
    "compliance-reviewer",
    "skeptic",
    "report-composer",
]

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


def parse_agent_file(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise ValueError(f"{path} has no parseable frontmatter")
    fm_text, body = m.group(1), m.group(2)
    fm: dict = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, body.strip()


def main() -> int:
    existing = json.loads(REGISTRY_PATH.read_text(encoding="utf-8")) if REGISTRY_PATH.exists() else []
    existing_by_name = {e["agent"]: e for e in existing}

    registry = []
    for stage_num, agent_name in enumerate(STAGE_ORDER, start=1):
        agent_path = AGENTS_DIR / f"{agent_name}.md"
        if not agent_path.exists():
            print(f"warning: missing agent file for '{agent_name}', skipping")
            continue
        fm, body = parse_agent_file(agent_path)

        prompt_filename = agent_name.replace("-", "_") + ".md"
        prompt_path = PROMPTS_DIR / prompt_filename

        prev = existing_by_name.get(agent_name)
        prev_body = None
        if prev and prompt_path.exists():
            prev_body = prompt_path.read_text(encoding="utf-8")
        version = 1
        if prev:
            version = prev.get("version", 1)
            if prev_body != body:
                version += 1

        prompt_path.write_text(body, encoding="utf-8")

        registry.append(
            {
                "stage": stage_num,
                "agent": agent_name,
                "prompt_file": f"prompts/{prompt_filename}",
                "source_of_truth": f".claude/agents/{agent_name}.md",
                "version": version,
                "model": fm.get("model", "inherit"),
                "tools": fm.get("tools", ""),
                "description": fm.get("description", ""),
            }
        )

    REGISTRY_PATH.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(f"wrote {len(registry)} entries to {REGISTRY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
