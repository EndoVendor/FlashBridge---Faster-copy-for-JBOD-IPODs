# Changelog

## Diagnostic update — experimental (2026-11-15)
- Log exact physical media and original Windows error separately for WRITE, FLUSH, read-modify-write edge READ and post-flush READBACK failures.
- Add DEVICE_IO_UNAVAILABLE event for WinError 55/1167; this does not assert media removal.
- Retain fail-closed behavior after physical I/O faults. Injected faults tested only on disposable synthetic media; no real-device qualification.
- Known unresolved issues: deletion/zero-byte entries (#1) and WinError 55 device I/O failure (#2).


## v0.2.1-alpha — partially tested
- Eliminated full megabyte read/modify/write on 2KiB-misaligned volume blocks: now pre-reads only 4KiB edges and writes the aligned interior directly.
- Closed logger file handles deterministically at GUI exit; prevents Windows temp-file locking in CI.
- Eliminated flush on untouched card for each successful write request.
- Added independent phase timings and touched-media details to JSONL write logs.
- Documented unresolved deletion/zero-byte-entry symptom as a known critical issue.
- No weakening of flush/readback verification. No physical-card throughput claim.

# Changelog

## 0.2.0-alpha — Partially tested · GitHub source preview

- English-first bilingual (EN/CS) GUI and public documentation.
- Vendor/size/disk-number independent detection of supported two-card concatenated FAT32 layouts.
- Ephemeral localhost port instead of static 9009/9011.
- Structured diagnostics with bounded rotation; pre-mount device/geometry revalidation.
- Experimental RO/RW ImDisk proxy, readback verification, fault gating, and safe-unmount controls.
- Built-in missing-only copy with `.flashbridge.partial` resume and optional SHA-256 check.
- Synthetic tests and Windows/Linux CI; public limitations/security documentation.

**Not a signed Windows executable or independently hardware-qualified release.**
