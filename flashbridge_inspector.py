"""Read-only forensic snapshots and a live card-to-iPod continuity comparison.

This is *not* a formatter, firmware builder or adapter detector. It only records
metadata and SHA256 digests of small source-device samples. Unsupported layouts
remain unsupported; no guessed mappings are used for mounting or writing.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import time
from pathlib import Path

from flashbridge_core import DiskInfo, RawDevice, eligible, parse_fat32_boot, probe_disk

SCHEMA = 'flashbridge-storage-inspector-v1'
SAMPLE_LEN = 4096


def _safe_disk(d: DiskInfo):
    if not eligible(d) or d.number < 1 or d.system or d.boot:
        raise ValueError('Physical disk is ineligible. Inspection never opens boot/system/fixed media.')
    if d.size < 16 * 1024 * 1024:
        raise ValueError('Device is unexpectedly small; refusing to inspect.')
    if d.logical_sector_size and (d.logical_sector_size not in (512, 1024, 2048, 4096)):
        raise ValueError('Unknown logical sector size.')


def _sample_offsets(size):
    # Fixed positions (including end) allow a later card -> iPod boundary test.
    positions = (0, SAMPLE_LEN, 64*1024, 1024*1024, 16*1024*1024,
                 size//2, max(0,size-1024*1024), size-SAMPLE_LEN)
    return tuple(sorted({p//512*512 for p in positions if 0 <= p <= size-SAMPLE_LEN}))


def _parts(mbr: bytes, size: int):
    if len(mbr) < 512 or mbr[510:512] != b'\x55\xaa':
        return {'mbr_signature': False, 'partitions': []}
    out = []
    for idx in range(4):
        p = mbr[446+idx*16:462+idx*16]
        start = struct.unpack_from('<I',p,8)[0]
        length = struct.unpack_from('<I',p,12)[0]
        if length:
            out.append({'slot':idx,'type_hex':f'{p[4]:02x}',
                        'start_lba':start,'sectors':length,
                        'possible_start_bytes':{str(b):start*b for b in (512,1024,2048,4096)
                                                if start*b < size}})
    return {'mbr_signature':True, 'partitions':out}


def capture_snapshot(d: DiskInfo, raw_factory=RawDevice):
    """One physical disk, completely read-only. No mount and no probe writes."""
    _safe_disk(d)
    anchors = {}
    with raw_factory(d.path, d.size) as dev:
        mbr = dev.read_at(0, 512)
        for off in _sample_offsets(d.size):
            anchors[str(off)] = hashlib.sha256(dev.read_at(off, SAMPLE_LEN)).hexdigest()
    try:
        # FAT candidate parsing uses bounded reads of primary/backup/FSInfo/FAT heads.
        fats = [dict(offset=x.offset, sector_size=x.sector_size,
                     volume_bytes=x.volume_bytes, end=x.end,
                     backup_matches=x.backup_matches,
                     fsinfo_valid=x.fsinfo_valid,
                     fat_head_match=x.fat_head_match)
                for x in probe_disk(d, raw_factory)]
        fat_error = None
    except (OSError, ValueError) as exc:
        fats = []
        fat_error = str(exc)
    return {'schema':SCHEMA, 'source':'physical-disk-read-only',
            'captured_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'disk':{'number':d.number,'name':d.name,'bus':d.bus,'size':d.size,
                    'logical_sector_size':d.logical_sector_size,
                    'physical_sector_size':d.physical_sector_size},
            'sample_bytes':SAMPLE_LEN,'anchors_sha256':anchors,
            'partition_table':_parts(mbr,d.size),
            'fat32_candidates':fats,'fat_probe_error':fat_error,
            'limitations':['Only sampled blocks were compared, not full image.',
                           'MBR sector geometry may differ between USB iPod and card readers.',
                           'Does not authenticate firmware or establish bootability.',
                           'Does not demonstrate that the target flash adapter concatenates media.']}


def load_snapshot(path):
    path=Path(path)
    if path.stat().st_size > 128 * 1024:
        raise ValueError('Snapshot JSON is unexpectedly large.')
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if (not isinstance(data,dict) or data.get('schema') != SCHEMA
            or data.get('sample_bytes') != SAMPLE_LEN
            or not isinstance(data.get('anchors_sha256'),dict)):
        raise ValueError('Not a supported FlashBridge inspection snapshot.')
    size=data.get('disk',{}).get('size')
    if type(size) is not int or size < 16 * 1024 * 1024:
        raise ValueError('Invalid disk size in snapshot.')
    expected = {str(v) for v in _sample_offsets(size)}
    if set(data['anchors_sha256']) != expected:
        raise ValueError('Missing or unexpected snapshot sample positions.')
    for off,digest in data['anchors_sha256'].items():
        if not off.isdecimal() or int(off)+SAMPLE_LEN>size or (len(digest)!=64
               or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('Malformed snapshot anchor.')
    return data


def compare_live_ipod(d: DiskInfo, snap_a: dict, snap_b: dict, raw_factory=RawDevice):
    """Read selected USB iPod at predicted card offsets for *both* possible orders.

    This cannot validate unseen media or infer an arbitrary adapter layout.
    Even a full match is only evidence for byte-linear storage, not bootability.
    """
    _safe_disk(d)
    if (snap_a.get('schema')!=SCHEMA or snap_b.get('schema')!=SCHEMA):
        raise ValueError('Both snapshots must use the supported inspector format.')
    for snap in (snap_a, snap_b):
        size = snap.get('disk',{}).get('size')
        if (type(size) is not int or size < 16*1024*1024 or
                not isinstance(snap.get('anchors_sha256'),dict) or
                set(snap['anchors_sha256']) != {str(v) for v in _sample_offsets(size)}):
            raise ValueError('Invalid or incomplete card snapshot.')
    if (snap_a['disk']['size']==snap_b['disk']['size'] and
            snap_a['anchors_sha256']==snap_b['anchors_sha256']):
        raise ValueError('The two card snapshots are identical; choose two independent captures.')
    # The third leg of the experiment: capture the assembled iPod's own MBR,
    # FAT32 candidate metadata and fixed-position hash anchors, not only pair matches.
    ipod_snapshot=capture_snapshot(d,raw_factory)
    variants=[]
    with raw_factory(d.path,d.size) as dev:
        for first,second,order in [(snap_a,snap_b,'A then B'),(snap_b,snap_a,'B then A')]:
            seam=first['disk']['size']
            total=seam+second['disk']['size']
            details=[]
            for snap,base,label in [(first,0,'first'),(second,seam,'second')]:
                for off,digest in sorted(snap['anchors_sha256'].items(),key=lambda p:int(p[0])):
                    at=base+int(off)
                    if at+SAMPLE_LEN>d.size:
                        details.append({'card':label,'offset_ipod':at,'result':'outside-reported-size'})
                        continue
                    actual=hashlib.sha256(dev.read_at(at,SAMPLE_LEN)).hexdigest()
                    details.append({'card':label,'offset_ipod':at,
                                    'result':'match' if digest==actual else 'mismatch'})
            matches=sum(x['result']=='match' for x in details)
            mismatches=sum(x['result']=='mismatch' for x in details)
            unavailable=sum(x['result']=='outside-reported-size' for x in details)
            # Fail closed: a few coincident zeros or signatures do not prove topology.
            status=('linear-layout-evidence' if matches>=6 and mismatches==0 and unavailable==0
                    and total==d.size else 'inconclusive-or-non-linear')
            variants.append({'order':order,'sum_card_bytes':total,'ipod_bytes':d.size,
                             'matches':matches,'mismatches':mismatches,'unavailable':unavailable,
                             'status':status,'samples':details})
    return {'schema':'flashbridge-ipod-comparison-v1',
            'captured_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'ipod_disk':{'number':d.number,'name':d.name,'bus':d.bus,'size':d.size},
            'ipod_snapshot':ipod_snapshot,
            'variants':variants,
            'conclusion':'CANDIDATE ONLY' if any(v['status']=='linear-layout-evidence' for v in variants)
                         else 'NOT PROVEN',
            'write_authorized':False,
            'notes':['Read-only; no partitioning, formatting, writes or firmware changes.',
                     'A hash match cannot prove iPod bootability or full data integrity.',
                     'No automatic mount or RW authorization is inferred.',
                     'Other adapter geometries may be unsupported; mismatches are not automatically damage.',
                     'The third iPod snapshot records observed partition/FAT32 metadata separately.']}
