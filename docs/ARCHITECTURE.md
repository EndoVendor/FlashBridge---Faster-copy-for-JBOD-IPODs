# Architecture (English)

[Česky](ARCHITECTURE.cs.md)

## System boundary

```text
 Windows GUI (Tkinter, EN / CS)
   | Windows Get-Disk + read-only raw probes
   v
 Evidence-based discovery -> immutable Plan(first, second, FAT32 geometry)
   | Revalidate physical devices, hashes and FAT32 before mount
   v
 ImDisk CLI <-> ImDisk Windows driver
                  | localhost TCP, ephemeral port, ImDisk protocol
                  v
             ProxyServer (read / experimental write)
                  |
             JoinedDisk (concatenate media A + B)
                  | immutable physical capacity boundary
             RawDevice A / RawDevice B
```

This is **linear concatenation**: logical byte offsets `[0, size(A))` map to media A; offsets `[size(A), size(A)+size(B))` map to media B. It is not RAID 0 striping. The visible virtual disk starts at the FAT32 partition offset of the joined byte stream, not at its concatenated MBR.

## Discovery evidence

- Eligible devices are Windows USB/SD/MMC media excluding system/boot, offline, zero-size and PhysicalDrive0. A genuine USB SSD could still appear eligible, but a candidate pair must match the volume geometry.
- For each candidate, inspect MBR partition starts at sector sizes 512/1024/2048/4096 and validate FAT32 BPB and backup geometry.
- Candidate first-media FAT32 volume must extend beyond the first physical device and end close to the combined capacity, with backup and FSInfo evidence; if multiple candidates survive, **fail closed**.
- The first 4 KiB of both physical media are fingerprinted during discovery and rechecked before serving.
- `Plan.read_write_safe` is a narrow structural gate based on first FAT-page equality and does **not** mean the filesystem is healthy; the GUI calls RW *experimental*.

## Proxy protocol

ImDisk sends `INFO`, `READ`, `WRITE`, and `CLOSE` messages as little-endian 64-bit fields. The `INFO` response advertises **512-byte minimum transfer alignment**, distinct from the **FAT32 logical sector size** passed to `imdisk -S`. Some ImDisk versions reject greater proxy I/O alignment.

The daemon binds to **127.0.0.1** on a randomly assigned port for each mount. The protocol has **no built-in authentication**; any sufficiently privileged local process that reaches the port could attempt I/O. Use on a trusted machine only, and do not forward the TCP listener.

`WRITE` requests are received in chunks and mapped to one or both physical media. Physical writes use per-device alignment obtained from a coherent `Get-Disk` logical/physical sector report: confirmed 512/512 uses 512-byte direct writes; unknown/inconsistent reports retain 4-KiB edge-preserving RMW, and larger known physical sectors are honored. The alignment is fixed for the mount and unaligned edges use read-modify-write while holding one internal lock. After the request, the daemon requests `FlushFileBuffers`; in VERIFIED mode it additionally reads back the full request and compares SHA-256. In FAST mode it deliberately skips block readback. Upon a write failure, the proxy replies with an error and blocks further writes without intentionally severing an active ImDisk connection. Read and close requests can still be serviced to assist cleanup.

This mechanism **does not** provide atomicity or journaling across FAT tables, clusters or the two physical cards. A crash or disconnect can leave the filesystem inconsistent.

## UI lifecycle

`DISCOVER -> VERIFY -> LISTEN -> MOUNT -> TRANSFER -> UNMOUNT -> CLOSE`

- Refresh is disabled while a mount or proxy is active.
- Mount requires a free Windows drive letter, no preexisting ImDisk unit, and revalidated physical devices.
- Unmount is normal ImDisk `-d`; no forced removal is attempted.
- The GUI retains the proxy and raw handles when unmount is incomplete.
- Unexpected driver disconnection may still require operating-system recovery.

## Copy semantics

The legacy non-GUI library copy helper (not exposed in v1.0.0) scans only `Music` and `Audiobooks`. It plans missing target paths, skips existing paths regardless of their contents, and skips files above FAT32's maximum file size. New files are written to `*.flashbridge.partial`, optionally verified by SHA-256, and then renamed. Existing partials are resumed only after comparing their prefix with source. This does not repair files left with their *final* names by other copy tools.

## Diagnostic evidence

Each run creates a human-readable log and bounded rotated `.jsonl` event stream under `%LOCALAPPDATA%\FlashBridge\logs`. Logs include device name, offsets, requests and full paths for copy operations. Review before public disclosure.

## Test strategy

Unit and synthetic integration tests cover ordering, ambiguity, FAT32 geometry, read-only rejection, cross-media writes, ImDisk TCP message sizes >64 MiB, injected physical failures, resume logic, and localization. Windows CI is a **synthetic software test**, not an end-to-end physical device qualification or a measured speed benchmark.


**v0.3.0:** Fast mode skips immediate per-block readback; a successful flush remains mandatory. This increases speed but does not repair FAT32 deletion/zero-byte problems or guarantee power-loss durability. Logs sample successful writes but record all errors.

**v0.3.2:** `IO_STATS` logs both cumulative active-only speed and per-interval
wall-clock speed, together with the last-10s wall-clock rate used in the GUI.
Separate timings for proxy READ work, idle protocol waits, RMW edge reads,
and physical-device writes help isolate Windows/ImDisk stalls from slow media.
No timeout-recovery write retries, buffering of unconfirmed writes, or
sector-size probing writes are performed.

### v0.3.3-rc1: interface and release packaging

The public GUI has no Music/Audiobooks copy wizard. The optional library helper is retained only for test/backwards compatibility; direct filesystem operations are performed by external user file managers. Normal unmount still calls `imdisk -d -m LETTER:`. On a refused removal, GUI checks the original ImDisk unit identity, logs `UNMOUNT_BUSY`, preserves server/raw handles, and offers a user-controlled retry after closing Explorer/Commander windows. It does not call ImDisk `-D`/`-R` or kill processes. Windows EXE packaging uses the workflow `windows-exe.yml` and requires ImDisk to be installed on the target machine. The physical proxy data path was not modified.


### v0.3.3-rc2 — read-only inspection and dependency setup

The iPod inspector (flashbridge_inspector.py) is isolated from the mounted proxy. It opens each selected PhysicalDrive in read-only mode and produces small-sample SHA-256 fingerprints plus disk size, reported sector geometry, parsed MBR entries and bounded FAT32 candidates. The three-leg workflow is card A snapshot → card B snapshot → live assembled-iPod snapshot and comparison. It tests both **linear** card orders; a candidate result never grants write access or establishes adapter identity, bootability, or full integrity. Non-linear mappings remain unsupported.

The opt-in ImDisk setup module (flashbridge_imdisk_setup.py) downloads only from the official LTR Data HTTPS host to an empty temporary directory, requires a valid Windows Authenticode signature with expected publisher text and launches the installer only on explicit user action. No kernel driver is embedded in the PyInstaller EXE.

For user-facing procedures and exact GUI control labels see [English guide](USER_GUIDE.md) and [český návod](USER_GUIDE.cs.md).
