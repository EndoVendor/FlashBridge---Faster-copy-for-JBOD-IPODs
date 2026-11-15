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

if __name__=='__main__':unittest.main()
