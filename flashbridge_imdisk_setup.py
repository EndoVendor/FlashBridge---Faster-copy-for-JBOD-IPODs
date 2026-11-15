"""Opt-in ImDisk installer assistant. Never silently installs a kernel driver.

Downloads only from the verified vendor host to a fresh, empty directory.
Automatic execution requires a valid Authenticode signature from the vendor;
otherwise the user must consult the official site and install manually.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request

VENDOR_PAGE = 'https://www.ltr-data.se/opencode.html#ImDisk'
VENDOR_EXE = 'https://static.ltr-data.se/files/imdiskinst.exe'
MAX_INSTALLER_BYTES = 5 * 1024 * 1024
ALLOWED_HOST = 'static.ltr-data.se'


def is_installed():
    return bool(shutil.which('imdisk.exe')) or (os.name=='nt' and
              (Path(os.environ.get('SystemRoot','C:/Windows'))/'System32'/'imdisk.exe').exists())


class VendorRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parts = urllib.parse.urlsplit(newurl)
        if parts.scheme!='https' or parts.hostname!=ALLOWED_HOST:
            raise ValueError('Installer download redirected outside the official HTTPS vendor host.')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch_official_installer(directory: Path):
    if os.name != 'nt':
        raise RuntimeError('Driver installation is only available on Windows.')
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError('Installer directory must be empty.')
    out=directory/'imdiskinst.exe'
    opener=urllib.request.build_opener(VendorRedirect)
    request=urllib.request.Request(VENDOR_EXE,headers={'User-Agent':'FlashBridge/0.3.3'})
    try:
        with opener.open(request,timeout=30) as response, out.open('xb') as target:
            if urllib.parse.urlsplit(response.url).hostname!=ALLOWED_HOST or not response.url.startswith('https://'):
                raise ValueError('Installer origin was not the expected HTTPS vendor host.')
            total=0
            while True:
                chunk=response.read(64*1024)
                if not chunk: break
                total+=len(chunk)
                if total > MAX_INSTALLER_BYTES: raise ValueError('Installer exceeds maximum expected download size.')
                target.write(chunk)
        if out.stat().st_size < 100_000:
            raise ValueError('Downloaded installer is unusually small.')
    except Exception:
        out.unlink(missing_ok=True)
        raise
    return out


def authenticode_vendor(path: Path):
    if os.name != 'nt':
        raise RuntimeError('Authenticode verification is Windows-only.')
    # Pass the path as an environment variable, not interpolated PowerShell code.
    # This also handles paths with spaces, non-ASCII characters and apostrophes.
    script = ('$s=Get-AuthenticodeSignature -LiteralPath $env:FLASHBRIDGE_INSTALLER_PATH;'
              '$subject=""; if($s.SignerCertificate){$subject=$s.SignerCertificate.Subject};'
              '[pscustomobject]@{Status=$s.Status.ToString();Subject=$subject} | '
              'ConvertTo-Json -Compress')
    env=os.environ.copy()
    env['FLASHBRIDGE_INSTALLER_PATH']=str(path)
    p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                     capture_output=True,text=True,timeout=25,errors='replace',env=env)
    if p.returncode: raise RuntimeError('Windows could not inspect installer signature.')
    info=json.loads(p.stdout.lstrip('\ufeff'))
    signed=info.get('Status')=='Valid'
    vendor=any(k in info.get('Subject','').lower() for k in ('ltr data','olof lagerkvist'))
    if not signed or not vendor:
        raise PermissionError('Installer signature/publisher not verified; no automatic execution. '
                              'Use the official vendor page for manual installation.')
    return info


def prepare_and_launch():
    if os.name != 'nt':
        raise RuntimeError('Windows required.')
    if is_installed():
        return {'status':'already_present'}
    folder=Path(tempfile.mkdtemp(prefix='FlashBridge-ImDisk-'))
    exe=fetch_official_installer(folder)
    signature=authenticode_vendor(exe)
    os.startfile(str(exe))  # user must approve UAC / installer dialogs
    return {'status':'installer_launched','file':str(exe),'signer':signature.get('Subject','')}
