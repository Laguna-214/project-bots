#!/usr/bin/env python3
"""Fetch checksum-pinned official Linux/x64 build tools into a private user cache."""
import concurrent.futures
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tarfile
import zipfile

CACHE = pathlib.Path(os.environ.get('NATIVE_TOOLS_CACHE', str(pathlib.Path(os.environ.get('XDG_CACHE_HOME', str(pathlib.Path.home()/'.cache')))/'project-bots/native-tools'))).expanduser().absolute()
CACHE.mkdir(parents=True, exist_ok=True, mode=0o700)
if CACHE.is_symlink() or not CACHE.is_dir() or CACHE.stat().st_uid != os.getuid() or CACHE.stat().st_mode & 0o077:
    raise ValueError('Build tools require a caller-owned private cache directory (0700); permissions were not changed')
LOCK=json.loads(pathlib.Path(__file__).with_name('toolchains.lock.json').read_text())

def install(item):
    name=item['url'].rsplit('/',1)[1]
    archive=CACHE/name
    if not archive.exists():
        partial=archive.with_suffix(archive.suffix+'.partial')
        subprocess.run(['curl','--fail','--location','--silent','--show-error','--retry','2','--max-time','180','--output',str(partial),item['url']],check=True)
        partial.rename(archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('Checksum mismatch; remove the corrupt archive and retry: '+str(archive))
    print('verified',name,item['sha256'],flush=True)
    dest=CACHE/item['destination']
    if dest.exists(): return
    stage=CACHE/('extract-'+name)
    shutil.rmtree(stage,ignore_errors=True)
    stage.mkdir()
    if item['format']=='tar':
        with tarfile.open(archive) as t:t.extractall(stage,filter='data')
    else:
        with zipfile.ZipFile(archive) as z:z.extractall(stage)
    children=list(stage.iterdir())
    if len(children)!=1:raise RuntimeError('Unexpected archive layout: '+name)
    dest.parent.mkdir(parents=True,exist_ok=True)
    children[0].rename(dest)
    stage.rmdir()
    for f in dest.rglob('*'):
        if f.is_file():
            with f.open('rb') as stream: magic=stream.read(4)
            if magic==b'\x7fELF' or f.suffix=='.sh' or (f.parent.name=='bin' and not f.suffix):f.chmod(0o755)

if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(install,LOCK.values()))
    print('Toolchains ready:',CACHE)
