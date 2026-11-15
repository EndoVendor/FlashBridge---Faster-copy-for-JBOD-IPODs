"""FlashBridge core: evidence-based two-media FAT32 JBOD discovery + ImDisk proxy.

Requires Python 3.10+, stdlib only. Real raw-device I/O is Windows-only.
This tool neither formats cards nor alters partition tables. Raw RW is inherently risky.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, BinaryIO
import ctypes
from collections import deque
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import queue
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import uuid

VERSION = '1.0.0'
WRITE_MODE_FAST = 'fast'
WRITE_MODE_VERIFIED = 'verified'
WRITE_MODES = frozenset((WRITE_MODE_FAST, WRITE_MODE_VERIFIED))
# In fast mode, completed writes are sampled rather than logging every MiB.
FAST_SUCCESS_SAMPLE_EVERY = 64

MIB = 1024 ** 2
GIB = 1024 ** 3
ALIGN = 4096  # conservative fallback; per-device alignment may be 512
IO_CHUNK = MIB
IMDISK_MAX_COMMAND = 4 * GIB
PROXY_ALIGNMENT = 512  # ImDisk SYS rejects requested proxy I/O alignment > 512
FAT32_MAX_FILE = 0xFFFFFFFF


def appdata_dir() -> Path:
    root = os.environ.get('LOCALAPPDATA') or str(Path.home() / '.flashbridge')
    return Path(root) / 'FlashBridge'


def make_logger(on_event=None, directory=None):
    directory = Path(directory or appdata_dir())
    directory.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    log_path = directory / 'logs' / ('flashbridge-' + run_id + '.log')
    events_path = directory / 'logs' / ('flashbridge-' + run_id + '.jsonl')
    log_path.parent.mkdir(exist_ok=True)
    logger = logging.getLogger('flashbridge.' + run_id)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    fmt = logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s %(threadName)s %(message)s', '%Y-%m-%dT%H:%M:%S')
    fh = RotatingFileHandler(log_path, maxBytes=8*MIB, backupCount=3, encoding='utf-8')
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    lg = RunLog(logger, events_path, log_path, on_event)
    lg.info('START', version=VERSION, python=sys.version.split()[0], platform=sys.platform)
    return lg


class RunLog:
    def __init__(self, logger, events_path, log_path, on_event):
        self.logger = logger
        self.events_path = Path(events_path)
        self.log_path = Path(log_path)
        self.on_event = on_event
        self.lock = threading.Lock()
        self.seq = 0
        self.max_event_bytes = 64 * MIB
        self.event_backups = 4

    def _rotate_event_file(self):
        if not self.events_path.exists() or self.events_path.stat().st_size < self.max_event_bytes:
            return
        for i in range(self.event_backups, 0, -1):
            source = (Path(str(self.events_path) + f'.{i-1}') if i > 1 else self.events_path)
            target = Path(str(self.events_path) + f'.{i}')
            if source.exists():
                source.replace(target)

    def event(self, kind, level='info', **fields):
        record = {'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  'event': kind, **fields}
        # Never record contents of source files, only operational metadata.
        with self.lock:
            self.seq += 1
            record['seq'] = self.seq
            self._rotate_event_file()
            with self.events_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
            getattr(self.logger, level.lower(), self.logger.info)('%s %s', kind, json.dumps(fields, ensure_ascii=False, default=str))
        if self.on_event:
            # Keep UI responsive during millions of physical reads. Full write/error
            # diagnostics remain in .jsonl on disk; GUI sees sampled progress.
            visible = kind not in ('IO_BEGIN', 'IO_END')
            if kind == 'IO_END' and fields.get('operation') == 'WRITE':
                visible = self.seq % 32 == 0
            if visible:
                self.on_event(record)

    def close(self):
        """Deterministically release log handles (required on Windows)."""
        with self.lock:
            for handler in list(self.logger.handlers):
                handler.flush()
                handler.close()
                self.logger.removeHandler(handler)

    def info(self, kind, **fields): self.event(kind, 'info', **fields)
    def warning(self, kind, **fields): self.event(kind, 'warning', **fields)
    def error(self, kind, **fields): self.event(kind, 'error', **fields)


@dataclass(frozen=True)
class DiskInfo:
    number: int
    size: int
    name: str
    bus: str
    serial: str = ''
    boot: bool = False
    system: bool = False
    readonly: bool = False
    offline: bool = False
    logical_sector_size: int = 0  # 0 = unverified, fail conservative
    physical_sector_size: int = 0

    @property
    def path(self):
        return rf'\\.\PhysicalDrive{self.number}'


def powershell_disks() -> list[DiskInfo]:
    if os.name != 'nt':
        raise RuntimeError('Physical disk enumeration is Windows-only.')
    script = r'''Get-Disk | ForEach-Object {
      [PSCustomObject]@{number=[int]$_.Number;size=[long]$_.Size;
      name=[string]$_.FriendlyName;bus=$_.BusType.ToString();
      serial=[string]$_.SerialNumber;boot=[bool]$_.IsBoot;
      system=[bool]$_.IsSystem;readonly=[bool]$_.IsReadOnly;
      offline=[bool]$_.IsOffline;
      logical_sector_size=[int]$_.LogicalSectorSize;
      physical_sector_size=[int]$_.PhysicalSectorSize}
    } | ConvertTo-Json -Compress -Depth 3'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=25, errors='replace')
    if result.returncode:
        raise RuntimeError('Get-Disk failed: ' + result.stderr[-1200:])
    raw = json.loads(result.stdout.lstrip('\ufeff'))
    if isinstance(raw, dict): raw = [raw]
    return [DiskInfo(**x) for x in (raw or [])]


def disk_write_alignment(d: DiskInfo) -> int:
    """No probing writes. Trust only a complete, coherent sector report.

    A confirmed 512/512 device can accept 512-aligned requests from ImDisk.
    A missing/contradictory report falls back to the prior 4KiB RMW path.
    Larger physical sector sizes are respected, never rounded down.
    This does not prove a USB bridge truthfully reports its media geometry.
    """
    logical, physical = d.logical_sector_size, d.physical_sector_size
    if logical == physical == 512:
        return 512
    if (logical in (512, 1024, 2048, 4096, 8192, 16384)
            and physical in (4096, 8192, 16384)
            and physical >= logical):
        return physical
    return ALIGN


def eligible(d: DiskInfo):
    # Do not mistake a 2TB system/external SSD for a card.
    return (d.number > 0 and d.size > 0 and not d.boot and not d.system
            and not d.offline and d.bus.lower() in ('usb', 'sd', 'mmc'))


class RawDevice:
    def __init__(self, path, size, writable=False):
        self.path = str(path)
        self.size = int(size)
        self.writable = writable
        self.file = None
        self.write_alignment = ALIGN

    def __enter__(self):
        self.file = open(self.path, 'r+b' if self.writable else 'rb', buffering=0)
        if os.name == 'nt' and self.path.lower().startswith('\\\\.\\physicaldrive'):
            import msvcrt
            handle = ctypes.c_void_p(msvcrt.get_osfhandle(self.file.fileno()))
            out = ctypes.c_ulonglong()
            returned = ctypes.c_ulong()
            if not ctypes.windll.kernel32.DeviceIoControl(
                    handle, 0x0007405C, None, 0, ctypes.byref(out), 8,
                    ctypes.byref(returned), None):
                self.__exit__(None, None, None)
                raise ctypes.WinError()
            if out.value != self.size:
                self.__exit__(None, None, None)
                raise RuntimeError(f'Device size changed: {self.path} '
                                   f'{out.value} != {self.size}')
        return self

    def __exit__(self, *args):
        if self.file:
            self.file.close()
            self.file = None

    def read_at(self, offset, count):
        if offset < 0 or count < 0 or count > self.size - offset:
            raise ValueError('READ out of range: ' + self.path)
        self.file.seek(offset)
        data = self.file.read(count)
        if len(data) != count:
            raise OSError(f'Short read from {self.path}: pos={offset}, n={count}, got={len(data)}')
        return data

    def write_at(self, offset, data):
        if not self.writable:
            raise PermissionError('Device is opened read-only.')
        align = self.write_alignment
        if offset % align or len(data) % align:
            raise ValueError(f'Internal alignment violation ({align} B): pos={offset}, length={len(data)}')
        if offset < 0 or len(data) > self.size - offset:
            raise ValueError('WRITE out of range: ' + self.path)
        self.file.seek(offset)
        n = self.file.write(data)
        if n != len(data):
            raise OSError(f'Short write: {self.path} pos={offset} {n}/{len(data)}')

    def sync(self):
        if not self.writable:
            return
        if os.name == 'nt' and self.path.lower().startswith('\\\\.\\physicaldrive'):
            import msvcrt
            handle = ctypes.c_void_p(msvcrt.get_osfhandle(self.file.fileno()))
            if not ctypes.windll.kernel32.FlushFileBuffers(handle):
                raise ctypes.WinError()
        else:
            self.file.flush()
            os.fsync(self.file.fileno())


@dataclass(frozen=True)
class FatCandidate:
    disk: int
    offset: int
    sector_size: int
    sectors_cluster: int
    sectors_reserved: int
    fat_count: int
    sectors_fat: int
    sectors_total: int
    root_cluster: int
    backup_sector: int
    fsinfo_sector: int
    backup_matches: bool
    fsinfo_valid: bool
    fat_head_match: bool

    @property
    def volume_bytes(self): return self.sector_size * self.sectors_total
    @property
    def end(self): return self.offset + self.volume_bytes


def _pow2(x): return bool(x) and x & (x-1) == 0


def parse_fat32_boot(buf, offset, disk, reader=None):
    if len(buf) < 512 or buf[510:512] != b'\x55\xaa': return None
    bps = struct.unpack_from('<H', buf, 11)[0]
    spc, fats = buf[13], buf[16]
    reserved = struct.unpack_from('<H', buf, 14)[0]
    total = struct.unpack_from('<I', buf, 32)[0]
    fatsize = struct.unpack_from('<I', buf, 36)[0]
    root = struct.unpack_from('<I', buf, 44)[0]
    fsinfo = struct.unpack_from('<H', buf, 48)[0]
    backup = struct.unpack_from('<H', buf, 50)[0]
    if (bps not in (512, 1024, 2048, 4096) or not _pow2(spc) or spc > 128
            or not 1 <= fats <= 2 or reserved < 2 or fatsize < 1 or total <= reserved + fats*fatsize
            or root < 2 or buf[82:87] != b'FAT32'):
        return None
    clusters = (total - reserved - fats*fatsize)//spc
    if (clusters < 65525 or clusters + 2 > fatsize*bps//4 or root >= clusters + 2):
        return None
    if bps*spc > 128*1024:  # avoid malformed BPB
        return None
    backup_ok = False
    fsinfo_ok = False
    fat_match = False
    if reader:
        if backup > 0 and backup < reserved and offset + backup*bps + bps <= reader.size:
            bb = reader.read_at(offset + backup*bps, bps)
            backup_ok = (bb[510:512] == b'\x55\xaa' and
                         bb[11:65] == buf[11:65] and bb[66:90] == buf[66:90])
        if fsinfo > 0 and fsinfo < reserved and offset + fsinfo*bps + bps <= reader.size:
            f = reader.read_at(offset + fsinfo*bps, bps)
            fsinfo_ok = (f[0:4] == b'RRaA' and
                         f[484:488] == b'rrAa' and f[508:512] == b'\0\0\x55\xaa')
        fat1 = offset + reserved*bps
        fat2 = fat1 + fatsize*bps
        if fats == 2 and fat2 + 4096 <= reader.size:
            fat_match = (reader.read_at(fat1, 4096) == reader.read_at(fat2, 4096))
    return FatCandidate(disk, offset, bps, spc, reserved, fats, fatsize, total,
                        root, backup, fsinfo, backup_ok, fsinfo_ok, fat_match)


def probe_disk(d: DiskInfo, raw_factory=RawDevice):
    results = []
    with raw_factory(d.path, d.size) as dev:
        mbr = dev.read_at(0, 512)
        partition_lbas = set()
        if mbr[510:512] == b'\x55\xaa':
            for i in range(4):
                p = mbr[446+i*16:462+i*16]
                lba = struct.unpack_from('<I', p, 8)[0]
                count = struct.unpack_from('<I', p, 12)[0]
                if lba > 0 and count > 0:
                    partition_lbas.add(lba)
        positions = {0}
        for lba in partition_lbas:
            for geom in (512, 1024, 2048, 4096):
                pos = lba * geom
                if pos + 4096 <= d.size: positions.add(pos)
        for offset in sorted(positions):
            first = dev.read_at(offset, min(4096, d.size - offset))
            candidate = parse_fat32_boot(first, offset, d.number, dev)
            if candidate: results.append(candidate)
    return results


@dataclass(frozen=True)
class Plan:
    first: DiskInfo
    second: DiskInfo
    fat: FatCandidate
    evidence: tuple[str, ...]
    read_write_safe: bool
    first_signature: str = ''
    second_signature: str = ''

    @property
    def combined(self): return self.first.size + self.second.size
    @property
    def volume_bytes(self): return self.fat.volume_bytes


def _manifest_match(disk, manifests, raw_factory):
    if not manifests: return []
    out = []
    with raw_factory(disk.path, disk.size) as dev:
        for m in manifests:
            if m.get('size_bytes') != disk.size: continue
            first = next((a for a in m.get('anchors', []) if a.get('offset') == 0), None)
            if not first or m.get('anchor_bytes') not in (512, 4096): continue
            actual = hashlib.sha256(dev.read_at(0, m['anchor_bytes'])).hexdigest()
            if actual.lower() == first.get('sha256', '').lower():
                out.append(str(m.get('label', '?')))
    return out


def discover_pair(disks: list[DiskInfo], raw_factory=RawDevice, manifests=None):
    if len(disks) != 2 or disks[0].number == disks[1].number:
        raise ValueError('Select exactly two distinct media.')
    if not all(eligible(d) for d in disks):
        raise ValueError('Selected device is not an eligible removable disk.')
    probes = {d.number: probe_disk(d, raw_factory) for d in disks}
    viable = []
    for first in disks:
        second = disks[1] if first.number == disks[0].number else disks[0]
        combined = first.size + second.size
        for b in probes[first.number]:
            if not first.size < b.end <= combined: continue
            # Reject pairs where the volume occupies only a small fraction of
            # the second media. Without this, any oversized external SSD could
            # falsely be selected as the continuation card.
            slack = combined - b.end
            if slack > max(64*MIB, int(combined*0.005)): continue
            if not b.backup_matches or not b.fsinfo_valid: continue
            # Check first-card mounted volume spans first card into the second.
            evidence = [f'FAT32 BPB on disk {first.number}: {b.volume_bytes} B, '
                        f'start {b.offset} B',
                        'Volume extends beyond the first medium and fits the pair',
                        'Backup boot sector and FSInfo were verified']
            if b.fat_head_match:
                evidence.append('FAT table headers match')
            else:
                evidence.append('WARNING: FAT table headers differ')
            if manifests:
                matches1 = _manifest_match(first, manifests, raw_factory)
                matches2 = _manifest_match(second, manifests, raw_factory)
                evidence.append('Historical signatures: first=' + ','.join(matches1 or ['unknown'])
                                + '; second=' + ','.join(matches2 or ['unknown']))
            with raw_factory(first.path, first.size) as card1:
                sig1 = hashlib.sha256(card1.read_at(0, 4096)).hexdigest()
            with raw_factory(second.path, second.size) as card2:
                sig2 = hashlib.sha256(card2.read_at(0, 4096)).hexdigest()
            viable.append(Plan(first, second, b, tuple(evidence), b.fat_head_match,
                               sig1, sig2))
    if not viable:
        raise RuntimeError('Cannot prove media order and spanning FAT32 volume. '
                           'RW is blocked; no formatting or guessing.')
    if len(viable) != 1:
        raise RuntimeError(f'{len(viable)} viable plans found. RW blocked: media order is ambiguous.')
    return viable[0]


def discover_all_pairs(disks: list[DiskInfo], raw_factory=RawDevice, manifests=None):
    """Automatically identify the unique viable pair from connected removable disks.

    No media changes. Ambiguity is an error, never a guessed order.
    """
    from itertools import combinations
    eligible_disks = [d for d in disks if eligible(d)]
    if len(eligible_disks) < 2:
        raise RuntimeError('At least two eligible removable media are required.')
    found = []
    for a, b in combinations(eligible_disks, 2):
        try:
            plan = discover_pair([a,b],raw_factory,manifests)
        except (RuntimeError, ValueError, OSError):
            continue
        found.append(plan)
    if len(found) != 1:
        raise RuntimeError(f'Auto-discovery found {len(found)} viable pairs. '
                           'RW requires exactly one unambiguous match.')
    return found[0]


def load_optional_manifests(folder):
    if not folder: return []
    out = []
    for fp in Path(folder).glob('*.json'):
        try:
            m = json.loads(fp.read_text(encoding='utf-8-sig'))
            if isinstance(m, dict) and m.get('size_bytes') and m.get('anchors'):
                out.append(m)
        except Exception:
            pass
    return out


class PhysicalOperationFailure(OSError):
    """Preserve source error codes and precise media/phase without dumping data."""
    def __init__(self, phase, physical_disk, physical_media, physical_offset, count, cause):
        errno = getattr(cause, 'errno', None)
        super().__init__(errno if errno is not None else 5,
                         f'{phase} failed on {physical_media} medium, disk '
                         f'{physical_disk}, at {physical_offset} ({count} bytes): {cause}')
        self.phase = phase
        self.physical_disk = physical_disk
        self.physical_media = physical_media
        self.physical_offset = physical_offset
        self.count = count
        self.root_error = repr(cause)
        self.winerror = getattr(cause, 'winerror', None)
        self.root_errno = errno


class JoinedDisk:
    def __init__(self, plan: Plan, writable: bool, raw_factory=RawDevice):
        self.plan, self.writable = plan, writable
        self.a = raw_factory(plan.first.path, plan.first.size, writable)
        self.b = raw_factory(plan.second.path, plan.second.size, writable)
        # Policy is locked per mount, never changed after RW begins.
        self.a.write_alignment = disk_write_alignment(plan.first)
        self.b.write_alignment = disk_write_alignment(plan.second)
        self.a.__enter__()
        try:
            self.b.__enter__()
        except BaseException:
            self.a.__exit__(None,None,None)
            raise
        self.lock = threading.RLock()

    def close(self):
        self.b.__exit__(None, None, None)
        self.a.__exit__(None, None, None)

    def _slices(self, offset, length):
        if offset < 0 or length < 0 or length > self.plan.combined - offset:
            raise ValueError('Operation outside JBOD bounds')
        while length:
            if offset < self.plan.first.size:
                dev, local = self.a, offset
                n = min(length, self.plan.first.size - offset)
            else:
                dev, local = self.b, offset - self.plan.first.size
                n = length
            yield dev, local, n
            offset += n
            length -= n

    def _error(self, phase, dev, offset, size, cause):
        if isinstance(cause, PhysicalOperationFailure):
            return cause
        is_first = dev is self.a
        return PhysicalOperationFailure(phase,
                 self.plan.first.number if is_first else self.plan.second.number,
                 'first' if is_first else 'second', offset, size, cause)

    def _device_read(self, dev, offset, size, phase):
        try:
            return dev.read_at(offset, size)
        except Exception as exc:
            raise self._error(phase, dev, offset, size, exc) from exc

    def _device_write(self, dev, offset, payload):
        try:
            dev.write_at(offset, payload)
        except Exception as exc:
            raise self._error('WRITE', dev, offset, len(payload), exc) from exc

    def _device_sync(self, dev):
        try:
            dev.sync()
        except Exception as exc:
            raise self._error('FLUSH', dev, None, 0, exc) from exc

    def read_raw(self, offset, length, phase='READ'):
        with self.lock:
            out = bytearray()
            for dev, pos, n in self._slices(offset, length):
                out.extend(self._device_read(dev, pos, n, phase))
            return bytes(out)

    def read_volume(self, offset, length, phase='READ'):
        if offset < 0 or length < 0 or length > self.plan.volume_bytes - offset:
            raise ValueError('Read outside FAT32 volume')
        return self.read_raw(self.plan.fat.offset + offset, length, phase=phase)

    def _write_aligned_one(self, dev, offset, content, metrics=None):
        """Fuse a misaligned request into ONE device-sector-aligned physical write.

        Never overwrite neighboring bytes with zeros. Pre-read each *partial*
        edge block (once if both edges share one block), overlay the full
        incoming payload, and issue exactly one aligned physical WRITE.
        No deferred writes, no shared dirty cache, and no weakened flush.

        On confirmed 512/512 devices, ImDisk requests are 512-aligned and
        require NO edge pre-reads. On unknown devices, the old 4KiB-safe
        strategy remains. No automatic retry after an ambiguous I/O error. The caller
        continues to handle the JBOD boundary before reaching this method.
        """
        if not content:
            return
        # Bound temporary buffers even for non-proxy callers.
        if len(content) > IO_CHUNK:
            for i in range(0, len(content), IO_CHUNK):
                self._write_aligned_one(dev, offset + i, content[i:i+IO_CHUNK], metrics)
            return
        align = getattr(dev, 'write_alignment', ALIGN)
        end = offset + len(content)
        aligned_start = (offset // align) * align
        aligned_end = ((end + align - 1) // align) * align
        if offset < 0 or end > dev.size or aligned_end > dev.size:
            raise ValueError('Physical write would exceed medium bounds')

        if metrics is None:
            metrics = {}
        if aligned_start == offset and aligned_end == end:
            # Preserve the zero-copy fast path for already aligned payloads.
            t_device_write = time.monotonic()
            try:
                self._device_write(dev, offset, content)
            finally:
                metrics['device_write_seconds'] = metrics.get('device_write_seconds', 0.0) + time.monotonic() - t_device_write
            metrics['physical_write_calls'] = metrics.get('physical_write_calls', 0) + 1
            metrics['physical_write_bytes'] = metrics.get('physical_write_bytes', 0) + len(content)
            return

        merged = bytearray(aligned_end - aligned_start)
        if offset != aligned_start:
            t_read = time.monotonic()
            try:
                edge = self._device_read(dev, aligned_start, align, 'RMW_READ')
            finally:
                metrics['rmw_read_seconds'] = metrics.get('rmw_read_seconds', 0.0) + time.monotonic() - t_read
            merged[:align] = edge
            metrics['rmw_read_calls'] = metrics.get('rmw_read_calls', 0) + 1
            metrics['rmw_read_bytes'] = metrics.get('rmw_read_bytes', 0) + align
        if end != aligned_end:
            tail_at = aligned_end - align
            if tail_at != aligned_start or offset == aligned_start:
                t_read = time.monotonic()
                try:
                    edge = self._device_read(dev, tail_at, align, 'RMW_READ')
                finally:
                    metrics['rmw_read_seconds'] = metrics.get('rmw_read_seconds', 0.0) + time.monotonic() - t_read
                merged[tail_at-aligned_start:tail_at-aligned_start+align] = edge
                metrics['rmw_read_calls'] = metrics.get('rmw_read_calls', 0) + 1
                metrics['rmw_read_bytes'] = metrics.get('rmw_read_bytes', 0) + align
        merged[offset-aligned_start:end-aligned_start] = content
        t_device_write = time.monotonic()
        try:
            self._device_write(dev, aligned_start, merged)
        finally:
            metrics['device_write_seconds'] = metrics.get('device_write_seconds', 0.0) + time.monotonic() - t_device_write
        metrics['physical_write_calls'] = metrics.get('physical_write_calls', 0) + 1
        metrics['physical_write_bytes'] = metrics.get('physical_write_bytes', 0) + len(merged)

    def write_volume(self, offset, payload):
        if not self.writable:
            raise PermissionError('RO JBOD')
        if offset < 0 or offset % 512 or len(payload) % 512 or len(payload) > self.plan.volume_bytes - offset:
            raise ValueError(f'Invalid write: logical_offset={offset} len={len(payload)}')
        metrics = {'physical_write_calls': 0, 'physical_write_bytes': 0,
                   'rmw_read_calls': 0, 'rmw_read_bytes': 0, 'rmw_read_seconds': 0.0,
                   'device_write_seconds': 0.0}
        with self.lock:
            for dev, pos, n in self._slices(self.plan.fat.offset + offset, len(payload)):
                self._write_aligned_one(dev, pos, payload[:n], metrics)
                payload = payload[n:]
        return metrics

    def sync(self):
        """Flush both media (used for a full-volume maintenance barrier)."""
        with self.lock:
            if self.writable:
                self._device_sync(self.a)
                self._device_sync(self.b)

    def sync_volume_range(self, offset, length):
        """Flush only media touched by an already-completed volume WRITE.

        Each completed proxy write is independently flushed before acknowledgement.
        This is NOT asynchronous or deferred flushing: only the unnecessary
        second-card FlushFileBuffers call is eliminated.
        """
        if not self.writable:
            raise PermissionError('RO JBOD')
        if offset < 0 or length < 0 or length > self.plan.volume_bytes - offset:
            raise ValueError('Invalid sync range')
        with self.lock:
            touched = []
            for dev, _pos, _n in self._slices(self.plan.fat.offset + offset, length):
                if dev not in touched:
                    touched.append(dev)
            for dev in touched:
                self._device_sync(dev)
            return tuple('first' if dev is self.a else 'second' for dev in touched)


def recv_exact(sock, length):
    if length < 0: raise ValueError('Negative recv')
    chunks = bytearray()
    while len(chunks) < length:
        blob = sock.recv(min(length - len(chunks), IO_CHUNK))
        if not blob:
            if not chunks: return None
            raise ConnectionError(f'Short TCP read: expected {length}, got {len(chunks)}')
        chunks += blob
    return bytes(chunks)


class ProxyServer(threading.Thread):
    def __init__(self, plan, writable, logger, port=9011, raw_factory=RawDevice,
                 on_state=None, write_mode=WRITE_MODE_VERIFIED):
        super().__init__(daemon=True, name='ProxyServer')
        if write_mode not in WRITE_MODES:
            raise ValueError('Unsupported write mode; expected fast or verified')
        # Immutable for the duration of the mount; no mid-session policy switch.
        self.write_mode = write_mode
        self.plan, self.writable = plan, writable
        self.log, self.port = logger, port
        self.factory = raw_factory
        self.on_state = on_state or (lambda status: None)
        self.started = threading.Event()
        self.stopping = threading.Event()
        self.ready = False
        self.failed = False
        self.active = False
        self.server = None
        self.dev = None
        self.bytes_written = 0
        self.bytes_read = 0
        self.verified_bytes = 0
        self.write_requests = 0
        self._write_total_seconds = 0.0
        self._write_physical_seconds = 0.0
        self._write_flush_seconds = 0.0
        self._write_readback_seconds = 0.0
        self._physical_write_calls = 0
        self._physical_write_bytes = 0
        self._rmw_read_calls = 0
        self._rmw_read_bytes = 0
        self._rmw_read_seconds = 0.0
        self._device_write_seconds = 0.0
        self._proxy_read_seconds = 0.0  # includes socket send + physical read
        self._proxy_read_requests = 0
        self._protocol_wait_seconds = 0.0  # idle waiting for next ImDisk command
        self._last_stats_snapshot = None
        self.last_speed = 0
        self.last_error = None
        self.client_count = 0
        self.req_id = 0
        self._last_rate = time.monotonic()
        self._last_n = 0
        self._recent_completed = deque(maxlen=4096)
        self._first_confirmed_ts = None
        self.volume_signature = None

    def _state(self, status):
        self.on_state(status)
        self.log.info('SERVER_STATE', status=status)

    def rolling_write_rate(self, window_seconds=10.0):
        """Confirmed bytes/sec over a sliding time window (not instantaneous block speed)."""
        now = time.monotonic()
        cutoff = now - window_seconds
        while self._recent_completed and self._recent_completed[0][0] < cutoff:
            self._recent_completed.popleft()
        if not self._recent_completed:
            return 0.0
        # The producing server and consuming GUI are separate threads, but
        # deque append/popleft are individually atomic under CPython's GIL.
        first = self._first_confirmed_ts or self._recent_completed[0][0]
        duration = max(1.0, min(window_seconds, now - first))
        return sum(n for t, n in tuple(self._recent_completed) if t >= cutoff) / duration

    def stop(self):
        self.stopping.set()
        # Let the loop exit after normal unmount; never force-close a live session.

    def run(self):
        try:
            self.dev = JoinedDisk(self.plan, self.writable, self.factory)
            # Check physical card identity and geometry again after opening RW.
            if self.plan.first_signature and (hashlib.sha256(self.dev.read_raw(0,4096)).hexdigest()
                                              != self.plan.first_signature):
                raise RuntimeError('HALT: FIRST physical medium identity changed')
            if self.plan.second_signature and (
                hashlib.sha256(self.dev.read_raw(self.plan.first.size,4096)).hexdigest()
                != self.plan.second_signature):
                raise RuntimeError('HALT: SECOND physical medium identity changed')
            boot = self.dev.read_raw(self.plan.fat.offset, self.plan.fat.sector_size)
            candidate = parse_fat32_boot(boot, self.plan.fat.offset, self.plan.first.number)
            if not candidate or (candidate.volume_bytes, candidate.sector_size,
                candidate.sectors_fat, candidate.sectors_reserved) != (
                self.plan.volume_bytes, self.plan.fat.sector_size,
                self.plan.fat.sectors_fat, self.plan.fat.sectors_reserved):
                raise RuntimeError('FAT32 boot parameters changed before mounting.')
            self.log.info('WRITE_POLICY', mode=self.write_mode if self.writable else 'readonly',
                          first_sector_sizes={'logical': self.plan.first.logical_sector_size,
                                              'physical': self.plan.first.physical_sector_size},
                          second_sector_sizes={'logical': self.plan.second.logical_sector_size,
                                               'physical': self.plan.second.physical_sector_size},
                          write_alignments={'first': self.dev.a.write_alignment,
                                            'second': self.dev.b.write_alignment},
                          flush_each_request=self.writable,
                          readback_each_request=self.writable and self.write_mode == WRITE_MODE_VERIFIED,
                          fast_success_log_sample=FAST_SUCCESS_SAMPLE_EVERY,
                          block_readback_is_not_durability_proof=True)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                self.server = sock
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('127.0.0.1', self.port))
                self.port = sock.getsockname()[1]
                sock.listen(1)
                sock.settimeout(.5)
                self.ready = True
                self.started.set()
                self._state('LISTENING')
                while not self.stopping.is_set() and not self.failed:
                    try: client, addr = sock.accept()
                    except socket.timeout: continue
                    with client:
                        self.active = True
                        self.client_count += 1
                        self.log.info('CLIENT_CONNECT', address=str(addr), client_count=self.client_count)
                        try:
                            self._handle_client(client)
                        except Exception as exc:
                            self.failed = True
                            self.last_error = repr(exc)
                            self.log.error('FATAL_PROXY', error=repr(exc),
                                           bytes_written=self.bytes_written, bytes_read=self.bytes_read)
                            self._state('FAULT')
                        finally:
                            self.active = False
                            self.log.info('CLIENT_DISCONNECT')
                self._state('STOPPED' if not self.failed else 'FAULT')
        except Exception as exc:
            self.failed = True
            self.last_error = repr(exc)
            self.log.error('SERVER_START_ERROR', error=repr(exc))
            self._state('FAULT')
        finally:
            self.started.set()
            # Device stays open until controller requests stop after confirmed dismount.
            # For cleanup, the controller can close it once the ImDisk device is absent.
            self.ready = False
            self.server = None

    def close_devices(self):
        if self.dev:
            self.dev.close()
            self.dev = None

    def _handle_client(self, client):
        client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        while not self.stopping.is_set():
            t_wait = time.monotonic()
            code_raw = recv_exact(client, 8)
            self._protocol_wait_seconds += time.monotonic() - t_wait
            if code_raw is None: return
            (code,) = struct.unpack('<Q', code_raw)
            self.req_id += 1
            ident = self.req_id
            if code == 1: # INFO
                client.sendall(struct.pack('<QQQ', self.plan.volume_bytes, PROXY_ALIGNMENT,
                                           0 if self.writable else 1))
                self.log.info('PROXY_INFO', request_id=ident, size=self.plan.volume_bytes,
                              alignment=PROXY_ALIGNMENT, writable=self.writable)
            elif code == 2: # READ
                header = recv_exact(client, 16)
                if header is None: raise ConnectionError('READ header missing')
                offset, nbytes = struct.unpack('<QQ', header)
                self._check_range(offset, nbytes)
                if ident % 128 == 0:
                    self.log.info('READ_SAMPLE', req_id=ident, logical_offset=offset, bytes=nbytes)
                t_read = time.monotonic()
                try:
                    # Covers device read AND socket send (both can stall the writer).
                    firstn = min(IO_CHUNK, nbytes)
                    first = self.dev.read_volume(offset, firstn)
                    client.sendall(struct.pack('<QQ', 0, nbytes))
                    if first: client.sendall(first)
                    at = offset + firstn
                    while at < offset + nbytes:
                        nn = min(IO_CHUNK, offset + nbytes - at)
                        client.sendall(self.dev.read_volume(at, nn))
                        at += nn
                    self.bytes_read += nbytes
                    self._proxy_read_requests += 1
                    if self.bytes_read // (256*MIB) != (self.bytes_read-nbytes)//(256*MIB):
                        self.log.info('READ_TOTAL', bytes_read=self.bytes_read)
                finally:
                    self._proxy_read_seconds += time.monotonic() - t_read
            elif code == 3: # WRITE
                header = recv_exact(client, 16)
                if header is None: raise ConnectionError('WRITE header missing')
                offset, nbytes = struct.unpack('<QQ', header)
                self._check_range(offset, nbytes)
                if not self.writable:
                    # Drain nothing: ImDisk will encounter EOF and report EROFS.
                    raise PermissionError('WRITE request on read-only volume')
                if offset % 512 or nbytes % 512:
                    raise ValueError('ImDisk requested unaligned write')
                # Always log beginnings in verified mode. Fast mode samples normal
                # successes; any failure below is logged fully with its offset.
                if self.write_mode == WRITE_MODE_VERIFIED or ident % FAST_SUCCESS_SAMPLE_EVERY == 0:
                    self.log.info('IO_BEGIN', req_id=ident, operation='WRITE', logical_offset=offset,
                                  raw_offset=offset+self.plan.fat.offset, bytes=nbytes,
                                  physical_first=self.plan.first.number,
                                  physical_second=self.plan.second.number,
                                  write_mode=self.write_mode)
                t0 = time.monotonic()
                need_readback = self.write_mode == WRITE_MODE_VERIFIED
                expected_hash = hashlib.sha256() if need_readback else None
                remaining = nbytes
                pos = offset
                fault = None
                receive_seconds = 0.0
                physical_write_seconds = 0.0
                flush_seconds = 0.0
                readback_seconds = 0.0
                flushed_media = ()
                io_counts = {'physical_write_calls':0, 'physical_write_bytes':0,
                             'rmw_read_calls':0, 'rmw_read_bytes':0, 'rmw_read_seconds':0.0,
                             'device_write_seconds':0.0}
                while remaining:
                    take = min(remaining, IO_CHUNK)
                    phase_start = time.monotonic()
                    chunk = recv_exact(client, take)
                    receive_seconds += time.monotonic() - phase_start
                    if chunk is None: raise ConnectionError('WRITE body truncated')
                    if fault is None and not self.failed:
                        if need_readback:
                            expected_hash.update(chunk)
                        try:
                            phase_start = time.monotonic()
                            try:
                                chunk_counts = self.dev.write_volume(pos, chunk)
                                for metric, value in (chunk_counts or {}).items():
                                    io_counts[metric] = io_counts.get(metric, 0) + value
                            finally:
                                physical_write_seconds += time.monotonic() - phase_start
                        except Exception as exc:
                            fault = exc
                            absolute = pos + self.plan.fat.offset
                            first = absolute < self.plan.first.size
                            diskno = self.plan.first.number if first else self.plan.second.number
                            local = absolute if first else absolute - self.plan.first.size
                            self.log.error('PHYSICAL_WRITE_FAIL', req_id=ident,
                                           logical_offset=pos, raw_offset=absolute,
                                           physical_disk=getattr(exc,'physical_disk',diskno),
                                           physical_media=getattr(exc,'physical_media',
                                                                'first' if first else 'second'),
                                           physical_offset=getattr(exc,'physical_offset',local),
                                           chunk_bytes=take, phase=getattr(exc,'phase','WRITE'),
                                           error=repr(exc), root_error=getattr(exc,'root_error',None),
                                           errno=getattr(exc,'root_errno',getattr(exc,'errno',None)),
                                           winerror=getattr(exc,'winerror',None))
                    pos += take
                    remaining -= take
                if fault is None and not self.failed:
                    stage = 'FLUSH'
                    try:
                        phase_start = time.monotonic()
                        try:
                            flushed_media = self.dev.sync_volume_range(offset, nbytes)
                        finally:
                            flush_seconds += time.monotonic() - phase_start
                        # FAST: flush then acknowledge, no post-write readback or
                        # SHA. VERIFIED: flush then full readback and SHA comparison.
                        actual_hash = None
                        if need_readback:
                            stage = 'READBACK'
                            actual_hash = hashlib.sha256()
                            remaining = nbytes
                            pos = offset
                            phase_start = time.monotonic()
                            try:
                                while remaining:
                                    take = min(remaining, IO_CHUNK)
                                    actual_hash.update(self.dev.read_volume(pos, take, phase='READBACK'))
                                    pos += take
                                    remaining -= take
                            finally:
                                readback_seconds += time.monotonic() - phase_start
                            stage = 'VERIFY'
                            if actual_hash.digest() != expected_hash.digest():
                                raise OSError('FATAL: post-flush hash mismatch')
                    except Exception as exc:
                        fault = exc
                        event = ('PHYSICAL_FLUSH_FAIL' if stage == 'FLUSH' else
                                 'PHYSICAL_READBACK_FAIL' if stage == 'READBACK' else
                                 'READBACK_HASH_MISMATCH')
                        self.log.error(event, req_id=ident, logical_offset=offset,
                                       request_bytes=nbytes, phase=getattr(exc,'phase',stage),
                                       physical_disk=getattr(exc,'physical_disk',None),
                                       physical_media=getattr(exc,'physical_media',None),
                                       physical_offset=getattr(exc,'physical_offset',None),
                                       error=repr(exc), root_error=getattr(exc,'root_error',None),
                                       errno=getattr(exc,'root_errno',getattr(exc,'errno',None)),
                                       winerror=getattr(exc,'winerror',None))
                        if getattr(exc,'winerror',None) in (55, 1167):
                            self.log.error('DEVICE_IO_UNAVAILABLE', req_id=ident,
                                           during_stage=stage,
                                           physical_disk=getattr(exc,'physical_disk',None),
                                           physical_media=getattr(exc,'physical_media',None),
                                           winerror=exc.winerror,
                                           note='I/O path unavailable, not proof of physical removal')
                if fault is not None or self.failed:
                    # Complete the ImDisk protocol with an ERROR response rather than
                    # abruptly dropping TCP and leaving a stuck virtual device.
                    self.failed = True
                    self.last_error = repr(fault or self.last_error)
                    self.log.error('WRITE_REJECTED', req_id=ident, logical_offset=offset,
                                   bytes=nbytes, error=self.last_error, future_writes_blocked=True)
                    client.sendall(struct.pack('<QQ', 5, 0))  # EIO
                    self._state('FAULT')
                    continue  # Read requests and ImDisk orderly CLOSE remain serviceable
                client.sendall(struct.pack('<QQ', 0, nbytes))
                self.bytes_written += nbytes
                confirmed_ts = time.monotonic()
                if self._first_confirmed_ts is None:
                    self._first_confirmed_ts = confirmed_ts
                self._recent_completed.append((confirmed_ts, nbytes))
                if need_readback:
                    self.verified_bytes += nbytes
                self.write_requests += 1
                self._physical_write_calls += io_counts['physical_write_calls']
                self._physical_write_bytes += io_counts['physical_write_bytes']
                self._rmw_read_calls += io_counts['rmw_read_calls']
                self._rmw_read_bytes += io_counts['rmw_read_bytes']
                self._rmw_read_seconds += io_counts['rmw_read_seconds']
                self._device_write_seconds += io_counts['device_write_seconds']
                elapsed = time.monotonic()-t0
                self._write_total_seconds += elapsed
                self._write_physical_seconds += physical_write_seconds
                self._write_flush_seconds += flush_seconds
                self._write_readback_seconds += readback_seconds
                if elapsed > 0:
                    self.last_speed = nbytes/elapsed
                # Keep full error diagnostics but avoid ~1M JSONL lines for
                # a 500-GiB copy. Verified mode retains per-request records.
                if (need_readback or self.write_requests <= 4 or
                        self.write_requests % FAST_SUCCESS_SAMPLE_EVERY == 0 or nbytes < 65536):
                    self.log.info('IO_END', req_id=ident, operation='WRITE', logical_offset=offset,
                                  bytes=nbytes, hash_sha256=actual_hash.hexdigest() if need_readback else None,
                                  readback_performed=need_readback, write_mode=self.write_mode,
                                  flush_completed=True, elapsed_ms=round(elapsed*1000,1),
                                  receive_ms=round(receive_seconds*1000,1),
                                  physical_write_ms=round(physical_write_seconds*1000,1),
                                  flush_ms=round(flush_seconds*1000,1),
                                  readback_ms=round(readback_seconds*1000,1),
                                  flushed_media=flushed_media,
                                  physical_write_calls=io_counts['physical_write_calls'],
                                  physical_write_bytes=io_counts['physical_write_bytes'],
                                  rmw_read_calls=io_counts['rmw_read_calls'],
                                  rmw_read_bytes=io_counts['rmw_read_bytes'],
                                  rmw_read_ms=round(io_counts['rmw_read_seconds']*1000,2),
                                  device_write_ms=round(io_counts['device_write_seconds']*1000,2),
                                  total_bytes_written=self.bytes_written,
                                  total_verified_bytes=self.verified_bytes,
                                  total_write_requests=self.write_requests,
                                  sample_every=1 if need_readback else FAST_SUCCESS_SAMPLE_EVERY)
                if self._last_stats_snapshot is None:
                    self._last_stats_snapshot = (
                        confirmed_ts, self.bytes_written, self._write_total_seconds,
                        self._proxy_read_seconds, self._protocol_wait_seconds,
                        self._proxy_read_requests, self.bytes_read)
                if self.write_requests % FAST_SUCCESS_SAMPLE_EVERY == 0:
                    old_ts, old_written, old_write_sec, old_read_sec, old_wait_sec, old_reads, old_read_bytes = self._last_stats_snapshot
                    interval_seconds = max(confirmed_ts-old_ts, 1e-9)
                    interval_written = self.bytes_written-old_written
                    interval_write_seconds = self._write_total_seconds-old_write_sec
                    self.log.info('IO_STATS', mode=self.write_mode,
                                  # Compare GUI's real-time rate with the active-only rate.
                                  rolling_wall_mib_s=round(self.rolling_write_rate()/MIB,2),
                                  interval_wall_mib_s=round(interval_written/MIB/interval_seconds,2),
                                  interval_active_mib_s=round(interval_written/MIB/max(interval_write_seconds,1e-9),2),
                                  interval_wall_seconds=round(interval_seconds,3),
                                  interval_write_seconds=round(interval_write_seconds,3),
                                  interval_proxy_read_seconds=round(self._proxy_read_seconds-old_read_sec,3),
                                  interval_proxy_read_requests=self._proxy_read_requests-old_reads,
                                  interval_proxy_read_bytes=self.bytes_read-old_read_bytes,
                                  interval_protocol_wait_seconds=round(self._protocol_wait_seconds-old_wait_sec,3),
                                  total_bytes_written=self.bytes_written,
                                  total_verified_bytes=self.verified_bytes,
                                  write_requests=self.write_requests,
                                  average_active_mib_s=round((self.bytes_written / MIB) /
                                                               max(self._write_total_seconds, 1e-9),2),
                                  physical_write_seconds=round(self._write_physical_seconds,3),
                                  flush_seconds=round(self._write_flush_seconds,3),
                                  readback_seconds=round(self._write_readback_seconds,3),
                                  physical_write_calls=self._physical_write_calls,
                                  physical_write_bytes=self._physical_write_bytes,
                                  rmw_read_calls=self._rmw_read_calls,
                                  rmw_read_bytes=self._rmw_read_bytes,
                                  rmw_read_seconds=round(self._rmw_read_seconds,3),
                                  device_write_seconds=round(self._device_write_seconds,3))
                    self._last_stats_snapshot = (
                        confirmed_ts, self.bytes_written, self._write_total_seconds,
                        self._proxy_read_seconds, self._protocol_wait_seconds,
                        self._proxy_read_requests, self.bytes_read)
            elif code == 5: # CLOSE
                self.log.info('PROXY_CLOSE', req_id=ident)
                return
            else:
                raise ValueError(f'Unsupported proxy command {code}, req_id={ident}')

    def _check_range(self, offset, nbytes):
        if nbytes > IMDISK_MAX_COMMAND or offset > self.plan.volume_bytes or nbytes > self.plan.volume_bytes - offset:
            raise ValueError(f'Proxy out-of-range: offset={offset}, bytes={nbytes}')


def imdisk_command(args, timeout=45):
    if os.name != 'nt': raise RuntimeError('ImDisk control is Windows-only.')
    p = subprocess.run(['imdisk.exe', *args], capture_output=True, text=True,
                       timeout=timeout, errors='replace')
    return p.returncode, p.stdout + p.stderr


def imdisk_list():
    return imdisk_command(['-l'], timeout=12)[1]


def imdisk_mount(plan: Plan, letter: str, writable: bool, port: int):
    if not re.match(r'^[A-Z]$', letter): raise ValueError('Invalid drive letter')
    opts = 'ip,hd' if writable else 'ip,hd,ro'
    return imdisk_command(['-a', '-t', 'proxy', '-o', opts, '-f', f'127.0.0.1:{port}',
                           '-s', str(plan.volume_bytes), '-S', str(plan.fat.sector_size), '-m', letter+':'], timeout=50)


def imdisk_unmount(letter: str):
    return imdisk_command(['-d', '-m', letter+':'], timeout=40)


def path_letter_free(letter):
    if os.name != 'nt': return True
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return (mask & (1 << (ord(letter)-ord('A')))) == 0


def is_elevated():
    if os.name != 'nt': return False
    return bool(ctypes.windll.shell32.IsUserAnAdmin())


def format_bytes(n):
    if n is None: return 'unknown'
    for unit in ('B','KiB','MiB','GiB','TiB'):
        if abs(n) < 1024 or unit == 'TiB': return f'{n:.1f} {unit}'
        n /= 1024

@dataclass(frozen=True)
class CopyEntry:
    source: Path
    destination: Path
    size: int


@dataclass(frozen=True)
class MissingCopyPlan:
    entries: tuple[CopyEntry, ...]
    bytes_to_copy: int
    existing_count: int
    differing_size_count: int
    over_fat32_limit: int
    free_bytes: int | None


def plan_missing_files(source_root, destination_root, log=None):
    """Metadata-only inspection: never changes target or reads file contents."""
    srcroot = Path(source_root)
    dstroot = Path(destination_root)
    if not srcroot.is_dir() or not dstroot.is_dir():
        raise RuntimeError('Source or destination is not a readable directory.')
    items = []
    existing = different = invalid = 0
    for folder in ('Music', 'Audiobooks'):
        source = srcroot / folder
        if not source.is_dir(): continue
        for parent, dirs, files in os.walk(source, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(parent) / d).is_symlink()]
            for name in files:
                src = Path(parent) / name
                if src.is_symlink(): continue
                dst = dstroot / src.relative_to(srcroot)
                size = src.stat().st_size
                if size > FAT32_MAX_FILE:
                    invalid += 1
                    if log: log.warning('FAT32_TOO_LARGE', path=str(src), bytes=size)
                elif dst.exists():
                    existing += 1
                    if dst.stat().st_size != size:
                        different += 1
                        if log: log.warning('EXISTING_SIZE_DIFFERENT', path=str(dst),
                                            src_bytes=size, dst_bytes=dst.stat().st_size)
                else:
                    items.append(CopyEntry(src,dst,size))
    try: free = shutil.disk_usage(dstroot).free
    except OSError: free = None
    result = MissingCopyPlan(tuple(items),sum(i.size for i in items),
                             existing,different,invalid,free)
    if log: log.info('COPY_PLAN', count=len(items), bytes=result.bytes_to_copy,
                     existing=existing, different=different, invalid=invalid, free=free)
    return result


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while True:
            block = stream.read(IO_CHUNK)
            if not block: break
            digest.update(block)
    return digest.hexdigest()


def copy_only_missing(plan: MissingCopyPlan, verify=True, log=None, stop=None,
                      progress=None, fault=None):
    """Never replace existing final paths. Resumes verified temporary files.

    If a write error occurs, preserve .flashbridge.partial and stop immediately.
    """
    written, count = 0, 0
    for entry in plan.entries:
        if stop and stop.is_set(): break
        if fault and fault(): raise RuntimeError('Proxy is in a fault state: writes are blocked')
        src, dst, size = entry.source, entry.destination, entry.size
        if dst.exists():
            if log: log.warning('COPY_SKIP_APPEARED', target=str(dst))
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        part = dst.with_name(dst.name + '.flashbridge.partial')
        offset = 0
        if part.exists():
            offset = part.stat().st_size
            if offset > size: raise RuntimeError(f'Partial file exceeds source size: {part}')
            with src.open('rb') as a, part.open('rb') as b:
                remaining = offset
                while remaining:
                    amount = min(IO_CHUNK, remaining)
                    if a.read(amount) != b.read(amount):
                        raise RuntimeError(f'Partial file does not match source: {part}')
                    remaining -= amount
            if log: log.info('COPY_RESUME', source=str(src), offset=offset)
        if log: log.info('COPY_START', source=str(src), target=str(dst), total_bytes=size, resume_from=offset)
        try:
            with src.open('rb') as inp, part.open('ab' if offset else 'xb') as out:
                inp.seek(offset)
                while True:
                    if fault and fault():
                        raise RuntimeError('Proxy failed while copying.')
                    chunk = inp.read(IO_CHUNK)
                    if not chunk: break
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            if part.stat().st_size != size: raise RuntimeError(f'Incomplete data in: {part}')
            if verify and file_hash(src) != file_hash(part):
                raise RuntimeError(f'SHA-256 file mismatch: {part}')
            if dst.exists():
                raise RuntimeError(f'Target file appeared during copy: {dst}')
            part.rename(dst)
            written += size-offset
            count += 1
            if log: log.info('COPY_COMPLETED', target=str(dst), bytes=size, verified=verify)
            if progress: progress(count,len(plan.entries),written,plan.bytes_to_copy,str(dst))
        except Exception as exc:
            if log: log.error('COPY_ERROR', source=str(src), target=str(dst), partial=str(part), error=repr(exc))
            raise
    return {'completed':count,'total_files':len(plan.entries),'new_bytes':written,
            'cancelled':bool(stop and stop.is_set())}
