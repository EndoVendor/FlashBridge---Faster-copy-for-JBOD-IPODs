"""Fast-versus-verified protocol and fault tests on disposable fake media only."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import struct
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flashbridge_core import (MIB, ProxyServer, RawDevice, discover_pair,
                              make_logger, recv_exact, WRITE_MODE_FAST,
                              WRITE_MODE_VERIFIED)
from test_flashbridge import D1, D2, Fixture, PART


class TestPolicies(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.plan = discover_pair([D1, D2], self.fx.factory)

    def tearDown(self):
        self.fx.close()

    def run_request(self, *, mode, phase=None, second=False, payload_size=4096):
        fx = self.fx
        observation = {'readback':0, 'flush':0, 'wrote':0}
        class ObservedRaw(RawDevice):
            def __init__(self, path, size, writable=False):
                self.number = int(path.lower().split('physicaldrive')[-1])
                self.did_write = False
                self.did_flush = False
                super().__init__(fx.mapping[self.number], size, writable)
            def read_at(self, offset, count):
                if self.did_flush and self.writable:
                    observation['readback'] += count
                    if phase == 'READBACK':
                        raise OSError(22, 'synthetic READBACK failure')
                return super().read_at(offset, count)
            def write_at(self, offset, data):
                if self.writable and phase == 'WRITE':
                    raise OSError(22, 'synthetic WRITE failure')
                super().write_at(offset, data)
                self.did_write = True
                observation['wrote'] += len(data)
            def sync(self):
                if self.did_write:
                    observation['flush'] += 1
                    if phase == 'FLUSH':
                        raise OSError(22, 'synthetic FLUSH failure')
                    self.did_flush = True
                return super().sync()
        logger = make_logger(directory=fx.root)
        server = ProxyServer(self.plan, True, logger, port=0, raw_factory=ObservedRaw,
                             write_mode=mode)
        server.start()
        self.assertTrue(server.started.wait(5))
        self.assertTrue(server.ready, server.last_error)
        start = (D1.size - PART - 4096) if second else 3*MIB
        body = b'X' * payload_size
        try:
            with socket.create_connection(('127.0.0.1', server.port), timeout=5) as c:
                c.settimeout(90)
                c.sendall(struct.pack('<QQQ', 3, start, len(body)) + body)
                result = struct.unpack('<QQ', recv_exact(c, 16))
                c.sendall(struct.pack('<Q', 5))
        finally:
            server.stop()
            server.join(10)
            self.assertFalse(server.is_alive())
            server.close_devices()
            logger.close()
        events = []
        for f in (fx.root/'logs').glob('*.jsonl'):
            events.extend(json.loads(line) for line in f.read_text().splitlines())
        return result, observation, server, events

    def test_fast_has_flush_but_no_block_readback_or_sha(self):
        result, observed, srv, events = self.run_request(mode=WRITE_MODE_FAST)
        self.assertEqual(result, (0,4096))
        self.assertEqual(observed['flush'],1)
        self.assertEqual(observed['readback'],0)
        self.assertEqual(srv.bytes_written,4096)
        self.assertEqual(srv.verified_bytes,0)
        done = next(e for e in events if e['event']=='IO_END')
        self.assertFalse(done['readback_performed'])
        self.assertIsNone(done['hash_sha256'])
        self.assertEqual(done['readback_ms'],0)
        self.assertEqual(next(e for e in events if e['event']=='WRITE_POLICY')['mode'],'fast')

    def test_verified_readback_sha_is_retained(self):
        result, observed, srv, events = self.run_request(mode=WRITE_MODE_VERIFIED)
        self.assertEqual(result,(0,4096))
        self.assertGreaterEqual(observed['readback'],4096)
        self.assertEqual(observed['flush'],1)
        self.assertEqual(srv.verified_bytes,4096)
        done = next(e for e in events if e['event']=='IO_END')
        self.assertTrue(done['readback_performed'])
        self.assertEqual(len(done['hash_sha256']),64)

    def test_fast_still_fails_closed_on_flush_failure(self):
        result, observed, srv, events = self.run_request(mode=WRITE_MODE_FAST,phase='FLUSH')
        self.assertEqual(result,(5,0))
        self.assertTrue(srv.failed)
        self.assertTrue(any(e['event']=='PHYSICAL_FLUSH_FAIL' for e in events))
        self.assertTrue(any(e['event']=='WRITE_REJECTED' for e in events))

    def test_fast_still_fails_closed_on_raw_write_failure(self):
        result, observed, srv, events = self.run_request(mode=WRITE_MODE_FAST,phase='WRITE')
        self.assertEqual(result,(5,0))
        self.assertTrue(srv.failed)
        self.assertTrue(any(e['event']=='PHYSICAL_WRITE_FAIL' for e in events))

    def test_verified_rejects_readback_error_while_fast_does_not_readback(self):
        result, observed, srv, events = self.run_request(mode=WRITE_MODE_VERIFIED,phase='READBACK')
        self.assertEqual(result,(5,0))
        self.assertTrue(srv.failed)
        self.assertTrue(any(e['event']=='PHYSICAL_READBACK_FAIL' for e in events))
        # fresh fixture prevents filesystem state from influencing the next test

    def test_fast_large_write_crosses_both_media(self):
        result, observed, srv, events = self.run_request(mode=WRITE_MODE_FAST,
                                                        second=True,payload_size=8*MIB)
        self.assertEqual(result,(0,8*MIB))
        self.assertEqual(observed['flush'],2)
        self.assertEqual(observed['readback'],0)
        self.assertEqual(srv.bytes_written,8*MIB)

    def test_fast_samples_normal_successes_but_preserves_counters(self):
        fx=self.fx
        logger=make_logger(directory=fx.root)
        srv=ProxyServer(self.plan,True,logger,port=0,raw_factory=fx.factory,write_mode=WRITE_MODE_FAST)
        srv.start();self.assertTrue(srv.started.wait(5));self.assertTrue(srv.ready,srv.last_error)
        try:
            with socket.create_connection(('127.0.0.1',srv.port),timeout=5) as c:
                c.settimeout(15)
                for i in range(66):
                    c.sendall(struct.pack('<QQQ',3,3*MIB+i*4096,4096)+b'Z'*4096)
                    self.assertEqual(struct.unpack('<QQ',recv_exact(c,16)),(0,4096))
                c.sendall(struct.pack('<Q',5))
        finally:
            srv.stop();srv.join(5);self.assertFalse(srv.is_alive());srv.close_devices();logger.close()
        e=[]
        for f in (fx.root/'logs').glob('*.jsonl'):
            e.extend(json.loads(line) for line in f.read_text().splitlines())
        self.assertEqual(srv.write_requests,66)
        self.assertEqual(srv.bytes_written,66*4096)
        self.assertEqual(srv.verified_bytes,0)
        # Small metadata writes are recorded individually; large data writes sampled.
        self.assertTrue(any(x['event']=='IO_STATS' for x in e))
        self.assertTrue(any(x['event']=='IO_END' for x in e))

    def test_invalid_policy_rejected_before_connecting_to_disk(self):
        logger=make_logger(directory=self.fx.root)
        try:
            with self.assertRaisesRegex(ValueError,'Unsupported write mode'):
                ProxyServer(self.plan,True,logger,port=0,write_mode='unsafe')
        finally:
            logger.close()

if __name__=='__main__':unittest.main()
