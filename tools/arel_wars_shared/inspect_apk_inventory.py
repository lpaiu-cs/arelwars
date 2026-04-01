#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import zipfile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect high-level APK inventory for Arel Wars assets")
    parser.add_argument("--apk", type=Path, required=True, help="Path to the APK file")
    parser.add_argument("--output", type=Path, required=True, help="Path to write the JSON report")
    return parser.parse_args()


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    apk_path = args.apk.resolve()

    ext_counts: Counter[str] = Counter()
    asset_dir_counts: Counter[str] = Counter()
    asset_samples: dict[str, list[str]] = {}
    with zipfile.ZipFile(apk_path) as zf:
        members = sorted(zf.namelist())
        for member in members:
            suffix = Path(member).suffix.lower() or "<none>"
            ext_counts.update([suffix])
            if member.startswith("assets/") and "/" in member[7:]:
                asset_dir = member.split("/")[1]
                asset_dir_counts.update([asset_dir])
                asset_samples.setdefault(asset_dir, [])
                if len(asset_samples[asset_dir]) < 12:
                    asset_samples[asset_dir].append(member)

    report = {
        "apkPath": str(apk_path),
        "extensionCounts": dict(sorted(ext_counts.items())),
        "assetDirectoryCounts": dict(sorted(asset_dir_counts.items())),
        "assetSamples": dict(sorted(asset_samples.items())),
    }
    write_json(args.output.resolve(), report)


if __name__ == "__main__":
    main()
