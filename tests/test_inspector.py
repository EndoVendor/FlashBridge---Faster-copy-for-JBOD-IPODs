"""Read-only iPod inspection tests. Test fixtures never open physical disks."""
import hashlib
import json
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flashbridge_core import DiskInfo
from flashbridge_inspector import capture_snapshot,compare_live_ipod,load_snapshot,SCHEMA,_parts
from flashbridge_imdisk_setup import VendorRedirect, ALLOWED_HOST

MB=1024*1024

class FixtureRaw:
    content={}
    opened=[]
    def __init__(self,path,size,writable=False):
        if writable: raise AssertionError('Unexpected WRITE access')
        self.path=path;self.size=size;self.bytes=FixtureRaw.content[path]
        FixtureRaw.opened.append((path,'readonly'))
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read_at(self,offset,n):
        assert offset>=0 and offset+n<=self.size
        return self.bytes[offset:offset+n]

class InspectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        r=random.Random(1001)
        cls.a=bytes(r.randbytes(20*MB))
        cls.b=bytes(r.randbytes(24*MB))
        FixtureRaw.content={'cardA':cls.a,'cardB':cls.b,'ipod':cls.a+cls.b,
                            'badpod':cls.b+cls.a}

    def disk(self,path,size,number):
        d=DiskInfo(number=number,size=size,name='test-'+path,bus='USB',
                   logical_sector_size=512,physical_sector_size=512)
        object.__setattr__(d,'path',path) if False else None
        return d

    def _capture(self,name,size,number):
        # DiskInfo.path is derived; mock maps the Windows raw path to fixture bytes.
        d=self.disk(name,size,number)
        FixtureRaw.content[d.path]=FixtureRaw.content[name]
        return capture_snapshot(d,FixtureRaw)

    def test_snapshot_has_only_hashes_and_metadata(self):
        s=self._capture('cardA',len(self.a),4)
        self.assertEqual(s['schema'],SCHEMA)
        self.assertEqual(s['source'],'physical-disk-read-only')
        self.assertNotIn('bytes',s)
        self.assertIn('0',s['anchors_sha256'])
        self.assertEqual(len(s['anchors_sha256']['0']),64)
        self.assertFalse(any('write' in mode for _,mode in FixtureRaw.opened))

    def test_linear_pair_identified_read_only(self):
        a=self._capture('cardA',len(self.a),4)
        b=self._capture('cardB',len(self.b),1)
        ipod=self.disk('ipod',len(self.a)+len(self.b),7)
        FixtureRaw.content[ipod.path]=FixtureRaw.content['ipod']
        result=compare_live_ipod(ipod,a,b,FixtureRaw)
        self.assertEqual(result['conclusion'],'CANDIDATE ONLY')
        self.assertEqual(result['ipod_snapshot']['source'],'physical-disk-read-only')
        self.assertEqual(result['ipod_snapshot']['disk']['size'],len(self.a)+len(self.b))
        self.assertIn('partition_table',result['ipod_snapshot'])
        self.assertIn('fat32_candidates',result['ipod_snapshot'])
        self.assertFalse(result['write_authorized'])
        x=result['variants'][0]
        self.assertEqual(x['mismatches'],0)
        self.assertEqual(x['unavailable'],0)
        self.assertGreaterEqual(x['matches'],10)
        self.assertNotEqual(result['variants'][1]['status'],'linear-layout-evidence')

    def test_reversed_order_detected(self):
        a=self._capture('cardA',len(self.a),4)
        b=self._capture('cardB',len(self.b),1)
        ipod=self.disk('badpod',len(self.a)+len(self.b),7)
        FixtureRaw.content[ipod.path]=FixtureRaw.content['badpod']
        result=compare_live_ipod(ipod,a,b,FixtureRaw)
        self.assertEqual(result['variants'][1]['status'],'linear-layout-evidence')
        self.assertEqual(result['variants'][0]['status'],'inconclusive-or-non-linear')

    def test_bad_or_corrupted_ipod_does_not_pass(self):
        a=self._capture('cardA',len(self.a),4)
        b=self._capture('cardB',len(self.b),1)
        ipod=self.disk('ipod',len(self.a)+len(self.b),7)
        raw=bytearray(FixtureRaw.content['ipod'])
        raw[0]=raw[0]^1
        FixtureRaw.content[ipod.path]=bytes(raw)
        result=compare_live_ipod(ipod,a,b,FixtureRaw)
        self.assertEqual(result['conclusion'],'NOT PROVEN')
        FixtureRaw.content[ipod.path]=FixtureRaw.content['ipod']

    def test_protected_system_disk_rejected(self):
        d=DiskInfo(number=3,size=len(self.a),name='system',bus='USB',boot=True)
        with self.assertRaises(ValueError): capture_snapshot(d,FixtureRaw)

    def test_snapshot_rejects_malformed_anchor(self):
        s=self._capture('cardA',len(self.a),4)
        s['anchors_sha256']['-10']='0'*64
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'capture.json';p.write_text(json.dumps(s))
            with self.assertRaises(ValueError): load_snapshot(p)

    def test_unknown_layout_is_nonproof_even_with_compatible_size(self):
        a=self._capture('cardA',len(self.a),4)
        b=self._capture('cardB',len(self.b),1)
        ipod=self.disk('ipod',len(self.a)+len(self.b),7)
        FixtureRaw.content[ipod.path]=bytes(len(self.a)+len(self.b))
        result=compare_live_ipod(ipod,a,b,FixtureRaw)
        self.assertEqual(result['conclusion'],'NOT PROVEN')
        FixtureRaw.content[ipod.path]=FixtureRaw.content['ipod']

    def test_repeated_same_snapshot_is_blocked(self):
        a=self._capture('cardA',len(self.a),4)
        ipod=self.disk('ipod',len(self.a)*2,7)
        with self.assertRaises(ValueError):
            compare_live_ipod(ipod,a,a,FixtureRaw)

    def test_missing_expected_anchor_is_blocked(self):
        a=self._capture('cardA',len(self.a),4)
        a['anchors_sha256'].pop('0')
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'a.json'
            path.write_text(json.dumps(a))
            with self.assertRaises(ValueError):
                load_snapshot(path)

    def test_imdisk_redirects_only_vendor_host(self):
        with self.assertRaises(ValueError):
            VendorRedirect().redirect_request(None,None,302,'',{},'https://evil.example/imdiskinst.exe')

if __name__=='__main__': unittest.main()
