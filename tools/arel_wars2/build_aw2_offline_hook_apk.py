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
LLVM_READELF = ANDROID_SDK / "ndk" / "30.0.14904198" / "toolchains" / "llvm" / "prebuilt" / "windows-x86_64" / "bin" / "llvm-readelf.exe"
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
        "label": "aw2-drm-oncreate-explicit-launcher",
        "file": "com/gamevil/ArelWars2/global/DRMLicensing.smali",
        "signature": ".method public onCreate(Landroid/os/Bundle;)V",
        "body": """
.method public onCreate(Landroid/os/Bundle;)V
    .registers 5
    .param p1, "icicle"    # Landroid/os/Bundle;

    const/4 v2, 0x1
    const/4 v1, 0x0

    invoke-super {p0, p1}, Lcom/gamevil/lib/GvDrmActivity;->onCreate(Landroid/os/Bundle;)V

    invoke-static {v2}, Lcom/gamevil/lib/utils/GvUtils;->setDebugLogEnable(Z)V

    const-string v0, "com.gamevil.ArelWars2.global.ArelWars2Launcher"
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setComponentName(Ljava/lang/String;)V

    const/16 v0, 0x73ae
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setGid(I)V

    const/4 v0, 0x5
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setCompany(B)V

    const/16 v0, 0xe
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setSale_cd(B)V

    const-string v0, "TJN9VGMBJ7PX6K4DXTT2"
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setFlurryApiKey(Ljava/lang/String;)V

    const-string v0, "1190b8e5574bb4c67a033fd4a6b53e90"
    invoke-static {v0}, Lcom/gamevil/lib/profile/GvProfileData;->setCihEmbers(Ljava/lang/String;)V

    invoke-static {v1}, Lcom/gamevil/lib/profile/GvProfileData;->setUsingNetworkEncryption(Z)V
    invoke-static {v1}, Lcom/gamevil/lib/profile/GvProfileData;->setNeedToCheckSIM(Z)V
    invoke-static {v1}, Lcom/gamevil/lib/profile/GvProfileData;->setUseTestServer(Z)V

    invoke-static {v2}, Lcom/gamevil/lib/profile/GvProfileData;->setServerType(B)V
    invoke-static {}, Lcom/gamevil/lib/profile/GvProfileData;->makeProfileBundleData()V

    new-instance v0, Landroid/content/Intent;
    invoke-direct {v0}, Landroid/content/Intent;-><init>()V

    const-string v1, "com.gamevil.ArelWars2.global"
    const-string v2, "com.gamevil.ArelWars2.global.ArelWars2Launcher"
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;

    const-string v1, "profileBundle"
    invoke-static {}, Lcom/gamevil/lib/profile/GvProfileData;->getProfileBundle()Landroid/os/Bundle;
    move-result-object v2
    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Bundle;)Landroid/content/Intent;

    invoke-virtual {p0, v0}, Lcom/gamevil/ArelWars2/global/DRMLicensing;->startActivity(Landroid/content/Intent;)V
    invoke-virtual {p0}, Lcom/gamevil/ArelWars2/global/DRMLicensing;->finish()V
    return-void
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
    {
        "label": "natives-change-ui-status-skip-news",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method private static changeUIStatus(I)V",
        "body": """
.method private static changeUIStatus(I)V
    .registers 2
    .param p0, "_status"    # I

    .prologue
    const/16 v0, 0x13

    if-eq p0, v0, :goto_title

    const/16 v0, 0x14

    if-eq p0, v0, :goto_title

    const/16 v0, 0x15

    if-eq p0, v0, :goto_title

    goto :goto_dispatch

    :goto_title
    const/4 p0, 0x1

    :goto_dispatch
    sget-object v0, Lcom/gamevil/nexus2/NexusGLActivity;->uiViewControll:Lcom/gamevil/nexus2/ui/NeoUIControllerView;

    invoke-virtual {v0, p0}, Lcom/gamevil/nexus2/ui/NeoUIControllerView;->changeUIStatus(I)V

    return-void
.end method
""".strip(),
    },
    {
        "label": "natives-net-connect-always-true",
        "file": "com/gamevil/nexus2/Natives.smali",
        "signature": ".method private static netConnect()I",
        "body": """
.method private static netConnect()I
    .registers 1

    .prologue
    const/4 v0, 0x1

    return v0
.end method
""".strip(),
    },
    {
        "label": "gvactivity-do-jellybeen-noop",
        "file": "com/gamevil/lib/GvActivity.smali",
        "signature": ".method public doJellyBeen()V",
        "body": """
.method public doJellyBeen()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvactivity-do-torchwood-noop",
        "file": "com/gamevil/lib/GvActivity.smali",
        "signature": ".method public doTorchwood()V",
        "body": """
.method public doTorchwood()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvdrm-start-launcher-explicit",
        "file": "com/gamevil/lib/GvDrmActivity.smali",
        "signature": ".method private startLauncherActivity()V",
        "body": """
.method private startLauncherActivity()V
    .registers 4

    new-instance v0, Landroid/content/Intent;

    invoke-direct {v0}, Landroid/content/Intent;-><init>()V

    const-string v1, "com.gamevil.ArelWars2.global"

    const-string v2, "com.gamevil.ArelWars2.global.ArelWars2Launcher"

    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->setClassName(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;

    const-string v1, "profileBundle"

    invoke-static {}, Lcom/gamevil/lib/profile/GvProfileData;->getProfileBundle()Landroid/os/Bundle;

    move-result-object v2

    invoke-virtual {v0, v1, v2}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Landroid/os/Bundle;)Landroid/content/Intent;

    invoke-virtual {p0, v0}, Lcom/gamevil/lib/GvDrmActivity;->startActivity(Landroid/content/Intent;)V

    invoke-virtual {p0}, Lcom/gamevil/lib/GvDrmActivity;->finish()V

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvprofile-show-net-error-noop",
        "file": "com/gamevil/lib/profile/GvProfileSender.smali",
        "signature": ".method public showNetError1()V",
        "body": """
.method public showNetError1()V
    .registers 1

    return-void
.end method
""".strip(),
    },
    {
        "label": "gvnews-show-banner-noop",
        "file": "com/gamevil/lib/news/GvNews.smali",
        "signature": ".method public static showNewsBanner(I)V",
        "body": """
.method public static showNewsBanner(I)V
    .registers 1
    .param p0, "_addressId"    # I

    .prologue
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


def find_symbol_value(binary: Path, symbol: str) -> int:
    result = run([str(LLVM_READELF), "-Ws", str(binary)])
    pattern = re.compile(rf"^\s*\d+:\s*([0-9a-fA-F]+)\s+\d+\s+FUNC\s+GLOBAL\s+DEFAULT\s+\d+\s+{re.escape(symbol)}\s*$")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match:
            return int(match.group(1), 16)
    raise RuntimeError(f"Symbol not found in {binary}: {symbol}")


def patch_native_socket_fail_open(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "MC_netSocketConnect")
    file_offset = (symbol_value & ~1) + 0x6E
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x19\xdb"
    patched = b"\x00\xbf"
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-socket-fail-open",
        "file": str(lib_path),
        "symbol": "MC_netSocketConnect",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_socket_write_stub(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "MC_netSocketWrite")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\x2d\xe9\xf0\x47"
    patched = b"\x10\x46\x70\x47"  # mov r0, r2 ; bx lr
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-socket-write-stub",
        "file": str(lib_path),
        "symbol": "MC_netSocketWrite",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_sendcb_negative_ignore(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN10CGsNetCore6SendCBEllPv")
    file_offset = (symbol_value & ~1) + 0x8
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x0a\xdb"
    patched = b"\x09\xdb"  # blt -> just return, skip Exception(-93)
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-sendcb-negative-ignore",
        "file": str(lib_path),
        "symbol": "_ZN10CGsNetCore6SendCBEllPv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_onconnectdone_skip_bootstrap_send(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet13OnConnectDoneEv")
    file_offset = (symbol_value & ~1) + 0x22
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\xc5\x21"
    patched = b"\x02\xe0"  # b -> epilogue, skip default send(0x314)
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-onconnectdone-skip-bootstrap-send",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet13OnConnectDoneEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_setdrawconnecting_always_off(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet17SetDrawConnectingEbb")
    file_offset = (symbol_value & ~1) + 0x4
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\x0d\x1c\x16\x1c\x00\x29"
    patched = b"\x00\x25\x00\x26\x00\x21"  # r5=0, r6=0, r1=0 => always hide / clear flags
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-setdrawconnecting-always-off",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet17SetDrawConnectingEbb",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_connect_disable_input_lock(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet7ConnectE15EnumNetLinkType")
    file_offset = (symbol_value & ~1) + 0x28
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x01\x21"
    patched = b"\x00\x21"  # movs r1, #0 before CPdSharing::SetInputLock
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-connect-disable-input-lock",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet7ConnectE15EnumNetLinkType",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_connect_shortcircuit_done(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet7ConnectE15EnumNetLinkType")
    file_offset = (symbol_value & ~1) + 0x72
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xcb\xf0\x13\xf9"  # bl CGsNetCore::Connect
    patched = b"\xff\xf7\x93\xff"  # bl OnConnectDone
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-connect-shortcircuit-done",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet7ConnectE15EnumNetLinkType",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_onconnecterror_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet14OnConnectErrorEi")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x47\x46"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-onconnecterror-noop",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet14OnConnectErrorEi",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_onerror_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN6CPdNet7OnErrorEii")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x47\x46"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-onerror-noop",
        "file": str(lib_path),
        "symbol": "_ZN6CPdNet7OnErrorEii",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_intro_touch_exit(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN13CPdStateIntro14OnPointerPressEP12GxPointerPos")
    file_offset = (symbol_value & ~1) + 0x30
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 6])
    expected = b"\x04\x23\x83\x64\x30\xbd"
    patched = b"\x00\xf0\x16\xf8\x30\xbd"  # bl ExitIntro ; pop {r4, r5, pc}
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 6] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-intro-touch-exit",
        "file": str(lib_path),
        "symbol": "_ZN13CPdStateIntro14OnPointerPressEP12GxPointerPos",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_touchcontinue_force_entergame(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu13TouchContinueEv")
    file_offset = (symbol_value & ~1) + 0x88
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 2])
    expected = b"\x37\xd1"  # bne -> popup-skip/entergame path only when slot exists
    patched = b"\x37\xe0"  # b -> always take entergame path
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 2] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-touchcontinue-force-entergame",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu13TouchContinueEv",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_onneterror_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu10OnNetErrorEii")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x4f\x46"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-onneterror-noop",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu10OnNetErrorEii",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_menu_onnetreceive_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "_ZN12CPdStateMenu12OnNetReceiveEi")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf0\xb5\x9b\x4c"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-menu-onnetreceive-noop",
        "file": str(lib_path),
        "symbol": "_ZN12CPdStateMenu12OnNetReceiveEi",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_openurl_noop(lib_path: Path) -> dict[str, str | int]:
    symbol_value = find_symbol_value(lib_path, "openUrl")
    file_offset = symbol_value & ~1
    data = bytearray(lib_path.read_bytes())
    original = bytes(data[file_offset : file_offset + 4])
    expected = b"\xf8\xb5\x05\x1c"
    patched = b"\x70\x47\x00\xbf"  # bx lr ; nop
    if original not in (expected, patched):
        raise RuntimeError(
            f"Unexpected bytes at {lib_path} + 0x{file_offset:x}: {original.hex()} (expected {expected.hex()} or {patched.hex()})"
        )
    data[file_offset : file_offset + 4] = patched
    lib_path.write_bytes(data)
    return {
        "label": "native-openurl-noop",
        "file": str(lib_path),
        "symbol": "openUrl",
        "symbolValue": symbol_value,
        "fileOffset": file_offset,
        "original": original.hex(),
        "patched": patched.hex(),
    }


def patch_native_libs(unpacked_dir: Path) -> list[dict[str, str | int]]:
    applied: list[dict[str, str | int]] = []
    for rel in [
        Path("lib/armeabi/libgameDSO.so"),
        Path("lib/armeabi-v7a/libgameDSO.so"),
    ]:
        lib_path = unpacked_dir / rel
        if lib_path.exists():
            applied.append(patch_native_socket_fail_open(lib_path))
            applied.append(patch_native_socket_write_stub(lib_path))
            applied.append(patch_native_sendcb_negative_ignore(lib_path))
            applied.append(patch_native_onconnectdone_skip_bootstrap_send(lib_path))
            applied.append(patch_native_setdrawconnecting_always_off(lib_path))
            applied.append(patch_native_connect_disable_input_lock(lib_path))
            applied.append(patch_native_connect_shortcircuit_done(lib_path))
            applied.append(patch_native_onconnecterror_noop(lib_path))
            applied.append(patch_native_onerror_noop(lib_path))
            applied.append(patch_native_intro_touch_exit(lib_path))
            applied.append(patch_native_touchcontinue_force_entergame(lib_path))
            applied.append(patch_native_menu_onneterror_noop(lib_path))
            applied.append(patch_native_menu_onnetreceive_noop(lib_path))
            applied.append(patch_native_openurl_noop(lib_path))
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
    for path in [ZIPALIGN, APKSIGNER, DEBUG_KEYSTORE, LLVM_READELF, *[TOOLING_DIR / name for name in TOOLING_DOWNLOADS]]:
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
    native_applied = patch_native_libs(unpacked)

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
        "patches": [*applied, *native_applied],
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
