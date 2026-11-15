"""Fail-injection tests on disposable sparse files. Never touches user storage."""
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flashbridge_core import (RawDevice, ProxyServer, JoinedDisk, make_logger,
                              recv_exact, MIB, PhysicalOperationFailure)
from test_flashbridge import Fixture, D1, D2, PART


class FailDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = Fixture()
        from flashbridge_core import discover_pair
        self.plan = discover_pair([D1,D2], self.fixture.factory)

    def tearDown(self):
        self.fixture.close()

    def _proxy_case(self, failing_stage, disk):
        fixture = self.fixture

        class FaultyRaw(RawDevice):
            def __init__(self, path, size, writable=False):
                self.number = int(path.lower().split('physicaldrive')[-1])
                super().__init__(fixture.mapping[self.number], size, writable)
                self.wrote = False
                self.synced = False

            def write_at(self, offset, data):
                if self.writable and self.number == disk and failing_stage == 'WRITE':
                    exc = OSError(22, 'Injected device unavailable during WRITE')
                    exc.winerror = 55
                    raise exc
                super().write_at(offset, data)
                self.wrote = True

            def sync(self):
                if self.writable and self.number == disk and self.wrote and failing_stage == 'FLUSH':
                    exc = OSError(22, 'Injected device unavailable during FLUSH')
                    exc.winerror = 55
                    raise exc
                super().sync()
                if self.wrote:
                    self.synced = True

            def read_at(self, offset, count):
                if self.writable and self.number == disk and self.synced and failing_stage == 'READBACK':
                    exc = OSError(22, 'Injected device unavailable during READBACK')
                    exc.winerror = 55
                    raise exc
                return super().read_at(offset, count)

        lg = make_logger(directory=fixture.root)
        srv = ProxyServer(self.plan, True, lg, port=0, raw_factory=FaultyRaw)
        srv.start()
        self.assertTrue(srv.started.wait(5))
        self.assertTrue(srv.ready, srv.last_error)
        try:
            with socket.create_connection(('127.0.0.1', srv.port), timeout=5) as conn:
                conn.settimeout(10)
                # Both media involved only when testing disk 11; the first media
                # then succeeds and the second is the actual failing device.
                border = D1.size - PART
                start = (border - 4096) if disk == 11 else 3*MIB
                count = 8192 if disk == 11 else 4096
                conn.sendall(struct.pack('<QQQ', 3, start, count) + b'Z'*count)
                self.assertEqual(struct.unpack('<QQ', recv_exact(conn,16)), (5,0))
                self.assertTrue(srv.failed)
                # Fault latch allows reads and CLOSE, refuses future writes.
                conn.sendall(struct.pack('<Q',5))
        finally:
            srv.stop()
            srv.join(5)
            srv.close_devices()
            lg.close()
        events = []
        for log in (fixture.root/'logs').glob('*.jsonl'):
            events.extend(json.loads(x) for x in log.read_text().splitlines())
        return events

    def test_write_failure_identifies_second_medium_after_boundary(self):
        events = self._proxy_case('WRITE', 11)
        failure = next(x for x in events if x['event'] == 'PHYSICAL_WRITE_FAIL')
        self.assertEqual((failure['physical_disk'], failure['physical_media'], failure['winerror']), (11,'second',55))
        self.assertEqual(failure['phase'],'WRITE')
        self.assertTrue(any(x['event']=='WRITE_REJECTED' for x in events))

    def test_flush_failure_identifies_correct_disk_and_winerror(self):
        events = self._proxy_case('FLUSH',7)
        failure = next(x for x in events if x['event'] == 'PHYSICAL_FLUSH_FAIL')
        self.assertEqual((failure['physical_disk'],failure['physical_media'],failure['winerror']), (7,'first',55))
        self.assertEqual(failure['phase'],'FLUSH')
        unavailable = next(x for x in events if x['event']=='DEVICE_IO_UNAVAILABLE')
        self.assertEqual((unavailable['physical_disk'], unavailable['during_stage']), (7,'FLUSH'))

    def test_readback_failure_identifies_correct_disk_and_winerror(self):
        events = self._proxy_case('READBACK',7)
        failure = next(x for x in events if x['event'] == 'PHYSICAL_READBACK_FAIL')
        self.assertEqual((failure['physical_disk'],failure['physical_media'],failure['winerror']), (7,'first',55))
        self.assertEqual(failure['phase'],'READBACK')
        self.assertEqual(failure['physical_offset'], 4*MIB)


if __name__ == '__main__':
    unittest.main()
