#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import zipfile

from formats import extract_strings, read_zt1


WEB_SAFE_SUFFIXES = {".png", ".ogg", ".html"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recover and catalog assets from arel_wars_1.apk")
    parser.add_argument("--apk", type=Path, required=True, help="Path to arel_wars_1.apk")
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory where extracted and decoded recovery artifacts are written",
    )
    parser.add_argument(
        "--web-root",
        type=Path,
        help="Optional web-accessible directory to receive a small recovery catalog and web-safe assets",
    )
    return parser.parse_args()


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def copy_member(zf: zipfile.ZipFile, member: str, root: Path) -> Path:
    target = root / member
    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member) as src, target.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    return target


def preferred_encoding_for(member: str) -> str | None:
    if "script_eng/" in member or "data_eng/" in member:
        return "utf-8"
    if "script_kor/" in member or "data_kor/" in member:
        return "cp949"
    return None


def kind_for(member: str) -> str:
    if "script_" in member:
        return "script"
    if "data_" in member:
        return "data"
    if "/map/" in member:
        return "map"
    return "unknown"


def locale_for(member: str) -> str | None:
    if "_eng/" in member:
        return "en"
    if "_kor/" in member:
        return "ko"
    return None


def main() -> None:
    args = parse_args()
    apk_path = args.apk.resolve()
    output_root = args.output.resolve()
    apk_unzip_root = output_root / "apk_unzip"
    decoded_root = output_root / "decoded" / "zt1"
    web_root = args.web_root.resolve() if args.web_root else None

    ensure_clean_dir(apk_unzip_root)
    ensure_clean_dir(decoded_root)
    if web_root is not None:
        ensure_clean_dir(web_root)

    ext_counts: Counter[str] = Counter()
    asset_dir_counts: Counter[str] = Counter()
    web_safe_assets: list[str] = []
    zt1_entries: list[dict[str, object]] = []

    with zipfile.ZipFile(apk_path) as zf:
        members = sorted(zf.namelist())
        for member in members:
            suffix = Path(member).suffix.lower() or "<none>"
            ext_counts[suffix] += 1
            if member.startswith("assets/") and "/" in member[7:]:
                asset_dir_counts[member.split("/")[1]] += 1

            copied_path = copy_member(zf, member, apk_unzip_root)

            if suffix in WEB_SAFE_SUFFIXES and web_root is not None:
                copy_member(zf, member, web_root / "raw")
                web_safe_assets.append(member)

            if suffix != ".zt1":
                continue

            decoded = read_zt1(copied_path.read_bytes())
            decoded_path = decoded_root / f"{member}.bin"
            decoded_path.parent.mkdir(parents=True, exist_ok=True)
            decoded_path.write_bytes(decoded.decoded)

            guessed_encoding, strings = extract_strings(
                decoded.decoded, preferred_encoding=preferred_encoding_for(member)
            )
            entry = {
                "path": member,
                "kind": kind_for(member),
                "locale": locale_for(member),
                "packedSize": decoded.packed_size,
                "decodedSize": decoded.unpacked_size,
                "encoding": guessed_encoding,
                "stringCount": len(strings),
                "stringsPreview": strings[:12],
                "decodedPath": str(decoded_path.relative_to(output_root)),
            }
            zt1_entries.append(entry)

            if strings:
                preview_path = decoded_root / f"{member}.strings.txt"
                write_text(preview_path, "\n".join(strings))

    featured_scripts = [
        entry
        for entry in sorted(
            (item for item in zt1_entries if item["kind"] == "script"),
            key=lambda item: (int(item["stringCount"]), int(item["decodedSize"])),
            reverse=True,
        )[:20]
    ]

    blocked_formats = [
        {
            "suffix": suffix,
            "count": ext_counts[suffix],
            "reason": reason,
        }
        for suffix, reason in (
            (
                ".pzx",
                "Primary sprite container. First zlib stream now decodes into chunk-level indexed bitmaps, but palette selection and whole-sprite assembly remain unresolved.",
            ),
            (".mpl", "Likely animation or mesh metadata. Parser still unknown."),
            (".ptc", "Particle or effect definition. Parser still unknown."),
        )
        if suffix in ext_counts
    ]

    catalog = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "apkPath": str(apk_path),
        "runtimeTarget": "Phaser + TypeScript + Vite, wrapped later with Capacitor for Android/iOS",
        "inventory": {
            "extensions": dict(sorted(ext_counts.items())),
            "assetDirectories": dict(sorted(asset_dir_counts.items())),
            "zt1Total": len(zt1_entries),
            "webSafeAssetCount": len(web_safe_assets),
        },
        "featuredScripts": featured_scripts,
        "blockedFormats": blocked_formats,
        "webSafeAssets": web_safe_assets[:40],
    }

    full_catalog = {
        **catalog,
        "zt1Entries": zt1_entries,
    }

    write_json(output_root / "catalog.json", full_catalog)
    if web_root is not None:
        write_json(web_root / "catalog.json", catalog)


if __name__ == "__main__":
    main()
