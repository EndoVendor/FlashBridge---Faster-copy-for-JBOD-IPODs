"""Profile analysis does not access devices or modify logs."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from profile_report import analyze

class ProfileReportTests(unittest.TestCase):
    def test_report_counts_timings_and_faults(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'run.jsonl'
            rows=[
                {'event':'IO_END','operation':'WRITE','bytes':1000000,'elapsed_ms':200,
                 'receive_ms':10,'physical_write_ms':40,'flush_ms':100,'readback_ms':45,
                 'flushed_media':['first']},
                {'event':'IO_END','operation':'WRITE','bytes':1000000,'elapsed_ms':200,
                 'receive_ms':10,'physical_write_ms':40,'flush_ms':100,'readback_ms':45,
                 'flushed_media':['second']},
                {'event':'WRITE_REJECTED','error':'fake'},
            ]
            path.write_text('\n'.join(map(json.dumps,rows))+'\n',encoding='utf-8')
            stats=analyze(path)
            self.assertEqual(stats['write_requests'],2)
            self.assertEqual(stats['fault_events'],1)
            self.assertEqual(stats['media_flush_counts'],{'first':1,'second':1})
            self.assertAlmostEqual(stats['measured_mb_s'],5.)
            self.assertAlmostEqual(stats['phase_seconds']['flush_ms'],0.2)

    def test_fast_samples_not_mistaken_for_session_totals(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'fast.jsonl'
            events = [
                {'event':'WRITE_POLICY','mode':'fast'},
                {'event':'IO_END','operation':'WRITE','bytes':1048576,
                 'elapsed_ms':37,'physical_write_ms':34,'flush_ms':0.1,
                 'readback_ms':0,'readback_performed':False,'write_mode':'fast'},
                {'event':'IO_STATS','mode':'fast','total_bytes_written':67108864,
                 'write_requests':64,'average_active_mib_s':28.1,
                 'physical_write_seconds':2.2,'flush_seconds':0.02,'readback_seconds':0,
                 'physical_write_calls':64, 'physical_write_bytes':67239936,
                 'rmw_read_calls':128, 'rmw_read_bytes':524288},
            ]
            path.write_text('\n'.join(map(json.dumps,events))+'\n')
            result=analyze(path)
            self.assertTrue(result['sampled_successes'])
            self.assertEqual(result['write_requests'],1)
            self.assertEqual(result['aggregate_confirmed_bytes'],67108864)
            self.assertEqual(result['aggregate_confirmed_requests'],64)
            self.assertEqual(result['aggregate_active_mib_s'],28.1)
            self.assertEqual(result['aggregate_physical_io']['physical_write_calls_per_request'],1)
            self.assertEqual(result['aggregate_physical_io']['rmw_reads_per_request'],2)

            self.assertIn('samples ONLY',result['sample_warning'])

if __name__=='__main__':unittest.main()
