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

## Working Hypothesis

현재 데이터 기반 분석에서 `frame-record`와 tail block을 `PZX` 내부 타임라인 후보로 보고 있었지만, 네이티브 심볼은 다른 해석을 강하게 시사한다.

- `PZX` later stream은 "프레임 조각/서브프레임/보조 배치" 계층일 수 있다.
- 실제 재생 순서, delay, clip index, loop 같은 시간축 정보는 `CGxPZAParser::DecodeAnimationData`가 해석하는 별도 구조일 수 있다.
- 첫 번째 조각 stream을 `PZF` 계층, 이후 animation stream을 `PZA` 계층으로 대응시키면 현재까지 관찰된 "placement는 보이는데 시간축이 안 보인다"는 현상을 자연스럽게 설명할 수 있다.
- 따라서 다음 reverse path의 우선순위는 `PZX tail` 일반화보다 `PZA parser -> PZx animation object` 연결 해체다.

## Next Reverse Steps

1. `CGxPZxMgr::Open/LoadAni/LoadFrame`의 xref를 기준으로 later stream을 `PZA`와 `PZF` 후보로 분할한다.
2. `CGxPZA::GetAnimation -> CGxPZAParser::DecodeAnimationData` 내부 필드 배치를 우선 해체해서 delay/frame index/loop 규칙을 확보한다.
3. `CGxPZFParser::UncompressAllDataFromBAR/FILE`와 현재 복원한 first-stream layout을 대조해 `PZF` 쪽 헤더 필드를 확정한다.
4. `CSpriteIns::DoAnimate`와 `GetAniProcessCount`가 소비하는 `CGxPZxAni` 필드를 역추적해, parser 출력이 실제 재생 시간축으로 어떻게 반영되는지 연결한다.
5. 마지막에 `.pzx` 후반 stream/tail이 `PZA` 입력인지, 독립 overlay track인지, 혹은 둘 다인지 결론을 낸다.
