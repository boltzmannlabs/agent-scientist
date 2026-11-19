"""Trusted executable metadata probe only; not a model import or scientific readiness test."""
import argparse
import json
from pathlib import Path
import re
import subprocess

P=Path(__file__).resolve().parents[1]
CATALOG=json.loads((P/'dependencies.json').read_text())['profiles']
def canonical(n):return re.sub(r'[-_.]+','-',n).lower()

def probe(executable,names):
    code='''import sys,json,re
import importlib.metadata as m
norm=lambda s:re.sub(r"[-_.]+","-",s).lower()
names=json.loads(sys.argv[1]);versions={};missing=[]
for name in names:
 try:versions[norm(name)]=m.version(name)
 except m.PackageNotFoundError:missing.append(name)
visible={}
for d in m.distributions():
 name=d.metadata.get('Name')
 if name and norm(name) in versions:visible.setdefault(norm(name),set()).add(d.version)
print(json.dumps({'python':sys.version.split()[0],'packages':versions,'missing':missing,'duplicate_metadata':{k:sorted(v) for k,v in visible.items() if len(v)>1},'prefix':sys.prefix,'base_prefix':sys.base_prefix}))
'''
    proc=subprocess.run([str(executable),'-I','-B','-c',code,json.dumps(names)],capture_output=True,text=True,timeout=90)
    if proc.returncode:raise RuntimeError('Trusted interpreter metadata probe failed; no model was executed')
    return json.loads(proc.stdout)

def compare(profile,observed):
    req=CATALOG[profile];actual={canonical(k):v for k,v in observed.get('packages',{}).items()}
    mismatch={k:{'expected':v,'observed':actual.get(canonical(k))} for k,v in req.get('packages',{}).items() if actual.get(canonical(k))!=v}
    version=tuple(int(x) for x in observed['python'].split('.')[:2])
    expected=req.get('python_observed');matches=observed['python']==expected if expected else version>=(3,12)
    return {'profile':profile,'status':'PASS_METADATA_ONLY' if matches and not mismatch else 'DEPENDENCY_MISMATCH','python':observed['python'],'python_matches':matches,'version_mismatches':mismatch,'duplicate_metadata':observed.get('duplicate_metadata',{}),'scientific_execution':False,'model_readiness_verified':False,'clean_install_verified':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=sorted(k for k in CATALOG if k!='biotools'),required=True);p.add_argument('--python',required=True);a=p.parse_args()
    try:r=compare(a.profile,probe(a.python,list(CATALOG[a.profile]['packages'])))
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):r={'status':'PROBE_FAILED','scientific_execution':False,'model_readiness_verified':False}
    print(json.dumps(r,indent=2));return 0 if r['status']=='PASS_METADATA_ONLY' else 2
if __name__=='__main__':raise SystemExit(main())
