"""No physical media or ImDisk: synthetic checks for migration preflight."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

import flashbridge_migrate as m


def _make_pair(folder: Path):
    """Sparse synthetic linear two-part FAT32 image, not a real iPod boot image."""
    a, b = folder/"A.img", folder/"B.img"
    # 288 MiB combined, 274 MiB FAT32; FAT32 has 70,000 clusters.
    with a.open("xb") as f:
        f.truncate(192*1024*1024)
    with b.open("xb") as f:
        f.truncate(96*1024*1024)
    boot = bytearray(512)
    boot[510:512] = b"\x55\xaa"
    struct.pack_into("<H", boot, 11, 512)
    boot[13] = 8  # sectors / cluster
    struct.pack_into("<H", boot, 14, 32)  # reserved
    boot[16] = 2
    struct.pack_into("<I", boot, 32, 32+1200+8*70000)
    struct.pack_into("<I", boot, 36, 600)
    struct.pack_into("<I", boot, 44, 2)
    struct.pack_into("<H", boot, 48, 1)
    struct.pack_into("<H", boot, 50, 6)
    boot[82:87] = b"FAT32"
    mbr = bytearray(512)
    mbr[510:512] = b"\x55\xaa"
    entry = 446
    mbr[entry+4] = 0x0C
    struct.pack_into("<I", mbr, entry+8, 8)
    struct.pack_into("<I", mbr, entry+12, 32+1200+8*70000)
    fsinfo = bytearray(512)
    fsinfo[0:4] = b"RRaA"
    fsinfo[484:488] = b"rrAa"
    fsinfo[508:512] = b"\x00\x00\x55\xaa"
    pstart = 4096
    fat1 = pstart + 32*512
    fat2 = fat1 + 600*512
    with a.open("r+b") as f:
        f.seek(0); f.write(mbr)
        f.seek(pstart); f.write(boot)
        f.seek(pstart+512); f.write(fsinfo)
        f.seek(pstart+6*512); f.write(boot)
        f.seek(fat1); f.write(b"\xF8\xFF\xFF\x0F\xFF\xFF\xFF\x0F")
        f.seek(fat2); f.write(b"\xF8\xFF\xFF\x0F\xFF\xFF\xFF\x0F")
    for image in (a,b):
        m.write_json_new(m.capture_info_path(image), {
            "schema": m.CAPTURE_SCHEMA, "image_name": image.name,
            "bytes": image.stat().st_size,
            "first4k_sha256": m.first_fingerprint(image),
            "sha256": m.file_digest(image),
        })
    return a,b


class MigrationPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.a, cls.b = _make_pair(cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_source_recognized_across_boundary(self):
        plan = m.reconstruct_plan(self.a, self.b)
        self.assertEqual(plan.first.size, 192*1024*1024)
        self.assertGreater(plan.fat.end, plan.first.size)
        self.assertLess(plan.fat.end, plan.combined)
        self.assertFalse(plan.read_write_safe)

    def test_source_images_wrong_order_fails_closed(self):
        with self.assertRaises(RuntimeError):
            m.reconstruct_plan(self.b, self.a, verify=False)

    def test_target_growth_plan_and_no_raw_cloning(self):
        plan = m.migration_plan(self.a, self.b, 1024*1024*1024, 1024*1024*1024)
        self.assertEqual(plan["target_combined_bytes"], 2*1024**3)
        self.assertFalse(plan["raw_clone_each_card_allowed"])
        self.assertIn("BLOCKED", plan["status"])
        self.assertEqual(plan["source_a_bytes"], 192*1024*1024)

    def test_equal_or_larger_than_512_lba_limit_rejected(self):
        with self.assertRaises(ValueError):
            m.migration_plan(self.a,self.b,192*1024*1024,96*1024*1024)
        with self.assertRaises(ValueError):
            m.migration_plan(self.a,self.b,1<<40,1<<40)

    def test_capture_hash_mismatch_is_no_go(self):
        path = m.capture_info_path(self.a)
        original = path.read_text(encoding="utf-8")
        try:
            record = json.loads(original)
            record["sha256"] = "0"*64
            path.write_text(json.dumps(record),encoding="utf-8")
            with self.assertRaises(RuntimeError):
                m.reconstruct_plan(self.a,self.b)
        finally:
            path.write_text(original,encoding="utf-8")

    def test_manifest_includes_hidden_rockbox_and_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, target = root/"source",root/"target"
            source.mkdir(); target.mkdir()
            (source/".rockbox").mkdir()
            (source/"Music").mkdir()
            (source/".rockbox"/"config.cfg").write_bytes(b"volume: -10\n")
            (source/"Music"/"song.flac").write_bytes(b"FLAC CONTENT TEST")
            (source/"empty").mkdir()
            dest = root/"manifest.json"
            result = m.manifest_source(source, dest)
            self.assertEqual(result["file_count"],2)
            self.assertIn(".rockbox/config.cfg",[x["path"] for x in result["files"]])
            self.assertIn("empty",result["directories"])
            shutil.copytree(source,target,dirs_exist_ok=True)
            self.assertTrue(m.verify_target(dest,target)["passed"])
            (target/"Music"/"song.flac").write_bytes(b"CORRUPTED CONTENT")
            report = m.verify_target(dest,target)
            self.assertFalse(report["passed"])
            self.assertEqual(report["mismatched"],["Music/song.flac"])

    def test_extras_are_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); s=root/"s"; t=root/"t"; s.mkdir(); t.mkdir()
            (s/"track.ape").write_bytes(b"x")
            (t/"track.ape").write_bytes(b"x")
            (t/"other.bin").write_bytes(b"y")
            mf=root/"manifest.json"
            m.manifest_source(s,mf)
            self.assertFalse(m.verify_target(mf,t)["passed"])
            self.assertTrue(m.verify_target(mf,t,allow_extras=True)["passed"])

    def test_no_manifest_into_mounted_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            with self.assertRaises(ValueError):
                m.manifest_source(folder, folder/"inside.json")

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"plan.json"
            m.write_json_new(path,{"ok":True})
            with self.assertRaises(FileExistsError):
                m.write_json_new(path,{"ok":False})
            self.assertTrue(json.loads(path.read_text())["ok"])


if __name__ == "__main__":
    unittest.main()
