"""No physical devices accessed: deterministic sparse-file FAT32 tests."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import socket
import struct
import tempfile
import time
import unittest
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from flashbridge_core import (
    DiskInfo, RawDevice, discover_pair, JoinedDisk, ProxyServer,
    make_logger, recv_exact, GIB, MIB, ALIGN,
    plan_missing_files, copy_only_missing, discover_all_pairs
)

D1 = DiskInfo(7, 40*MIB, 'CARD X', 'USB')
D2 = DiskInfo(11, 50*MIB, 'CARD Y', 'USB')
PART = 1*MIB
BPS = 512
VOLUME = 70*MIB

class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='flashbridge-tests-')
        self.root = Path(self.tmp.name)
        self.mapping = {7: self.root/'card7.bin', 11:self.root/'card11.bin'}
        for d in (D1,D2):
            with self.mapping[d.number].open('wb') as f:
                f.truncate(d.size)
        self.build_card(D1, declared=VOLUME, fat=1120)
        self.build_card(D2, declared=45*MIB, fat=722)

    def close(self): self.tmp.cleanup()

    def factory(self, path, size, writable=False):
        no = int(path.lower().split('physicaldrive')[-1])
        return RawDevice(self.mapping[no], size, writable)

    def build_card(self, disk, declared, fat):
        nsecs = declared//BPS
        boot=bytearray(BPS)
        boot[0:3]=b'\xeb\x58\x90'
        boot[3:11]=b'MSWIN4.1'
        struct.pack_into('<H',boot,11,BPS)
        boot[13]=1
        struct.pack_into('<H',boot,14,32)
        boot[16]=2
        struct.pack_into('<I',boot,32,nsecs)
        struct.pack_into('<I',boot,36,fat)
        struct.pack_into('<I',boot,44,2)
        struct.pack_into('<H',boot,48,1)
        struct.pack_into('<H',boot,50,6)
        boot[82:90]=b'FAT32   '
        boot[510:512]=b'\x55\xaa'
        backup=boot[:];backup[65]=0;boot[65]=1
        fs=bytearray(BPS);fs[0:4]=b'RRaA';fs[484:488]=b'rrAa';fs[508:512]=b'\0\0\x55\xaa'
        mbr=bytearray(512)
        mbr[510:512]=b'\x55\xaa'
        p=446
        mbr[p+4]=0x0b
        struct.pack_into('<I',mbr,p+8,2048)
        struct.pack_into('<I',mbr,p+12,nsecs)
        with self.mapping[disk.number].open('r+b') as f:
            f.write(mbr)
            f.seek(PART);f.write(boot)
            f.seek(PART+BPS);f.write(fs)
            f.seek(PART+6*BPS);f.write(backup)
            f.seek(PART+7*BPS);f.write(fs)
            fat1=PART+32*BPS
            fat2=fat1+fat*BPS
            f.seek(fat1);f.write(b'\xF8\xFF\xFF\x0F\xFF\xFF\xFF\x0F'+bytes(4088))
            f.seek(fat2);f.write(b'\xF8\xFF\xFF\x0F\xFF\xFF\xFF\x0F'+bytes(4088))


class FlashBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture=Fixture()
        self.plan=discover_pair([D2,D1], self.fixture.factory)

    def tearDown(self): self.fixture.close()

    def test_order_is_evidence_based_not_disk_number_or_size(self):
        self.assertEqual((self.plan.first.number,self.plan.second.number),(7,11))
        self.assertEqual(self.plan.volume_bytes,VOLUME)
        self.assertEqual(self.plan.fat.sector_size,512)
        self.assertTrue(self.plan.read_write_safe)

    def test_automatic_pair_ignores_unrelated_external_ssd(self):
        external=DiskInfo(15,500*MIB,'unrelated external SSD','USB')
        self.fixture.mapping[15]=self.fixture.root/'external.bin'
        with self.fixture.mapping[15].open('wb') as f:
            f.truncate(external.size)
        p=discover_all_pairs([D2, external,D1], self.fixture.factory)
        self.assertEqual((p.first.number,p.second.number),(7,11))

    def test_first_is_not_necessarily_larger_card(self):
        self.assertLess(self.plan.first.size,self.plan.second.size)

    def test_do_not_guess_when_no_spanning_fat32(self):
        # Both cards carry only local FAT32, so order is unprovable.
        self.fixture.build_card(D1,declared=34*MIB, fat=547)
        with self.assertRaisesRegex(RuntimeError,'Cannot prove media order'):
            discover_pair([D1,D2],self.fixture.factory)

    def test_cross_boundary_raw_write(self):
        j=JoinedDisk(self.plan,True,self.fixture.factory)
        try:
            at=D1.size-PART-1536
            before=j.read_volume(at-512,512)
            after=j.read_volume(at+5120,512)
            payload=b'Q'*5120
            j.write_volume(at,payload)
            j.sync()
            self.assertEqual(j.read_volume(at,len(payload)),payload)
            self.assertEqual(j.read_volume(at-512,512),before)
            self.assertEqual(j.read_volume(at+5120,512),after)
            self.assertTrue(self.fixture.mapping[11].stat().st_size==D2.size)
        finally:j.close()

    def test_flush_only_touched_media_preserves_write_verification_barrier(self):
        j = JoinedDisk(self.plan, True, self.fixture.factory)
        calls = []
        try:
            j.a.sync = lambda: calls.append('first')
            j.b.sync = lambda: calls.append('second')
            border = D1.size - PART
            self.assertEqual(j.sync_volume_range(0, 4096), ('first',))
            self.assertEqual(calls, ['first'])
            calls.clear()
            self.assertEqual(j.sync_volume_range(border + 4096, 4096), ('second',))
            self.assertEqual(calls, ['second'])
            calls.clear()
            self.assertEqual(j.sync_volume_range(border - 4096, 8192), ('first', 'second'))
            self.assertEqual(calls, ['first', 'second'])
            calls.clear()
            self.assertEqual(j.sync_volume_range(border, 0), ())
            self.assertEqual(calls, [])
        finally:
            j.close()

    def test_adjacent_partial_metadata_writes_preserve_neighboring_bytes(self):
        j = JoinedDisk(self.plan, True, self.fixture.factory)
        try:
            at = 3*MIB
            baseline = j.read_volume(at, 4096)
            j.write_volume(at, b'B'*2048)
            j.write_volume(at+2048, b'C'*512)
            j.sync_volume_range(at, 2560)
            self.assertEqual(j.read_volume(at, 4096), b'B'*2048 + b'C'*512 + baseline[2560:])
        finally:
            j.close()

    def test_read_only_device_rejects_write(self):
        j=JoinedDisk(self.plan,False,self.fixture.factory)
        try:
            with self.assertRaises(PermissionError):
                j.write_volume(0,b'A'*512)
        finally:j.close()

    def test_copy_only_missing_never_replaces_existing_and_resumes_partials(self):
        root=self.fixture.root
        source=root/'source'; target=root/'dest'
        (source/'Music').mkdir(parents=True)
        (target/'Music').mkdir(parents=True)
        original=b'A'*20000+b'B'*10000
        (source/'Music'/'song.flac').write_bytes(original)
        (source/'Music'/'existing.flac').write_bytes(b'NEW_SOURCE')
        (target/'Music'/'existing.flac').write_bytes(b'EXISTING_TARGET')
        partial=(target/'Music'/'song.flac.flashbridge.partial')
        partial.write_bytes(original[:17000])
        p=plan_missing_files(source,target)
        self.assertEqual(len(p.entries),1)
        self.assertEqual(p.existing_count,1)
        self.assertEqual(p.differing_size_count,1)
        summary=copy_only_missing(p,verify=True)
        self.assertEqual(summary['completed'],1)
        self.assertEqual((target/'Music'/'song.flac').read_bytes(),original)
        self.assertEqual((target/'Music'/'existing.flac').read_bytes(),b'EXISTING_TARGET')
        self.assertFalse(partial.exists())
        self.assertEqual(len(plan_missing_files(source,target).entries),0)

    def test_bad_partial_is_rejected_without_overwrite(self):
        root=self.fixture.root
        source=root/'source'; target=root/'dest'
        (source/'Music').mkdir(parents=True)
        (target/'Music').mkdir(parents=True)
        (source/'Music'/'song.flac').write_bytes(b'A'*10000)
        part=target/'Music'/'song.flac.flashbridge.partial'
        part.write_bytes(b'WRONG')
        p=plan_missing_files(source,target)
        with self.assertRaisesRegex(RuntimeError,'does not match'):
            copy_only_missing(p)
        self.assertEqual(part.read_bytes(),b'WRONG')
        self.assertFalse((target/'Music'/'song.flac').exists())

    def test_proxy_survives_physical_write_failure_for_clean_unmount(self):
        fixture=self.fixture
        class FaultyRaw(RawDevice):
            def __init__(self,path,size,writable=False):
                no=int(path.split('PhysicalDrive')[-1])
                super().__init__(fixture.mapping[no],size,writable)
            def write_at(self,pos,data):
                if self.writable: raise OSError(22,'Injected physical write failure')
                return super().write_at(pos,data)
        log=make_logger(directory=fixture.root)
        srv=ProxyServer(self.plan,True,log,port=0,raw_factory=FaultyRaw)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));srv.port=sock.getsockname()[1]
        srv.start();self.assertTrue(srv.started.wait(5));self.assertTrue(srv.ready,srv.last_error)
        with socket.create_connection(('127.0.0.1',srv.port),timeout=5) as client:
            client.settimeout(15)
            client.sendall(struct.pack('<QQQ',3, 3*MIB, 4096)+b'W'*4096)
            self.assertEqual(struct.unpack('<QQ',recv_exact(client,16)),(5,0))
            self.assertTrue(srv.failed)
            client.sendall(struct.pack('<QQQ',2,3*MIB,4096))
            self.assertEqual(struct.unpack('<QQ',recv_exact(client,16)),(0,4096))
            self.assertEqual(len(recv_exact(client,4096)),4096)
            client.sendall(struct.pack('<Q',5))
        srv.stop();srv.join(5)
        self.assertFalse(srv.is_alive())
        srv.close_devices()
        log.close()

    def test_proxy_large_write_66mib_and_flush_readback(self):
        log=make_logger(directory=self.fixture.root)
        srv=ProxyServer(self.plan,True,log, port=0,raw_factory=self.fixture.factory)
        # Pick a free port before starting.
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            srv.port=sock.getsockname()[1]
        srv.start()
        self.assertTrue(srv.started.wait(5))
        self.assertTrue(srv.ready, srv.last_error)
        with socket.create_connection(('127.0.0.1',srv.port),timeout=10) as conn:
            conn.settimeout(120)
            conn.sendall(struct.pack('<Q',1))
            size, align, flags=struct.unpack('<QQQ',recv_exact(conn,24))
            self.assertEqual((size,align,flags),(VOLUME,512,0))
            large=66*MIB
            pos=3*MIB
            conn.sendall(struct.pack('<QQQ',3,pos,large))
            # Distinct reproducible megabyte chunks; spans card boundary.
            chunk = bytes(range(256)) * 4096
            for i in range(66):
                conn.sendall(chunk)
            err, n=struct.unpack('<QQ',recv_exact(conn,16))
            self.assertEqual((err,n),(0,large))
            conn.sendall(struct.pack('<QQQ',2,pos+40*MIB,4096))
            err,n=struct.unpack('<QQ',recv_exact(conn,16))
            self.assertEqual((err,n),(0,4096))
            self.assertEqual(recv_exact(conn,4096),chunk[:4096])
            conn.sendall(struct.pack('<Q',5))
        srv.stop()
        srv.join(5)
        self.assertFalse(srv.is_alive())
        self.assertFalse(srv.failed,srv.last_error)
        self.assertEqual(srv.bytes_written,66*MIB)
        srv.close_devices()
        log.close()
        text=(list((self.fixture.root/'logs').glob('*.jsonl'))[0]).read_text()
        self.assertIn('IO_END',text)
        self.assertIn('flush_completed',text)
        self.assertIn('physical_write_ms',text)
        self.assertIn('readback_ms',text)
        self.assertIn('flushed_media',text)


# Context manager convenience for fixture tests if needed.
JoinedDisk.__enter__ = lambda self: self
JoinedDisk.__exit__ = lambda self, *_: self.close()

if __name__=='__main__':unittest.main()
