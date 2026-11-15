"""Read-only performance report for FlashBridge JSONL logs (no device access).

Usage: python tools/profile_report.py "<path-to-session>.jsonl"
Fast mode samples successful IO_END records; IO_STATS carries cumulative totals.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PHASES = ('receive_ms', 'physical_write_ms', 'flush_ms', 'readback_ms')

def analyze(path):
    rows = 0
    seconds = 0.0
    sampled_size = 0
    durations = {key: 0.0 for key in PHASES}
    touched = {}
    faults = 0
    policy = None
    aggregate = None
    with Path(path).open('r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get('event')
            if kind == 'WRITE_POLICY':
                policy = event.get('mode')
            if kind == 'IO_STATS':
                aggregate = event
            if kind in ('WRITE_REJECTED', 'PHYSICAL_WRITE_FAIL',
                        'PHYSICAL_FLUSH_FAIL', 'PHYSICAL_READBACK_FAIL', 'FATAL_PROXY'):
                faults += 1
            if kind != 'IO_END' or event.get('operation') != 'WRITE':
                continue
            rows += 1
            sampled_size += int(event.get('bytes', 0))
            seconds += float(event.get('elapsed_ms', 0)) / 1000
            for key in PHASES:
                durations[key] += float(event.get(key, 0))
            media = '+'.join(event.get('flushed_media', [])) or 'unknown'
            touched[media] = touched.get(media, 0) + 1
            if policy is None:
                policy = event.get('write_mode')
    sampled = policy == 'fast'
    result = {
        'write_policy': policy,
        'sampled_successes': sampled,
        'write_requests': rows,
        'write_gib': sampled_size / 1024**3,
        'measured_mb_s': sampled_size / 1e6 / seconds if seconds else None,
        'total_request_seconds': seconds,
        'phase_seconds': {k: v / 1000 for k, v in durations.items()},
        'media_flush_counts': touched,
        'fault_events': faults,
    }
    if aggregate is not None:
        result['aggregate_confirmed_bytes'] = int(aggregate['total_bytes_written'])
        result['aggregate_confirmed_requests'] = int(aggregate['write_requests'])
        result['aggregate_active_mib_s'] = float(aggregate.get('average_active_mib_s',0))
        result['aggregate_phase_seconds'] = {
            'physical_write': float(aggregate.get('physical_write_seconds',0)),
            'flush': float(aggregate.get('flush_seconds',0)),
            'readback': float(aggregate.get('readback_seconds',0)),
        }
        io_count_keys = ('physical_write_calls', 'physical_write_bytes',
                         'rmw_read_calls', 'rmw_read_bytes')
        if any(key in aggregate for key in io_count_keys):
            result['aggregate_physical_io'] = {
                key: int(aggregate.get(key, 0)) for key in io_count_keys
            }
            requests = result['aggregate_confirmed_requests']
            if requests:
                result['aggregate_physical_io']['physical_write_calls_per_request'] = (
                    result['aggregate_physical_io']['physical_write_calls']/requests)
                result['aggregate_physical_io']['rmw_reads_per_request'] = (
                    result['aggregate_physical_io']['rmw_read_calls']/requests)
        result['aggregate_note'] = ('Cumulative totals at the most recent IO_STATS snapshot; '
                                    'the final few requests may follow it.')
    if sampled:
        result['sample_warning'] = ('Fast-mode per-request IO_END records are sampled; '
                                    'write_gib and measured_mb_s above refer to samples ONLY. '
                                    'Use aggregate_confirmed_bytes / aggregate_active_mib_s '
                                    'for totals where IO_STATS is present.')
    return result

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('jsonl', type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(args.jsonl), indent=2))

if __name__ == '__main__':
    main()
