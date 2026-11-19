"""Read only explicitly approved assets; verify hashes, never load models or infer permissions."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from check_dependencies import CATALOG

def check_bindings(bindings,profile,read_roots=(),verify=False):
    result={'status':'ASSET_CHECK_BLOCKED','errors':[],'verified_assets':[],'scientific_execution':False,'model_readiness_verified':False,'authorization_granted':False}
    if not isinstance(bindings,dict) or not isinstance(bindings.get('assets'),list):
        result['errors'].append('Bindings object with assets array required');return result
    byid={}
    for a in bindings['assets']:
        if not isinstance(a,dict) or not isinstance(a.get('id'),str) or a['id'] in byid:
            result['errors'].append('Asset entries need unique text IDs');continue
        byid[a['id']]=a
    required=CATALOG[profile].get('assets',[])
    if not required:
        result['status']='NO_NATIVE_ASSETS_CHECKED';return result
    roots=[Path(p).resolve(strict=True) for p in read_roots] if verify else []
    if verify and (not roots or any(not p.is_dir() for p in roots)):
        result['errors'].append('Explicit approved read-root directories required');return result
    for identifier in required:
        a=byid.get(identifier,{})
        if not isinstance(a.get('path'),str) or not a['path'].strip() or not isinstance(a.get('sha256'),str) or not re.fullmatch('[a-f0-9]{64}',a['sha256']):
            result['errors'].append(identifier+': missing explicit path/SHA-256');continue
        if a.get('license_reviewed') is not True:
            result['errors'].append(identifier+': parent license/asset review not recorded');continue
        if not verify:continue
        try:
            raw=Path(a['path'])
            if not raw.is_absolute():raise ValueError('Absolute asset paths required')
            p=raw.resolve(strict=True)
            if not any(p.is_relative_to(root) for root in roots) or not p.is_file():raise ValueError('Outside approved roots or not a regular file')
            h=hashlib.sha256()
            with p.open('rb') as stream:
                for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
            if h.hexdigest()!=a['sha256']:raise ValueError('Asset checksum mismatch')
            result['verified_assets'].append(identifier)
        except (OSError,ValueError):result['errors'].append(identifier+': missing, outside approved root, or checksum mismatch')
    if not result['errors']:result['status']='PASS_ASSET_INTEGRITY_ONLY' if verify else 'METADATA_COMPLETE_NO_ASSET_READS'
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('bindings',type=Path);p.add_argument('--profile',choices=sorted(CATALOG),required=True)
    p.add_argument('--verify-assets',action='store_true');p.add_argument('--read-root',action='append',type=Path,default=[]);a=p.parse_args()
    if bool(a.read_root)!=a.verify_assets:p.error('Asset reads need --verify-assets and explicit --read-root')
    try:out=check_bindings(json.loads(a.bindings.read_text(encoding="utf-8-sig")),a.profile,a.read_root,a.verify_assets)
    except (OSError,ValueError):out={'status':'ASSET_CHECK_BLOCKED','errors':['Invalid bindings/root input'],'scientific_execution':False,'model_readiness_verified':False}
    print(json.dumps(out,indent=2));return 2 if out.get('errors') else 0
if __name__=='__main__':raise SystemExit(main())
