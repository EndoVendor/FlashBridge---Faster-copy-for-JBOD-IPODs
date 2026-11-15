# FlashBridge v0.3.3-rc2 — Release checklist / Přejímka

## Completed in source / Hotovo ve zdrojích
- [x] Final rc2 commit passed 62 synthetic tests on Windows/Linux, Python 3.10 and 3.13
- [x] Step-by-step user guides EN/CS linked from both READMEs
- [x] EN/CS help toolbox with first-use guide, safety, unmount troubleshooting and logs
- [x] Removed optional Music/Audiobooks copy workflow from public GUI
- [x] Safe normal unmount: no force, user retry, preserve proxy/media if busy
- [x] New bilingual READMEs and release notes; observed limitations documented
- [x] PyInstaller Windows EXE build workflow + custom application icon
- [x] Physical write engine kept unchanged from v0.3.2-alpha
- [x] Synthetic tests and compile on Linux

## Still required for a stable / generally recommended release
- [x] GitHub Windows runner built `FlashBridge.exe` successfully on the final rc2 commit (run #43717489315)
- [x] EXE PE signature (file format, not Authenticode) and ZIP/SHA-256 inspected on CI and downloaded artifact
- [x] Windows rc2 ran elevated on a development machine; real physical-card write diagnostics were captured (not a full safety or installer acceptance test)
- [ ] ImDisk installed separately; no-imdisk error and normal mount behavior tested
- [ ] RO reading of existing FAT32 with correct card order tested on physical media
- [ ] Safe unmount tested with all file managers closed
- [ ] Refused unmount + Retry tested with Explorer/Total Commander on both `R:` and unrelated `C:` windows
- [ ] Proxy remains alive after any refused unmount; both raw devices stay connected
- [ ] RW file transfers and data integrity verified on DISPOSABLE cards, with rollback procedure
- [ ] Previously observed Shift+Delete/zero-length files and WinError 55 investigated; do not claim fixed
- [ ] Virus-scan/SmartScreen and unsigned-executable distribution instructions checked
- [ ] No personal paths, private logs or protected card images bundled

**Near-final release candidate, not stable. Supplied AS IS without warranty under MIT. Do not call v0.3.3-rc2 production-safe before hardware acceptance.**

- [ ] On actual Windows, capture card A + card B snapshots without any write; review physical disk selection and independently captured iPod partition/FAT32 metadata
- [ ] Compare assembled iPod USB disk against both snapshots; inspect both order outcomes and report
- [ ] Verify non-linear / mismatched / changed geometry stays inconclusive and no RW is granted
- [ ] Test ImDisk installer assistant with official publisher certificate and system UAC, including failure paths
- [ ] Verify installer cannot run while virtual drive is mounted
