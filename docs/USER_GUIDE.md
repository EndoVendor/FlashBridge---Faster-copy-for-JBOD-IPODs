# FlashBridge v1.0.0 — User guide (English)

[Český návod](USER_GUIDE.cs.md) · [Project home](../README.md) · [Security](../SECURITY.md) · [Release checklist](../RELEASE_CHECKLIST.md)

**Release status: experimental functional prototype; working reference reported on ONE modified iPod, no general compatibility assurance. Provided AS IS without warranty.**

## 1. What FlashBridge does — and does not do

FlashBridge exposes an **existing, two-card, linearly concatenated FAT32 JBOD** from a flash-modified iPod as a temporary Windows drive through ImDisk. Insert the original cards into **two separate USB readers**. File transfers are done in Explorer, Total Commander, or another file manager; FlashBridge itself does not copy music.

The **iPod Storage Inspector** captures read-only evidence from **card A, card B and the assembled iPod connected through USB**. It records device geometry, available MBR/FAT32 evidence and SHA-256 hashes of small fixed samples. It compares **both possible linear card orders**. This is not a full-media test, firmware inspection, adapter-model identification, proof of bootability or authorization for RW.

**There is no formatting or initialization function.** FlashBridge does not create a new JBOD, rewrite partitions, install iPod firmware/bootloader, run filesystem repair or infer how an unknown flash adapter maps its media. A sample mismatch is not proof that a card is defective.

## 2. Download and install

1. Open the [v1.0.0 functional-prototype GitHub release](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/releases/tag/v1.0.0). Under **Assets**, download **FlashBridge-v1.0.0-Windows-x64-UNSIGNED.zip** (or the standalone EXE), alongside **SHA256.txt**. This is an **unsigned, experimental prerelease**, not a code-signed stable release.
2. Extract the ZIP, review the included README, and run **FlashBridge.exe** on Windows 10/11 x64. Approve the administrator/UAC prompt. **You do not need Python or a CMD launcher.** The EXE is unsigned and Windows may display a SmartScreen warning. This is not a security audit: verify the download originates from this repository.
3. **ImDisk Virtual Disk Driver is a separate dependency** and is not bundled in the EXE. Use **Inspect ImDisk** to check it. If absent, choose **Install ImDisk…**. After confirmation, the assistant downloads the installer from LTR Data's official HTTPS host, validates its Windows Authenticode signature and expected publisher, and only then launches the interactive installer. If validation fails, it refuses automatic launch and directs you to the [official ImDisk site](https://www.ltr-data.se/opencode.html#ImDisk).
4. If Windows offers to **Initialize** or **Format** either loose SD card, **cancel**. A component of a JBOD should not be treated as an independent FAT32 volume.

## 3. Exact GUI controls

| Control (English GUI) | Action | Writes to SD cards? |
| --- | --- | --- |
| **Refresh disks** | Enumerates physical disks and identities reported by Windows | No |
| **Auto-detect JBOD** | Searches for an existing, evidence-supported two-card FAT32 layout | No |
| **Verify selected pair** | Checks the two selected physical disks without guessing by drive number/capacity | No |
| **Save selected card snapshot (RO)** | Saves metadata and hashes of small blocks from one selected physical card | No |
| **Compare selected iPod disk (RO)** | Compares the selected live iPod physical disk with two previously saved snapshots | No |
| **Inspect ImDisk** | Checks ImDisk status/availability | No |
| **Install ImDisk…** | Downloads and verifies a Windows driver installer, with separate user consent | Not to cards |
| **Mount RO** | Exposes the recognized JBOD as a read-only virtual Windows volume | No |
| **Mount RW (experimental)** | Enables physical write access after explicit **WRITE** authorization | **Yes** |
| **FAST** | Requests a flush per write request, **without block readback** | Yes, in RW |
| **VERIFIED** | Requests flush and SHA-256 comparison after re-reading written blocks | Yes, in RW |
| **Safe unmount** | Requests normal ImDisk removal and checks that the specific unit is gone | Does not initiate user file copies; Windows may complete pending I/O |
| **Open log folder** | Shows local text and JSONL diagnostic records | No |

An inspector report of **CANDIDATE ONLY** means some sampled evidence supports a linear byte layout; it is **not** full data verification or adapter certification. **NOT PROVEN** means the sampled linear mapping was not established; it does not automatically mean the hardware is broken. Inspector results never override the separate write-authorization checks used for mounting.

## 4. Workflow A — inspect cards and the assembled iPod (recommended first)

**No ImDisk installation or virtual JBOD mount is required for this workflow.** FlashBridge opens the selected devices in read-only mode.

1. Remove both cards from the flash adapter. Mark their original physical positions **A** and **B** to avoid a mix-up.
2. Insert **card A only** into a USB reader. Click **Refresh disks**, inspect its size and device name, and select **exactly one physical disk**.
3. Click **Save selected card snapshot (RO)**, saving the JSON as **card-A.json** somewhere other than the SD card.
4. Repeat with card B and save **card-B.json**. Refuse any Windows initialization or formatting prompt.
5. Return both cards to their **original slots** in the adapter and iPod. Connect the assembled iPod in **USB disk mode**. Click **Refresh disks** and identify the **iPod's physical disk**, not a drive letter or your Windows system disk.
6. Select the iPod physical disk and click **Compare selected iPod disk (RO)**. Supply both saved JSON snapshots and save **flashbridge-ipod-comparison.json**.
7. Inspect **variants / order / matches / mismatches / unavailable / status**, capacities and the independent **ipod_snapshot** with partition/FAT32 metadata and sample hashes. Both A→B and B→A are evaluated.
8. If mapping is inconclusive, do **not** force a mount or infer how the adapter works. Different adapters may use different sector geometry or completely different mappings.

Snapshot JSON contains hardware metadata and sample hashes, not your music files. Review and redact it before public sharing.

## 5. Workflow B — read an existing JBOD, optionally transfer files

1. Place the **two original JBOD cards** into separate USB card readers. Do not format.
2. Start FlashBridge as administrator, check ImDisk, then press **Auto-detect JBOD**. If ambiguous, select **exactly two physical disks** and choose **Verify selected pair**. Stop if the layout cannot be verified.
3. Review **FIRST / SECOND**, FAT32 start and length, sector geometry, backup boot-sector evidence, FSInfo and FAT-table headers. These are structural checks, **not** complete filesystem integrity verification.
4. Choose an unused virtual letter (for example **R:**). First **Mount RO** and check the folder structure with your regular file manager.
5. Only on **disposable test media**, with an independent backup, choose **FAST** or **VERIFIED**, click **Mount RW (experimental)** and type **WRITE** exactly. This grants real physical write access.
6. Transfer files through Windows Explorer or Total Commander. The optional Music/Audiobooks missing-file copy wizard has been removed from the public GUI.
7. **Avoid Shift+Delete and permanent deletion.** In the owner's test, Shift+Delete was associated with a few zero-byte/undeletable entries; ordinary **Delete without Shift** worked instead. The affected FAT32 errors were repaired using Windows `chkdsk /f` **after reassembling the iPod and connecting it via USB**; a follow-up check was clean. This does not prove Shift+Delete caused the issue or that ordinary Delete is universally safe. Use backups; FAST is not content verification.
8. After all copies are finished, close **all** Explorer/Commander windows, including ones showing **C:** or other unrelated volumes. Click **Safe unmount**. Once the original ImDisk unit has disappeared, safely eject both USB readers in Windows; only then remove the cards.

If ImDisk refuses unmount, **leave both cards connected and keep FlashBridge running**. Close any programs holding volume handles and choose **Retry**. Do not force-remove ImDisk or terminate its proxy while the virtual device exists.

## 6. Troubleshooting

| Symptom | Safe response |
| --- | --- |
| Windows asks to format/initialize | **Cancel**. A loose JBOD card may not be an independent filesystem. |
| Card is missing | Check reader/cable and Windows device enumeration, then **Refresh disks**. Do not initialize the card. |
| JBOD auto-detection fails | Check pair, card capacities and evidence. Different adapters may be unsupported. Use the read-only inspector first. |
| Inspector says NOT PROVEN | Review both possible orders and sample counts. It is not a declaration of damage. |
| ImDisk missing | Use **Inspect ImDisk** or **Install ImDisk…**. If signature verification fails, use the official vendor webpage. |
| Virtual letter in use | Choose another free drive letter. |
| Safe unmount refused | Close **all** Explorer/Commander windows and file dialogs (even on C:), then **Retry**. Keep the cards attached. |
| I/O fault, WinError or zero-byte files | Stop issuing new writes, preserve the log, and attempt normal safe unmount. Do not blindly run CHKDSK or force detach. |
| Want to prepare two new, blank cards | **Not supported.** Formatting, partition creation and firmware provisioning are deliberately absent. |

## 7. Logs, performance and privacy

Logs are written to **%LOCALAPPDATA%\FlashBridge\logs** as human-readable **.log** and structured **.jsonl** files. In FAST mode, successful individual **IO_END** entries are sampled; use **IO_STATS** cumulative counters for total bytes. Throughput may swing substantially with the physical media, readers and card firmware; no speed is guaranteed.

**Limits:** exactly two recognized, linearly concatenated FAT32 media; not arbitrary JBOD, exFAT, RAID0, three or more cards, firmware restoration, partitioning or filesystem repair. Flush and even VERIFIED readback are **not** guarantees against data loss after power failure. Redact disk identities, paths and hashes before posting logs or snapshots publicly.

## 8. Validation status and bug reports

- The final rc2 commit passed **62 synthetic tests** on Windows and Linux, with Python 3.10 and 3.13.
- A native Windows x64 EXE was successfully built with PyInstaller and published as a GitHub Actions artifact.
- The maintainer confirms a successful real Windows EXE transfer to an existing two-card FAT32 JBOD, followed by removal/reinsertion of the cards and successful Rockbox recognition with contents apparently functional (15 Nov 2026). This is ONE owner-reported reference, not full-file hash verification or compatibility certification.
- **Not yet independently qualified:** clean ImDisk installation, inspector against an assembled iPod, refused unmount + Retry, full file checksum verification, other iPod/adapter models. See [compatibility matrix](COMPATIBILITY.md).

Report reproducible issues via [GitHub Issues](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues) with Windows version, USB reader models, exact steps and **redacted** JSONL logs. Do not upload full SD-card images, private file paths or copyrighted music.
