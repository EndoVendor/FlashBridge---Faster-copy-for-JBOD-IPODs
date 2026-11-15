# FlashBridge v1.0.0 — Compatibility / Kompatibilita

**EXPERIMENTAL FUNCTIONAL PROTOTYPE; AS IS WITHOUT WARRANTY / EXPERIMENTÁLNÍ FUNKČNÍ PROTOTYP BEZ ZÁRUKY.**

## One reference test — owner report, 2026-11-15

| Component | Reported observation | Limitation |
| --- | --- | --- |
| iPod | One flash-modified iPod Video 5.5G using Rockbox | Not independent cross-generation validation |
| Adapter | Existing **two-card linear FAT32 JBOD**; exact adapter model unrecorded | No proof for other adapters, including iFlash Dual/Quad |
| Cards | Windows reported ~512.7 GB + ~1,025.4 GB devices | Exact card brands/models unknown |
| EXE | Owner ran Windows x64 v0.3.3-rc2 EXE elevated; existing two-card JBOD mounted and real FAST transfers ran | v1.0.0 has the SAME physical I/O engine but new binary must be tested separately |
| After transfer | Cards returned to iPod; Rockbox recognized storage and files appeared accessible | NOT full-file checksum verification |
| Throughput | Long test generally 27–30 MiB/s with faster bursts | Hardware-dependent, not guaranteed |

## Unknown/untested

Other iPod generations, adapter brands/models, different card sizes/brands, reader controllers, ImDisk installer on clean Windows, assembled-iPod inspector, blocked-unmount recovery, file-by-file checksum integrity, power-loss resilience, Shift+Delete and free-space reclamation. No arbitrary JBOD/exFAT/RAID0/3+ cards, formatting, firmware installation or filesystem repair.

## Community test protocol

1. Use disposable test files and independent media backups. Two separate USB readers, Windows 10/11 x64, ImDisk installed separately. Cancel all Windows initialize/format offers.
2. Record iPod model, exact flash adapter model, card A/B capacities and manufacturers, USB readers, Windows and ImDisk versions.
3. Start with read-only discovery/mount; verify unambiguous card order. Never force an ambiguous result.
4. If testing RW, copy ONLY disposable files. Ideally compare file hashes independently after safe unmount and reassembly.
5. Close file managers, successfully unmount ImDisk normally, then safely eject both readers; NEVER unplug while virtual drive is mounted.
6. Reinsert cards, test Rockbox boot and file access, and submit a [compatibility report](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues/new/choose): PASS / FAIL / INCONCLUSIVE separately for each step, with redacted logs only.

**Known issue:** Shift+Delete/space reclamation unreliable. FAST doesn't read back every write. VERIFIED does not guarantee survival after power loss. Never publish private paths, unique device IDs or copyrighted music files.
