# Arel Wars 1 Disassembly Progress

이 파일은 `disassemble` 브랜치의 중간 진행 보고용 메모다. 세부 근거와 함수 단위 reverse 결과는 [arel_wars1-disassembly.md](/C:/vs/other/arelwars/docs/arel_wars1-disassembly.md)에 누적하고, 여기에는 이번 세션의 checkpoint만 적는다.

## 2026-04-01 Session

### Confirmed

- `CGxPZAParser::DecodeHeader`
  - `3-byte` 헤더
  - `header[1..2] = animation count`
- `CGxPZAParser::Open`
  - `count * 4` index table 준비
  - `SeekIndexTable(index)`를 통해 `u32 offset` 기반 animation blob seek
- `CGxPZAParser::DecodeAnimationData`
  - clip blob 형식은 `frameCount:u8 + frameCount * 8-byte frame`
  - frame = `frameIndex:u16`, `delay:u8`, `x:s16`, `y:s16`, `control:u8`
- `CGxPZxAni`
  - 런타임 frame record는 `12-byte`
  - `delay/x/y/frame pointer`만 저장
  - `frameIndex`는 별도 `u16[]`로 분리
- `CGxPZAMgr::LoadAni*`
  - 분리된 `frameIndex[]`를 사용해 `CGxPZFMgr::LoadFrameEx` 호출
  - 결과 frame pointer를 `CGxPZxAni` frame record에 주입
- `CGxPZF19CreateSubFrameIndex` / `CGxPZFMgr::LoadFrameEx`
  - `PZF`도 같은 방식으로 `u16 subFrameIndex[]` 캐시를 가짐
  - `LoadFrameEx`는 그 배열을 따라 `CGxPZDPackage` loader를 돌고, 결과 pointer를 `CGxPZxFrame` 내부 array에 저장
  - 즉 네이티브 계층이 `PZA -> PZF -> PZD`로 이어진다는 점이 더 강해졌다.
- `CGxPZxParserBase::CheckPZxType`
  - 루트 `PZX\x01` 헤더를 special-case 한다.
  - 파일 시작 16바이트의 `field4/field8/field12`를 typed subresource offset table로 취급한다.
  - 타입 코드는 `PZD=0`, `PZF=1`, `PZA=2`로 고정된다.
- `CGxPZxMgr::SetSource`
  - `CGxPZxResource` 하나를 만든 뒤 `PZFMgr`와 `PZAMgr`에 공유한다.
  - 따라서 `PZF/PZA`는 별도 파일이 아니라 같은 `.pzx` 내부 typed subresource다.
- `CGxPZxFrameBB::GetTotalBoundingBoxCount / GetBoundingBoxCount / GetBoundingBox`
  - bbox count byte는 frame `+0x20/+0x21`
  - bbox format variant는 frame `+0x22`
  - bbox record array는 frame `+0x1c`
  - variant `1/3` bbox record는 `x, y, w, h` 4-word shape로 소비된다.

### Asset-side Validation

- `tools/arel_wars1/inspect_binary_assets.py`에 animation clip stream 파서를 추가했다.
- exact-fit 조건으로 다시 스캔했을 때:
  - `144` stems에서 animation clip stream 검출
  - 검출된 stream index는 모두 `2`
  - 즉 다수 `.pzx`에서 세 번째 zlib stream이 `PZA` animation blob으로 보인다.
- 현재 관찰 범위:
  - `frameIndex = 0..85`
  - `delay = 0..32`
  - `x = 0`
  - `y = -80..10`
  - `control = 0`
- raw `PZA` subresource까지 직접 파싱하면:
  - `159` stems에서 `PZA` index table + payload가 clip 구조로 정확히 읽힌다.
  - `145` stems는 raw `PZA` payload가 zlib stream index `2`와 byte-identical 하다.
  - `PZF` raw header의 `frameCount`는 `PZA frameIndex`가 가리키는 실제 frame pool 크기다.
  - 집계상 `143` stems는 `max(frameIndex)+1 == PZF frameCount`, 나머지 `16` stems도 in-range sparse reference다.
- raw `PZF` head가 샘플마다 달라 보이는 이유도 방향이 잡혔다.
  - `BeginDecodeFrame`가 먼저 bounding-box count byte를 읽고
  - count가 nonzero인 프레임은 `DecodeBoundingBoxFromBAR/FILE`가 먼저 stream을 소비한 뒤
  - `EndDecodeFrameFromBAR/FILE`가 subframe list를 읽는 구조로 보인다.
  - 그래서 `010`처럼 count가 0인 샘플은 record head가 바로 보이지만, `082` 같은 샘플은 payload head만 보고는 subframe index가 안 보일 수 있다.
- raw `PZF` frame parser도 자산측에 내렸다.
  - `253/253` stems에서 raw embedded `PZF`가 frame 단위로 exact-fit 된다.
  - `216` stems는 raw `PZF` payload가 zlib stream index `1`과 byte-identical 하다.
  - `51` stems는 old frame-record parser의 `recordOffsetsPreview`가 raw `PZF` frame offset table prefix와 정확히 맞는다.
  - 즉 stream `1`과 frame-record heuristic은 native `PZF`의 partial/misaligned read로 보는 쪽이 맞다.
- `PZF` subframe record의 현재 working shape:
  - `subFrameIndex:u16`, `x:s16`, `y:s16`, `extraFlag:u8`, `extraPayload`
  - `extraPayload`는 자산 exact-fit 기준으로 `extraFlag` 또는 `extraFlag + 4` 바이트로 닫힌다.
  - marker형 payload는 `66 xx 00 00 00` / `67 xx 00 00 00`가 우세하다.
  - 이 hybrid rule은 asset 쪽 exact-fit은 주지만, 아직 `EndDecodeFrame*` 디스어셈블만으로는 설명이 완전히 닫히지 않았다.

### Resolved

- 이전 negative result였던 "`frameIndex max < visible frame-record count` 불성립"은 이제 설명된다.
- 원인은 visible frame-record stream을 실제 `PZF` frame pool로 착각한 데 있었다.
- 예: `082.pzx`
  - raw `PZF frameCount = 86`
  - raw `PZA frameIndex range = 0..85`
  - 즉 native `frameIndex`는 frame-record stream 길이가 아니라 raw `PZF` subresource count를 가리킨다.

### Next Focus

1. `CGxPZDPackage / CGxPZDMgr::LoadImage*`를 따라 `subFrameIndex[] -> PZD image -> first-stream chunk` 연결을 확정한다.
2. `CGxPZxFrame::Draw`와 `CGxPZxFrameBB::*` consumer를 더 따라가서 `extraPayload(66/67...)`와 bbox group 의미를 런타임 동작에 붙인다.
3. `082/083/084`와 `198/208/240`을 기준 샘플로, old frame-record/tail heuristic이 native `PZF`의 어느 subset을 잘못 읽은 것인지 정리한다.

### Refresh Commands

```powershell
python tools/arel_wars1/disassemble_libgameDSO.py --defaults
python tools/arel_wars1/extract_assets.py --apk arel_wars1/arel_wars_1.apk --output recovery/arel_wars1/native_tmp/extract
python tools/arel_wars1/inspect_binary_assets.py --assets-root recovery/arel_wars1/native_tmp/extract/apk_unzip/assets --output recovery/arel_wars1/native_tmp/binary_asset_report-session.json
```
