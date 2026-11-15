"""FlashBridge core: evidence-based two-media FAT32 JBOD discovery + ImDisk proxy.

Requires Python 3.10+, stdlib only. Real raw-device I/O is Windows-only.
This tool neither formats cards nor alters partition tables. Raw RW is inherently risky.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, BinaryIO
import ctypes
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

MIB = 1024 ** 2
GIB = 1024 ** 3
ALIGN = 4096
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
    lg.info('START', version='0.2.1-alpha', python=sys.version.split()[0], platform=sys.platform)
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
      offline=[bool]$_.IsOffline}
    } | ConvertTo-Json -Compress -Depth 3'''
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                            capture_output=True, text=True, timeout=25, errors='replace')
    if result.returncode:
        raise RuntimeError('Get-Disk failed: ' + result.stderr[-1200:])
    raw = json.loads(result.stdout.lstrip('\ufeff'))
    if isinstance(raw, dict): raw = [raw]
    return [DiskInfo(**x) for x in (raw or [])]


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
        if offset % ALIGN or len(data) % ALIGN:
            raise ValueError(f'Internal alignment violation: pos={offset}, length={len(data)}')
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


class JoinedDisk:
    def __init__(self, plan: Plan, writable: bool, raw_factory=RawDevice):
        self.plan, self.writable = plan, writable
        self.a = raw_factory(plan.first.path, plan.first.size, writable)
        self.b = raw_factory(plan.second.path, plan.second.size, writable)
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

    def read_raw(self, offset, length):
        with self.lock:
            out = bytearray()
            for dev, pos, n in self._slices(offset, length):
                out.extend(dev.read_at(pos, n))
            return bytes(out)

    def read_volume(self, offset, length):
        if offset < 0 or length < 0 or length > self.plan.volume_bytes - offset:
            raise ValueError('Read outside FAT32 volume')
        return self.read_raw(self.plan.fat.offset + offset, length)

    def _write_aligned_one(self, dev, offset, content):
        """Preserve only misaligned 4KiB edge blocks; stream aligned interior.

        A volume whose byte offset is 2KiB modulo 4KiB makes almost all
        1MiB proxy chunks misaligned. Reading and rewriting the *entire*
        aligned megabyte was unnecessary and slow. At most two 4KiB edge
        blocks need pre-reading; the interior can be written directly.
        """
        if not content:
            return
        end = offset + len(content)
        if offset < 0 or end > dev.size or ((end + ALIGN - 1)//ALIGN)*ALIGN > dev.size:
            raise ValueError('Physical write would exceed medium bounds')
        cursor = 0
        misaligned = offset % ALIGN
        if misaligned:
            edge_start = offset - misaligned
            n = min(ALIGN - misaligned, len(content))
            edge = bytearray(dev.read_at(edge_start, ALIGN))
            edge[misaligned:misaligned+n] = content[:n]
            dev.write_at(edge_start, bytes(edge))
            cursor = n
            offset += n
        full = ((len(content) - cursor)//ALIGN)*ALIGN
        if full:
            dev.write_at(offset, content[cursor:cursor+full])
            cursor += full
            offset += full
        if cursor < len(content):
            edge = bytearray(dev.read_at(offset, ALIGN))
            n = len(content) - cursor
            edge[:n] = content[cursor:]
            dev.write_at(offset, bytes(edge))

    def write_volume(self, offset, payload):
        if not self.writable:
            raise PermissionError('RO JBOD')
        if offset < 0 or offset % 512 or len(payload) % 512 or len(payload) > self.plan.volume_bytes - offset:
            raise ValueError(f'Invalid write: logical_offset={offset} len={len(payload)}')
        with self.lock:
            for dev, pos, n in self._slices(self.plan.fat.offset + offset, len(payload)):
                self._write_aligned_one(dev, pos, payload[:n])
                payload = payload[n:]

    def sync(self):
        """Flush both media (used for a full-volume maintenance barrier)."""
        with self.lock:
            if self.writable:
                self.a.sync()
                self.b.sync()

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
                dev.sync()
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
    def __init__(self, plan, writable, logger, port=9011, raw_factory=RawDevice, on_state=None):
        super().__init__(daemon=True, name='ProxyServer')
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
        self.last_speed = 0
        self.last_error = None
        self.client_count = 0
        self.req_id = 0
        self._last_rate = time.monotonic()
        self._last_n = 0
        self.volume_signature = None

    def _state(self, status):
        self.on_state(status)
        self.log.info('SERVER_STATE', status=status)

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
            code_raw = recv_exact(client, 8)
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
                t0 = time.monotonic()
                # First chunk fetched before success reply; remainder streamed.
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
                if self.bytes_read // (256*MIB) != (self.bytes_read-nbytes)//(256*MIB):
                    self.log.info('READ_TOTAL', bytes_read=self.bytes_read)
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
                self.log.info('IO_BEGIN', req_id=ident, operation='WRITE', logical_offset=offset,
                              raw_offset=offset+self.plan.fat.offset, bytes=nbytes,
                              physical_first=self.plan.first.number,
                              physical_second=self.plan.second.number)
                t0 = time.monotonic()
                expected_hash = hashlib.sha256()
                remaining = nbytes
                pos = offset
                fault = None
                receive_seconds = 0.0
                physical_write_seconds = 0.0
                flush_seconds = 0.0
                readback_seconds = 0.0
                flushed_media = ()
                while remaining:
                    take = min(remaining, IO_CHUNK)
                    phase_start = time.monotonic()
                    chunk = recv_exact(client, take)
                    receive_seconds += time.monotonic() - phase_start
                    if chunk is None: raise ConnectionError('WRITE body truncated')
                    if fault is None and not self.failed:
                        expected_hash.update(chunk)
                        try:
                            phase_start = time.monotonic()
                            try:
                                self.dev.write_volume(pos, chunk)
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
                                           physical_disk=diskno, physical_offset=local,
                                           chunk_bytes=take, error=repr(exc),
                                           errno=getattr(exc,'errno',None),
                                           winerror=getattr(exc,'winerror',None))
                    pos += take
                    remaining -= take
                if fault is None and not self.failed:
                    try:
                        phase_start = time.monotonic()
                        try:
                            flushed_media = self.dev.sync_volume_range(offset, nbytes)
                        finally:
                            flush_seconds += time.monotonic() - phase_start
                        # Check full request after flush, without buffering it all.
                        actual_hash = hashlib.sha256()
                        remaining = nbytes
                        pos = offset
                        phase_start = time.monotonic()
                        try:
                            while remaining:
                                take = min(remaining, IO_CHUNK)
                                actual_hash.update(self.dev.read_volume(pos, take))
                                pos += take
                                remaining -= take
                        finally:
                            readback_seconds += time.monotonic() - phase_start
                        if actual_hash.digest() != expected_hash.digest():
                            raise OSError('FATAL: post-flush hash mismatch')
                    except Exception as exc:
                        fault = exc
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
                elapsed = time.monotonic()-t0
                if elapsed > 0:
                    self.last_speed = nbytes/elapsed
                self.log.info('IO_END', req_id=ident, operation='WRITE', logical_offset=offset,
                              bytes=nbytes, hash_sha256=actual_hash.hexdigest(),
                              flush_completed=True, elapsed_ms=round(elapsed*1000,1),
                              receive_ms=round(receive_seconds*1000,1),
                              physical_write_ms=round(physical_write_seconds*1000,1),
                              flush_ms=round(flush_seconds*1000,1),
                              readback_ms=round(readback_seconds*1000,1),
                              flushed_media=flushed_media,
                              total_bytes_written=self.bytes_written)
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
