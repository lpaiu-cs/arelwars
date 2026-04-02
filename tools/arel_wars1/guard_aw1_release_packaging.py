#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GATE = REPO_ROOT / "recovery" / "arel_wars1" / "native_tmp" / "go_no_go_gate" / "phase9-gate.json"
DEFAULT_UNSIGNED_APK = Path(r"C:\Users\lpaiu\AndroidStudioProjects\arelwars1\app\build\outputs\apk\release\app-release-unsigned.apk")
DEFAULT_SIGNED_APK = Path(r"C:\Users\lpaiu\AndroidStudioProjects\arelwars1\app\build\outputs\apk\release\app-release-signed.apk")
DEFAULT_KEYSTORE = Path(r"C:\Users\lpaiu\AndroidStudioProjects\arelwars1\release\arelwars1-release.keystore")
DEFAULT_OUTPUT = REPO_ROOT / "recovery" / "arel_wars1" / "native_tmp" / "phase10-packaging-gate.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    hasher = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_apksigner() -> str | None:
    sdk_root = Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "build-tools"
    if not sdk_root.is_dir():
        return None
    candidates = sorted(sdk_root.glob("*/apksigner.bat"), reverse=True)
    if not candidates:
        return None
    return str(candidates[0])


def sign_apk(apksigner: str, unsigned_apk: Path, signed_apk: Path, keystore: Path, alias: str, storepass: str, keypass: str) -> dict:
    signed_apk.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(unsigned_apk, signed_apk)
    subprocess.run(
        [
            apksigner,
            "sign",
            "--ks",
            str(keystore),
            "--ks-key-alias",
            alias,
            "--ks-pass",
            f"pass:{storepass}",
            "--key-pass",
            f"pass:{keypass}",
            str(signed_apk),
        ],
        check=True,
    )
    verify = subprocess.run(
        [apksigner, "verify", "--print-certs", str(signed_apk)],
        check=True,
        capture_output=True,
        text=True,
    )
    return {
        "signedApk": str(signed_apk),
        "signedSha256": sha256_file(signed_apk),
        "verifyOutput": verify.stdout.strip(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guard AW1 release packaging behind the phase9 go/no-go gate.",
    )
    parser.add_argument("--gate", type=Path, default=DEFAULT_GATE)
    parser.add_argument("--unsigned-apk", type=Path, default=DEFAULT_UNSIGNED_APK)
    parser.add_argument("--signed-apk", type=Path, default=DEFAULT_SIGNED_APK)
    parser.add_argument("--keystore", type=Path, default=DEFAULT_KEYSTORE)
    parser.add_argument("--alias", default="arelwars1")
    parser.add_argument("--storepass")
    parser.add_argument("--keypass")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = load_json(args.gate)
    report = {
        "specVersion": "aw1-release-packaging-gate-v1",
        "generatedAtIso": now_iso(),
        "gatePath": str(args.gate),
        "gateVerdict": gate.get("verdict"),
        "failedChecks": gate.get("failedChecks", []),
        "recommendedPath": gate.get("recommendedPath"),
        "unsignedApk": {
            "path": str(args.unsigned_apk),
            "exists": args.unsigned_apk.is_file(),
            "sha256": sha256_file(args.unsigned_apk),
        },
        "preexistingSignedApk": {
            "path": str(args.signed_apk),
            "exists": args.signed_apk.is_file(),
            "sha256": sha256_file(args.signed_apk),
            "acceptedAsFinal": False,
            "note": "Any existing signed APK created before a `go` verdict is provisional and not accepted for equivalence.",
        },
    }

    if gate.get("verdict") != "go":
        report["status"] = "blocked"
        report["packagingAllowed"] = False
        report["reason"] = "phase9 gate is not satisfied; signed packaging is forbidden"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(args.output)
        print(json.dumps({"status": "blocked", "verdict": gate.get("verdict")}, ensure_ascii=False))
        return 0

    missing = []
    if not args.unsigned_apk.is_file():
        missing.append("unsigned-apk")
    if not args.keystore.is_file():
        missing.append("keystore")
    if not args.storepass:
        missing.append("storepass")
    if not args.keypass:
        missing.append("keypass")
    apksigner = find_apksigner()
    if apksigner is None:
        missing.append("apksigner")
    if missing:
        report["status"] = "ready-but-blocked"
        report["packagingAllowed"] = True
        report["reason"] = "gate passed, but signing prerequisites are missing"
        report["missing"] = missing
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(args.output)
        print(json.dumps({"status": "ready-but-blocked", "missing": missing}, ensure_ascii=False))
        return 0

    signed_info = sign_apk(
        apksigner=apksigner,
        unsigned_apk=args.unsigned_apk,
        signed_apk=args.signed_apk,
        keystore=args.keystore,
        alias=args.alias,
        storepass=args.storepass,
        keypass=args.keypass,
    )
    report["status"] = "signed"
    report["packagingAllowed"] = True
    report["signing"] = signed_info
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)
    print(json.dumps({"status": "signed", "signedApk": signed_info["signedApk"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
