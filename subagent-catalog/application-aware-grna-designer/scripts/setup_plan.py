"""Create a review-only dependency plan. Never install or execute the emitted commands."""
import argparse
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
CATALOG=json.loads((P/'dependencies.json').read_text(encoding="utf-8-sig"))

def plan(profile,prefix,write_root):
    prefix=Path(prefix).resolve();root=Path(write_root).resolve()
    if not prefix.is_relative_to(root) or prefix==root:raise ValueError('Environment prefix must be a child of the parent-approved write root')
    if prefix.exists():raise ValueError('Prefix already exists: use an approved read-only dependency check, not an in-place install')
    record={'status':'PLAN_ONLY_REQUIRES_PARENT_APPROVAL','profile':profile,'scientific_execution':False,'installation_executed':False,'authorization_granted':False,'commands':[],'required_assets':CATALOG['external_assets_required'].get(profile,[]),'notes':['Plan output and path checks are not permission or a sandbox.','Set package caches and temporary storage inside the approved write root.','Review licenses, downloads, cost, disk and effective compute before execution.','Python requirements are observed pins, not complete reproducible or clean-solver guarantees.']}
    if profile=='core':record['notes'].append('Use approved Python3.12+; standard-library request/policy fixtures require no external packages.');return record
    cfg=CATALOG['profiles'][profile]
    if 'environment_file' not in cfg:
        record['status']='MANUAL_SOURCE_SETUP_REQUIRED';return record
    recipe=P/cfg['environment_file'];record['commands'].append(['conda','env','create','--prefix',str(prefix),'--file',str(recipe)])
    if profile=='editing':record['notes'].append('Install requirements-torch-cpu.txt separately using a recipient-reviewed CPU-wheel index; none is selected or invoked by this plan.')
    binding=str(prefix/'bin/Rscript') if 'R_observed' in cfg else str(prefix/'bin/python')
    check=['APPROVED_QA_PYTHON','-B',str(P/'scripts/check_dependencies.py'),'--profile',profile,'--rscript' if 'R_observed' in cfg else '--python',binding]
    record['commands'].append(check)
    if profile=='cbe':record['notes'].append('Additionally bind RNAfold2.5.1 from this prefix and verify original source/energy dictionary/25CBE+5V0weights; native fixture required before readiness.')
    return record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',required=True,choices=['core']+list(CATALOG['profiles']))
    parser.add_argument('--prefix',required=True,type=Path)
    parser.add_argument('--write-root',required=True,type=Path)
    args=parser.parse_args()
    try:result=plan(args.profile,args.prefix,args.write_root)
    except ValueError as exc:parser.error(str(exc))
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
