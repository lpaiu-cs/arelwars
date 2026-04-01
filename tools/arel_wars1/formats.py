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
    run_kinds: tuple[str, ...]
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
    prefix_marker_hex: str | None
    row_separator_hexes: tuple[str, ...]
    trailing_sentinel_hex: str | None

    @property
    def decoded_pixel_count(self) -> int:
        return sum(len(row.decoded) for row in self.rows)


@dataclass(frozen=True)
class PzxFirstStream:
    table_span: int
    offsets: tuple[int, ...]
    chunks: tuple[PzxChunk, ...]


@dataclass(frozen=True)
class PzxRowStream:
    rows: tuple[PzxRow, ...]
    prefix_marker_hex: str | None
    row_separator_hexes: tuple[str, ...]
    trailing_sentinel_hex: str | None

    @property
    def height(self) -> int:
        return len(self.rows)

    @property
    def width(self) -> int | None:
        widths = {len(row.decoded) for row in self.rows}
        if len(widths) != 1:
            return None
        return next(iter(widths))

    @property
    def width_range(self) -> tuple[int, int]:
        widths = [len(row.decoded) for row in self.rows]
        return (min(widths), max(widths))

    @property
    def decoded_pixel_count(self) -> int:
        return sum(len(row.decoded) for row in self.rows)


@dataclass(frozen=True)
class PzxSimplePlacement:
    mode: int
    chunk_index: int
    x: int
    y: int


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


def decode_pzx_row(body: bytes, cursor: int, width: int) -> tuple[PzxRow, int]:
    decoded = bytearray()
    skips: list[int] = []
    run_lengths: list[int] = []
    run_kinds: list[str] = []

    while len(decoded) < width:
        if cursor + 2 > len(body):
            raise ValueError("PZX row ended mid-opcode")
        word = struct.unpack("<H", body[cursor : cursor + 2])[0]

        if word < 0x8000:
            decoded.extend(b"\x00" * word)
            skips.append(word)
            cursor += 2
            continue

        if 0x8000 <= word < 0xC000:
            literal_len = word & 0x3FFF
            cursor += 2
            literal = body[cursor : cursor + literal_len]
            if len(literal) != literal_len:
                raise ValueError("PZX row ended mid-literal")
            decoded.extend(literal)
            run_lengths.append(literal_len)
            run_kinds.append("literal")
            cursor += literal_len
        elif 0xC000 <= word < 0xFDFF:
            repeat_len = word & 0x3FFF
            cursor += 2
            if cursor >= len(body):
                raise ValueError("PZX row ended mid-repeat")
            value = body[cursor]
            decoded.extend(bytes([value]) * repeat_len)
            run_lengths.append(repeat_len)
            run_kinds.append("repeat")
            cursor += 1
        else:
            raise ValueError(f"Unknown PZX opcode family: {word:#06x}")

        if len(decoded) > width:
            raise ValueError(f"PZX row width overflow: decoded={len(decoded)} expected={width}")

    if len(decoded) != width:
        raise ValueError(f"PZX row width mismatch: decoded={len(decoded)} expected={width}")

    return (
        PzxRow(
            skips=tuple(skips),
            run_lengths=tuple(run_lengths),
            run_kinds=tuple(run_kinds),
            decoded=bytes(decoded),
        ),
        cursor,
    )


def decode_pzx_row_until_marker(body: bytes, cursor: int) -> tuple[PzxRow, int, int]:
    decoded = bytearray()
    skips: list[int] = []
    run_lengths: list[int] = []
    run_kinds: list[str] = []

    while True:
        if cursor + 2 > len(body):
            raise ValueError("PZX row ended before a row separator")
        word = struct.unpack("<H", body[cursor : cursor + 2])[0]
        if word in (0xFFFE, 0xFFFF):
            return (
                PzxRow(
                    skips=tuple(skips),
                    run_lengths=tuple(run_lengths),
                    run_kinds=tuple(run_kinds),
                    decoded=bytes(decoded),
                ),
                cursor,
                word,
            )

        if word < 0x8000:
            decoded.extend(b"\x00" * word)
            skips.append(word)
            cursor += 2
            continue

        if 0x8000 <= word < 0xC000:
            literal_len = word & 0x3FFF
            cursor += 2
            literal = body[cursor : cursor + literal_len]
            if len(literal) != literal_len:
                raise ValueError("PZX row ended mid-literal")
            decoded.extend(literal)
            run_lengths.append(literal_len)
            run_kinds.append("literal")
            cursor += literal_len
            continue

        if 0xC000 <= word < 0xFDFF:
            repeat_len = word & 0x3FFF
            cursor += 2
            if cursor >= len(body):
                raise ValueError("PZX row ended mid-repeat")
            value = body[cursor]
            decoded.extend(bytes([value]) * repeat_len)
            run_lengths.append(repeat_len)
            run_kinds.append("repeat")
            cursor += 1
            continue

        raise ValueError(f"Unknown PZX opcode family: {word:#06x}")


def read_pzx_row_stream(body: bytes) -> PzxRowStream | None:
    if not body:
        return None

    cursor = 0
    rows: list[PzxRow] = []
    prefix_marker_hex: str | None = None
    row_separator_hexes: list[str] = []
    trailing_sentinel_hex: str | None = None

    if body[:2] in (b"\xfd\xff", b"\xfe\xff"):
        prefix_marker_hex = body[:2].hex()
        cursor = 2

    while cursor < len(body):
        row, cursor, marker = decode_pzx_row_until_marker(body, cursor)

        if marker == 0xFFFE:
            rows.append(row)
            row_separator_hexes.append("feff")
            cursor += 2
            continue

        if row.decoded:
            rows.append(row)
        trailing_sentinel_hex = "ffff"
        cursor += 2
        break

    if cursor != len(body):
        raise ValueError(f"Unexpected trailing PZX bytes: {body[cursor:].hex()}")
    if not rows:
        return None

    return PzxRowStream(
        rows=tuple(rows),
        prefix_marker_hex=prefix_marker_hex,
        row_separator_hexes=tuple(row_separator_hexes),
        trailing_sentinel_hex=trailing_sentinel_hex,
    )


def read_pzx_simple_placement_stream(stream: bytes, chunk_count: int) -> tuple[PzxSimplePlacement, ...] | None:
    if chunk_count <= 0 or len(stream) != chunk_count * 10:
        return None

    placements: list[PzxSimplePlacement] = []
    seen_indices: set[int] = set()

    for cursor in range(0, len(stream), 10):
        record = stream[cursor : cursor + 10]
        if record[1] != 0 or record[2] != 0 or record[4] != 0 or record[9] != 0:
            return None

        chunk_index = record[3]
        if chunk_index >= chunk_count or chunk_index in seen_indices:
            return None

        placements.append(
            PzxSimplePlacement(
                mode=record[0],
                chunk_index=chunk_index,
                x=struct.unpack("<h", record[5:7])[0],
                y=struct.unpack("<h", record[7:9])[0],
            )
        )
        seen_indices.add(chunk_index)

    if len(placements) != chunk_count:
        return None

    return tuple(placements)


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
        row_stream = read_pzx_row_stream(body)
        if row_stream is None:
            return None

        if row_stream.height != height:
            raise ValueError(f"PZX chunk row count mismatch: rows={row_stream.height} height={height}")
        if row_stream.width != width:
            raise ValueError(f"PZX chunk width mismatch: rows={row_stream.width} width={width}")
        if row_stream.decoded_pixel_count != width * height:
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
                rows=row_stream.rows,
                prefix_marker_hex=row_stream.prefix_marker_hex,
                row_separator_hexes=row_stream.row_separator_hexes,
                trailing_sentinel_hex=row_stream.trailing_sentinel_hex,
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
