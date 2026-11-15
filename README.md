# FlashBridge — v0.3.3-rc2

**Two-card FAT32 JBOD manager for Windows** · [Česky](README.cs.md) · [Release notes](RELEASE_NOTES.md)

**Release classification: PARTIALLY TESTED RELEASE CANDIDATE.** FlashBridge is not a filesystem repair tool and its experimental raw-write mode has not undergone independent hardware qualification. **Do not use the only copy of important data.** The release candidate includes untested changes to the GUI and the unmount error handling; its physical read/write engine is unchanged from v0.3.2-alpha.

## What it is

FlashBridge temporarily presents an **existing concatenated FAT32 volume** spread across **two physical cards** as one Windows drive. It does not create or format a new JBOD, install an iPod firmware, stripe writes as RAID0, or modify partition tables. Its purpose is to bypass the slow USB interface on some flash-modified iPods by accessing the two cards via USB readers.

For the already supported JBOD arrangement it finds the card order from real MBR/FAT32 structures, including backup boot sector, FSInfo and FAT header evidence. It rejects ambiguous or unsafe arrangements instead of guessing disk numbers or capacities. Device identity and FAT32 geometry are re-checked before mounting.

## What you need

- Windows 10/11 x64, administrator privileges, **two physically separate USB card readers**, and the original cards forming one supported FAT32 JBOD.
- **ImDisk Virtual Disk Driver**, installable on request with the in-app assistant or separately. FlashBridge calls its `imdisk.exe` utility and requires it to be available on PATH. [ImDisk official project](https://www.ltr-data.se/opencode.html/#ImDisk). The FlashBridge EXE **does not** contain the driver or an installer for it.
- A reliable backup before using experimental RW mode. FAT32 has no journal.
- For the packaged edition: `FlashBridge.exe` (no Python, CMD or PowerShell needed for normal launch). Windows prompts for administrator approval on startup. The executable is **unsigned**; Windows SmartScreen may show a publisher warning.

## First use (recommended)

1. Connect the two original JBOD cards using separate readers; do not format either card when Windows prompts.
2. Install ImDisk using the in-app **Install ImDisk** assistant or the official publisher installer, then launch **`FlashBridge.exe`** and approve Windows UAC.
3. Click **Auto-detect JBOD**. Review **FIRST**, **SECOND**, FAT32 geometry, and the evidence text. If ambiguous, do not guess or force mounting.
4. Choose a free virtual drive letter (usually `R:`). Start with **Mount RO** to inspect files without writing.
5. If you explicitly need to modify data, ensure you have backups, select **FAST** or **VERIFIED**, choose **Mount RW**, and type the confirmation phrase. Use Windows Explorer, Total Commander, or another normal file manager to copy files. **There is no built-in Music/Audiobooks copy wizard.**
6. Finish transfers and close **all** Explorer and Total Commander windows, even those displaying a different drive such as `C:`. Close file dialogs, terminals or players that might enumerate volumes.
7. Click **Safe unmount**. If it fails, leave cards and FlashBridge connected, close remaining file-manager windows, then click **Retry**. Wait until the virtual ImDisk device has actually disappeared.
8. Only after successful virtual unmount, eject both physical readers using Windows safe removal, then return the cards to the iPod.

## Safe unmount: important Windows/ImDisk limitation

Normal removal uses `imdisk.exe -d -m R:` (substituting the chosen letter). It may fail if **any** Windows Explorer or Total Commander window is open, **even when that window displays C: rather than R:**. That was observed during development; it is **not proven** that every such window always holds an R: handle.

The application now explains this issue, preserves the proxy and device handles on refusal, logs `UNMOUNT_BUSY`, and offers explicit **Retry**. It **never** kills Explorer, restarts the shell or invokes force removal (`-D` / `-R`). These commands are not a safe remedy for a FAT32 filesystem with pending writes. If normal unmount remains blocked, preserve logs and identify the process holding the volume before proceeding. **Never unplug the physical cards while ImDisk still reports the virtual disk.**

## Modes and their limits

| Mode | What it does | Protection / cost |
|---|---|---|
| RO | Read-only ImDisk mount | Good for inspection, does not imply the filesystem is healthy |
| RW FAST | Writes to physical media and calls `FlushFileBuffers` before acknowledging each write request | Faster; does not verify written content; firmware may cache data |
| RW VERIFIED | Same write + flush, then SHA-256 comparison to re-read blocks | Slower, not a guarantee of survival after sudden power loss |

**Known unresolved issue:** Shift+Delete/permanent deletion has left zero-length files or not reclaimed free space in development sessions; previously `WinError 55` also occurred. Do not rely on deletion/reclamation in RW. Automatic repair, CHKDSK, formatting, forced removal, speculative retries and write-behind caching are deliberately absent.

## In-app information and logs

The **Help & safety** button opens six topics: Overview, How to use, Safe unmount, Safety, Diagnostics and iPod inspector, available in English and Czech. It explains what FlashBridge can and cannot do, the mounting sequence, and failure recovery.

Session logs: `%LOCALAPPDATA%\FlashBridge\logs\` (`.log` and `.jsonl`). The GUI has an **Open log folder** button. The `IO_STATS` event contains cumulative confirmed bytes and separates elapsed, active, device-write, read and wait times. FAST samples individual `IO_END` events; do not sum samples as if they were all writes.

The actual two-reader test on 2026-11-15 observed ordinary 27–30 MiB/s writes with intermittent 40–50+ MiB/s bursts. Performance varies with card, reader and usage; **these are observations, not guaranteed transfer rates**. Fan experiments did not isolate a reliable thermal cause.

**Privacy:** log files can include disk names, file paths and other local information. Read and redact before public sharing.

## EXE packaging for maintainers

Source code remains available, but the end-user release artifact is a **Windows GUI executable**, not a `.cmd` launcher. GitHub Actions workflow `.github/workflows/windows-exe.yml` builds the executable on `windows-latest` using **PyInstaller**, bundles it with README, licence and release notes, and publishes an Actions artifact. The binary requests UAC elevation and has no console window. It is **not code-signed**.

A Windows maintainer can reproduce it using `python -m pip install pyinstaller==6.22.3` and `python -m PyInstaller --clean --noconfirm --onefile --windowed --uac-admin --name FlashBridge --icon assets\flashbridge.ico flashbridge_gui.pyw`. PyInstaller must run on Windows; the Linux synthetic tests cannot produce or validate a native Windows EXE. [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html).

Development checks: `python -m unittest discover -s tests -v` and `python -m py_compile flashbridge_core.py flashbridge_gui.py flashbridge_i18n.py` (tests use synthetic media, no physical disks). The legacy internal copy helper remains in source for compatibility/tests, but is **not exposed in the product UI**.

## Scope / release gates

Supported: two-card concatenated FAT32 with unambiguous identification; RO/RW ImDisk proxy; EN/CS UI; structured diagnostics. **Not supported:** arbitrary JBOD layouts, exFAT, 3+ cards, RAID striping, health certification, filesystem recovery, transactional deletion, or iPod bootloader installation.

Before presenting a public stable release, verify EXE build and first launch on real Windows 10/11; ImDisk detection; mounting and graceful unmount with/without Explorer windows; RO data reads; and RW operations on **disposable** test media with file-content verification and unplug/recovery scenarios. Passing unit tests alone is insufficient.

MIT licensed ([LICENSE](LICENSE)); ImDisk is a separately installed dependency with its own licence. See [Security](SECURITY.md), [Architecture](docs/ARCHITECTURE.md) and [Release checklist](RELEASE_CHECKLIST.md).

## Read-only storage inspector (new in rc2)

**The product does not format any SD card or provision iPod firmware.** Only one original iPod 5/5.5G and one flash adapter were investigated in the reference case; that is insufficient to derive a general iPod initialization/formatting algorithm. The Apple device may have an MBR with a dedicated firmware partition followed by a FAT32 data partition (or a different Mac layout); sector units and presentation can vary.

For a device that is already prepared by its iPod:

1. Remove card A and insert it alone in a USB reader. **Select exactly one physical disk**, click **Save selected card snapshot (RO)**, and save JSON A. Repeat for card B, creating JSON B. Never accept Windows' offer to initialize/format an unrecognized card.
2. Return both cards to their original adapter inside the iPod. Connect the iPod in its USB disk mode. Refresh disks and identify the iPod's **physical disk** by model/size.
3. Select that single disk, click **Compare selected iPod disk (RO)**, choose JSON A and B, and save the comparison report. Both linear concatenation orders are inspected.
4. Review matches, mismatches and reported sizes. Matching small SHA-256 anchors and compatible capacities are **candidate evidence**, not a complete disk image comparison. A mismatch may mean a different adapter mapping, different exposed capacity, modification between captures, or error. Inconclusive adapters are **not automatically supported**.

The inspector also records a separate read-only snapshot of the assembled iPod: its actual reported disk capacity, MBR partition entries, FAT32 boot/backup candidates and sampled hashes. It reads only tiny samples at known offsets, the partition table and FAT32 boot/backup metadata; it does not change, mount, repair or clone any card and it **never authorizes RW**. The legacy JBOD detection/mounting code remains independently evidence-gated. Exported JSON contains disk metadata and hashes; inspect before sharing.

## Optional ImDisk driver installer assistant

The **Install ImDisk** button uses HTTPS to fetch the publisher's `imdiskinst.exe` from `static.ltr-data.se` into a **new empty directory**. Windows Authenticode must report `Valid` with the expected LTR Data/Olof Lagerkvist publisher; otherwise FlashBridge does **not** execute it and offers the official vendor webpage for manual installation. The final installer still requires an explicit user action and Windows elevation. The publisher notes ImDisk is based on a legacy volume-emulation design and may have modern Windows limitations. Installer availability, signing and first-run operation must be checked on the actual target Windows system; none of these are silently assumed.

ImDisk official publisher: https://www.ltr-data.se/opencode.html#ImDisk
