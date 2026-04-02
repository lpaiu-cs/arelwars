#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "runtime-reopen-options.json"


def detect_paths() -> dict[str, bool]:
    windows_apps = Path(r"C:\Program Files\WindowsApps")
    has_wsa = False
    if windows_apps.exists():
        has_wsa = any(path.name.startswith("MicrosoftCorporationII.WindowsSubsystemForAndroid") for path in windows_apps.glob("*"))
    return {
        "bluestacksProgramFiles": Path(r"C:\Program Files\BlueStacks_nxt").exists(),
        "bluestacksProgramData": Path(r"C:\ProgramData\BlueStacks_nxt").exists(),
        "wsaPackage": has_wsa,
    }


def main() -> None:
    paths = detect_paths()
    report = {
        "preferredReopenPath": "BlueStacks5-ARM32-or-ARM-instance",
        "localPresence": paths,
        "readyNow": paths["bluestacksProgramFiles"] or paths["bluestacksProgramData"] or paths["wsaPackage"],
        "note": (
            "Official Android Emulator on this host cannot run the original AW2 APK. "
            "BlueStacks 5 with an ARM or ARM 32-bit ABI instance is the strongest documented reopen option."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
