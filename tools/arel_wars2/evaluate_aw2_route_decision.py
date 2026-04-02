#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "phase4-route-decision.json"


def main() -> None:
    report = {
        "phase": 4,
        "track": "aw2-feasibility-first-packaging",
        "verdict": "route-c",
        "route": "C",
        "routeLabel": "static-reverse-engineering-only",
        "rationale": [
            "Original AW2 APK is present and statically analyzable.",
            "Existing x86_64 AVD rejects the APK with INSTALL_FAILED_NO_MATCHING_ABIS.",
            "The current Android Emulator build on this host cannot boot ARMv7 guests.",
            "The current Android Emulator build on this host cannot boot ARM64 guests either.",
            "Phases 1 and 2 remain blocked because no runnable original AW2 runtime exists in the current environment.",
            "Phase 3 static bootstrap is complete and remains productive.",
        ],
        "implications": {
            "phase5To10Allowed": False,
            "packagingAllowed": False,
            "originalEquivalenceAllowed": False,
            "staticReverseEngineeringAllowed": True,
        },
        "reopenConditions": [
            "A third-party Android runtime on this host that can execute armeabi-v7a apps.",
            "A real ARM Android device.",
            "A different emulator stack with working ARM guest support.",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"route": report["route"], "packagingAllowed": False}, indent=2))


if __name__ == "__main__":
    main()
