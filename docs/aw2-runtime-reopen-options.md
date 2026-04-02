# AW2 Runtime Reopen Options

Audit date: 2026-04-03

## Current Situation

The official Android Emulator path is exhausted on this host:

- existing `x86_64` AVD rejects the APK with `INSTALL_FAILED_NO_MATCHING_ABIS`
- current emulator build cannot boot `ARMv7`
- current emulator build cannot boot `ARM64`

## Most Viable Reopen Path

The strongest remaining option is `BlueStacks 5`.

Official BlueStacks support says:

- BlueStacks 5 supports both `x86` and `ARM` ABIs and lets you choose the ABI when creating a new instance
- for newer instance types it also exposes custom `ARM 32 bit` and `ARM 64 bit` selection
- app compatibility issues can be resolved by creating an instance with ABI set to `ARM` or `ARM 32-bit`

Sources:

- [What is Application Binary Interface (ABI) in BlueStacks 5](https://support.bluestacks.com/hc/en-us/articles/360058929011-What-is-Application-Binary-Interface-ABI-in-BlueStacks-5)
- [How to resolve app-related issues using ABI setting on BlueStacks 5](https://support.bluestacks.com/hc/en-us/articles/4405943338381-How-to-resolve-app-related-issues-using-ABI-setting-on-BlueStacks-5)
- [BlueStacks 5.0 Release Notes](https://support.bluestacks.com/hc/en-us/articles/360056521752-BlueStacks-5-0-Release-Notes)

## Recommended BlueStacks Shape

For AW2, the best first attempt is:

1. install `BlueStacks 5`
2. open `Multi-instance Manager`
3. create a fresh instance
4. choose a runtime that allows ABI customization
5. set ABI to `ARM 32-bit` first
6. if that fails, retry with `ARM`
7. install [arel_wars_2.apk](/C:/vs/other/arelwars/arel_wars2/arel_wars_2.apk)
8. if install succeeds, resume `Phase 1` immediately

## Why BlueStacks Beats WSA Here

`WSA` is not the preferred route anymore:

- Microsoft deprecated Windows Subsystem for Android distribution/support
- the current machine does not already have a working WSA install

So BlueStacks is the more practical runtime-reopen target.

## Local Probe

Local readiness snapshot can be regenerated with:

```powershell
python tools/arel_wars2/probe_aw2_runtime_reopen_options.py
```
