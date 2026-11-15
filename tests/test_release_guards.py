"""Tests that simulate hardware interactions without opening physical drives."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flashbridge_core import (
    DiskInfo, eligible, make_logger, ProxyServer, recv_exact, discover_pair,
)
from test_flashbridge import Fixture, D1, D2


class ReleaseGuardsTests(unittest.TestCase):
    def test_system_and_boot_disks_are_never_eligible(self):
        self.assertFalse(eligible(DiskInfo(0, 1024, 'SSD', 'USB')))
        self.assertFalse(eligible(DiskInfo(5, 1024, 'SSD', 'USB', boot=True)))
        self.assertFalse(eligible(DiskInfo(5, 1024, 'SSD', 'USB', system=True)))
        self.assertFalse(eligible(DiskInfo(5, 1024, 'SSD', 'NVMe')))
        self.assertTrue(eligible(D1))

    def test_jsonl_rollover_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            lg = make_logger(directory=folder)
            lg.max_event_bytes = 600
            lg.event_backups = 2
            for _ in range(20):
                lg.info('TEST', payload='x'*100)
            path = lg.events_path
            self.assertTrue(path.exists())
            self.assertTrue(Path(str(path)+'.1').exists())
            self.assertTrue(Path(str(path)+'.2').exists())
            self.assertFalse(Path(str(path)+'.3').exists())

    def test_proxy_can_bind_ephemeral_localhost_port(self):
        fixture = Fixture()
        try:
            plan = discover_pair([D2,D1], fixture.factory)
            log = make_logger(directory=fixture.root)
            srv = ProxyServer(plan, False, log, port=0, raw_factory=fixture.factory)
            srv.start()
            self.assertTrue(srv.started.wait(5))
            self.assertTrue(srv.ready, srv.last_error)
            self.assertGreater(srv.port,0)
            import socket, struct
            with socket.create_connection(('127.0.0.1', srv.port), timeout=5) as client:
                client.settimeout(5)
                client.sendall(struct.pack('<Q',1))
                info = struct.unpack('<QQQ',recv_exact(client,24))
                self.assertEqual(info[1:],(512,1))
                client.sendall(struct.pack('<Q',5))
            srv.stop()
            srv.join(5)
            self.assertFalse(srv.is_alive())
            srv.close_devices()
        finally:
            fixture.close()


if __name__ == '__main__':
    unittest.main()
