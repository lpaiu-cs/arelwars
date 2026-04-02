#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "runtime-reopen-options.json"
PROBE_DIR = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "oracle_vbox_probe"
PORTABLE_PROBE = ROOT / "recovery" / "arel_wars2" / "native_tmp" / "bluestacks_portable_probe" / "portable-launch-probe.json"


def detect_paths() -> dict[str, bool]:
    windows_apps = Path(r"C:\Program Files\WindowsApps")
    has_wsa = False
    if windows_apps.exists():
        has_wsa = any(path.name.startswith("MicrosoftCorporationII.WindowsSubsystemForAndroid") for path in windows_apps.glob("*"))
    portable_root = ROOT / "$root" / "PD" / "Engine" / "Nougat32"
    return {
        "oracleVirtualBox": Path(r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe").exists(),
        "bluestacksProgramFiles": Path(r"C:\Program Files\BlueStacks_nxt").exists(),
        "bluestacksProgramData": Path(r"C:\ProgramData\BlueStacks_nxt").exists(),
        "portableBlueStacksRoot": portable_root.exists(),
        "portableBlueStacksVmConfig": (portable_root / "Android.bstk").exists(),
        "portableBlueStacksDataVdi": (portable_root / "Data.vdi").exists(),
        "wsaPackage": has_wsa,
    }


def detect_oracle_candidate() -> dict[str, object]:
    probe = PROBE_DIR / "oracle-ide-primaryslave-piix3-vga.json"
    if not probe.exists():
        return {
            "exists": False,
            "stableNoReset": False,
            "adbOnline": False,
        }
    data = json.loads(probe.read_text(encoding="utf-8"))
    log_tail = data.get("vboxLogTail", "")
    adb_text = data.get("adbDevices", "")
    showvminfo = data.get("showvminfo", "")
    return {
        "exists": True,
        "stableNoReset": "ACPI: Reset initiated by ACPI" not in log_tail and "AHCI#0:" not in log_tail,
        "adbOnline": "\tdevice" in adb_text or " device " in adb_text,
        "adbTcp5555Open": data.get("adbTcp5555Open"),
        "showvminfoHasPiix3": "Chipset:                     piix3" in showvminfo,
        "guestPropertyOnlyHostInfo": "/VirtualBox/HostInfo/" in data.get("guestPropertyStdout", "")
        and "/VirtualBox/VMInfo/" in data.get("guestPropertyStdout", "")
        and "/VirtualBox/GuestInfo/" not in data.get("guestPropertyStdout", ""),
        "osDetectWorked": data.get("osdetectRc") == 0,
        "serialLogBytes": data.get("serialLog", {}).get("bytes"),
        "storageStatsPresent": "/Public/Storage/" in data.get("debugStatisticsStdout", ""),
        "probeFile": str(probe),
    }


def detect_portable_client_candidate() -> dict[str, object]:
    if not PORTABLE_PROBE.exists():
        return {
            "exists": False,
        }
    data = json.loads(PORTABLE_PROBE.read_text(encoding="utf-8"))
    vmmgr = data.get("vmmgrListVms", {})
    hd_player = data.get("hdPlayerProbe", {})
    late_processes = hd_player.get("lateProcesses", [])
    if isinstance(late_processes, dict):
        late_processes = [late_processes]
    return {
        "exists": True,
        "vmmgrComReady": vmmgr.get("returncode") == 0,
        "vmmgrClassNotRegistered": "REGDB_E_CLASSNOTREG" in ((vmmgr.get("stdout") or "") + (vmmgr.get("stderr") or "")),
        "hdPlayerSpawnedVBox": bool(hd_player.get("spawnedVBoxProcess")),
        "hdPlayerTcp5555Open": hd_player.get("tcp5555Open"),
        "hdPlayerAdbOnline": "\tdevice" in ((hd_player.get("sdkAdb") or {}).get("stdout", "")),
        "lateProcessCount": len(late_processes),
        "probeFile": str(PORTABLE_PROBE),
    }


def main() -> None:
    paths = detect_paths()
    oracle_candidate = detect_oracle_candidate()
    portable_candidate = detect_portable_client_candidate()
    has_portable_candidate = (
        paths["oracleVirtualBox"]
        and paths["portableBlueStacksVmConfig"]
        and paths["portableBlueStacksDataVdi"]
    )
    if has_portable_candidate:
        preferred = "OracleVBox-BlueStacks-N32-portable-candidate"
        note = (
            "The strongest reopen path is now the locally unpacked BlueStacks Nougat32 guest "
            "registered under Oracle VirtualBox. The Oracle VBox candidate reaches a stable no-reset boot "
            "shape under the oracle-ide-primaryslave-piix3-vga profile, but it still stalls before guest "
            "userspace or adb-online observability. The portable BlueStacks client path is also blocked: "
            "BstkVMMgr still reports REGDB_E_CLASSNOTREG and HD-Player does not bring up a live guest."
        )
    else:
        preferred = "BlueStacks5-ARM32-or-ARM-instance"
        note = (
            "Official Android Emulator on this host cannot run the original AW2 APK. "
            "BlueStacks 5 with an ARM or ARM 32-bit ABI instance is the strongest documented reopen option."
        )
    report = {
        "preferredReopenPath": preferred,
        "localPresence": paths,
        "oracleVBoxPortableCandidate": oracle_candidate,
        "portableBlueStacksClientCandidate": portable_candidate,
        "readyNow": bool(oracle_candidate.get("adbOnline"))
        or bool(portable_candidate.get("hdPlayerAdbOnline"))
        or paths["bluestacksProgramFiles"]
        or paths["bluestacksProgramData"]
        or paths["wsaPackage"],
        "note": note,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
