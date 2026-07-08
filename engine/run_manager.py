"""
Run scaffolding.

Creates runs/<run_id>/ with the input artifact stamped, ready for the
pipeline to fill in the remaining numbered stage files.

Usage:
    python engine/run_manager.py init --source pasted --text "..." --name "Acme Corp"
    python engine/run_manager.py init --source file --file-path "C:\\path\\to\\scenario.txt" --name "Acme Corp"

--name is optional but strongly recommended. Pass the organization/subject
name from the scenario (the calling skill is expected to read the scenario
text and supply this; this script has no way to infer it on its own). It is
slugified into the run_id so runs are identifiable at a glance
(runs/acme-corp_20260707T235959Z/) instead of bare timestamps. Omitting it
falls back to a timestamp-only run_id.

Prints the run_id to stdout on success (and nothing else), so the calling
skill can capture it directly: run_id=$(python engine/run_manager.py init ...)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"

MAX_SLUG_LEN = 40


def slugify(name: str) -> str:
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[:MAX_SLUG_LEN].rstrip("-")


def make_run_id(name: str | None = None) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = slugify(name) if name else ""
    return f"{slug}_{timestamp}" if slug else f"run_{timestamp}"


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init")
    init_p.add_argument("--source", choices=["pasted", "file"], required=True)
    init_p.add_argument("--text", default=None, help="raw scenario text (source=pasted)")
    init_p.add_argument("--file-path", default=None, help="path to scenario file (source=file)")
    init_p.add_argument(
        "--name",
        default=None,
        help="organization/subject name from the scenario, used to build a readable run_id",
    )

    args = parser.parse_args()

    if args.cmd == "init":
        if args.source == "pasted":
            if not args.text:
                print("error: --text is required when --source pasted", file=sys.stderr)
                return 1
            raw_text = args.text
            file_path = None
        else:
            if not args.file_path:
                print("error: --file-path is required when --source file", file=sys.stderr)
                return 1
            p = Path(args.file_path)
            if not p.exists():
                print(f"error: file not found: {p}", file=sys.stderr)
                return 1
            raw_text = p.read_text(encoding="utf-8")
            file_path = str(p)

        run_id = make_run_id(args.name)
        run_dir = RUNS_DIR / run_id
        run_dir.mkdir(parents=True, exist_ok=False)

        scenario_input = {
            "raw_text": raw_text,
            "source": args.source,
            "file_path": file_path,
            "received_at": datetime.now(timezone.utc).isoformat(),
        }
        (run_dir / "01_input.json").write_text(
            json.dumps(scenario_input, indent=2), encoding="utf-8"
        )
        (run_dir / "decision_log.json").write_text("[]", encoding="utf-8")
        (run_dir / "prompts_manifest.json").write_text("[]", encoding="utf-8")

        print(run_id)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
