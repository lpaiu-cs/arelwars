#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any


DEFAULT_APK = Path("arel_wars2/arel_wars_2.apk")
DEFAULT_OUTPUT = Path("recovery/arel_wars2/native_tmp/phase0-installability-gate.json")
SDK_ROOT = Path(os.environ.get("ANDROID_SDK_ROOT", Path.home() / "AppData/Local/Android/Sdk"))


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_command(cmd: list[str], *, check: bool = True, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=True,
        timeout=timeout,
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def detect_aapt() -> Path | None:
    build_tools = SDK_ROOT / "build-tools"
    if not build_tools.exists():
        return None
    candidates = sorted(build_tools.rglob("aapt.exe"), reverse=True)
    return candidates[0] if candidates else None


def parse_badging(stdout: str) -> dict[str, Any]:
    report: dict[str, Any] = {
        "packageName": None,
        "versionCode": None,
        "versionName": None,
        "sdkVersion": None,
        "targetSdkVersion": None,
        "launchableActivity": None,
        "nativeCode": [],
        "usesPermissions": [],
    }
    package_match = re.search(r"package: name='([^']+)' versionCode='([^']+)' versionName='([^']+)'", stdout)
    if package_match:
        report["packageName"] = package_match.group(1)
        report["versionCode"] = package_match.group(2)
        report["versionName"] = package_match.group(3)
    sdk_match = re.search(r"sdkVersion:'([^']+)'", stdout)
    if sdk_match:
        report["sdkVersion"] = sdk_match.group(1)
    target_match = re.search(r"targetSdkVersion:'([^']+)'", stdout)
    if target_match:
        report["targetSdkVersion"] = target_match.group(1)
    launch_match = re.search(r"launchable-activity: name='([^']+)'", stdout)
    if launch_match:
        report["launchableActivity"] = launch_match.group(1)
    native_match = re.search(r"native-code:\s+(.+)", stdout)
    if native_match:
        report["nativeCode"] = re.findall(r"'([^']+)'", native_match.group(1))
    report["usesPermissions"] = re.findall(r"uses-permission: name='([^']+)'", stdout)
    return report


def inspect_apk_libs(apk_path: Path) -> dict[str, list[str]]:
    by_abi: dict[str, list[str]] = {}
    with zipfile.ZipFile(apk_path) as zf:
        for name in zf.namelist():
            if name.startswith("lib/") and name.endswith(".so"):
                _, abi, so_name = name.split("/", 2)
                by_abi.setdefault(abi, []).append(so_name)
    return {abi: sorted(names) for abi, names in sorted(by_abi.items())}


def adb_devices() -> list[dict[str, str]]:
    adb = shutil.which("adb")
    if not adb:
        return []
    proc = run_command([adb, "devices", "-l"], check=True, timeout=10)
    devices: list[dict[str, str]] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        parts = line.split()
        devices.append(
            {
                "serial": parts[0],
                "state": parts[1] if len(parts) > 1 else "unknown",
                "raw": line,
            }
        )
    return devices


def installed_system_images() -> list[str]:
    root = SDK_ROOT / "system-images"
    if not root.exists():
        return []
    images: list[str] = []
    for path in root.rglob("source.properties"):
        images.append(str(path.parent.relative_to(SDK_ROOT)).replace("\\", "/"))
    return sorted(images)


def installed_avds() -> list[dict[str, str]]:
    avd_root = Path.home() / ".android" / "avd"
    records: list[dict[str, str]] = []
    if not avd_root.exists():
        return records
    for ini in sorted(avd_root.glob("*.ini")):
        entry = {"name": ini.stem, "path": "", "target": ""}
        for line in ini.read_text(encoding="utf-8").splitlines():
            if line.startswith("path="):
                entry["path"] = line.split("=", 1)[1]
            elif line.startswith("target="):
                entry["target"] = line.split("=", 1)[1]
        records.append(entry)
    return records


def classify_status(apk_exists: bool, native_code: list[str], devices: list[dict[str, str]]) -> dict[str, str]:
    if not apk_exists:
        return {"verdict": "blocked", "reason": "apk-missing"}
    if not devices:
        return {"verdict": "blocked", "reason": "no-adb-device"}
    if not native_code:
        return {"verdict": "blocked", "reason": "native-code-undetected"}
    return {"verdict": "ready-for-install-attempt", "reason": "apk-present-and-device-connected"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe AW2 feasibility-first packaging Phase 0 installability gate.")
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    apk_path = args.apk.resolve()
    output_path = args.output.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    apk_exists = apk_path.exists()
    aapt = detect_aapt()
    aapt_badging = None
    badging_report: dict[str, Any] = {}
    if apk_exists and aapt:
        proc = run_command([str(aapt), "dump", "badging", str(apk_path)], check=True, timeout=30)
        aapt_badging = proc.stdout
        badging_report = parse_badging(proc.stdout)

    devices = adb_devices()
    native_code = badging_report.get("nativeCode", [])
    report = {
        "generatedAt": now_iso(),
        "apk": {
            "path": str(apk_path),
            "exists": apk_exists,
            "sha256": sha256_file(apk_path) if apk_exists else None,
            "sizeBytes": apk_path.stat().st_size if apk_exists else None,
        },
        "aapt": {
            "path": str(aapt) if aapt else None,
            "available": bool(aapt),
            "parsedBadging": badging_report,
            "rawBadging": aapt_badging,
        },
        "apkLibsByAbi": inspect_apk_libs(apk_path) if apk_exists else {},
        "adbDevices": devices,
        "installedSystemImages": installed_system_images(),
        "installedAvds": installed_avds(),
        "phase0": classify_status(apk_exists, native_code, devices),
    }

    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report["phase0"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
