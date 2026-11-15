# Changelog

## v1.0.0 — First working owner-demonstrated prototype (2026-11-15)

- Owner confirms real Windows EXE transfers on a two-microSD FAT32 JBOD and Rockbox recognition after returning cards to a modified iPod.
- Classified as an experimental community-test functional prototype, AS IS, without warranty, not hardware-qualified across adapters or generations.
- Documentation, compatibility reporting and unsigned Windows packaging updated. The physical I/O path is unchanged. Owner later observed recoverable FAT32 metadata errors associated with Shift+Delete; normal Delete worked in the observed case and CHKDSK /f repaired the reported errors, but cause remains unresolved.


## v0.3.3-rc2 — Read-only iPod reference inspection + opt-in ImDisk installer

- New per-device read-only snapshots and live assembled-iPod continuity comparison (both possible card orders). Reports are metadata and SHA-256 samples only. No formatter or firmware provisioning.
- Explicit ImDisk installer assistant with vendor-host and Authenticode validation, official-page fallback.
- Existing engine, RW gate and safe unmount semantics unchanged.


## v0.3.3-rc1 — Usability and Windows packaging (partially tested)

- Bilingual Help/Safety toolbox and focused main GUI; optional Music/Audiobooks copy wizard removed from the GUI.
- Safe ImDisk unmount retry with busy-volume guidance, no forced removal.
- Windows GUI executable packaging in GitHub Actions; EXE unsigned, ImDisk external prerequisite.
- Documentation refreshed EN/CS; physical I/O engine unchanged from v0.3.2.


## v0.3.2-alpha — Sector-aware direct I/O and wall-clock diagnostics (partially tested)
- Use Windows reported physical/logical sector sizes per device, re-read at mount.
  Confirmed 512/512 uses **512B-aligned direct writes without 4KiB RMW**.
  Unknown/inconsistent reports retain prior 4KiB fallback; larger coherent
  physical sectors are respected.
- Preserve per-request synchronous flush, no speculative write caching or
  automatic retry after partial/unknown I/O; error handling stays fail-closed.
- Separate real 10s GUI throughput from cumulative active-write speed;
  instrument proxy read time, protocol waiting, RMW edge read time and actual
  physical device write time in `IO_STATS` and the offline report tool.
- Added synthetic 512-sector, mixed geometry and slowdown-metrics regression
  tests. **No real SD/USB hardware validation of 512B writes yet.**
- Known permanent-delete/zero-byte and USB I/O disappearance issues unresolved.


## v0.3.1-alpha — Fused aligned writes, partially tested
- Replaced the old three-write 4KiB RMW path for misaligned 1MiB requests
  with a **single merged 4KiB-aligned physical write**, preserving bytes in
  both boundary blocks by pre-reading at most two 4KiB edges.
- No unaligned physical writes, no write-behind, no dirty cache, no reduced
  flush requirements, no implicit recovery/repair or target file deletion.
- Added per-request sampled and cumulative counters for physical write
  calls/bytes and RMW edge read calls/bytes.
- Kept Fast / Verified policy, fail-closed fault handling, media-order checks,
  read-only operations and source file preservation unchanged.
- Added deterministic random adjacent-write, one-block, already-aligned,
  >1MiB and across-the-two-media synthetic regression coverage.
- No new physical-card testing. Actual speedup is **unknown** until measured.
- Permanent deletion (Shift+Delete), zero-byte entries and device WinError 55
  remain unresolved. Synthetic green tests do not qualify media integrity.


## v0.3.0-alpha — Fast write policy, partially tested
- Added selectable Fast (write+flush) / Verified (write+flush+SHA256 readback) policy, fixed per mount.
- Removed redundant SHA calculation and synchronous readback in Fast.
- Retained per-request physical flush, fault latch, device checks and edge-preserving writes.
- Sampled normal Fast logs and added cumulative IO_STATS; monitor uses rolling 10s confirmed write throughput.
- Explicit EN/CS warnings about unresolved permanent-deletion behavior; synchronized GUI/core version.
- 33 synthetic tests including Fast physical fault injection. Windows CI required.


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
