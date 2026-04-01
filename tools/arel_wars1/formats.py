from __future__ import annotations

from dataclasses import dataclass
import struct
import zlib


ZLIB_HEADERS = {0x01, 0x5E, 0x9C, 0xDA}


def _is_text_char(char: str) -> bool:
    if char.isascii():
        return char.isalnum() or char in " .,!?'-:;()[]/&+\""
    return "\uac00" <= char <= "\ud7a3"


@dataclass(frozen=True)
class Zt1File:
    packed_size: int
    unpacked_size: int
    decoded: bytes


@dataclass(frozen=True)
class ZlibStreamHit:
    offset: int
    consumed: int
    decoded: bytes


@dataclass(frozen=True)
class PzxRow:
    skips: tuple[int, ...]
    run_lengths: tuple[int, ...]
    decoded: bytes


@dataclass(frozen=True)
class PzxChunk:
    index: int
    width: int
    height: int
    magic_hex: str
    declared_payload_len: int
    reserved: int
    body: bytes
    rows: tuple[PzxRow, ...]
    trailing_sentinel_hex: str | None

    @property
    def decoded_pixel_count(self) -> int:
        return sum(len(row.decoded) for row in self.rows)


@dataclass(frozen=True)
class PzxFirstStream:
    table_span: int
    offsets: tuple[int, ...]
    chunks: tuple[PzxChunk, ...]


def read_zt1(data: bytes) -> Zt1File:
    if len(data) < 8:
        raise ValueError("ZT1 payload is too short")

    packed_size, unpacked_size = struct.unpack("<II", data[:8])
    decoded = zlib.decompress(data[8:])
    if unpacked_size != len(decoded):
        raise ValueError(
            f"ZT1 unpacked size mismatch: header={unpacked_size}, decoded={len(decoded)}"
        )
    return Zt1File(packed_size=packed_size, unpacked_size=unpacked_size, decoded=decoded)


def find_zlib_streams(data: bytes, *, min_out: int = 8, min_consumed: int = 8) -> list[ZlibStreamHit]:
    hits: list[ZlibStreamHit] = []
    seen: set[tuple[int, int, int]] = set()

    for offset in range(len(data) - 2):
        if data[offset] != 0x78 or data[offset + 1] not in ZLIB_HEADERS:
            continue
        try:
            obj = zlib.decompressobj()
            decoded = obj.decompress(data[offset:])
            consumed = len(data[offset:]) - len(obj.unused_data)
        except zlib.error:
            continue

        if consumed < min_consumed or len(decoded) < min_out:
            continue

        key = (offset, consumed, len(decoded))
        if key in seen:
            continue
        seen.add(key)
        hits.append(ZlibStreamHit(offset=offset, consumed=consumed, decoded=decoded))

    return hits


def split_pzx_row_segments(body: bytes) -> list[bytes]:
    segments: list[bytes] = []
    start = 0

    while True:
        marker = body.find(b"\xfe\xff", start)
        if marker == -1:
            if start < len(body):
                segments.append(body[start:])
            break
        segments.append(body[start:marker])
        start = marker + 2

    return segments


def decode_pzx_row(segment: bytes, width: int) -> PzxRow:
    if segment == b"\xff\xff":
        raise ValueError("PZX row sentinel is not a decodable row")

    decoded = bytearray()
    skips: list[int] = []
    run_lengths: list[int] = []
    cursor = 0

    if cursor + 2 <= len(segment):
        maybe_skip = struct.unpack("<H", segment[cursor : cursor + 2])[0]
        if maybe_skip < 0x8000:
            decoded.extend(b"\x00" * maybe_skip)
            skips.append(maybe_skip)
            cursor += 2

    while cursor < len(segment):
        if cursor + 2 > len(segment):
            raise ValueError("PZX row ended mid-opcode")
        opcode = struct.unpack("<H", segment[cursor : cursor + 2])[0]
        if opcode < 0x8000:
            raise ValueError(f"Expected PZX literal opcode, got {opcode:#06x}")

        literal_len = opcode & 0x7FFF
        cursor += 2
        literal = segment[cursor : cursor + literal_len]
        if len(literal) != literal_len:
            raise ValueError("PZX row ended mid-literal")
        decoded.extend(literal)
        run_lengths.append(literal_len)
        cursor += literal_len

        if cursor == len(segment):
            break

        if cursor + 2 > len(segment):
            raise ValueError("PZX row ended mid-skip")
        skip = struct.unpack("<H", segment[cursor : cursor + 2])[0]
        if skip >= 0x8000:
            raise ValueError(f"Expected PZX skip word, got {skip:#06x}")
        decoded.extend(b"\x00" * skip)
        skips.append(skip)
        cursor += 2

    if len(decoded) != width:
        raise ValueError(f"PZX row width mismatch: decoded={len(decoded)} expected={width}")

    return PzxRow(skips=tuple(skips), run_lengths=tuple(run_lengths), decoded=bytes(decoded))


def read_pzx_first_stream(stream: bytes, table_span: int) -> PzxFirstStream | None:
    if table_span <= 0 or table_span % 4 != 0 or len(stream) < table_span:
        return None

    chunk_count = table_span // 4
    offsets = [struct.unpack("<I", stream[index : index + 4])[0] for index in range(0, table_span, 4)]

    if offsets[0] != table_span:
        return None
    if any(offset < 0 or offset > len(stream) for offset in offsets):
        return None
    if any(offsets[index] > offsets[index + 1] for index in range(len(offsets) - 1)):
        return None

    chunks: list[PzxChunk] = []

    for index, start in enumerate(offsets):
        end = offsets[index + 1] if index + 1 < len(offsets) else len(stream)
        chunk = stream[start:end]
        if len(chunk) < 16:
            return None

        width = struct.unpack("<H", chunk[:2])[0]
        height = struct.unpack("<H", chunk[2:4])[0]
        body = chunk[16:]
        rows: list[PzxRow] = []
        trailing_sentinel_hex: str | None = None

        for segment in split_pzx_row_segments(body):
            if segment == b"\xff\xff":
                trailing_sentinel_hex = segment.hex()
                continue
            rows.append(decode_pzx_row(segment, width))

        if len(rows) != height:
            raise ValueError(f"PZX chunk row count mismatch: rows={len(rows)} height={height}")
        if sum(len(row.decoded) for row in rows) != width * height:
            raise ValueError("PZX chunk decoded pixel count mismatch")

        chunks.append(
            PzxChunk(
                index=index,
                width=width,
                height=height,
                magic_hex=chunk[4:8].hex(),
                declared_payload_len=struct.unpack("<I", chunk[8:12])[0],
                reserved=struct.unpack("<I", chunk[12:16])[0],
                body=body,
                rows=tuple(rows),
                trailing_sentinel_hex=trailing_sentinel_hex,
            )
        )

    return PzxFirstStream(table_span=table_span, offsets=tuple(offsets), chunks=tuple(chunks))


def _extract_runs(text: str) -> list[str]:
    runs: list[str] = []
    current: list[str] = []

    for char in text:
        if _is_text_char(char):
            current.append(char)
            continue

        if current:
            candidate = "".join(current).strip(" -")
            if len(candidate) >= 3 and any(ch.isalnum() or ("\uac00" <= ch <= "\ud7a3") for ch in candidate):
                runs.append(candidate)
            current = []

    if current:
        candidate = "".join(current).strip(" -")
        if len(candidate) >= 3 and any(ch.isalnum() or ("\uac00" <= ch <= "\ud7a3") for ch in candidate):
            runs.append(candidate)

    return runs


def extract_strings(data: bytes, preferred_encoding: str | None = None) -> tuple[str | None, list[str]]:
    encodings: list[str] = []
    if preferred_encoding is not None:
        encodings.append(preferred_encoding)
    for fallback in ("utf-8", "cp949"):
        if fallback not in encodings:
            encodings.append(fallback)

    best_encoding: str | None = None
    best_matches: list[str] = []
    best_score = 0

    for encoding in encodings:
        try:
            chunks = [chunk.decode(encoding, errors="ignore") for chunk in data.split(b"\x00") if chunk]
        except LookupError:
            continue

        matches: list[str] = []
        score = 0
        for chunk in chunks:
            for candidate in _extract_runs(chunk):
                matches.append(candidate)
                score += len(candidate)

        if score > best_score:
            best_score = score
            best_matches = matches
            best_encoding = encoding

    deduped: list[str] = []
    seen: set[str] = set()
    for item in best_matches:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)

    if best_score == 0:
        return None, []

    return best_encoding, deduped
