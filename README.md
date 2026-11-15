# FlashBridge

**Evidence-based two-media FAT32 JBOD detection, mounting and copy monitoring for Windows.**  
**English (primary)** | [Čeština](README.cs.md)

> **Status: PARTIALLY TESTED · v0.2.1-alpha · experimental source preview.** Read-only discovery has been tested on real two-card media in the development scenario; the new public release is tested on synthetic media and has **not** undergone an independent Windows/ImDisk/USB hardware qualification. Raw write access can corrupt a filesystem. Do not treat a successful boot-sector check as a health certification.

FlashBridge provides a Tk desktop GUI for joining two physical flash media into a **concatenated** virtual disk without writing an image file. It detects media order from on-media evidence rather than card brand, capacity or Windows disk number. It then exposes the existing FAT32 filesystem through the separate [ImDisk Virtual Disk Driver](https://www.ltr-data.se/opencode.html/#ImDisk) using a localhost TCP proxy.

The project was developed to address very slow transfers through an iPod's USB interface. Using two independent USB card readers can bypass that interface, **but performance is hardware-dependent and no universal speedup is claimed**.

## Supported / not supported

| Capability | Status |
|---|---|
| Windows 10/11, Python 3.10+, Tkinter GUI | Supported target; Windows integration still needs hardware qualification |
| Two USB/SD flash media, variable brands and capacities | Supported when detected unambiguously |
| Sequential/concatenated FAT32 spanning the two media | Supported design |
| Automatic ordering based on MBR, FAT32 BPB, backup and FSInfo | Implemented; fails closed if ambiguous |
| Read-only mounting via ImDisk | Implemented |
| Read-write mounting, flushed readback, structured fault logs | **Experimental** |
| Copy *missing* Music/Audiobooks files with optional SHA-256 checks | Implemented; does not replace existing files |
| Arbitrary JBOD / RAID 0 striping / 3+ cards / exFAT / NAS | **Not supported** |
| Flash health/bit-error certification or automatic FAT repair | **Not supported** |

*Flash-agnostic* here means independent of card vendor, nominal size, and physical disk number; it does **not** mean that every unknown multi-disk layout can be reconstructed automatically.

## Known issue: deletion on RW-mounted FAT32

**Unresolved, observed on development media:** some deletes appeared not to remove
files, or left zero-length directory entries. This is **not confirmed fixed**.
Windows may have been interrupted while updating FAT/directory entries during an
earlier failed proxy session; other causes remain possible. FlashBridge has no
independent FAT consistency checker and no transaction recovery. **Do not use RW
mode for irreplaceable data or depend on deletion/space reclamation.** If this
symptom occurs, stop writes, unmount normally, save diagnostic logs and inspect
filesystem consistency with suitable read-only tooling before any repair.

## Performance / v0.2.1 profile

Every accepted write still receives a physical flush and full post-flush
SHA-256 readback before successful acknowledgement. To avoid an unnecessary
flush, this version preserves only the two misaligned 4KiB edge sectors instead of pre-reading an entire megabyte when the FAT32 volume is shifted by 2KiB. It also syncs **only the physical card touched** by a write, or
both when the request crosses the card boundary. `IO_END` JSONL records now
include `receive_ms`, `physical_write_ms`, `flush_ms`, `readback_ms` and
`flushed_media` so bottlenecks can be quantified. This does not make the two
SD cards parallel: concatenated JBOD normally writes to one card at a time.
No throughput improvement is claimed until Windows hardware benchmarks exist.

## Install and launch

1. Download and extract the source release to a folder (for example `C:\FlashBridge`). Do **not** run it from inside the ZIP.
2. Install Python 3.10+ including Tkinter and the official ImDisk driver/CLI. **ImDisk is not bundled or re-licensed here.**
3. Double-click `START_FlashBridge.cmd` to request UAC elevation. Alternatively open an elevated PowerShell and run `python flashbridge_gui.pyw`.
4. Select **English** (default) or **Čeština** at the top right.
5. Let the app scan and identify one *unique* pair. Verify its evidence and order. If automatic detection is ambiguous, select exactly two devices and verify them explicitly.
6. Choose an unused drive letter. Start with **Mount RO** when you do not need to write. **Mount RW (experimental)** requires a confirmation phrase and explicit permission to write to *both* physical media.
7. Optionally select a source folder containing `Music` and `Audiobooks`, click **Find missing files**, review free space and the summary, then click **Copy missing only**. Already-existing file paths are never replaced.
8. Close all file handles and choose **Safe unmount**. Wait until the device is removed from ImDisk. Eject the USB readers in Windows before disconnecting.

### Safety defaults

- **No formatting, partition-table changes, CHKDSK, automatic repair, mirroring, deletion, or test writes** are performed by discovery.
- Disk identity, sizes and FAT32 geometry are rechecked immediately before mount; protected boot/system disks are excluded.
- RW is refused if identification is ambiguous or basic FAT headers disagree. This is **not** a full FAT32 consistency audit.
- Physical writes use 4 KiB-aligned read-modify-write on partial boundaries and handle large proxy requests incrementally. On a write fault, subsequent writes are blocked and an error response is returned to ImDisk.
- `FlushFileBuffers` and post-flush readback are requested, but USB/flash firmware may still cache data. A successful write acknowledgement does **not** guarantee that all data will survive unexpected power loss.
- Copying to a partially corrupted filesystem cannot be made fully safe by application-level checks. Consider the state of your files before enabling RW.
- Existing files are skipped **by path**; a truncated or corrupted file that already exists will not be repaired. Files larger than the FAT32 4 GiB limit are skipped.

### Logs and diagnostics

Logs live in `%LOCALAPPDATA%\FlashBridge\logs\` (a plain-text `.log` and a structured `.jsonl`, rotated to limit size). They record the session, devices, offset/length, write verification and errors. They can contain device names **and full music/file paths**. Review and redact paths before opening public GitHub issues; never upload raw device images or private music files as diagnostics.

### Development / validation

```powershell
python -m unittest discover -s tests -v
python -m py_compile flashbridge_core.py flashbridge_gui.py flashbridge_gui.pyw flashbridge_i18n.py
```

CI runs these tests on Windows and Linux using synthetic sparse-file media. It does not access actual drives or claim measured hardware performance. See [architecture](docs/ARCHITECTURE.md), [security model](SECURITY.md) and [contributing](CONTRIBUTING.md).

## Release and licensing

**Release classification: Partially tested.** 21 synthetic unit tests passed locally; read-only two-card discovery was exercised in a development scenario. The public codebase has not passed independent Windows/ImDisk/USB integration testing, and physical RW operation remains experimental. No general performance or data-safety guarantees are made.


Source code is available under the [MIT License](LICENSE). ImDisk and Windows are external prerequisites with their own terms. This release is a **GitHub-ready source tree**, not a signed `.exe` or hardware-certified production release. Feedback and test reports are welcome; do not benchmark against real data without understanding the raw-write risk.

### Inspect write performance (read-only)

Once a session has ended, you can examine the write breakdown without touching
any SD card:

```powershell
python tools/profile_report.py "$env:LOCALAPPDATA\FlashBridge\logs\YOUR_SESSION.jsonl"
```

A request's total time includes write, flush, readback, and TCP overhead.
A high `flush_ms` ratio suggests controller/firmware flush latency; a high
`readback_ms` ratio highlights the extra verification pass. Both cards can be
attached by separate USB readers, but the **concatenated filesystem does not
normally write to both in parallel**. The new optimization avoids only an
unnecessary flush; no unsafe background acknowledgements are introduced.
