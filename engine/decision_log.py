"""
Append-only decision log for a run.

Every pipeline stage MUST log itself here after it completes (whether it
passed or failed validation) so the run folder is a full audit trail:
stage, inputs consumed, output produced, validation status, retry count,
free-text notes.

Usage:
    python engine/decision_log.py append <run_dir> \
        --stage 02_context \
        --inputs 01_input.json \
        --output 02_context.json \
        --status valid \
        --retries 0 \
        --notes "context extracted cleanly"
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    append_p = sub.add_parser("append")
    append_p.add_argument("run_dir")
    append_p.add_argument("--stage", required=True)
    append_p.add_argument("--inputs", default="", help="comma-separated input filenames")
    append_p.add_argument("--output", required=True)
    append_p.add_argument("--status", choices=["valid", "invalid", "skipped"], required=True)
    append_p.add_argument("--retries", type=int, default=0)
    append_p.add_argument("--notes", default="")

    args = parser.parse_args()
    run_dir = Path(args.run_dir)
    log_path = run_dir / "decision_log.json"

    entries = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else []
    entries.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "stage": args.stage,
            "inputs": [s for s in args.inputs.split(",") if s],
            "output": args.output,
            "validation_status": args.status,
            "retries": args.retries,
            "notes": args.notes,
        }
    )
    log_path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print(f"logged stage '{args.stage}' -> {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
