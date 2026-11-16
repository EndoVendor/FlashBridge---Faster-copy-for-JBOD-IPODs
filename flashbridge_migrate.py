"""FlashBridge migration preparation, image-backed read-only source and verification.

This tool deliberately does NOT provision/formats target cards, install firmware,
write raw target devices or automatically copy files. It reuses existing ImDisk
for a read-only source volume so Commander/Explorer can copy to a separately
prepared target JBOD. Run only with known-good backup and disposable targets.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import struct
import sys
import time

from flashbridge_core import (
    DiskInfo, Plan, ProxyServer, RawDevice, FAT32_MAX_FILE, MIB,
    eligible, discover_pair, imdisk_mount, imdisk_unmount, is_elevated, make_logger,
    parse_fat32_boot, path_letter_free, powershell_disks,
)

CHUNK = 8 * MIB
LIMIT_512_LBA = (2**32) * 512
CAPTURE_SCHEMA = "flashbridge-image-v1"
FILE_SCHEMA = "flashbridge-file-manifest-v1"


def file_digest(path: Path) -> str:
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as f:
        for data in iter(lambda: f.read(CHUNK), b""):
            h.update(data)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"File changed while hashing: {path}")
    return h.hexdigest()


def first_fingerprint(path: Path) -> str:
    with path.open("rb") as f:
        block = f.read(4096)
    if len(block) != 4096:
        raise ValueError("Image is too short for a 4096-byte fingerprint.")
    return hashlib.sha256(block).hexdigest()


def write_json_new(path: Path, data: dict) -> None:
    """Fail closed when an output already exists; never overwrite evidence."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False, sort_keys=True)
        out.write("\n")


def capture_info_path(image: Path) -> Path:
    return image.with_name(image.name + ".capture.json")


def read_capture(image: Path, full_hash: bool = True) -> dict:
    info_path = capture_info_path(image)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    if info.get("schema") != CAPTURE_SCHEMA:
        raise RuntimeError(f"Missing/invalid capture schema: {info_path}")
    if not image.is_file() or image.is_symlink():
        raise RuntimeError(f"Not a regular image: {image}")
    actual = image.stat().st_size
    if actual < 8192 or actual != info.get("bytes"):
        raise RuntimeError(f"Image length differs from capture record: {image}")
    if image.name != info.get("image_name"):
        raise RuntimeError("Capture record does not match image basename.")
    if first_fingerprint(image) != info.get("first4k_sha256"):
        raise RuntimeError(f"Image header fingerprint mismatch: {image}")
    if full_hash and file_digest(image) != info.get("sha256"):
        raise RuntimeError(f"Image SHA-256 mismatch: {image}")
    return info


def probe():
    for d in powershell_disks():
        if not eligible(d):
            continue
        try:
            with RawDevice(d.path, d.size, False) as raw:
                fingerprint = hashlib.sha256(raw.read_at(0, 4096)).hexdigest()
        except (OSError, ValueError) as exc:
            fingerprint = f"UNREADABLE ({type(exc).__name__})"
        print(json.dumps({
            "disk_number": d.number, "bytes": d.size, "bus": d.bus,
            "model": d.name, "read_only_reported": d.readonly,
            "first4k_sha256": fingerprint,
        }, ensure_ascii=False))


def assert_not_on_source_disk(number: int, image: Path):
    """Reject destination drive letters physically backed by source SD device."""
    drive = image.drive.rstrip(":").upper()
    if not re.fullmatch(r"[A-Z]", drive):
        raise RuntimeError("Image output must be on a distinct local drive letter.")
    script = ("$ErrorActionPreference='Stop'; "
              "$p=Get-Partition -DriveLetter '" + drive + "'; "
              "[string]$p.DiskNumber")
    res = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, timeout=25, errors="replace")
    if res.returncode or not res.stdout.strip().isdigit():
        raise RuntimeError("Could not establish image destination physical disk identity.")
    if int(res.stdout.strip()) == number:
        raise RuntimeError("Refusing to create image ON its own source physical disk.")


def capture_disk(number: int, expected_size: int, expected_first4k: str, image: Path):
    if os.name != "nt":
        raise RuntimeError("Capturing physical drives requires Windows.")
    if not is_elevated():
        raise RuntimeError("Run from an elevated Windows terminal.")
    image = image.expanduser().absolute()
    assert_not_on_source_disk(number, image)
    info_path = capture_info_path(image)
    partial = image.with_name(image.name + ".partial")
    if any(p.exists() for p in (image, info_path, partial)):
        raise FileExistsError("Output image/manifest/partial already exists; refusing overwrite.")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_first4k):
        raise ValueError("Expected SHA-256 fingerprint must contain 64 hex digits.")
    disks = {d.number: d for d in powershell_disks() if eligible(d)}
    disk = disks.get(number)
    if disk is None or disk.size != expected_size:
        raise RuntimeError("Disk identity/size differs from probe; no image written.")
    # All physical handles opened read-only. This cannot prevent other software
    # from writing to an independently mounted volume: ensure exclusive custody.
    with RawDevice(disk.path, disk.size, False) as raw:
        first = hashlib.sha256(raw.read_at(0, 4096)).hexdigest()
        if first.lower() != expected_first4k.lower():
            raise RuntimeError("First 4KiB identity mismatch; no image written.")
        image.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with partial.open("xb") as out:
            offset = 0
            next_progress = 1024**3
            while offset < disk.size:
                n = min(CHUNK, disk.size - offset)
                data = raw.read_at(offset, n)
                out.write(data)
                digest.update(data)
                offset += n
                if offset >= next_progress or offset == disk.size:
                    print(f"Captured {offset}/{disk.size} bytes (input RO)", flush=True)
                    next_progress = offset + 1024**3
            out.flush()
            os.fsync(out.fileno())
        # Detect source header change during imaging. Not a replacement for
        # physical write protection or a stable-source guarantee.
        if hashlib.sha256(raw.read_at(0, 4096)).hexdigest() != first:
            raise RuntimeError("Source fingerprint changed while imaging; partial retained.")
    # Independent reread before publishing capture evidence.
    if partial.stat().st_size != disk.size or file_digest(partial) != digest.hexdigest():
        raise RuntimeError("Image second-pass integrity check failed; partial retained.")
    partial.replace(image)
    write_json_new(info_path, {
        "schema": CAPTURE_SCHEMA, "image_name": image.name, "bytes": disk.size,
        "first4k_sha256": first, "sha256": digest.hexdigest(),
        "source_bus": disk.bus, "source_model": disk.name,
        "sector_size_reported": disk.logical_sector_size,
        "captured_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_must_remain_read_only": True,
    })
    return info_path


@dataclass(frozen=True)
class ImageMedia:
    number: int
    size: int
    path: str
    logical_sector_size: int = 512
    physical_sector_size: int = 512


def reconstruct_plan(image_a: Path, image_b: Path, verify: bool = True) -> Plan:
    """Prove FAT32 starts on A and spans into B without reading physical disks."""
    image_a, image_b = image_a.resolve(), image_b.resolve()
    if image_a == image_b:
        raise ValueError("First and second image cannot be the same.")
    info_a = read_capture(image_a, full_hash=verify)
    info_b = read_capture(image_b, full_hash=verify)
    first = ImageMedia(90001, info_a["bytes"], str(image_a))
    second = ImageMedia(90002, info_b["bytes"], str(image_b))
    offsets = set()
    with RawDevice(str(image_a), first.size, False) as raw:
        mbr = raw.read_at(0, 512)
        if mbr[510:512] != b"\x55\xaa":
            raise RuntimeError("Source image A has no valid MBR signature.")
        for i in range(4):
            entry = mbr[446 + i*16:462 + i*16]
            start_lba = struct.unpack_from("<I", entry, 8)[0]
            sectors = struct.unpack_from("<I", entry, 12)[0]
            if start_lba and sectors:
                for sector_bytes in (512, 1024, 2048, 4096):
                    offset = start_lba * sector_bytes
                    if offset + 4096 <= first.size:
                        offsets.add(offset)
        candidates = []
        combined = first.size + second.size
        for offset in sorted(offsets):
            boot = raw.read_at(offset, min(4096, first.size-offset))
            fat = parse_fat32_boot(boot, offset, first.number, reader=raw)
            if not fat or not fat.backup_matches or not fat.fsinfo_valid:
                continue
            if not (first.size < fat.end <= combined):
                continue
            # The same strict end-of-pair requirement as original FlashBridge.
            if combined-fat.end > max(64*MIB, int(combined * .005)):
                continue
            if not fat.fat_head_match:
                raise RuntimeError("FAT header disagreement; inspect source before migration.")
            candidates.append(fat)
    if len(candidates) != 1:
        raise RuntimeError(f"Source has {len(candidates)} valid spanning FAT32 candidates; no guessing.")
    fat = candidates[0]
    return Plan(first, second, fat,
                ("Read-only captured image A||B", "Validated FAT32 boot/backup/FSInfo/FAT headers"),
                False, info_a["first4k_sha256"], info_b["first4k_sha256"])


def migration_plan(image_a: Path, image_b: Path, target_a_bytes: int, target_b_bytes: int) -> dict:
    plan = reconstruct_plan(image_a, image_b, verify=True)
    total_target = target_a_bytes + target_b_bytes
    if min(target_a_bytes, target_b_bytes) <= 0 or (
        target_a_bytes % 512 or target_b_bytes % 512
    ):
        raise ValueError("Target card sizes must be positive, exact, 512-byte aligned.")
    if total_target <= plan.combined:
        raise ValueError("Target pair is not larger than the existing source pair.")
    if total_target >= LIMIT_512_LBA:
        raise ValueError("Target exceeds safe 32-bit LBA capacity for 512B sectors.")
    return {
        "schema": "flashbridge-migration-plan-v1",
        "source_image_a": str(image_a.resolve()),
        "source_image_b": str(image_b.resolve()),
        "source_a_bytes": plan.first.size, "source_b_bytes": plan.second.size,
        "source_combined_bytes": plan.combined,
        "source_partition_start_bytes": plan.fat.offset,
        "source_fat32_bytes": plan.volume_bytes,
        "source_fat32_sectors": plan.fat.sectors_total,
        "source_fat32_sector_size": plan.fat.sector_size,
        "source_image_a_sha256": read_capture(image_a, False)["sha256"],
        "source_image_b_sha256": read_capture(image_b, False)["sha256"],
        "target_a_bytes": target_a_bytes, "target_b_bytes": target_b_bytes,
        "target_combined_bytes": total_target,
        "target_additional_bytes_raw": total_target-plan.combined,
        "status": "BLOCKED_TARGET_PROVISIONING_NOT_IMPLEMENTED",
        "required_before_copy": [
            "Target pair separately verified as correctly provisioned FAT32 JBOD",
            "Compatible iPod firmware/bootloader independently verified",
            "Target FAT32 is expanded to the validated target capacity",
            "Target cards physically identified, backed up and approved for writes",
            "Original cards unchanged and disconnected from target write path",
        ],
        "raw_clone_each_card_allowed": False,
        "source_images_read_only": True,
    }



def check_provisioned_target(plan_path: Path, first_disk: int, second_disk: int) -> dict:
    """Strictly read-only physical target check. NOT a boot/FS-health certificate."""
    if os.name != "nt":
        raise RuntimeError("Target physical disk inspection requires Windows.")
    if first_disk == second_disk:
        raise ValueError("Target media must be two distinct devices.")
    config = json.loads(plan_path.read_text(encoding="utf-8"))
    if config.get("schema") != "flashbridge-migration-plan-v1":
        raise RuntimeError("Unknown migration plan schema.")
    devices = {d.number: d for d in powershell_disks() if eligible(d)}
    first, second = devices.get(first_disk), devices.get(second_disk)
    if first is None or second is None:
        raise RuntimeError("Target card identification is incomplete or unsafe.")
    if first.size != config["target_a_bytes"] or second.size != config["target_b_bytes"]:
        raise RuntimeError("Physical target card sizes do not match the approved plan.")
    # Existing FlashBridge evidence-based detector; opens physical cards RO.
    physical = discover_pair([first, second])
    if physical.first.number != first_disk or physical.second.number != second_disk:
        raise RuntimeError("Target A/B card order differs from supplied order.")
    if not physical.read_write_safe or not physical.fat.backup_matches or not physical.fat.fsinfo_valid:
        raise RuntimeError("Target FAT32 structural checks did not pass.")
    if physical.volume_bytes <= config["source_fat32_bytes"]:
        raise RuntimeError("Target FAT32 is not larger than original; space was not expanded.")
    if physical.fat.end > config["target_combined_bytes"]:
        raise RuntimeError("Target FAT32 exceeds physical target media bounds.")
    # A first-4KiB hash alone may not uniquely identify a card (B may be
    # empty); keep external card-label/serial custody as a mandatory owner gate.
    return {
        "schema": "flashbridge-target-inspection-v1",
        "status": "TARGET_FAT32_GEOMETRY_VERIFIED_BOOT_AND_RW_UNVERIFIED",
        "first_disk": first_disk, "second_disk": second_disk,
        "first_bytes": first.size, "second_bytes": second.size,
        "target_fat32_bytes": physical.volume_bytes,
        "gain_fat32_bytes": physical.volume_bytes - config["source_fat32_bytes"],
        "backup_boot_matches": physical.fat.backup_matches,
        "fsinfo_valid": physical.fat.fsinfo_valid,
        "fat_head_matches": physical.fat.fat_head_match,
        "manual_target_card_identity_still_required": True,
        "bootloader_and_cold_boot_unverified": True,
        "complete_fat_integrity_unverified": True,
        "no_media_writes_performed": True,
    }


def mount_source(image_a: Path, image_b: Path, letter: str):
    if os.name != "nt" or not is_elevated():
        raise RuntimeError("Mount requires elevated Windows and installed ImDisk.")
    letter = letter.upper()
    if not re.fullmatch(r"[A-Z]", letter) or not path_letter_free(letter):
        raise RuntimeError("Drive letter is invalid or occupied.")
    plan = reconstruct_plan(image_a, image_b, verify=True)
    log = make_logger()
    server = ProxyServer(plan, False, log, port=0)
    server.start()
    if not server.started.wait(25) or not server.ready:
        server.stop()
        server.join(10)
        log.close()
        raise RuntimeError(f"Source image proxy failed to start: {server.last_error}")
    code, info = imdisk_mount(plan, letter, False, server.port)
    if code:
        server.stop()
        server.join(15)
        log.close()
        raise RuntimeError(f"ImDisk read-only mount failed: {info}")
    print(f"Read-only image source mounted at {letter}:")
    print("Copy with Total Commander to a SEPARATELY PROVISIONED target volume.")
    print("Press Ctrl+C to request a NORMAL unmount. Never remove images while mounted.")
    warned = False
    try:
        while True:
            if server.failed and not warned:
                print("Proxy failed; unmount normally before leaving.", file=sys.stderr)
                warned = True
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    # Keep process/handles alive while ImDisk still owns the volume.
    try:
        while True:
            code, info = imdisk_unmount(letter)
            if code == 0:
                print("Normal ImDisk unmount acknowledged.")
                break
            print(f"ImDisk unmount refused: {info}", file=sys.stderr)
            print("Close Explorer/Commander windows and release all file handles.")
            try:
                input("Press Enter to RETRY normal unmount; do not close this process: ")
            except (KeyboardInterrupt, EOFError):
                time.sleep(2)
    finally:
        if code == 0:
            server.stop()
            server.join(15)
            log.close()


def is_reparse_or_link(path: Path) -> bool:
    """Windows directory junctions are not consistently reported as symlinks."""
    attrs = getattr(path.lstat(), "st_file_attributes", 0)
    return path.is_symlink() or bool(attrs & 0x400)


def scan_tree(root: Path, hash_files: bool = True) -> dict:
    """Inventory all regular files, including hidden and .rockbox; no symlink traversal."""
    if not root.is_dir() or is_reparse_or_link(root):
        raise RuntimeError(f"Not a safe mounted directory: {root}")
    files, directories, seen = [], [], set()
    def fail_walk(error):
        raise RuntimeError(f"Directory traversal incomplete: {error}") from error
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False,
                                        onerror=fail_walk):
        here = Path(current)
        for name in dirs:
            path = here/name
            if is_reparse_or_link(path):
                raise RuntimeError(f"Refusing symlink/reparse directory: {path}")
            rel = path.relative_to(root).as_posix()
            key = rel.casefold()
            if key in seen:
                raise RuntimeError(f"Duplicate case-insensitive relative path: {rel}")
            seen.add(key)
            directories.append(rel)
        for name in names:
            path = here/name
            if is_reparse_or_link(path) or not path.is_file():
                raise RuntimeError(f"Refusing symlink/special file: {path}")
            rel = path.relative_to(root).as_posix()
            key = rel.casefold()
            if key in seen:
                raise RuntimeError(f"Duplicate case-insensitive relative path: {rel}")
            seen.add(key)
            stat = path.stat()
            if stat.st_size > FAT32_MAX_FILE:
                raise RuntimeError(f"File exceeds FAT32 max size: {rel}")
            files.append({
                "path": rel, "bytes": stat.st_size,
                "sha256": file_digest(path) if hash_files else None,
            })
    files.sort(key=lambda item: item["path"].casefold())
    directories.sort(key=str.casefold)
    return {
        "schema": FILE_SCHEMA, "directories": directories, "files": files,
        "file_count": len(files),
        "total_file_bytes": sum(item["bytes"] for item in files),
        "complete_file_sha256": hash_files,
        "source_root": str(root.resolve()),
    }


def manifest_source(root: Path, output: Path):
    if output.exists() or (root.resolve() in output.resolve().parents):
        raise ValueError("Manifest must be a NEW file outside the source volume.")
    content = scan_tree(root)
    write_json_new(output, content)
    return content


def verify_target(manifest: Path, target: Path, allow_extras: bool = False):
    expected = json.loads(manifest.read_text(encoding="utf-8"))
    if expected.get("schema") != FILE_SCHEMA or not expected.get("complete_file_sha256"):
        raise RuntimeError("Refusing incomplete/unknown source manifest.")
    if expected.get("source_root") == str(target.resolve()):
        raise RuntimeError("Verification target is the same path as the source manifest.")
    actual = scan_tree(target)
    a = {x["path"].casefold(): x for x in actual["files"]}
    b = {x["path"].casefold(): x for x in expected["files"]}
    missing = sorted(x["path"] for k,x in b.items() if k not in a)
    mismatched = sorted(x["path"] for k,x in b.items()
                        if k in a and (x["bytes"] != a[k]["bytes"] or
                                       x["sha256"] != a[k]["sha256"]))
    extras = sorted(x["path"] for k,x in a.items() if k not in b)
    dirs_missing = sorted(set(expected["directories"])-set(actual["directories"]))
    passed = (not missing and not mismatched and not dirs_missing and
              (allow_extras or not extras))
    return {
        "schema": "flashbridge-verify-report-v1", "passed": passed,
        "files_checked": len(expected["files"]), "target_file_count": len(actual["files"]),
        "missing": missing, "mismatched": mismatched,
        "extra_target_files": extras, "missing_directories": dirs_missing,
        "allow_extras": allow_extras,
        "boot_tested": False, "fat32_consistency_tested": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("probe", help="Read-only listing of candidate SD devices and fingerprints")
    capture = sub.add_parser("capture", help="Read-only image of ONE physical card")
    capture.add_argument("--disk-number", type=int, required=True)
    capture.add_argument("--expect-size", type=int, required=True)
    capture.add_argument("--expect-first4k", required=True)
    capture.add_argument("--output", type=Path, required=True)
    plan_cmd = sub.add_parser("plan", help="Inspect source images and larger target sizes; NO writes")
    plan_cmd.add_argument("--image-a", type=Path, required=True)
    plan_cmd.add_argument("--image-b", type=Path, required=True)
    plan_cmd.add_argument("--target-a-bytes", type=int, required=True)
    plan_cmd.add_argument("--target-b-bytes", type=int, required=True)
    plan_cmd.add_argument("--output", type=Path, required=True)
    target_cmd = sub.add_parser("check-target", help="RO validate already prepared larger JBOD")
    target_cmd.add_argument("--plan", type=Path, required=True)
    target_cmd.add_argument("--first-disk", type=int, required=True)
    target_cmd.add_argument("--second-disk", type=int, required=True)
    target_cmd.add_argument("--output", type=Path, required=True)
    mount = sub.add_parser("mount-source", help="Image-backed ImDisk RO mount for Commander")
    mount.add_argument("--image-a", type=Path, required=True)
    mount.add_argument("--image-b", type=Path, required=True)
    mount.add_argument("--letter", required=True)
    manifest = sub.add_parser("manifest", help="Hash ALL source files from mounted RO drive")
    manifest.add_argument("--source", type=Path, required=True)
    manifest.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify", help="Hash target and compare to source manifest")
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--target", type=Path, required=True)
    verify.add_argument("--report", type=Path, required=True)
    verify.add_argument("--allow-extra-target-files", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "probe":
        probe()
    elif args.command == "capture":
        print("Captured:", capture_disk(args.disk_number, args.expect_size,
                                         args.expect_first4k, args.output))
    elif args.command == "plan":
        write_json_new(args.output, migration_plan(args.image_a, args.image_b,
                            args.target_a_bytes, args.target_b_bytes))
        print("Plan written, status BLOCKED until target provisioning:", args.output)
    elif args.command == "check-target":
        result = check_provisioned_target(args.plan, args.first_disk, args.second_disk)
        write_json_new(args.output, result)
        print("Target read-only geometry checked; boot/RW remain unverified:", args.output)
    elif args.command == "mount-source":
        mount_source(args.image_a, args.image_b, args.letter)
    elif args.command == "manifest":
        result = manifest_source(args.source, args.output)
        print(f"Manifest: {result['file_count']} files, {result['total_file_bytes']} bytes")
    elif args.command == "verify":
        if args.target.resolve() in args.report.resolve().parents:
            raise RuntimeError("Verification report must be written outside the target disk.")
        result = verify_target(args.manifest, args.target, args.allow_extra_target_files)
        write_json_new(args.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result["passed"]:
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("MIGRATION HALTED:", str(exc), file=sys.stderr)
        sys.exit(1)
