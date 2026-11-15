# Security and data integrity

[Česky](SECURITY.cs.md)

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

On a development JBOD, some deleted files reportedly remained or became zero-byte directory entries after previous interrupted write sessions. This behaviour is **not resolved**. Do not use experimental RW mode with irreplaceable data or assume delete/space reclamation is safe.


**v0.3.0:** Fast mode skips immediate per-block readback; a successful flush remains mandatory. This increases speed but does not repair FAT32 deletion/zero-byte problems or guarantee power-loss durability. Logs sample successful writes but record all errors.
