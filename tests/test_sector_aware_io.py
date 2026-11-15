"""Synthetic, non-destructive tests for per-media sector geometry and I/O telemetry."""
from __future__ import annotations
from dataclasses import replace
import json
from pathlib import Path
import socket
import struct
import tempfile
import time
import unittest

from flashbridge_core import (ALIGN, MIB, DiskInfo, JoinedDisk, ProxyServer,
                              disk_write_alignment, discover_pair, make_logger,
                              recv_exact, WRITE_MODE_FAST)
from test_flashbridge import D1, D2, Fixture, PART


class SectorAwareTests(unittest.TestCase):
    def test_device_policy_requires_coherent_report(self):
        assert_policy = self.assertEqual
        basic = DiskInfo(7, 40*MIB, 'SD', 'USB')
        assert_policy(disk_write_alignment(basic), 4096)
        assert_policy(disk_write_alignment(replace(basic, logical_sector_size=512,
                                                          physical_sector_size=512)), 512)
        assert_policy(disk_write_alignment(replace(basic, logical_sector_size=512,
                                                          physical_sector_size=4096)), 4096)
        assert_policy(disk_write_alignment(replace(basic, logical_sector_size=512,
                                                          physical_sector_size=8192)), 8192)
        assert_policy(disk_write_alignment(replace(basic, logical_sector_size=512,
                                                          physical_sector_size=0)), 4096)
        assert_policy(disk_write_alignment(replace(basic, logical_sector_size=0,
                                                          physical_sector_size=512)), 4096)
        assert_policy(disk_write_alignment(replace(basic, logical_sector_size=512,
                                                          physical_sector_size=1024)), 4096)

    def test_reported_512_sector_allows_direct_write_with_no_rmw(self):
        fx = Fixture()
        try:
            d1 = replace(D1, logical_sector_size=512, physical_sector_size=512)
            d2 = replace(D2, logical_sector_size=512, physical_sector_size=512)
            j = JoinedDisk(discover_pair([d1,d2],fx.factory), True, fx.factory)
            try:
                self.assertEqual((j.a.write_alignment, j.b.write_alignment), (512,512))
                pos = 3*MIB+2048  # would have forced two RMW reads in v0.3.1
                prev = j.read_volume(pos-512, 512)
                after = j.read_volume(pos+MIB, 512)
                body = b'M'*MIB
                reads = []
                orig_read = j.a.read_at
                def spy(offset,length):
                    reads.append((offset,length))
                    return orig_read(offset,length)
                j.a.read_at=spy
                stats = j.write_volume(pos,body)
                self.assertEqual(stats['rmw_read_calls'],0)
                self.assertEqual(stats['physical_write_calls'],1)
                self.assertEqual(stats['physical_write_bytes'],MIB)
                self.assertEqual(reads,[])
                self.assertEqual(j.read_volume(pos,MIB),body)
                self.assertEqual(j.read_volume(pos-512,512),prev)
                self.assertEqual(j.read_volume(pos+MIB,512),after)
            finally:
                j.close()
        finally:
            fx.close()

    def test_mixed_512_and_4096_media_at_boundary(self):
        fx=Fixture()
        try:
            first=replace(D1,logical_sector_size=512,physical_sector_size=512)
            second=replace(D2,logical_sector_size=512,physical_sector_size=4096)
            j=JoinedDisk(discover_pair([first,second],fx.factory),True,fx.factory)
            try:
                self.assertEqual((j.a.write_alignment,j.b.write_alignment),(512,4096))
                border=D1.size-PART
                off=border-1024
                payload=b'Q'*4096
                before=j.read_volume(off-512,512)
                after=j.read_volume(off+len(payload),512)
                counters=j.write_volume(off,payload)
                self.assertEqual(counters['physical_write_calls'],2)
                self.assertGreater(counters['rmw_read_calls'],0)
                self.assertEqual(j.read_volume(off,len(payload)),payload)
                self.assertEqual(j.read_volume(off-512,512),before)
                self.assertEqual(j.read_volume(off+len(payload),512),after)
            finally: j.close()
        finally: fx.close()

    def test_512_sector_rejects_misaligned_raw_device_write(self):
        fx=Fixture()
        try:
            a=replace(D1,logical_sector_size=512,physical_sector_size=512)
            b=replace(D2,logical_sector_size=512,physical_sector_size=512)
            j=JoinedDisk(discover_pair([a,b],fx.factory),True,fx.factory)
            try:
                with self.assertRaisesRegex(ValueError, 'Internal alignment violation'):
                    j.a.write_at(1,b'0'*512)
                with self.assertRaisesRegex(ValueError, 'Internal alignment violation'):
                    j.a.write_at(512,b'0'*511)
            finally:j.close()
        finally:fx.close()

    def test_summary_records_wall_active_and_read_wait_separately(self):
        fx=Fixture()
        try:
            a=replace(D1,logical_sector_size=512,physical_sector_size=512)
            b=replace(D2,logical_sector_size=512,physical_sector_size=512)
            plan=discover_pair([a,b],fx.factory)
            logger=make_logger(directory=fx.root)
            srv=ProxyServer(plan,True,logger,port=0,raw_factory=fx.factory,write_mode=WRITE_MODE_FAST)
            srv.start()
            self.assertTrue(srv.started.wait(5))
            self.assertTrue(srv.ready,srv.last_error)
            try:
                with socket.create_connection(('127.0.0.1',srv.port),timeout=5) as c:
                    c.settimeout(10)
                    for i in range(64):
                        c.sendall(struct.pack('<QQQ',3,3*MIB+i*512,512)+b'X'*512)
                        self.assertEqual(struct.unpack('<QQ',recv_exact(c,16)),(0,512))
                        if i==20:
                            time.sleep(0.05)
                            c.sendall(struct.pack('<QQQ',2,0,512))
                            self.assertEqual(struct.unpack('<QQ',recv_exact(c,16)),(0,512))
                            self.assertEqual(recv_exact(c,512).__len__(),512)
                    c.sendall(struct.pack('<Q',5))
            finally:
                srv.stop();srv.join(5);srv.close_devices();logger.close()
            events=[json.loads(line) for f in (fx.root/'logs').glob('*.jsonl') for line in f.read_text().splitlines()]
            event=next(e for e in events if e['event']=='IO_STATS')
            self.assertEqual(event['write_requests'],64)
            self.assertEqual(event['rmw_read_calls'],0)
            self.assertEqual(event['interval_proxy_read_requests'],1)
            self.assertGreater(event['interval_protocol_wait_seconds'],0.02)
            self.assertGreaterEqual(event['interval_proxy_read_seconds'],0)
            # Tiny 512-byte I/O can round both rates to 0.01 MiB/s on slow CI.
            # Verify elapsed vs active time rather than strict rounded-rate order.
            self.assertGreaterEqual(event['interval_active_mib_s'],event['interval_wall_mib_s'])
            self.assertGreater(event['interval_wall_seconds'],event['interval_write_seconds'])
            self.assertEqual(next(e for e in events if e['event']=='WRITE_POLICY')['write_alignments'],{'first':512,'second':512})
        finally:fx.close()

if __name__=='__main__':unittest.main()
