## AW2 BlueStacks HKLM Bootstrap Fix

Current AW2 runtime reopening is blocked before `BstkSVC`/wrapper handoff because
`HD-Player.exe` resolves its bootstrap roots from `HKLM\SOFTWARE\BlueStacks_nxt`,
not from the existing `HKCU` mirror.

Dynamic evidence:

- `utlDataDir` crash remains at `HD-Player.exe+0x4fa32c`
- `installDir` and `commonAppData` patches survive
- `dataDir` is re-zeroed before the crash
- the state guard at `base + 0x1A02568` is also reset by runtime bootstrap
- `reg query HKLM\SOFTWARE\BlueStacks_nxt /s` currently returns no key

Required fix:

- create a machine-level `HKLM:\SOFTWARE\BlueStacks_nxt` mirror
- populate at least:
  - `InstallDir`
  - `ClientInstallDir`
  - `UserDefinedDir`
  - `DataDir`
  - `LogDir`

Prepared script:

- [register_aw2_bluestacks_hklm.ps1](/C:/vs/other/arelwars/tools/arel_wars2/register_aw2_bluestacks_hklm.ps1)

Run from elevated PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File C:\vs\other\arelwars\tools\arel_wars2\register_aw2_bluestacks_hklm.ps1
```

After this, the next validation steps are:

1. rerun [debug_aw2_hdplayer_boot.py](/C:/vs/other/arelwars/tools/arel_wars2/debug_aw2_hdplayer_boot.py)
2. confirm the `dataDir` global no longer collapses to zero
3. retry `HD-Player.exe --instance Nougat32 --hidden`
4. check whether `C:\bstk\bstk-wrapper.log` appears and whether `adb` sees a live guest
