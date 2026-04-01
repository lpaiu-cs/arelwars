#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
import tempfile


DEFAULT_INPUT_DIR = Path("recovery/arel_wars1/native_tmp/extract/apk_unzip")
DEFAULT_OUTPUT_APK = Path("recovery/arel_wars1/native_tmp/arel_wars_1-repacked-signed.apk")
DEFAULT_KEYSTORE = Path("recovery/arel_wars1/native_tmp/debug.keystore")
SIGNATURE_PREFIX = "META-INF/"
STORE_EXTENSIONS = {
    ".arsc",
    ".dex",
    ".jpg",
    ".jpeg",
    ".ogg",
    ".otf",
    ".png",
    ".so",
    ".ttf",
    ".webp",
    ".zip",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild and sign an APK from an exploded APK directory using keytool + jarsigner.",
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-apk", type=Path, default=DEFAULT_OUTPUT_APK)
    parser.add_argument("--keystore", type=Path, default=DEFAULT_KEYSTORE)
    parser.add_argument("--alias", default="androiddebugkey")
    parser.add_argument("--storepass", default="android")
    parser.add_argument("--keypass", default="android")
    parser.add_argument("--dname", default="CN=Android Debug,O=Android,C=US")
    parser.add_argument("--create-keystore", action="store_true")
    return parser.parse_args()


def should_skip(rel_path: str) -> bool:
    return rel_path.upper().startswith(SIGNATURE_PREFIX)


def build_unsigned_apk(input_dir: Path, output_apk: Path) -> None:
    import zipfile

    output_apk.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_apk, "w") as zf:
        for path in sorted(input_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(input_dir).as_posix()
            if should_skip(rel_path):
                continue
            compress_type = zipfile.ZIP_STORED if path.suffix.lower() in STORE_EXTENSIONS else zipfile.ZIP_DEFLATED
            zf.write(path, rel_path, compress_type=compress_type)


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def ensure_keystore(args: argparse.Namespace) -> None:
    if args.keystore.exists():
        return
    if not args.create_keystore:
        raise FileNotFoundError(
            f"Keystore not found: {args.keystore}. Re-run with --create-keystore or provide an existing keystore."
        )
    args.keystore.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "keytool",
            "-genkeypair",
            "-keystore",
            str(args.keystore),
            "-storepass",
            args.storepass,
            "-alias",
            args.alias,
            "-keypass",
            args.keypass,
            "-dname",
            args.dname,
            "-keyalg",
            "RSA",
            "-keysize",
            "2048",
            "-validity",
            "10000",
        ]
    )


def sign_apk(unsigned_apk: Path, args: argparse.Namespace) -> None:
    run(
        [
            "jarsigner",
            "-keystore",
            str(args.keystore),
            "-storepass",
            args.storepass,
            "-keypass",
            args.keypass,
            "-sigalg",
            "SHA256withRSA",
            "-digestalg",
            "SHA-256",
            str(unsigned_apk),
            args.alias,
        ]
    )
    run(["jarsigner", "-verify", "-certs", str(unsigned_apk)])


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_apk = args.output_apk.resolve()
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input dir does not exist: {input_dir}")

    ensure_keystore(args)

    with tempfile.TemporaryDirectory(prefix="arelwars-apk-") as temp_dir:
        unsigned_apk = Path(temp_dir) / "unsigned.apk"
        build_unsigned_apk(input_dir, unsigned_apk)
        sign_apk(unsigned_apk, args)
        output_apk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(unsigned_apk, output_apk)

    print(f"Signed APK written to {output_apk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
