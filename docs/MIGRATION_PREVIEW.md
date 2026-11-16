# FlashBridge — safe two-card JBOD migration preview (16 Nov 2026)

**EXPERIMENTAL PREFLIGHT. NOT A FINISHED MIGRATOR.** No real card has been imaged or migrated with this code. The new paths have synthetic checks only until independently accepted on Windows/disposable cards. The existing FlashBridge GUI/data path remains unchanged.

## Why file-level migration, not cloning

Original A and B are one linearly concatenated FAT32 filesystem. When first card size grows (512 GB + 1 TB → 1 TB + 1 TB), the position of all data following the old A/B boundary changes. Blind old-A→new-A / old-B→new-B raw cloning gives the wrong placement for part of FAT32. Do not do this.

Build a **separately provisioned, working, bootable** new iPod JBOD with larger FAT32. Preserve its firmware/boot structure. Expose captured old cards as ONE read-only volume and copy its file tree with Total Commander, FreeCommander or Explorer. Verify every file against a source manifest. This preview **does not** create target JBOD, format cards, install Rockbox or automatically copy files.

## Hard stop conditions

- Windows 10/11 x64, Python 3.10+, official ImDisk and sufficient local free space (~1.5 TB for 512 GB + 1 TB images plus margin).
- Read-only custody of original media: opening a raw device with a read-only handle does NOT prevent Windows or another program from writing to its independently mounted partitions. No iPod connection during imaging, no automatic repair/initialization, no CHKDSK /f on sources.
- Exact device identity, size and original order from fresh observation; never select by remembered PhysicalDrive number.
- All image reads succeed, SHA-256 independent second pass succeeds, source geometry and FAT32 metadata agree.
- Any source metadata corruption or ambiguous layout is a BLOCKER; never automatically repair.
- Target requires exact physical sizes, working firmware/bootloader and FAT32 expanded to intended supported capacity. The CLI does not prepare or validate all those properties.
- Source A and B never used as target write media. Keep original pair intact as rollback.
- Experimentally mounted target RW inherits open FlashBridge issues #1 and #2. Test only with expendable media until a real-data safety gate passes.

## PowerShell workflow (from project root)

### 1. Discover original cards, read-only

    py -3.13 flashbridge_migrate.py probe

Record disk_number, exact bytes and first4k_sha256 from this fresh run. Confirm physical labels and slot order.

### 2. Capture each full physical card

Replace all angle-bracket placeholders with exact observed values:

    py -3.13 flashbridge_migrate.py capture --disk-number 4 --expect-size <EXACT_BYTES_A> --expect-first4k <SHA256_A> --output E:\iPodBackup\source_A.img
    py -3.13 flashbridge_migrate.py capture --disk-number 5 --expect-size <EXACT_BYTES_B> --expect-first4k <SHA256_B> --output E:\iPodBackup\source_B.img

Each capture uses read-only input handles, writes to a NEW .partial image, independently checks the output SHA-256, then publishes source_A.img and its .capture.json evidence. Never overwrites evidence. A failed/interrupted capture leaves .partial and is NOT declared complete. These are whole-card images including MBR/firmware/FAT/free space, not just music.

### 3. Produce non-writing capacity and layout plan

    py -3.13 flashbridge_migrate.py plan --image-a E:\iPodBackup\source_A.img --image-b E:\iPodBackup\source_B.img --target-a-bytes <EXACT_TARGET_A_BYTES> --target-b-bytes <EXACT_TARGET_B_BYTES> --output E:\iPodBackup\migration-plan.json

Verifies source image SHA-256 in full, detects FAT32 spanning A/B and rejects nonsensical target sizes or >= 2 TiB 512B-sector addressing boundary. The output deliberately says BLOCKED_TARGET_PROVISIONING_NOT_IMPLEMENTED. It does NOT mean the target is prepared for writing.

### 4. Check capacity of the *already provisioned* target pair in RO mode

After the NEW target iPod was separately initialized and its booting/formatting
procedure has been proven, remove only the new target cards, confirm their slot
order and use a fresh probe to identify the two PhysicalDrive numbers:

    py -3.13 flashbridge_migrate.py check-target --plan E:\iPodBackup\migration-plan.json --first-disk <TARGET_DISK_A> --second-disk <TARGET_DISK_B> --output E:\iPodBackup\target-check.json

This read-only step reuses FlashBridge discovery to require the two exact
sizes, correct order, validated FAT32 header/backup/FSInfo, aligned FAT headers
and **FAT32 volume size greater than the original**. It does not write cards
or prove bootability, filesystem health or unique SD identity. A matching
header hash on a blank continuation card is NOT unique: physically label and
keep custody of the target cards. Failing this gate means STOP, not format.

### 5. Mount images as ONE read-only virtual source disk via existing ImDisk

    py -3.13 flashbridge_migrate.py mount-source --image-a E:\iPodBackup\source_A.img --image-b E:\iPodBackup\source_B.img --letter S

The image-backed ProxyServer is strictly read-only. The original physical cards can remain disconnected. Keep the CLI process open while S: is mounted. Ctrl+C requests NORMAL unmount. If ImDisk refuses, close Commander/Explorer windows and retry; do not force-remove the volume or backing files.

### 6. Inventory ALL files, including hidden folders, and compute full SHA-256

    py -3.13 flashbridge_migrate.py manifest --source S:\ --output E:\iPodBackup\source-files.json

Captures paths, sizes, SHA-256 and empty directories, including .rockbox, playlists, bookmarks and iPod_Control. This is not limited to Music/Audiobooks. File-by-file readability is not an independent full FAT consistency check: verify FAT metadata read-only as a separate prerequisite.

### 7. Controlled copy, retaining external file managers

Source: S: (read-only captured image). Target: a SEPARATE mounted and already provisioned FAT32 JBOD, e.g. T:.

Use Total Commander / FreeCommander / Explorer to copy the entire filesystem tree. Include hidden/system files and directories; preserve timestamps and attributes. Avoid blindly replacing target-specific firmware/boot and incompatible Rockbox binaries. Decide and document such conflicts separately. Copy the files only after proving correct target identity, supported capacity, firmware and safe RW path. There is NO automated copy or provisioning command in this preview.

### 8. Independently verify the target file tree after normal safe unmount/remount

    py -3.13 flashbridge_migrate.py verify --manifest E:\iPodBackup\source-files.json --target T:\ --report E:\iPodBackup\verify-report.json

Exit 0 requires every expected file and directory plus matching SHA-256 and no unexpected files. The optional --allow-extra-target-files records, but permits, extra boot/system files. Missing/changed source files always fail. The verifier does not claim the iPod booted or FAT32 is consistent.

### 9. Hardware acceptance and rollback

Verify that the new iPod independently boots, reports intended higher capacity, reads files located beyond the old A/B boundary, plays music, accesses playlists, audiobooks and bookmarks, and survives a cold reboot. Replace original A and B in the original iPod in the correct order and verify it still works. Result is ACCEPTED / REJECTED / INCONCLUSIVE with evidence; no implied success from tests alone.

## Known limitations

- The preview provides CLI probe/capture/plan/check-target/read-only-image-mount/manifest/verify. No GUI migration wizard and no target provisioning, formatting, direct raw writer, automatic file-copy routine or bootloader copy.
- Source imaging and image SHA are separate from FAT32 metadata audit; unknown source damage stays a blocker.
- Real USB removal, capture failure, native Windows ImDisk mount/unmount, reader compatibility and end-to-end transfer are NOT proven by synthetic CI tests.
- Do not publish a stable claim or run RW on unique media based on this preview.

Prior handoff (requirements and safeguards):
https://docs.google.com/document/d/1HhXvkDObOZoeuKBVeELRPAkphhNCsqfgmixTmpEgkjY/edit
