"""Administrator-pinned GGUF import/removal. Never delete preserved model data."""

def apply_model(home, name, entry, action, allow_file=False):
    # Standalone so the same reviewed implementation runs via fixed strict SSH.
    from pathlib import Path
    import hashlib,json,os,re,urllib.request
    from urllib.parse import urlsplit
    home=Path(home)
    if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',name):
        raise ValueError('Safe llama.cpp preset identifier required')
    base=home/'.local/share/project-bots-llama'
    base.mkdir(parents=True,exist_ok=True,mode=0o700)
    registry_path=base/'registry.json'
    registry=json.loads(registry_path.read_text()) if registry_path.exists() else {}
    if action=='download':
        url=urlsplit(entry['url'])
        if not (url.scheme=='https' and url.hostname in ('huggingface.co',) and not url.username and not url.password) and not (allow_file and url.scheme=='file'):
            raise ValueError('Untrusted model download URL')
        digest=entry['sha256'];size=entry['size'];context=entry['context']
        if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest) or type(size) is not int or not 4<size<=32*1024**3 or type(context) is not int or not 2048<=context<=131072:
            raise ValueError('Pinned model hash/size/context required')
        if name in registry:
            if registry[name]['sha256']!=digest:raise ValueError('Model name already assigned')
            existing=Path(registry[name]['path'])
            if existing.is_symlink() or existing.stat().st_size!=size:raise ValueError('Registered model drift')
            with existing.open('rb') as check:actual=hashlib.file_digest(check,'sha256').hexdigest()
            if actual!=digest:raise ValueError('Registered model hash drift')
            return registry[name]
        folder=base/'gguf';folder.mkdir(exist_ok=True,mode=0o700)
        target=folder/(name+'-'+digest+'.gguf');part=target.with_suffix('.partial')
        if target.is_symlink() or part.is_symlink():raise ValueError('Unsafe model path')
        try:
            hasher=hashlib.sha256();count=0
            with urllib.request.urlopen(entry['url'],timeout=300) as response,part.open('wb') as output:
                while True:
                    chunk=response.read(1024*1024)
                    if not chunk:break
                    count+=len(chunk)
                    if count>size:raise ValueError('Model size exceeds pin')
                    hasher.update(chunk);output.write(chunk)
                output.flush();os.fsync(output.fileno())
            with part.open('rb') as check:magic=check.read(4)
            if count!=size or hasher.hexdigest()!=digest or magic!=b'GGUF':raise ValueError('GGUF hash/size/format mismatch')
            os.replace(part,target)
        finally:
            if part.exists():part.unlink()
        registry[name]={**entry,'path':str(target),'managed':True}
    elif action=='delete':
        current=registry.get(name,entry)
        if current.get('managed') is not True:raise ValueError('Preserved model cannot be removed')
        target=Path(current['path'])
        expected=base/'gguf'/(name+'-'+current['sha256']+'.gguf')
        if target!=expected or target.is_symlink():raise ValueError('Model ownership mismatch')
        with target.open('rb') as check:digest=hashlib.file_digest(check,'sha256').hexdigest()
        if digest!=current['sha256']:
            raise ValueError('Model ownership/hash mismatch')
        target.unlink();registry.pop(name,None)
    else:raise ValueError('Unsupported model operation')
    # The source registry is authoritative; a crash before preset publication is
    # uncertain and requires inspection, never blind mutation replay.
    temp=registry_path.with_suffix('.new');temp.write_text(json.dumps(registry,indent=2));temp.chmod(0o600);os.replace(temp,registry_path)
    text='version = 1\n'
    for key,value in registry.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',key) or '\n' in value['path']:raise ValueError('Unsafe preset')
        text+='['+key+']\nmodel = '+value['path']+'\nc = '+str(value['context'])+'\n'
    temp=base/'models.ini.new';temp.write_text(text);temp.chmod(0o600);os.replace(temp,base/'models.ini')
    return registry.get(name,{'removed':True,'name':name})


class SSHModelStore:
    """All SSH argv/catalog paths are trusted local admin configuration."""
    def __init__(self,config,registry_path,registry):
        self.config=config;self.registry_path=registry_path;self.registry=registry

    def apply(self,name,action):
        import inspect,json,subprocess
        from pathlib import Path
        if action=='download':
            entry=self.config['catalog'].get(name)
            if not entry:raise ValueError('Model absent from administrator-pinned catalog')
        else:
            entry=self.registry.get(name)
            if not entry or not entry.get('managed'):raise ValueError('Preserved model cannot be removed')
        script=inspect.getsource(apply_model)+'\nfrom pathlib import Path\nimport json\nprint(json.dumps(apply_model(Path.home(),'+repr(name)+','+repr(entry)+','+repr(action)+')))\n'
        result=subprocess.run(self.config['ssh']+['python3 -'],input=script,text=True,capture_output=True,timeout=600)
        if result.returncode:raise RuntimeError('Pinned model mutation failed; inspect remote state before retrying')
        actual=json.loads(result.stdout)
        if action=='download':self.registry[name]=actual
        else:self.registry.pop(name,None)
        path=Path(self.registry_path);temp=path.with_suffix('.new');temp.write_text(json.dumps(self.registry,indent=2));temp.chmod(0o600);temp.replace(path)
        return actual
