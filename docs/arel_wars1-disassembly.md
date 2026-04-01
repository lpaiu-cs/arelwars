# Arel Wars 1 Native Disassembly

이 브랜치는 `.pzx`의 후반 메타데이터를 데이터 패턴만으로 추론하는 대신, `arel_wars1/arel_wars_1.apk` 안의 `lib/armeabi/libgameDSO.so`를 직접 추적해서 원본 디코더 경로를 찾는 데 집중한다.

## Entry Point

`libgameDSO.so`는 APK 안에 그대로 들어 있다.

```powershell
powershell -ExecutionPolicy Bypass -File tools/arel_wars1/inspect_libgameDSO.ps1
```

위 스크립트는 다음을 자동으로 수행한다.

- APK에서 `lib/armeabi/libgameDSO.so` 추출
- ELF32 section / symbol table 파싱
- `PZX`, `PZA`, `PZF`, `MPL`, `Animation`, `inflate`, `ZT1` 관련 함수 추출
- Thumb `BL` immediate call-site를 스캔해서 함수 간 call edge 구성
- 결과를 `recovery/arel_wars1/disassembly/` 아래 JSON/TSV로 저장

생성 산출물은 `.gitignore`에 추가되어 있으므로 브랜치를 오염시키지 않는다.
전체 call-edge 스캔까지 포함하면 실행 시간은 환경에 따라 수 분 걸릴 수 있다.

함수 바디를 직접 볼 때는 아래 파이썬 디스어셈블러를 사용한다.

```powershell
python tools/arel_wars1/disassemble_libgameDSO.py --defaults
python tools/arel_wars1/disassemble_libgameDSO.py --find DecodeAnimation
python tools/arel_wars1/disassemble_libgameDSO.py --function _ZN12CGxPZAParser19DecodeAnimationDataEti
```

이 스크립트는 `capstone`과 `pyelftools`를 사용해 Thumb 코드를 디스어셈블하고, branch target을 심볼명으로 주석 처리한다.

## Current Native Findings

- `libgameDSO.so`는 `ELF32 little-endian / EM_ARM (0x0028)`이다.
- 심볼이 충분히 남아 있어서, 함수명만으로도 네이티브 로더 계층을 추적할 수 있다.
- APK asset table에는 `.pza` / `.pzf` 파일이 따로 없고, 실제 이미지 자산은 `.pzx`, `.mpl`, `.ptc`, `.zt1`만 존재한다.
- 그런데 네이티브 호출축은 `PZX` 매니저가 내부적으로 `PZA` / `PZF` 서브매니저를 여는 구조를 보인다.
  - `CGxPZxMgr::Open -> CGxPZAMgr::Open + CGxPZFMgr::Open`
  - `CGxPZxMgr::LoadAni -> CGxPZAMgr::LoadAni / LoadAniEx`
  - `CGxPZxMgr::LoadFrame -> CGxPZFMgr::LoadFrameEx`
- 즉 `.pzx` 후반 stream은 "정체불명의 tail"이라기보다, 네이티브 런타임에서 `PZA`(animation) / `PZF`(frame) parser가 소비하는 서브영역일 가능성이 크다.
- `PZX` 쪽 로더/렌더러 축은 다음 이름들로 드러난다.
  - `CGsPzxResourceMgr::Load`
  - `CGsPzxResource::Load`
  - `CGxPZxMgr::Open`
  - `CGxPZxMgr::LoadFrame`
  - `CGxPZxMgr::LoadAni`
  - `CGxPZxAni::Play`
  - `CGxPZxAni::DoPlay`
  - `CGxPZxAni::GetCurrentDelayFrameCount`
- 시간축 애니메이션 메타데이터 쪽의 핵심 후보는 `PZX` 전용 함수보다 오히려 다음 축이다.
  - `CGxPZAMgr::LoadAni`
  - `CGxPZAMgr::LoadAniAll`
  - `CGxPZA::GetAnimation`
  - `CGxPZAParser::Open`
  - `CGxPZAParser::DecodeHeader`
  - `CGxPZAParser::DecodeAnimationData`
- call xref 기준으로 `CGxPZA::GetAnimation -> CGxPZAParser::DecodeAnimationData`가 직접 연결된다.
- 재생 루프 쪽은 `CSpriteIns::DoAnimate -> CGxPZxAni::DoPlay`, `CSpriteIns::GetAniProcessCount -> CGxPZxAni::GetCurrentDelayFrameCount`로 이어진다.
- 즉 현재까지의 네이티브 구조상, "조각 배치"와 "시간축 재생"은 같은 계층이 아닐 가능성이 높다.
  - `PZX` 계층은 프레임/이미지 조각 로딩
  - `PZA` 계층은 애니메이션 인덱스/프레임 진행 메타데이터
- `inflate*` 심볼이 외부 import가 아니라 라이브러리 내부에 정적으로 들어 있으므로, zlib 호출자를 직접 따라가면 실제 디코더 함수를 좁힐 수 있다.
- 실제로 `inflateInit / inflate / inflateEnd`는 모두 `uncompress` 내부에서만 보이고, parser 계층은 `GxUncompress`를 통해 zlib를 우회 호출한다.
  - `GxUncompress` caller: `CGxPZFParser::UncompressAllDataFromBAR`, `CGxPZFParser::UncompressAllDataFromFILE`, `CGxPZDParser::DecodeImageData`
  - `GxUncompressZT1` caller: `LoadResource`, `LoadFile`
- 따라서 `.zt1` 복호 경로와 `.pzx`/`.pza`/`.pzf` 복호 경로는 네이티브에서도 이미 분리되어 있다.

## Current Structure

- `CGxPZAParser::DecodeHeader`는 사실상 `3-byte` PZA 헤더를 읽는다.
  - `header[0]`: storage / parser mode flag
  - `header[1..2]`: animation count (`u16`)
- `CGxPZAParser::Open`는 이 animation count를 바탕으로 `count * 4` 바이트짜리 index table을 준비한다.
  - storage flag에 따라 raw seek path와 `UncompressAllDataFromBAR/FILE` path로 갈린다.
  - 즉 `PZA`의 index table entry는 `4-byte offset`이다.
- `CGxPZxParserBase::SeekIndexTable(index)`는:
  - index table 시작점으로 이동
  - `index * 4` 위치의 `u32 offset`를 읽고
  - 그 offset으로 다시 seek 한다.
- 따라서 `DecodeAnimationData(index, ...)`는 "animation index -> offset table -> animation blob" 흐름으로 동작한다.

## Animation Layout

- `CGxPZA::GetAnimation(index)`는 `CGxPZAParser::DecodeAnimationData`를 호출해 `CGxPZxAni*`를 만든다.
- 동시에 `frameIndex` 목록은 `CGxPZxAni` 안에 넣지 않고, 별도 `u16` 배열로 받아서 `CGxPZA::CreateAniFrameIndex`가 animation index별 캐시로 복제한다.
- `CGxPZAMgr::LoadAni*`는 그 별도 `frameIndex` 배열을 이용해 `CGxPZFMgr::LoadFrameEx`를 호출하고, 결과 frame pointer를 `CGxPZxAni` 내부 frame record에 꽂는다.
- 즉 현재 구조는 명확히 분리된다.
  - `PZA`: timeline / frame index / per-frame offset-delay 메타데이터
  - `PZF`: 실제 frame payload
- `CreateAniFrameIndex`는 실제로 `frameCount * 2` 바이트를 할당해서 `u16[]`를 복사한다.
- `LoadAni`는 animation object의 `frameCount`만큼 순회하면서:
  - manager 쪽 `u16 frameIndex[]`를 읽고
  - `CGxPZFMgr` virtual call을 통해 frame pointer를 로드하고
  - `CGxPZxAni` frame record array(`stride = 0x0C`)의 첫 필드에 저장한다.
- `PZF`도 동일한 구조를 반복한다.
  - `CGxPZF::CreateSubFrameIndex`는 `subFrameCount * 2` 바이트 `u16[]`를 캐시한다.
  - `CGxPZFMgr::LoadFrameEx`는 그 `subFrameIndex[]`를 따라가며 `CGxPZDPackage` loader를 호출하고, 결과 subframe/resource pointer를 `CGxPZxFrame` 내부 array(`stride = 0x10`)에 저장한다.
- 따라서 현재 네이티브 계층은 다음처럼 읽히는 편이 가장 자연스럽다.
  - `PZA clip -> PZF frame index -> PZD subframe index -> 실제 리소스 pointer`

`CGxPZxAni` 객체 레이아웃은 현재까지 다음처럼 보인다.

```text
CGxPZxAni (size 0x18)
  +0x08  clip state pointer
  +0x0C  owns clip state flag
  +0x10  frame record array pointer
  +0x14  frame count
```

`CreateAniClip`이 만드는 clip state는 `4-byte` 구조다.

```text
clip state (size 4)
  +0  current frame index
  +1  current delay position
  +2  playback flags
  +3  signed global delay bias
```

`DecodeAnimationData`가 채우는 per-frame record는 `12-byte` 구조다.

```text
frame record (size 0x0C)
  +0x00  frame pointer (later filled by PZF manager)
  +0x04  x offset (s16)
  +0x06  y offset (s16)
  +0x08  local delay (u8)
  +0x09..0x0B  padding / unused in current reading
```

애니메이션 blob의 현재 working decode는 다음과 같다.

```text
animation:
  frameCount:u8
  repeat frameCount times:
    frameIndex:u16
    delay:u8
    x:s16
    y:s16
    control:u8
```

- `frameIndex`는 `CGxPZxAni` frame record에 저장되지 않는다.
- 대신 별도 `u16[]`로 빠져서 `CGxPZAMgr::LoadAni*`가 `PZF` frame 로딩에 사용한다.
- `control:u8`는 `CGxPZxAni`에 저장되지 않는다.
- 대신 0이 아닐 때 stream callback을 한 번 더 치는 구조라서, runtime 재생 플래그보다는 container / separator 계층일 가능성이 높다.
- `DecodeAnimationData` 내부의 두 갈래는 서로 다른 animation 포맷이 아니라 `CGxStream` backend 차이로 보인다.
  - direct memory buffer path
  - callback-based stream path

## Asset Cross-check

네이티브에서 복원한 위 레이아웃을 실제 `.pzx` zlib stream에 대입하면, asset 쪽에서도 꽤 강하게 닫힌다.

- `tools/arel_wars1/inspect_binary_assets.py`는 이제 exact-fit animation clip stream을 인식한다.
- 현재 휴리스틱은 다음이다.
  - stream 전체가 `frameCount:u8 + frameCount * 8-byte frame record`의 clip 연속체로 끝까지 정확히 소진될 것
  - 각 frame record는 `frameIndex:u16`, `delay:u8`, `x:s16`, `y:s16`, `control:u8`
  - `delay`와 `x/y`는 네이티브에서 보이는 runtime 범위에 맞춰 제한한다.
- 이 조건으로 APK 전체를 다시 스캔하면:
  - exact-fit animation clip stream이 `144`개 stem에서 검출된다.
  - 검출된 stream index는 전부 `2`다.
  - 즉 다수 자산에서 "세 번째 zlib stream = PZA animation blob"이 거의 확정적이다.
- 현재까지 확인된 전체 범위는 다음과 같다.
  - `frameIndex`: `0..85`
  - `delay`: `0..32`
  - `x`: 항상 `0`
  - `y`: `-80..10`
  - `control`: 확인된 exact-fit stream에서는 모두 `0`
- clip 개수 분포도 자연스럽다.
  - single-clip stem이 가장 많고
  - 그 다음이 3-clip stem이다.
  - 즉 "한 sprite 안에 여러 animation clip" 구조와 잘 맞는다.
- 반대로, `frameIndex max < frame-record count` 같은 단순 대응은 아직 성립하지 않는다.
  - 예: `082/083/084.pzx` 계열은 animation stream이 잡히지만 `frameIndex` 최댓값이 visible frame-record 수보다 훨씬 크다.
  - 따라서 `frameIndex`는 현재 보고 있는 frame-record stream 길이가 아니라, `CGxPZFMgr::LoadFrameEx`가 여는 별도 frame pool / decompressed frame table을 가리킬 가능성이 높다.

## Working Hypothesis

현재 데이터 기반 분석에서 `frame-record`와 tail block을 `PZX` 내부 타임라인 후보로 보고 있었지만, 네이티브 심볼은 다른 해석을 강하게 시사한다.

- `PZX` later stream은 "프레임 조각/서브프레임/보조 배치" 계층일 수 있다.
- 실제 재생 순서, delay, clip index, loop 같은 시간축 정보는 `CGxPZAParser::DecodeAnimationData`가 해석하는 별도 구조일 수 있다.
- 첫 번째 조각 stream을 `PZF` 계층, 이후 animation stream을 `PZA` 계층으로 대응시키면 현재까지 관찰된 "placement는 보이는데 시간축이 안 보인다"는 현상을 자연스럽게 설명할 수 있다.
- 특히 현재는 "세 번째 zlib stream이 곧 `PZA` blob"인 stem이 대량으로 존재하므로, 남은 문제는 stream 포맷 추정 자체보다 `frameIndex -> PZF frame pool` 연결을 해체하는 쪽으로 좁혀졌다.
- 따라서 다음 reverse path의 우선순위는 `PZX tail` 일반화보다 `PZA parser -> PZx animation object` 연결 해체다.

## Next Reverse Steps

1. `CGxPZAMgr::LoadAni*`와 `CGxPZA::CreateAniFrameIndex`를 더 파서, `frameIndex` 배열이 정확히 어떤 `PZF` 리소스 테이블로 들어가는지 잡는다.
2. `CGxPZFMgr::LoadFrameEx`와 `CGxPZFParser::UncompressAllDataFromBAR/FILE`를 해체해서, 현재 first-stream / frame-record stream과 네이티브 frame pool 사이의 대응을 확정한다.
3. `082/083/084.pzx` 같은 frame-record + animation 동시 보유 stem을 기준 샘플로 삼아, "visible frame-record 수"와 "animation frameIndex 상한"이 왜 어긋나는지 설명 가능한 구조를 만든다.
4. `CSpriteIns::DoAnimate`와 `GetAniProcessCount`가 소비하는 `CGxPZxAni` 필드를 역추적해, parser 출력이 실제 재생 시간축으로 어떻게 반영되는지 연결한다.
5. 마지막에 `.pzx` 후반 stream/tail이 `PZA` 입력인지, 독립 overlay track인지, 혹은 둘 다인지 결론을 낸다.
