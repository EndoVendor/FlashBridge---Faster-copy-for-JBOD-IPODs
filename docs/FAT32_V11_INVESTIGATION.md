# FlashBridge v1.1 — FAT32 integrity investigation and release gate

**Status: defect observed on real iPod; root cause NOT established; no data-safe fix shipped.**

## Evidence

- The owner reports the symptoms appearing in connection with **Shift+Delete** during experimental RW. Some FLAC entries became zero-byte or undeletable; Windows FAT32 CHKDSK on the reassembled iPod found invalid allocation links, invalid beginning clusters and two cross-linked clusters. Ordinary **Delete without Shift** worked as an observed workaround in this case. This is a timing/behavior observation, not proof of exclusive causation or universal safety.
- CHKDSK /f on the assembled iPod in direct Rockbox USB disk mode repaired the errors and freed 31,920 KiB; a subsequent no-fix CHKDSK reported no errors. File count remained 31,974; several entries regained an apparent normal size and became deletable. This was **recoverable filesystem metadata damage in one reference case, without observed loss of the whole library**. **Not proof of intact audio data or causation.**
- A prior RW session recorded WinError 55 and Windows disk controller errors (issue #2). A later ~93.7 GB confirmed FAST physical write session recorded no write fault in its *incomplete, user-exported text log*; the log lacks a final unmount record. It therefore cannot demonstrate metadata safety through filesystem teardown.
- FlashBridge v1.0.0 performs per-request physical FlushFileBuffers after data writes and does not perform automatic filesystem repair. It does not independently validate every FAT allocation chain, prove full directory consistency or make directory/FAT mutations atomic.
- ImDisk upstream README documents its legacy Windows compatibility limitations; this is a **candidate layer to test**, not an adjudicated cause.

## Hypotheses to distinguish (no assumption that one is correct)

1. Different Windows FAT32 metadata sequences for **Shift+Delete versus ordinary Delete** (Recycle Bin behavior) could expose a failure; this is the user's strongest reported trigger, but needs independent reproduction.
2. Partial Windows FAT32 metadata transaction due to earlier USB/media/flush fault, unplug or abrupt unmount after WinError 55.
2. ImDisk proxy/Windows FAT32 caching, flush and safe-unmount edge cases on current Windows.
3. Physical-card/controller/USB-reader write instability or incomplete flush guarantees.
4. FlashBridge logical-to-physical offset, crossing boundary, alignment, RMW edge behavior or protocol implementation error.
5. Already-existing metadata damage unrelated to later sessions.

## Real validation protocol (disposable media only)

1. Create a FAT32 volume on two **expendable** media with known layout (never format the reference music cards). Record a clean baseline, both FAT copies/FSInfo, media identities and a full independent CHKDSK before and after tests.
2. Run a real Windows + ImDisk proxy mount. Create directories and thousands of test files including long filenames, rename, overwrite, ordinary Delete and Shift+Delete, recreate names, check directory entries and free-space totals. Include cases near the media boundary and both cards.
3. Capture full unsampled metadata write requests during controlled small tests, physical write/flush/readback results, errors, and exact successful unmount/close events. Verify across full reopens, not just cached reads.
4. After NORMAL unmount, independently check all file hashes; run CHKDSK read-only and compare both FAT copies, FSInfo, and directory entries. Reassemble and repeat verification through iPod USB/Rockbox.
5. Inject partial-write, failed-flush, link loss and busy-unmount conditions only on sacrificial test media or simulated proxy, verify errors latch and future writes fail closed; ensure no forced removal or unsafe automatic retry.
6. Compare against baseline on the same hardware through direct iPod USB and a standard ImDisk-backed image to isolate iPod firmware, Windows filesystem, physical microSD readers and FlashBridge.
7. If FAT corruption reproduces, isolate the exact sequence and fix the responsible layer; if the issue originates in ImDisk's unsupported design, evaluate a supported disk virtualization driver. Avoid weakening durability or turning on write-behind to hide symptoms.

## v1.1 acceptance / no premature release

- [ ] Reproducible and root-caused observed corruption, or explicit documented limitation and blocked unsafe operations.
- [ ] Native Windows filesystem integration regression for copy, overwrite, rename, delete, safe unmount, remount and integrity verification.
- [ ] CHKDSK clean and independent hashes matching after repeated disposable-media RW cycles, including Rockbox reassembly.
- [ ] Fault-injection and failed-unmount cases safely fail closed.
- [ ] Rebuilt signed/unsigned binary provenance, CI and owner hardware verification documented accurately.
- [ ] Retest with a second adapter/iPod before claiming wider hardware compatibility.

Public issue: [#1 FAT32 corruption](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues/1). Related [#2 device WinError 55](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues/2).
