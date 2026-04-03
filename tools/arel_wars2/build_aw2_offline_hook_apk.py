#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APK_PATH = ROOT / "arel_wars2" / "arel_wars_2.apk"
DEXDUMP_DIR = ROOT / "recovery" / "arel_wars2" / "dexdump"
NATIVE_TMP = ROOT / "recovery" / "arel_wars2" / "native_tmp"
BUILD_DIR = NATIVE_TMP / "offline_hook_build"
REPORT_PATH = NATIVE_TMP / "aw2_offline_hook_report.json"
TOOLING_DIR = NATIVE_TMP / "tooling"

ANDROID_SDK = Path(os.environ.get("ANDROID_SDK_ROOT", Path.home() / "AppData" / "Local" / "Android" / "Sdk"))
BUILD_TOOLS = ANDROID_SDK / "build-tools" / "36.1.0"
ZIPALIGN = BUILD_TOOLS / "zipalign.exe"
APKSIGNER = BUILD_TOOLS / "apksigner.bat"
DEBUG_KEYSTORE = Path.home() / ".android" / "debug.keystore"
JAVA = shutil.which("java") or "java"
TOOLING_DOWNLOADS = {
    "smali-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/smali/2.5.2/smali-2.5.2.jar",
    "baksmali-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/baksmali/2.5.2/baksmali-2.5.2.jar",
    "util-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/util/2.5.2/util-2.5.2.jar",
    "dexlib2-2.5.2.jar": "https://repo1.maven.org/maven2/org/smali/dexlib2/2.5.2/dexlib2-2.5.2.jar",
    "jcommander-1.64.jar": "https://repo1.maven.org/maven2/com/beust/jcommander/1.64/jcommander-1.64.jar",
    "guava-27.1-android.jar": "https://repo1.maven.org/maven2/com/google/guava/guava/27.1-android/guava-27.1-android.jar",
    "antlr-3.5.2.jar": "https://repo1.maven.org/maven2/org/antlr/antlr/3.5.2/antlr-3.5.2.jar",
    "antlr-runtime-3.5.2.jar": "https://repo1.maven.org/maven2/org/antlr/antlr-runtime/3.5.2/antlr-runtime-3.5.2.jar",
    "stringtemplate-3.2.1.jar": "https://repo1.maven.org/maven2/org/antlr/stringtemplate/3.2.1/stringtemplate-3.2.1.jar",
    "jsr305-3.0.2.jar": "https://repo1.maven.org/maven2/com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar",
}


def ensure_tooling() -> None:
    TOOLING_DIR.mkdir(parents=True, exist_ok=True)
    for filename, url in TOOLING_DOWNLOADS.items():
        target = TOOLING_DIR / filename
        if target.exists():
            continue
        urllib.request.urlretrieve(url, target)


def tooling_classpath() -> str:
    return str(TOOLING_DIR / "*")


PATCHES = [
    {
        "label": "billing-supported-always-true",
        "file": "com/gamevil/ArelWars2/global/BillingService.smali",
        "signature": ".method public checkBillingSupported()Z",
        "body": """
.method public checkBillingSupported()Z
    .registers 2

    const/4 v0, 0x1

    return v0
.end method
""".strip(),
    },
    {
        "label": "gamevil-live-check-login-noop",
        "file": "com/gamevil/nexus2/live/GamevilLive.smali",
        "signature": ".method public checkLogin()V",
        "body": """
.method public checkLogin()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gamevil-gift-connect-noop",
        "file": "com/gamevil/nexus2/cpi/GamevilGift.smali",
        "signature": ".method public static connect(Landroid/content/Context;Ljava/lang/String;III)V",
        "body": """
.method public static connect(Landroid/content/Context;Ljava/lang/String;III)V
    .registers 5

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-connect-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static connect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V",
        "body": """
.method public static connect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)V
    .registers 5

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-banner-address-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static addNewsBannerAddressId(Landroid/app/Activity;III)V",
        "body": """
.method public static addNewsBannerAddressId(Landroid/app/Activity;III)V
    .registers 4

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-end-session-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static endSession()V",
        "body": """
.method public static endSession()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "tapjoy-connect-noop",
        "file": "com/tapjoy/TapjoyConnect.smali",
        "signature": ".method public static requestTapjoyConnect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)V",
        "body": """
.method public static requestTapjoyConnect(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)V
    .registers 3

    return-void
.end method
""".strip(),
    },
    {
        "label": "gamevil-gift-end-session-noop",
        "file": "com/gamevil/nexus2/cpi/GamevilGift.smali",
        "signature": ".method public static endSession()V",
        "body": """
.method public static endSession()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-set-news-data-noop",
        "file": "com/gamevil/lib/news/GvNewsDataManager.smali",
        "signature": ".method public setNewsData(Ljava/lang/String;)V",
        "body": """
.method public setNewsData(Ljava/lang/String;)V
    .registers 2

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvutils-is-dl-runtime-false",
        "file": "com/gamevil/lib/utils/GvUtils.smali",
        "signature": ".method public static isDLRuntime()Z",
        "body": """
.method public static isDLRuntime()Z
    .registers 2

    const/4 v0, 0x0

    return v0
.end method
""".strip(),
    },
    {
        "label": "gvprofile-is-terms-accepted-true",
        "file": "com/gamevil/lib/profile/GvProfileData.smali",
        "signature": ".method public static isTermsAccepted(Landroid/content/Context;)I",
        "body": """
.method public static isTermsAccepted(Landroid/content/Context;)I
    .registers 2
    .param p0, "_context"    # Landroid/content/Context;

    .prologue
    const/4 v0, 0x1

    return v0
.end method
""".strip(),
    },
    {
        "label": "natives-update-dialogue-noop",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method public static updateDialogue()V",
        "body": """
.method public static updateDialogue()V
    .registers 1

    return-void
.end method
""".strip(),
    },
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=True,
    )


def ensure_disassembly(classes_dex: Path, smali_root: Path, force: bool) -> None:
    if smali_root.exists() and not force:
        return
    if smali_root.exists():
        shutil.rmtree(smali_root)
    smali_root.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            JAVA,
            "-cp",
            tooling_classpath(),
            "org.jf.baksmali.Main",
            "disassemble",
            str(classes_dex),
            "-o",
            str(smali_root),
        ]
    )


def replace_method(text: str, signature: str, body: str) -> tuple[str, bool]:
    pattern = re.compile(rf"^{re.escape(signature)}\n.*?^\.end method$", re.MULTILINE | re.DOTALL)
    replacement = body.replace("\n", "\n")
    new_text, count = pattern.subn(replacement, text, count=1)
    return new_text, count == 1


def patch_smali_tree(smali_root: Path) -> list[dict[str, str]]:
    applied: list[dict[str, str]] = []
    for patch in PATCHES:
        target = smali_root / patch["file"]
        text = target.read_text(encoding="utf-8")
        new_text, ok = replace_method(text, patch["signature"], patch["body"])
        if not ok:
            raise RuntimeError(f"Failed to patch {patch['label']} in {target}")
        target.write_text(new_text, encoding="utf-8", newline="\n")
        applied.append({"label": patch["label"], "file": str(target)})
    return applied


def assemble_smali(smali_root: Path, output_dex: Path) -> None:
    output_dex.parent.mkdir(parents=True, exist_ok=True)
    if output_dex.exists():
        output_dex.unlink()
    run([JAVA, "-cp", tooling_classpath(), "org.jf.smali.Main", "assemble", "-o", str(output_dex), str(smali_root)])


def unpack_apk(apk: Path, unpacked_dir: Path) -> None:
    if unpacked_dir.exists():
        shutil.rmtree(unpacked_dir)
    unpacked_dir.mkdir(parents=True)
    with zipfile.ZipFile(apk) as zf:
        zf.extractall(unpacked_dir)


def read_compression_map(apk: Path) -> dict[str, int]:
    with zipfile.ZipFile(apk) as zf:
        return {info.filename: info.compress_type for info in zf.infolist()}


def repack_apk(unpacked_dir: Path, unsigned_apk: Path, compression_map: dict[str, int]) -> None:
    if unsigned_apk.exists():
        unsigned_apk.unlink()
    unsigned_apk.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(unsigned_apk, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(unpacked_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(unpacked_dir).as_posix()
            if rel.startswith("META-INF/"):
                continue
            zf.write(path, rel, compress_type=compression_map.get(rel, zipfile.ZIP_DEFLATED))


def align_and_sign(unsigned_apk: Path, aligned_apk: Path, signed_apk: Path) -> None:
    if aligned_apk.exists():
        aligned_apk.unlink()
    if signed_apk.exists():
        signed_apk.unlink()
    run([str(ZIPALIGN), "-f", "4", str(unsigned_apk), str(aligned_apk)])
    shutil.copy2(aligned_apk, signed_apk)
    run(
        [
            str(APKSIGNER),
            "sign",
            "--ks",
            str(DEBUG_KEYSTORE),
            "--ks-key-alias",
            "androiddebugkey",
            "--ks-pass",
            "pass:android",
            "--key-pass",
            "pass:android",
            str(signed_apk),
        ]
    )


def install_apk(device: str, apk: Path) -> subprocess.CompletedProcess[str]:
    try:
        return run(["adb", "-s", device, "install", "-r", str(apk)])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "") + (exc.stdout or "")
        if "INSTALL_FAILED_UPDATE_INCOMPATIBLE" in stderr or "INSTALL_FAILED_VERSION_DOWNGRADE" in stderr:
            run(["adb", "-s", device, "uninstall", "com.gamevil.ArelWars2.global"])
            return run(["adb", "-s", device, "install", "-r", str(apk)])
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a test-only offline-hook APK for Arel Wars 2.")
    parser.add_argument("--apk", type=Path, default=APK_PATH)
    parser.add_argument("--device", default="emulator-5554")
    parser.add_argument("--force-disassembly", action="store_true")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    if not args.apk.exists():
        raise SystemExit(f"APK not found: {args.apk}")
    ensure_tooling()
    for path in [ZIPALIGN, APKSIGNER, DEBUG_KEYSTORE, *[TOOLING_DIR / name for name in TOOLING_DOWNLOADS]]:
        if not Path(path).exists():
            raise SystemExit(f"Required tool missing: {path}")

    unpacked = BUILD_DIR / "unpacked"
    classes_dex = BUILD_DIR / "classes.dex"
    smali_cache = DEXDUMP_DIR / "smali"
    patched_smali = BUILD_DIR / "smali_patched"
    unsigned_apk = NATIVE_TMP / "arel_wars_2-offline-hook-unsigned.apk"
    aligned_apk = NATIVE_TMP / "arel_wars_2-offline-hook-aligned.apk"
    signed_apk = NATIVE_TMP / "arel_wars_2-offline-hook-signed.apk"

    unpack_apk(args.apk, unpacked)
    shutil.copy2(unpacked / "classes.dex", classes_dex)
    ensure_disassembly(classes_dex, smali_cache, args.force_disassembly)

    if patched_smali.exists():
        shutil.rmtree(patched_smali)
    shutil.copytree(smali_cache, patched_smali)
    applied = patch_smali_tree(patched_smali)

    rebuilt_dex = BUILD_DIR / "classes.patched.dex"
    assemble_smali(patched_smali, rebuilt_dex)
    shutil.copy2(rebuilt_dex, unpacked / "classes.dex")

    repack_apk(unpacked, unsigned_apk, read_compression_map(args.apk))
    align_and_sign(unsigned_apk, aligned_apk, signed_apk)

    install_result = None
    if args.install:
        install_result = install_apk(args.device, signed_apk)

    report = {
        "sourceApk": str(args.apk),
        "sourceApkSha256": sha256(args.apk),
        "signedApk": str(signed_apk),
        "signedApkSha256": sha256(signed_apk),
        "patches": applied,
        "install": {
            "requested": args.install,
            "device": args.device,
            "stdout": install_result.stdout if install_result else "",
            "stderr": install_result.stderr if install_result else "",
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
