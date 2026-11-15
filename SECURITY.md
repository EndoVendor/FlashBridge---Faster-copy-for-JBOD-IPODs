# Security and data integrity

[Česky](SECURITY.cs.md)

**KNOWN LIMITATION — Shift+Delete (owner test, 15 Nov 2026):** After permanent deletion during development RW sessions, a small number of files appeared as zero-byte or undeletable entries and FAT32 allocation errors were detected. On the assembled iPod, Windows `chkdsk D: /f` repaired the detected filesystem errors; a second `chkdsk D:` reported **no problems**. The entries then showed usable file sizes and could be deleted; ordinary **Delete (without Shift)** worked in this case. This was **recoverable in the reference test**, not widespread library loss. The precise cause is **not proven** (an earlier USB/proxy `WinError 55` also occurred), and ordinary Delete has not been certified safe across hardware. **Avoid Shift+Delete; use ordinary Delete if needed, keep backups, and safely unmount.** Experimental RW is at your own risk. [Technical issue #1](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues/1).

**v1.0.0 functional prototype demonstrated by one owner on one modified iPod, provided AS IS without warranty, with raw-disk write access.** A software bug, driver issue, disconnect, or power failure can irreversibly corrupt data. RO detection does not establish the health of every file, cluster chain, or FAT entry. Read this before enabling experimental RW.

The application has no online telemetry, no account access and no remote listener. However, its ImDisk localhost proxy protocol is **unauthenticated**, and an untrusted process on the same machine could potentially connect to the short-lived port. Run only on a trusted PC. Elevation to administrator is required to open physical devices.

## Defensive behavior

- Fail closed when media order is not unique.
- Exclude detected boot/system/offline disks; recheck disk numbers, size, physical fingerprints and filesystem parameters before RW.
- No formatting, CHKDSK, mirroring, automatic FAT repair, test writes or forced unmount.
- Both RW policies acknowledge only after a successful flush. VERIFIED also requires complete SHA-256 post-flush readback; FAST skips it. Both latch I/O faults and block subsequent writes.
- Incomplete ImDisk removal prevents normal GUI exit. Do not kill the server while a mount is present.
- Existing destination paths are not overwritten. The program does not repair truncated final-name files from other tools.

## Limitations

- No transactional/journaled FAT updates. Windows may perform several logically related writes; a fault after only some of them can corrupt filesystem metadata.
- Windows and flash-device caches can acknowledge writes without guaranteeing power-loss durability.
- This is sequential two-media FAT32 only. Do not try RAID0, unknown card layouts or 3+ cards.
- The physical card readers and USB stack have not been hardware-qualified for public release.
- Logs include device metadata and, during built-in copy, local file paths. Redact before sharing.

## Reporting issues responsibly

Open a GitHub issue with OS version, Python version, ImDisk version, card-reader model (optional), and **redacted** human-readable/event logs. Do not post raw disk images, card hashes, exact personal folder names, or copyrighted music files. For security-sensitive findings, contact the repository maintainer privately using GitHub's private vulnerability-reporting feature once enabled. No private contact address is supplied by this source release.

## Known unresolved deletion issue

**Observed in the owner's reference case:** Following Shift+Delete during experimental RW, a few directory entries appeared zero-length or undeletable. Windows CHKDSK detected FAT32 allocation errors, repaired them via `chkdsk /f` on the assembled iPod, and a subsequent check was clean; normal Delete worked in that case. No catastrophic library failure was observed, but individual FLAC content was not independently hash-verified. **Avoid Shift+Delete.** Do not infer that ordinary Delete is guaranteed safe on other hardware or that the causation is established; keep backups and report repeatable failures.


**v0.3.0:** Fast mode skips immediate per-block readback; a successful flush remains mandatory. This increases speed but does not repair FAT32 deletion/zero-byte problems or guarantee power-loss durability. Logs sample successful writes but record all errors.
