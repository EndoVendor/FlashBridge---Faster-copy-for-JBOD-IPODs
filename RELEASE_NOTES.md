# FlashBridge v0.3.3-rc1 — PARTIALLY TESTED / ČÁSTEČNĚ TESTOVÁNO

**Release candidate, not a stable or hardware-certified release.**

- Removed the optional Music/Audiobooks missing-only copy wizard **from the GUI**. Copy ordinary files using Windows File Explorer / Total Commander instead. Internal compatibility code remains for tests.
- Added a bilingual, five-tab **Help & safety / Nápověda a bezpečnost** information toolbox covering requirements, workflow, safe unmount, safety and diagnostic logs.
- Revised normal ImDisk unmount failure handling: when a virtual unit remains and `imdisk -d` refuses, preserve proxy/media, log `UNMOUNT_BUSY`, show actionable guidance to close all Explorer / Commander windows (including those on other drives), and offer **Retry**. No automatic process termination, no forced removal.
- Added a Windows **PyInstaller single-EXE build workflow** (console-free, UAC admin manifest, custom icon) and clarified prerequisites and release gates. ImDisk driver must still be installed separately; output unsigned.
- Rewrote English and Czech README for users, including known risks, first-run guide and physical-medium removal precautions.
- **No changes to the physical write path** from v0.3.2-alpha (sector-aware writes, Fast/Verified, synchronous flush, fail-closed faults).

Validation: synthetic tests and source compilation on Linux; native Windows GUI/ImDisk behavior and EXE build **not yet independently verified**. Do not package this candidate as stable until Windows build and disposable-media acceptance tests succeed.
