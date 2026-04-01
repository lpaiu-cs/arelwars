#!/usr/bin/env python3
from __future__ import annotations

import argparse
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
import sys


DEFAULT_APK = Path("arel_wars1/arel_wars_1.apk")
DEFAULT_WORKSPACE = Path(".")
DEFAULT_OUTPUT = Path("recovery/arel_wars1/native_tmp/apk_runtime_audit.json")
ANDROID_PROJECT_FILENAMES = {
    "androidmanifest.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradle.properties",
    "cmakelists.txt",
    "android.mk",
    "application.mk",
}
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".java", ".kt"}
SKIP_TOP_LEVEL = {".git", ".idea", ".venv", "__pycache__", "recovery"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the current Arel Wars 1 APK for x86_64 packaging readiness and JNI/native blockers.",
    )
    parser.add_argument("--apk", type=Path, default=DEFAULT_APK)
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def normalize_class_name(class_name: str) -> str:
    if class_name.startswith("L") and class_name.endswith(";"):
        return class_name[1:-1]
    return class_name


def format_method_ref(class_name: str, name: str, descriptor: str) -> str:
    return f"{class_name}->{name}{descriptor}"


def unwrap_method(method):
    return method.get_method() if hasattr(method, "get_method") else method


def jni_escape(text: str) -> str:
    escaped: list[str] = []
    for ch in text:
        if ch.isalnum():
            escaped.append(ch)
        elif ch == "_":
            escaped.append("_1")
        elif ch == "/":
            escaped.append("_")
        elif ch == ";":
            escaped.append("_2")
        elif ch == "[":
            escaped.append("_3")
        else:
            escaped.append(f"_0{ord(ch):04x}")
    return "".join(escaped)


def jni_symbol_for_method(class_name: str, method_name: str, descriptor: str, overloaded: bool) -> str:
    owner = normalize_class_name(class_name)
    base = f"Java_{jni_escape(owner)}_{jni_escape(method_name)}"
    if not overloaded:
        return base
    args_descriptor = descriptor[descriptor.find("(") + 1 : descriptor.find(")")]
    return f"{base}__{jni_escape(args_descriptor)}"


def iter_workspace_files(root: Path):
    for path in root.iterdir():
        if path.name in SKIP_TOP_LEVEL:
            continue
        if path.is_dir():
            yield from _iter_workspace_files(path)
        else:
            yield path


def _iter_workspace_files(root: Path):
    for path in root.iterdir():
        if path.name in {"__pycache__"}:
            continue
        if path.is_dir():
            yield from _iter_workspace_files(path)
        else:
            yield path


def discover_workspace_context(workspace_root: Path) -> dict:
    build_files: list[str] = []
    source_files: list[str] = []
    for path in iter_workspace_files(workspace_root):
        rel = path.relative_to(workspace_root).as_posix()
        if path.name.lower() in ANDROID_PROJECT_FILENAMES:
            build_files.append(rel)
        if path.suffix.lower() in SOURCE_SUFFIXES:
            source_files.append(rel)
    return {
        "androidProjectFiles": sorted(build_files),
        "sourceFilesPreview": sorted(source_files)[:32],
        "sourceFileCount": len(source_files),
    }


def analyze_apk_zip(apk_path: Path) -> dict:
    libs_by_abi: dict[str, list[str]] = defaultdict(list)
    file_count_by_top_level: Counter[str] = Counter()
    with zipfile.ZipFile(apk_path) as zf:
        for name in zf.namelist():
            top = name.split("/", 1)[0]
            file_count_by_top_level[top] += 1
            if name.startswith("lib/") and name.endswith(".so"):
                parts = name.split("/")
                if len(parts) >= 3:
                    libs_by_abi[parts[1]].append(parts[-1])
    return {
        "fileCountByTopLevel": dict(sorted(file_count_by_top_level.items())),
        "nativeLibsByAbi": {abi: sorted(names) for abi, names in sorted(libs_by_abi.items())},
    }


def load_androguard():
    try:
        from loguru import logger

        logger.remove()
    except ModuleNotFoundError:
        pass
    try:
        from androguard.misc import AnalyzeAPK
    except ModuleNotFoundError as exc:
        raise SystemExit("missing dependency: install androguard with `python -m pip install androguard`") from exc
    return AnalyzeAPK


def disassemble_method(method) -> list[tuple[str, str]]:
    method = unwrap_method(method)
    code = method.get_code()
    if code is None:
        return []
    return [(ins.get_name(), ins.get_output()) for ins in code.get_bc().get_instructions()]


def summarize_loadlibrary_call(method, callee_name: str) -> dict:
    method = unwrap_method(method)
    instructions = disassemble_method(method)
    last_string: str | None = None
    libraries: list[str] = []
    for name, output in instructions:
        if name == "const-string":
            parts = output.split(", ", 1)
            if len(parts) == 2:
                last_string = parts[1].strip('"')
        elif name == "invoke-static" and f"Ljava/lang/System;->{callee_name}" in output:
            libraries.append(last_string or "<unknown>")
    return {
        "caller": format_method_ref(method.class_name, method.name, method.descriptor),
        "loader": callee_name,
        "libraries": libraries or ["<unknown>"],
    }


def analyze_dex(apk_path: Path) -> dict:
    AnalyzeAPK = load_androguard()
    apk, dexes, dx = AnalyzeAPK(str(apk_path))
    dex = dexes[0]

    native_methods: list[dict] = []
    native_name_counts: Counter[str] = Counter()
    for cls in dex.get_classes():
        for method in cls.get_methods():
            access = method.get_access_flags_string()
            if "native" not in access:
                continue
            native_name_counts[f"{method.get_class_name()}::{method.get_name()}"] += 1
            native_methods.append(
                {
                    "className": method.get_class_name(),
                    "methodName": method.get_name(),
                    "descriptor": method.get_descriptor(),
                    "access": access,
                }
            )

    native_methods.sort(key=lambda item: (item["className"], item["methodName"], item["descriptor"]))
    expected_jni_symbols: list[str] = []
    for item in native_methods:
        overloaded = native_name_counts[f"{item['className']}::{item['methodName']}"] > 1
        expected_jni_symbols.append(
            jni_symbol_for_method(item["className"], item["methodName"], item["descriptor"], overloaded)
        )

    loadlibrary_calls: list[dict] = []
    for target_name in ("loadLibrary", "load"):
        seen: set[str] = set()
        for method_analysis in dx.find_methods(classname="Ljava/lang/System;", methodname=target_name):
            for _, caller, _ in method_analysis.get_xref_from():
                caller_method = unwrap_method(caller)
                key = format_method_ref(caller_method.class_name, caller_method.name, caller_method.descriptor)
                if key in seen:
                    continue
                seen.add(key)
                loadlibrary_calls.append(summarize_loadlibrary_call(caller_method, target_name))
    loadlibrary_calls.sort(key=lambda item: (item["caller"], item["loader"]))

    native_callers: dict[str, list[str]] = {}
    for target in (
        "InitializeJNIGlobalRef",
        "NativeInitWithBufferSize",
        "NativeRender",
        "NativeResize",
        "NativePauseClet",
        "NativeResumeClet",
        "NativeDestroyClet",
    ):
        callers: set[str] = set()
        for method_analysis in dx.find_methods(
            classname="Lcom/gamevil/nexus2/Natives;",
            methodname=target,
        ):
            for _, caller, _ in method_analysis.get_xref_from():
                caller_method = unwrap_method(caller)
                callers.add(format_method_ref(caller_method.class_name, caller_method.name, caller_method.descriptor))
        native_callers[target] = sorted(callers)

    return {
        "packageName": apk.get_package(),
        "appName": apk.get_app_name(),
        "versionName": apk.get_androidversion_name(),
        "versionCode": apk.get_androidversion_code(),
        "minSdkVersion": apk.get_min_sdk_version(),
        "targetSdkVersion": apk.get_target_sdk_version(),
        "mainActivities": sorted(apk.get_main_activities()),
        "activities": apk.get_activities(),
        "nativeMethods": native_methods,
        "expectedJniSymbols": sorted(expected_jni_symbols),
        "systemLoadCalls": loadlibrary_calls,
        "criticalNativeCallers": native_callers,
    }


def load_pyelftools():
    try:
        from elftools.elf.elffile import ELFFile
    except ModuleNotFoundError as exc:
        raise SystemExit("missing dependency: install pyelftools with `python -m pip install pyelftools`") from exc
    return ELFFile


def analyze_native_libs(apk_path: Path) -> dict:
    ELFFile = load_pyelftools()
    libs: list[dict] = []
    exports_by_abi: dict[str, set[str]] = defaultdict(set)
    with zipfile.ZipFile(apk_path) as zf:
        for name in sorted(n for n in zf.namelist() if n.startswith("lib/") and n.endswith(".so")):
            blob = zf.read(name)
            elf = ELFFile(io.BytesIO(blob))
            dynamic = elf.get_section_by_name(".dynamic")
            dynsym = elf.get_section_by_name(".dynsym")
            exports: list[str] = []
            if dynsym is not None:
                for sym in dynsym.iter_symbols():
                    if sym.name.startswith("Java_") or sym.name == "JNI_OnLoad":
                        exports.append(sym.name)
            parts = name.split("/")
            abi = parts[1]
            exports_by_abi[abi].update(exports)
            needed = []
            if dynamic is not None:
                needed = [tag.needed for tag in dynamic.iter_tags() if tag.entry.d_tag == "DT_NEEDED"]
            libs.append(
                {
                    "path": name,
                    "abi": abi,
                    "name": parts[-1],
                    "elfClass": elf.elfclass,
                    "machine": elf["e_machine"],
                    "needed": needed,
                    "jniExports": sorted(exports),
                }
            )
    return {
        "libs": libs,
        "jniExportsByAbi": {abi: sorted(symbols) for abi, symbols in sorted(exports_by_abi.items())},
    }


def build_readiness_summary(workspace: dict, apk_zip: dict, dex: dict, native_libs: dict) -> dict:
    blockers: list[str] = []
    libs_by_abi = apk_zip["nativeLibsByAbi"]
    if "x86_64" not in libs_by_abi:
        blockers.append("APK contains no `lib/x86_64/*.so`; there is no x86_64-native payload to load.")
    if list(libs_by_abi.keys()) == ["armeabi"]:
        blockers.append("APK ships only `lib/armeabi/libgameDSO.so`, so the current build is ARM32-only.")
    if not workspace["androidProjectFiles"]:
        blockers.append("Workspace contains no Android project files outside recovery outputs, so there is no local build tree to rebuild the APK from source.")
    if not workspace["sourceFilesPreview"]:
        blockers.append("Workspace contains no Java/Kotlin/C/C++ source tree outside recovery outputs, so `libgameDSO.so` cannot be recompiled locally.")

    libraries_loaded = sorted(
        {lib for call in dex["systemLoadCalls"] for lib in call["libraries"] if lib != "<unknown>"}
    )
    if "gameDSO" in libraries_loaded:
        blockers.append("Java launcher hardcodes `System.loadLibrary(\"gameDSO\")`; any working x86_64 port still needs a replacement `libgameDSO.so`.")

    critical_callers = dex["criticalNativeCallers"]
    if critical_callers.get("NativeInitWithBufferSize") and critical_callers.get("NativeRender"):
        blockers.append("Renderer startup and frame loop (`NativeInitWithBufferSize`, `NativeRender`, `NativeResize`) are native; asset repackaging alone cannot produce a runnable x86_64 build.")

    expected = set(dex["expectedJniSymbols"])
    exports_by_abi = {abi: set(symbols) for abi, symbols in native_libs["jniExportsByAbi"].items()}
    jni_resolution: dict[str, dict] = {}
    for abi, exported in sorted(exports_by_abi.items()):
        missing = sorted(expected - exported)
        jni_resolution[abi] = {
            "matchedDirectJniExportCount": len(expected) - len(missing),
            "missingDirectJniExports": missing,
        }
    x86_64_ready = "x86_64" in libs_by_abi and not jni_resolution.get("x86_64", {}).get("missingDirectJniExports")

    return {
        "loadedLibraries": libraries_loaded,
        "jniResolutionByAbi": jni_resolution,
        "x86_64Ready": x86_64_ready,
        "blockers": blockers,
    }


def main() -> int:
    args = parse_args()
    workspace_root = args.workspace_root.resolve()
    apk_path = args.apk.resolve()

    workspace = discover_workspace_context(workspace_root)
    apk_zip = analyze_apk_zip(apk_path)
    dex = analyze_dex(apk_path)
    native_libs = analyze_native_libs(apk_path)
    readiness = build_readiness_summary(workspace, apk_zip, dex, native_libs)

    result = {
        "workspace": workspace,
        "apkZip": apk_zip,
        "dex": dex,
        "nativeLibs": native_libs,
        "readiness": readiness,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"APK audit: {dex['packageName']} {dex['versionName']} ({dex['versionCode']}) | "
        f"ABIs={','.join(sorted(apk_zip['nativeLibsByAbi'])) or '<none>'} | "
        f"x86_64Ready={readiness['x86_64Ready']}"
    )
    for blocker in readiness["blockers"]:
        print(f"- {blocker}")
    print(f"Audit report written to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
