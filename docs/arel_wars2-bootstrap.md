# Arel Wars 2 Bootstrap Notes

This is the shortest path for starting `arel_wars_2.apk` with the least wasted motion.

## First Facts

Use [`apk_inventory.json`](/Users/lpaiu/vs/others/arelwars/recovery/arel_wars2/apk_inventory.json) before adapting any `arel_wars1` tool.

High-level layout differences from Arel Wars 1:

- `arel_wars_1.apk`
  - `700` `.zt1`
  - `256` `.pzx`
  - `65` `.mpl`
  - `50` `.ptc`
  - main asset roots: `img`, `script_eng`, `script_kor`, `data_eng`, `data_kor`
- `arel_wars_2.apk`
  - `530` `.zt1`
  - `393` `.pzx`
  - `107` `.mpl`
  - `63` `.pzd`
  - `16` `.pzf`
  - `51` `.ptc`
  - main asset roots: `img`, `pc`, `eng`, `kor`, `jpn`, `script`, `table`, `sound`, `plasma`

## What Reuses Cleanly

- `ZT1` header + zlib decoding reuses directly.
- The current `ZT1` event parser also works on sampled AW2 localized script files:
  - `assets/eng/script/000.zt1`
  - `assets/kor/script/000.zt1`
  - `assets/jpn/script/000.zt1`
- AW2 script text is therefore a good first target. It is the lowest-risk way to get immediate narrative structure back.

## What Does Not Reuse Cleanly

- AW1 path assumptions do not hold:
  - localized scripts are under `assets/{eng,kor,jpn}/script/`
  - there is also a separate non-localized `assets/script/`
  - table data lives under `assets/table/*.zt1`
- AW1 `MPL` assumptions do not hold:
  - sampled AW2 `assets/pc/armor/0/000.mpl` is only `2` bytes, so it is not the same “6-word header + 2 full palette banks” structure used by AW1 `assets/img/*.mpl`
- AW1 `PZX` first-stream decoder does not apply directly:
  - sampled AW2 `assets/img/145.pzx` still starts with `PZX\x01`
  - but its first zlib stream does not decode into an offset table; it starts with dense byte data and AW1 `read_pzx_first_stream()` rejects it
  - AW2 `145.pzx` also exposes many more zlib streams (`22` in the sample), so metadata layering is likely deeper

## New Formats Introduced In AW2

- `PZD`
  - sampled file: `assets/pc/armor/0/000.pzd`
  - magic: `PZD\x02`
  - contains multiple embedded zlib streams
  - likely a new major container family for player/character content
- `PZF`
  - present in `16` files
  - not yet inspected here, but treat it as another new container instead of an alias for AW1 `PZX`
- `plasma/`
  - large Samsung/Android UI asset subtree; likely not core gameplay data

## Recommended Order For AW2

1. Run [`inspect_apk_inventory.py`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars_shared/inspect_apk_inventory.py) on the APK.
2. Clone `ZT1` extraction first, not sprite extraction.
   - Adapt paths for `assets/{eng,kor,jpn}/script`, `assets/script`, and `assets/table`.
   - Reuse [`read_zt1()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py) and [`extract_script_events()`](/Users/lpaiu/vs/others/arelwars/tools/arel_wars1/formats.py).
3. Build a fresh AW2 inventory of `PZX`, `PZD`, `PZF`, and `MPL` by directory.
   - Do not start by forcing AW1 `MPL` or `PZX` assumptions onto AW2.
4. Investigate `PZD` before spending too much time on AW2 `img/*.pzx`.
   - `pc/armor/*` strongly suggests that character presentation data moved there.
5. Only after `PZD/PZF` are understood should you revisit AW2 `img/*.pzx` for battle or effect assets.

## Concrete Starting Commands

```bash
python3 tools/arel_wars_shared/inspect_apk_inventory.py \
  --apk arel_wars2/arel_wars_2.apk \
  --output recovery/arel_wars2/apk_inventory.json
```

For quick script sanity checks, reuse AW1 helpers in a one-off Python session:

```python
from tools.arel_wars1.formats import read_zt1, extract_script_events
```

## Practical Warning

If you treat AW2 as “AW1 plus more files,” you will lose time. The script layer is clearly reusable; the sprite/container layer is not.
