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

`WRITE` requests are received in chunks and mapped to one or both physical media. Physical writes are 4 KiB-aligned; unaligned edges use read-modify-write while holding one internal lock. After the request, the daemon requests `FlushFileBuffers`, reads back and compares SHA-256. Upon a write failure, the proxy replies with an error and blocks further writes without intentionally severing an active ImDisk connection. Read and close requests can still be serviced to assist cleanup.

This mechanism **does not** provide atomicity or journaling across FAT tables, clusters or the two physical cards. A crash or disconnect can leave the filesystem inconsistent.

## UI lifecycle

`DISCOVER -> VERIFY -> LISTEN -> MOUNT -> TRANSFER -> UNMOUNT -> CLOSE`

- Refresh is disabled while a mount or proxy is active.
- Mount requires a free Windows drive letter, no preexisting ImDisk unit, and revalidated physical devices.
- Unmount is normal ImDisk `-d`; no forced removal is attempted.
- The GUI retains the proxy and raw handles when unmount is incomplete.
- Unexpected driver disconnection may still require operating-system recovery.

## Copy semantics

The built-in copy feature scans only `Music` and `Audiobooks`. It plans missing target paths, skips existing paths regardless of their contents, and skips files above FAT32's maximum file size. New files are written to `*.flashbridge.partial`, optionally verified by SHA-256, and then renamed. Existing partials are resumed only after comparing their prefix with source. This does not repair files left with their *final* names by other copy tools.

## Diagnostic evidence

Each run creates a human-readable log and bounded rotated `.jsonl` event stream under `%LOCALAPPDATA%\FlashBridge\logs`. Logs include device name, offsets, requests and full paths for copy operations. Review before public disclosure.

## Test strategy

Unit and synthetic integration tests cover ordering, ambiguity, FAT32 geometry, read-only rejection, cross-media writes, ImDisk TCP message sizes >64 MiB, injected physical failures, resume logic, and localization. Windows CI is a **synthetic software test**, not an end-to-end physical device qualification or a measured speed benchmark.
