# FlashBridge

**Evidence-based two-media FAT32 JBOD detection, mounting and copy monitoring for Windows.**  
**English (primary)** | [Čeština](README.cs.md)

> **Status: PARTIALLY TESTED · v0.3.1-alpha · experimental source preview.** Read-only discovery has been tested on real two-card media in the development scenario; the new public release is tested on synthetic media and has **not** undergone an independent Windows/ImDisk/USB hardware qualification. Raw write access can corrupt a filesystem. Do not treat a successful boot-sector check as a health certification.

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
| Read-write mounting (Fast or Verified), physical flush and fault logs | **Experimental** |
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

## Throughput: FAST versus VERIFIED (v0.3.1-alpha)

Choose the policy **before** mounting RW; it cannot change while mounted.

| Mode | Physical writes | FlushFileBuffers | SHA-256 post-write block readback | Default in GUI |
|---|---|---|---|---|
| **FAST** | Yes | After every accepted write request, touched media only | **No** | **Yes** |
| VERIFIED | Yes | After every accepted write request, touched media only | Yes, entire request | No |

**FAST does not verify written block contents.** It acknowledges to ImDisk only after
all request data has been accepted by the underlying Windows write calls and
`FlushFileBuffers` has returned successfully. A successful flush is not a guarantee
of power-loss durability on all flash devices or USB bridges. FAT32 has no journal,
so interrupting updates can leave inconsistent metadata in *either* mode.

FAST avoids the redundant ~28 ms/MiB readback observed on the development
reader; the measured physical-write phase was ~35–36 ms/MiB. This suggests a
**theoretical active-I/O ceiling around 27–29 MiB/s** for that reader,
not a guaranteed file-copy speed; 200 MB/s initially shown by Explorer was
likely affected by Windows caching. Speeds vary with card, reader, FAT32
metadata access and workload. Two independent readers **do not** make a
sequential JBOD into parallel striped storage.

New in v0.3.1: for a 1MiB write shifted by 2KiB relative to 4KiB physical
alignment, FlashBridge pre-reads only the two partial 4KiB edge blocks and
combines the full payload into **one aligned device WRITE**, replacing the old
three WRITE calls. The two edge pre-reads remain necessary under the existing
conservative alignment policy. This can reduce per-call USB overhead; **real
throughput improvement is not yet measured**. This is still synchronous, not
write-behind, and write acknowledgements still require a successful flush.
Flushes touch only media covered by each request, or both when crossing the
physical-media boundary. Every accepted request also records the cumulative
number of raw physical READ/WRITE calls and bytes for tuning.

FAST reduces normal per-request JSONL logging (first few writes, small metadata
writes, then samples), with periodic `IO_STATS` containing **all confirmed byte
counts** and phase totals. Every physical WRITE/FLUSH fault is logged in full,
including the medium and original error. The GUI shows **confirmed throughput
averaged over a rolling 10-second window**, not an instantaneous single-block
speed. VERIFIED retains full write and readback records.

**Known critical issue:** `Shift+Delete` / permanent deletes were reported to
leave files or zero-byte entries; normal `Delete` may simply move to Recycle Bin.
Neither write policy fixes this. See [issue #1](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues/1).

## Install and launch

1. Download and extract the source release to a folder (for example `C:\FlashBridge`). Do **not** run it from inside the ZIP.
2. Install Python 3.10+ including Tkinter and the official ImDisk driver/CLI. **ImDisk is not bundled or re-licensed here.**
3. Double-click `START_FlashBridge.cmd` to request UAC elevation. Alternatively open an elevated PowerShell and run `python flashbridge_gui.pyw`.
4. Select **English** (default) or **Čeština** at the top right.
5. Let the app scan and identify one *unique* pair. Verify its evidence and order. If automatic detection is ambiguous, select exactly two devices and verify them explicitly.
6. Choose an unused drive letter. For RW, choose **FAST** (default; flush, no per-block verification) or **VERIFIED** (flush + full SHA-256 block readback) **before Mount RW**. RW always requires explicit confirmation for both physical media. Start with **Mount RO** if you do not need to write.
7. Optionally select a source folder containing `Music` and `Audiobooks`, click **Find missing files**, review free space and the summary, then click **Copy missing only**. Already-existing file paths are never replaced.
8. Close all file handles and choose **Safe unmount**. Wait until the device is removed from ImDisk. Eject the USB readers in Windows before disconnecting.

### Safety defaults

- **No formatting, partition-table changes, CHKDSK, automatic repair, mirroring, deletion, or test writes** are performed by discovery.
- Disk identity, sizes and FAT32 geometry are rechecked immediately before mount; protected boot/system disks are excluded.
- RW is refused if identification is ambiguous or basic FAT headers disagree. This is **not** a full FAT32 consistency audit.
- Physical writes use 4 KiB-aligned read-modify-write on partial boundaries and handle large proxy requests incrementally. On a write fault, subsequent writes are blocked and an error response is returned to ImDisk.
- `FlushFileBuffers` is requested in both RW modes; **only VERIFIED** additionally performs per-write post-flush SHA-256 readback. USB/flash firmware may cache data. A successful write acknowledgement does **not** guarantee that all data survive unexpected power loss.
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

**Release classification: Partially tested.** 40 synthetic tests passed locally; read-only two-card discovery was exercised in a development scenario. The public codebase has not passed independent Windows/ImDisk/USB integration testing, and physical RW operation remains experimental. No general performance or data-safety guarantees are made.


Source code is available under the [MIT License](LICENSE). ImDisk and Windows are external prerequisites with their own terms. This release is a **GitHub-ready source tree**, not a signed `.exe` or hardware-certified production release. Feedback and test reports are welcome; do not benchmark against real data without understanding the raw-write risk.

### Inspect write performance (read-only)

Once a session has ended, you can examine the write breakdown without touching
any SD card:

```powershell
python tools/profile_report.py "$env:LOCALAPPDATA\FlashBridge\logs\YOUR_SESSION.jsonl"
```

FAST reports sampled `IO_END` records and aggregate `IO_STATS`; never treat
FAST's sampled IO_END count as the whole session's written bytes. In FAST,
`readback_ms` is zero by design. VERIFIED includes per-write readback timing.
Neither mode acknowledges writes before its required flush.
