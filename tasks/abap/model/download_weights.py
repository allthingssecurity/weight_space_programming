"""Download the public selected-model release asset and verify its SHA-256."""
import hashlib,json,os,tempfile,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def main():
    spec=json.loads((ROOT/'weights.json').read_text());target=ROOT/spec['file']
    if target.exists() and sha256(target)==spec['sha256']:
        print('Verified:',target);return
    tmp=None
    try:
        with tempfile.NamedTemporaryFile(dir=ROOT,suffix='.part',delete=False) as out:
            tmp=Path(out.name)
            request=urllib.request.Request(spec['url'],headers={'User-Agent':'weight-space-programming-model-downloader'})
            with urllib.request.urlopen(request,timeout=120) as response:
                for chunk in iter(lambda:response.read(1024*1024),b''):out.write(chunk)
        if tmp.stat().st_size!=spec['bytes'] or sha256(tmp)!=spec['sha256']:
            raise RuntimeError('Model artifact size or SHA-256 mismatch; download was not installed.')
        os.replace(tmp,target);print('Downloaded and verified:',target)
    finally:
        if tmp is not None and tmp.exists():tmp.unlink()
if __name__=='__main__':main()
