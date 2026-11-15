"""No physical devices accessed. Regression tests for fused 4KiB-safe writes."""
from __future__ import annotations

import random
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flashbridge_core import ALIGN, IO_CHUNK, JoinedDisk, MIB, RawDevice, discover_pair
from test_flashbridge import Fixture, D1, D2, PART


class TestFusedWrites(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.plan = discover_pair([D1, D2], self.fx.factory)
        self.dev = JoinedDisk(self.plan, True, self.fx.factory)
        self.reads = []
        self.writes = []
        for disk in (self.dev.a, self.dev.b):
            old_read = disk.read_at
            old_write = disk.write_at
            def read(pos, size, *, old=old_read, device=disk):
                self.reads.append((device.path, pos, size))
                return old(pos, size)
            def write(pos, value, *, old=old_write, device=disk):
                self.writes.append((device.path, pos, len(value)))
                return old(pos, value)
            disk.read_at = read
            disk.write_at = write

    def tearDown(self):
        self.dev.close()
        self.fx.close()

    def test_misaligned_megabyte_is_one_physical_write(self):
        pos = 3*MIB + 2048
        surrounding_start = pos - 2048
        baseline = self.dev.read_volume(surrounding_start, MIB + 4096)
        self.reads.clear()
        payload = bytes(range(256))*4096
        stats = self.dev.write_volume(pos, payload)
        self.assertEqual(stats, dict(physical_write_calls=1,
                                     physical_write_bytes=MIB+ALIGN,
                                     rmw_read_calls=2, rmw_read_bytes=8192))
        self.assertEqual(len(self.writes), 1)
        self.assertEqual(self.writes[0][1] % ALIGN, 0)
        self.assertEqual(self.writes[0][2], MIB + ALIGN)
        self.assertEqual([r[2] for r in self.reads], [ALIGN, ALIGN])
        self.assertEqual(self.dev.read_volume(surrounding_start, MIB+4096),
                         baseline[:2048]+payload+baseline[2048+len(payload):])

    def test_already_aligned_megabyte_does_not_read_edges(self):
        pos = 3*MIB
        payload = b'B'*MIB
        stats = self.dev.write_volume(pos, payload)
        self.assertEqual(stats['physical_write_calls'], 1)
        self.assertEqual(stats['physical_write_bytes'], MIB)
        self.assertEqual(stats['rmw_read_calls'], 0)
        self.assertEqual(len(self.reads), 0)
        self.assertEqual(self.dev.read_volume(pos, MIB), payload)

    def test_single_4k_block_read_only_once(self):
        pos = 3*MIB + 512
        before = self.dev.read_volume(3*MIB, ALIGN)
        self.reads.clear()
        stats = self.dev.write_volume(pos, b'S'*512)
        self.assertEqual(stats['physical_write_calls'], 1)
        self.assertEqual(stats['physical_write_bytes'], ALIGN)
        self.assertEqual(stats['rmw_read_calls'], 1)
        self.assertEqual(self.dev.read_volume(3*MIB, ALIGN),
                         before[:512] + b'S'*512 + before[1024:])

    def test_cross_media_at_boundary_only_writes_each_device_once(self):
        pos = D1.size - PART - 1536
        original = self.dev.read_volume(pos-512, 5120+1024)
        self.reads.clear()
        payload = bytes([0xDA])*5120
        stats = self.dev.write_volume(pos, payload)
        self.assertEqual(stats['physical_write_calls'], 2)
        self.assertEqual(len(self.writes), 2)
        self.assertNotEqual(self.writes[0][0], self.writes[1][0])
        self.assertEqual(self.dev.read_volume(pos-512, len(original)),
                         original[:512] + payload + original[512+len(payload):])

    def test_random_partial_updates_preserve_nonrequested_bytes(self):
        rng = random.Random(231107)
        pos = 7*MIB
        reference = bytearray(self.dev.read_volume(pos, 2*MIB))
        for _ in range(64):
            off = 512*rng.randrange(0, (2*MIB-8192)//512)
            size = 512*rng.randrange(1, 17)
            payload = bytes([rng.randrange(1, 255)])*size
            stats = self.dev.write_volume(pos+off, payload)
            self.assertEqual(stats['physical_write_calls'], 1)
            reference[off:off+size] = payload
        self.assertEqual(self.dev.read_volume(pos, 2*MIB), reference)

    def test_large_nonproxy_call_stays_bounded_and_data_exact(self):
        pos = 4*MIB+2048
        payload = bytes(range(256))*(2*MIB//256) + b'Q'*512
        self.assertGreater(len(payload), IO_CHUNK)
        stats = self.dev.write_volume(pos,payload)
        self.assertEqual(stats['physical_write_calls'], 3)
        self.assertEqual(self.dev.read_volume(pos,len(payload)), payload)

    def test_fast_proxy_reports_fused_io_counters(self):
        # Whole-path assertions for log telemetry are in test_write_modes.py;
        # this test deliberately covers only the raw geometry contract.
        pos=4*MIB+2048
        stats=self.dev.write_volume(pos, b'M'*MIB)
        for key in ('physical_write_calls','physical_write_bytes',
                    'rmw_read_calls','rmw_read_bytes'):
            self.assertIsInstance(stats[key], int)
        self.assertEqual(stats['physical_write_calls'], 1)
        self.assertEqual(stats['rmw_read_calls'], 2)

if __name__ == '__main__':
    unittest.main()
