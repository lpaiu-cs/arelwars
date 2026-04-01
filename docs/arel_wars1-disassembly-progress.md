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

### Negative Result

- `frameIndex max < visible frame-record count`는 성립하지 않았다.
- 특히 `082/083/084.pzx` 계열은 frame-record stream도 보이지만, animation stream의 `frameIndex` 상한이 그 record 수보다 훨씬 크다.
- 따라서 `frameIndex`는 현재 잡아낸 frame-record stream 길이가 아니라, `CGxPZFMgr::LoadFrameEx`가 여는 별도 frame pool / decompressed frame table을 가리킬 가능성이 높다.

### Next Focus

1. `CGxPZAMgr::LoadAni*`와 `CGxPZA::CreateAniFrameIndex`에서 `frameIndex[]` 소비 지점을 더 좁힌다.
2. `CGxPZFMgr::LoadFrameEx`와 `CGxPZFParser::UncompressAllDataFromBAR/FILE`를 깨서 native frame pool 구조를 찾는다.
3. `082/083/084.pzx`를 기준 샘플로 삼아 `frame-record stream`과 `PZA animation stream`의 분리 관계를 설명한다.

### Refresh Commands

```powershell
python tools/arel_wars1/disassemble_libgameDSO.py --defaults
python tools/arel_wars1/extract_assets.py --apk arel_wars1/arel_wars_1.apk --output recovery/arel_wars1/native_tmp/extract
python tools/arel_wars1/inspect_binary_assets.py --assets-root recovery/arel_wars1/native_tmp/extract/apk_unzip/assets --output recovery/arel_wars1/native_tmp/binary_asset_report-session.json
```
