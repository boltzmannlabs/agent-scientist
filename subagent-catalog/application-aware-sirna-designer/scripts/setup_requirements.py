"""Plan first; optionally create a fresh isolated software environment after explicit approval.
No model downloads, license acceptance, scientific inference or SCI runtime mutation.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from check_dependencies import CATALOG,compare,probe
P=Path(__file__).resolve().parents[1]

def make_plan(profile,python,prefix,approved_root,wheelhouse=None,index_url=None,allow_network=False):
    if profile=='biotools':
        raise ValueError('Biotools uses the separate reviewed conda recipe; do not pip-install it')
    req=CATALOG[profile];prefix=Path(prefix).resolve();root=Path(approved_root).resolve(strict=True)
    if not root.is_dir() or prefix==root or not prefix.is_relative_to(root):raise ValueError('Fresh prefix must be strictly below the approved write root')
    if prefix.exists():raise ValueError('Existing prefix is never overwritten or reused by setup')
    for protected in [P,Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve()]:
        if prefix.is_relative_to(protected):raise ValueError('Refuse installation inside package/current runtime')
    observation=probe(python,[])
    for key in ['prefix','base_prefix']:
        if prefix.is_relative_to(Path(observation[key]).resolve()):raise ValueError('Refuse installation inside selected interpreter runtime')
    expected=req.get('python_observed');v=observation['python']
    if (expected and v!=expected) or (not expected and tuple(map(int,v.split('.')[:2]))<(3,12)):
        raise ValueError('Select the profile interpreter version before setup; it is not downloaded here')
    executable=prefix/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    commands=[[str(python),'-I','-B','-m','venv']+(['--without-pip'] if profile=='core' else [])+[str(prefix)]]
    if req['packages']:
        cmd=[str(executable),'-I','-B','-m','pip','install','--disable-pip-version-check','--no-input','--only-binary=:all:']
        if wheelhouse is not None:
            wh=Path(wheelhouse).resolve(strict=True)
            if not wh.is_dir():raise ValueError('Approved wheelhouse directory required')
            if index_url or allow_network:raise ValueError('Offline and network modes must not be mixed')
            cmd+=['--no-index','--find-links',str(wh)]
        elif allow_network and index_url:
            parsed=urlsplit(index_url)
            if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:raise ValueError('Reviewed HTTPS package index without credentials/query required')
            cmd+=['--index-url',index_url]
        else:raise ValueError('Non-core setup needs an approved offline wheelhouse or explicit network/index approval')
        cmd+=['-r',str(P/('dependencies/requirements-'+profile+'.txt'))];commands.append(cmd)
    return {'profile':profile,'status':'PLAN_ONLY','prefix':str(prefix),'approved_write_root':str(root),'python_observed':v,'commands':commands,'requirements_sha256':__import__('hashlib').sha256((P/('dependencies/requirements-'+profile+'.txt')).read_bytes()).hexdigest(),'model_assets_required':req.get('assets',[]),'scientific_execution':False,'model_readiness_verified':False}

def apply(plan,approved=False):
    if not approved:raise ValueError('Explicit install approval required; plan data is not permission')
    requirements=P/('dependencies/requirements-'+plan['profile']+'.txt')
    if __import__('hashlib').sha256(requirements.read_bytes()).hexdigest()!=plan['requirements_sha256']:
        raise ValueError('Requirements changed since planning; approval must be renewed')
    prefix=Path(plan['prefix'])
    if prefix.exists():raise ValueError('Prefix appeared since planning; refusing reuse')
    root=Path(plan['approved_write_root']);env=os.environ.copy()
    prefix.parent.mkdir(parents=True,exist_ok=True)
    prefix.mkdir(mode=0o700)  # Exclusive ownership before venv can reuse an existing directory.
    for key in list(env):
        if key in {'PYTHONPATH','PYTHONHOME','VIRTUAL_ENV'} or key.startswith('PIP_'):
            env.pop(key,None)
    # Keep installer caches/temp writes under the explicitly approved output root.
    for key,directory in [('TMPDIR','setup-temp'),('PIP_CACHE_DIR','pip-cache'),('XDG_CACHE_HOME','xdg-cache')]:
        d=prefix/directory;d.mkdir();env[key]=str(d)
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PIP_CONFIG_FILE=os.devnull)
    steps=[]
    for command in plan['commands']:
        try:
            proc=subprocess.run(command,capture_output=True,text=True,env=env,timeout=1800)
            steps.append({'command':command,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:break
        except (OSError,subprocess.TimeoutExpired) as exc:
            def text(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else (value or '')
            steps.append({'command':command,'returncode':None,'stdout':text(getattr(exc,'stdout',None)),'stderr':text(getattr(exc,'stderr',None)),'exception_type':type(exc).__name__,'exception':str(exc),'outcome':'Incomplete; do not automatically retry'})
            break
    report=dict(plan);report['steps']=steps;report['status']='SOFTWARE_SETUP_FAILED'
    if steps and all(s['returncode']==0 for s in steps):
        py=prefix/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        try:
            meta=compare(plan['profile'],probe(py,list(CATALOG[plan['profile']]['packages'])))
            report['metadata']=meta;report['status']='SOFTWARE_SETUP_VERIFIED_ONLY' if meta['status']=='PASS_METADATA_ONLY' else 'SOFTWARE_SETUP_FAILED'
        except (OSError,RuntimeError,ValueError,subprocess.TimeoutExpired):
            report['metadata_probe']='FAILED_AFTER_SETUP; no native readiness inferred'
    # Keep partial environments and real failure diagnostics; never silently retry or delete.
    if prefix.is_dir():
        with (prefix/'setup-receipt.json').open('x') as stream:json.dump(report,stream,indent=2)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',choices=sorted(k for k in CATALOG if k!='biotools'),required=True)
    p.add_argument('--python',required=True);p.add_argument('--prefix',type=Path,required=True);p.add_argument('--approved-root',type=Path,required=True)
    p.add_argument('--wheelhouse',type=Path);p.add_argument('--index-url');p.add_argument('--allow-network',action='store_true')
    p.add_argument('--execute',action='store_true');p.add_argument('--approve-install',action='store_true');a=p.parse_args()
    try:
        if a.execute and not a.approve_install:raise ValueError('Execution needs --approve-install after parent/user review')
        plan=make_plan(a.profile,a.python,a.prefix,a.approved_root,a.wheelhouse,a.index_url,a.allow_network)
        out=apply(plan,a.approve_install) if a.execute else plan
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
        out={'status':'SETUP_BLOCKED','reason':str(exc),'scientific_execution':False,'model_readiness_verified':False}
    print(json.dumps(out,indent=2));return 0 if out['status'] in {'PLAN_ONLY','SOFTWARE_SETUP_VERIFIED_ONLY'} else 2
if __name__=='__main__':raise SystemExit(main())
