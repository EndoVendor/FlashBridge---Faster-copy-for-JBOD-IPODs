# FlashBridge v0.3.3-rc1 — Release checklist / Přejímka

## Completed in source / Hotovo ve zdrojích
- [x] EN/CS help toolbox with first-use guide, safety, unmount troubleshooting and logs
- [x] Removed optional Music/Audiobooks copy workflow from public GUI
- [x] Safe normal unmount: no force, user retry, preserve proxy/media if busy
- [x] New bilingual READMEs and release notes; observed limitations documented
- [x] PyInstaller Windows EXE build workflow + custom application icon
- [x] Physical write engine kept unchanged from v0.3.2-alpha
- [x] Synthetic tests and compile on Linux

## Still REQUIRED before shipping an EXE to normal users
- [ ] GitHub Windows runner has built `FlashBridge.exe` successfully
- [ ] EXE hash and artifact inspected; launch and UAC confirmed on Windows 10/11
- [ ] ImDisk installed separately; no-imdisk error and normal mount behavior tested
- [ ] RO reading of existing FAT32 with correct card order tested on physical media
- [ ] Safe unmount tested with all file managers closed
- [ ] Refused unmount + Retry tested with Explorer/Total Commander on both `R:` and unrelated `C:` windows
- [ ] Proxy remains alive after any refused unmount; both raw devices stay connected
- [ ] RW file transfers and data integrity verified on DISPOSABLE cards, with rollback procedure
- [ ] Previously observed Shift+Delete/zero-length files and WinError 55 investigated; do not claim fixed
- [ ] Virus-scan/SmartScreen and unsigned-executable distribution instructions checked
- [ ] No personal paths, private logs or protected card images bundled

**Do not call v0.3.3-rc1 stable or production-safe before hardware acceptance.**
