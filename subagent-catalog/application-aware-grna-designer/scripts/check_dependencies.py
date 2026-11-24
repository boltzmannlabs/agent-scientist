"""Read-only dependency version checks. No installation, network calls or native inference.
A passing result verifies observed version metadata, not scientific/backend readiness.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
P=Path(__file__).resolve().parents[1]
CATALOG=json.loads((P/'dependencies.json').read_text(encoding="utf-8-sig"))

def probe_python(executable, package_names=None):
    # Resolve effective versions using the interpreter's own lookup precedence.
    # Enumerating distributions into a dict incorrectly lets later duplicate metadata win.
    code='''import sys,json,re
norm=lambda s:re.sub(r"[-_.]+","-",s).lower()
wanted=json.loads(sys.argv[1])
try:
 import importlib.metadata as m
 all_d=list(m.distributions())
 names=wanted or sorted(set(x.metadata['Name'] for x in all_d if x.metadata.get('Name')))
 d={}
 for name in names:
  try:d[norm(name)]=m.version(name)
  except m.PackageNotFoundError:pass
 visible={}
 for x in all_d:
  name=x.metadata.get('Name')
  if name and norm(name) in d:visible.setdefault(norm(name),set()).add(x.version)
 conflicts={k:sorted(v) for k,v in visible.items() if len(v)>1}
except ImportError:
 import pkg_resources
 names=wanted or [x.key for x in pkg_resources.working_set]
 d={}
 for name in names:
  try:d[norm(name)]=pkg_resources.get_distribution(name).version
  except pkg_resources.DistributionNotFound:pass
 conflicts={}
print(json.dumps({'python':sys.version.split()[0],'packages':d,'duplicate_distribution_metadata':conflicts}))
'''
    r=subprocess.run([executable,'-B','-c',code,json.dumps(package_names)],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=45)
    if r.returncode:
        raise RuntimeError('Selected executable metadata probe failed; no scientific execution occurred')
    return json.loads(r.stdout)

def canonical_name(name):
    return re.sub(r'[-_.]+','-',name).lower()

def check_python(profile, observed):
    required=CATALOG['profiles'][profile]
    packages={canonical_name(k):v for k,v in observed['packages'].items()}
    missing=[]
    mismatch=[]
    for name,wanted in required['observed_distribution_versions'].items():
        actual=packages.get(canonical_name(name))
        if actual is None:
            missing.append(name)
        elif actual!=wanted:
            mismatch.append({'package':name,'expected':wanted,'observed':actual})
    interpreter_match=observed['python']==required['python_observed']
    return {'profile':profile,'status':'PASS_METADATA_ONLY' if not missing and not mismatch and interpreter_match else 'DEPENDENCY_MISMATCH','observed_python':observed['python'],'expected_python':required['python_observed'],'interpreter_match':interpreter_match,'missing_distributions':missing,'version_mismatches':mismatch,'duplicate_distribution_metadata':observed.get('duplicate_distribution_metadata',{}),'version_resolution':'Effective interpreter metadata lookup; duplicate metadata is reported, not a clean-install guarantee.','scientific_execution':False,'model_readiness_verified':False}

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--profile',choices=['core']+list(CATALOG['profiles']),default='core')
    a.add_argument('--python',dest='python_executable',help='Approved isolated native Python executable; selecting it authorizes only the described metadata probe')
    a.add_argument('--rscript',help='Approved isolated Rscript executable for metadata probe')
    args=a.parse_args()
    if args.profile=='core':
        if args.python_executable or args.rscript:
            a.error('core checks the currently executing trusted Python only')
        ok=sys.version_info[:2]>=tuple(CATALOG['core']['python_minimum'])
        result={'profile':'core','status':'PASS_METADATA_ONLY' if ok else 'DEPENDENCY_MISMATCH','observed_python':sys.version.split()[0],'third_party_packages_required':[],'scientific_execution':False,'model_readiness_verified':False}
    elif 'R_observed' in CATALOG['profiles'][args.profile]:
        if not args.rscript or args.python_executable:
            a.error('R profiles require --rscript and do not accept --python')
        r=CATALOG['profiles'][args.profile];names=list(r['observed_distribution_versions'])
        code='cat("R_VERSION\\t",as.character(getRversion()),"\\n",sep="");for(p in c('+','.join(json.dumps(n) for n in names)+')){v<-tryCatch(as.character(packageVersion(p)),error=function(e)"MISSING");cat(p,"\\t",v,"\\n",sep="")}'
        proc=subprocess.run([args.rscript,'-e',code],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=45)
        if proc.returncode:raise RuntimeError('Selected Rscript metadata probe failed')
        observed=dict(line.split('\t',1) for line in proc.stdout.splitlines() if '\t' in line)
        diff={n:{'expected':v,'observed':observed.get(n)} for n,v in r['observed_distribution_versions'].items() if observed.get(n)!=v}
        ok=not diff and observed.get('R_VERSION')==r['R_observed']
        result={'profile':args.profile,'status':'PASS_METADATA_ONLY' if ok else 'DEPENDENCY_MISMATCH','observed_R':observed.get('R_VERSION'),'expected_R':r['R_observed'],'version_mismatches':diff,'scientific_execution':False,'model_readiness_verified':False}
    else:
        if not args.python_executable or args.rscript:
            a.error('native Python profiles require --python and do not accept --rscript')
        result=check_python(args.profile,probe_python(args.python_executable,list(CATALOG['profiles'][args.profile]['observed_distribution_versions'])))
    print(json.dumps(result,indent=2))
    return 0 if result['status']=='PASS_METADATA_ONLY' else 2
if __name__=='__main__':
    raise SystemExit(main())
