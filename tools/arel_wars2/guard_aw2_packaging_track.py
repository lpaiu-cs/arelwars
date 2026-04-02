#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "phase5-to-phase10-status.json"


def main() -> None:
    blocked = {
        "status": "blocked",
        "reason": "route-a-not-selected",
    }
    report = {
        "track": "aw2-feasibility-first-packaging",
        "route": "C",
        "packagingAllowed": False,
        "overallStatus": "closed",
        "phases": {
            "phase5": blocked,
            "phase6": blocked,
            "phase7": blocked,
            "phase8": blocked,
            "phase9": blocked,
            "phase10": blocked,
        },
        "note": "Phase 5 through Phase 10 require Route A. Current environment selected Route C.",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overallStatus": report["overallStatus"], "packagingAllowed": False}, indent=2))


if __name__ == "__main__":
    main()
