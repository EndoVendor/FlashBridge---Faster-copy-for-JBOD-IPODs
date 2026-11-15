# FlashBridge v1.0.0 — FUNCTIONAL PROTOTYPE / FUNKČNÍ PROTOTYP

**Experimental community hardware-testing prototype, unsigned, provided AS IS without warranty under MIT. NOT a stable or certified disk utility.**

The maintainer confirms a successful real Windows EXE transfer to an existing two-card FAT32 JBOD, followed by removal/reinsertion of the cards and successful Rockbox recognition with contents apparently functional (15 Nov 2026). This is ONE owner-reported reference, not full-file hash verification or compatibility certification.

Vlastník potvrdil skutečný přenos prostřednictvím Windows EXE na existující dvoukartové FAT32 JBOD, následné vrácení karet do iPodu a jejich úspěšné rozpoznání Rockboxem s na pohled funkčními daty (15. 11. 2026). Jde o JEDEN referenční test, nikoli kontrolu hashů všech souborů ani certifikaci kompatibility.

- Compared with v0.3.3-rc2, **only version/distribution/docs metadata changed**. The physical write path and error handling have **not** been modified; no new safety or adapter coverage is implied.
- Reference setup: modified iPod Video 5.5G, two physical microSD cards in an existing supported linear FAT32 JBOD, two USB readers, Windows x64 and Rockbox. Exact adapter model unknown. Visible Rockbox files are not independently checksum-verified.
- Needs testing: other iPod and adapter models, card/reader combinations, safe-unmount refusal and retry, fresh ImDisk installation, inspector, full file-hash comparison and recoverability.
- **Known Shift+Delete limitation and practical workaround:** In the owner's reference test, permanent deletion was associated with a few zero-byte/undeletable entries and FAT32 allocation errors. Windows `chkdsk /f` on the reassembled iPod repaired the reported errors; a subsequent CHKDSK was clean and ordinary **Delete (without Shift)** worked. The problem was **recoverable in this case** (no observed wholesale library loss), but its precise cause and general deletion safety remain unproven. **Avoid Shift+Delete; make backups and use RW at your own risk.** FlashBridge does not run CHKDSK/repair, format media, force-unmount or automatically retry uncertain I/O.
- Submit test results using [compatibility matrix](docs/COMPATIBILITY.md) and a GitHub Issue; redact diagnostic logs.

---

## Previous release notes (v0.3.3-rc2)

**Near-final release candidate — experimental software provided "AS IS" without warranty under the MIT license.** It is not a stable, certified or universally compatible disk utility. Back up important data; do not use the only copy.

- Removed the optional Music/Audiobooks missing-only copy wizard **from the GUI**. Copy ordinary files using Windows File Explorer / Total Commander instead. Internal compatibility code remains for tests.
- Added a bilingual, six-tab **Help & safety / Nápověda a bezpečnost** information toolbox covering requirements, workflow, safe unmount, safety and diagnostic logs.
- Revised normal ImDisk unmount failure handling: when a virtual unit remains and `imdisk -d` refuses, preserve proxy/media, log `UNMOUNT_BUSY`, show actionable guidance to close all Explorer / Commander windows (including those on other drives), and offer **Retry**. No automatic process termination, no forced removal.
- Added a Windows **PyInstaller single-EXE build workflow** (console-free, UAC admin manifest, custom icon) and clarified prerequisites and release gates. ImDisk driver must still be installed separately; output unsigned.
- Rewrote English and Czech README for users, including known risks, first-run guide and physical-medium removal precautions.
- **No changes to the physical write path** from v0.3.2-alpha (sector-aware writes, Fast/Verified, synchronous flush, fail-closed faults).

Validation: **62 synthetic tests passed** on Windows and Linux, using Python 3.10 and 3.13. A real Windows x64 EXE was built successfully by GitHub Actions (run #43717489315); a development user ran rc2 elevated on Windows with actual physical-card writes and supplied a timestamped diagnostic log. **Still not verified:** independent disposable-media recovery/integrity testing, the inspector with a live assembled iPod, opt-in ImDisk installer on a target PC, and blocked-unmount retry. Do not label this release stable before those gates are satisfied.

### rc2 additions

- Added a read-only iPod storage inspector, including independent snapshot of the assembled iPod device and partition/FAT32 structures. First capture JSON snapshots of the two original SD cards individually, then connect the assembled iPod through USB and compare sampled block digests across both possible concatenation orders. It never formats, writes, installs firmware, infers bootability or grants RW. A non-linear adapter cannot be reconstructed from these limited samples.
- Added an opt-in ImDisk installer assistant: official HTTPS download into a fresh directory, valid vendor Authenticode signature required before launching; if verification fails, link to vendor's official download site instead. No silent driver installation or bundled binary.
- Added separate synthetic tests for sampling, order comparisons, failure cases and vendor-only redirects. GUI bilingual smoke checked with Tk virtual display; Windows native install and disk behavior still require acceptance tests.
- **Not implemented:** initializing SD media for the iPod, repartitioning, FAT32 formatting, bootloader or firmware provision, automated clone/restore, and support for arbitrary flash adapter layouts. Those require more independent hardware evidence.
