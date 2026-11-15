"""Read-only bottleneck report for FlashBridge JSONL logs (no device access).

Usage: python tools/profile_report.py "<path-to-session>.jsonl"
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PHASES = ('receive_ms','physical_write_ms','flush_ms','readback_ms')

def analyze(path):
    rows = 0
    seconds = 0.0
    size = 0
    durations = {key:0.0 for key in PHASES}
    touched = {}
    faults = 0
    with Path(path).open('r',encoding='utf-8') as f:
        for line in f:
            try: event = json.loads(line)
            except json.JSONDecodeError: continue
            if event.get('event') in ('WRITE_REJECTED','PHYSICAL_WRITE_FAIL','FATAL_PROXY'):
                faults += 1
            if event.get('event') != 'IO_END' or event.get('operation') != 'WRITE':
                continue
            rows += 1
            size += int(event.get('bytes',0))
            seconds += float(event.get('elapsed_ms',0))/1000
            for key in PHASES:
                durations[key] += float(event.get(key,0))
            media = '+'.join(event.get('flushed_media',[])) or 'unknown'
            touched[media] = touched.get(media,0)+1
    return {'write_requests': rows, 'write_gib': size/1024**3,
            'measured_mb_s': size/1e6/seconds if seconds else None,
            'total_request_seconds':seconds,'phase_seconds':{k:v/1000 for k,v in durations.items()},
            'media_flush_counts': touched, 'fault_events':faults}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl',type=Path)
    args=parser.parse_args()
    print(json.dumps(analyze(args.jsonl),indent=2))

if __name__=='__main__':main()
