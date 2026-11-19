"""Current-version package QA. No installation, network, LLM or native scientific inference.
Run with an approved harness-QA Python. --sci-source enables the installed SCI's strict
portable-package schema; this only reads the selected local implementation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
P=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qa-profile',choices=['harness','sdk_qa'],default='harness',help='Select the actual existing QA runtime metadata, not a scientific environment')
    parser.add_argument('--cbe-rnafold',type=Path,help='Approved existing RNAfold binary: version only')
    parser.add_argument('--cbe-python',type=Path,help='Approved existing CBE executable: metadata only, no inference/install')
    parser.add_argument('--rfcombined-rscript',type=Path,help='Approved existing R executable: metadata only')
    parser.add_argument('--sci-source',type=Path,help='Approved installed SCI source root; never fetch upstream')
    parser.add_argument('--sci-python',type=Path,help='Approved SCI interpreter for SDK-only checks; separate from this harness interpreter')
    a=parser.parse_args()
    if a.sci_python and not a.sci_source:parser.error('--sci-python requires --sci-source')
    try:import yaml
    except ImportError:
        if not a.sci_source:raise SystemExit('Use approved PyYAML or supply an approved installed SCI source for sci_yaml; nothing installed')
        sys.path.insert(0,str(a.sci_source.resolve(strict=True)))
        import sci_yaml as yaml
    manifest=yaml.safe_load((P/'manifest.yaml').read_text(encoding="utf-8-sig"))
    checks=[];details={};failures=[]
    def run(label,args):
        proc=subprocess.run([sys.executable,'-B']+args,cwd=P,capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=120,env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1'})
        (P/'tests'/(label+'.log')).write_text((proc.stdout+proc.stderr).replace(str(P),'<PACKAGE_ROOT>'),encoding="utf-8")
        details[label]={'returncode':proc.returncode,'scope':'Local metadata/software QA, not native scientific execution'}
        if proc.returncode:failures.append(label)
        else:checks.append(label+' passed')
        print(('PASS ' if proc.returncode==0 else 'FAIL ')+label)
        return proc
    strict='NOT_RUN_NO_APPROVED_SCI_SOURCE'
    def strict_check(check_evidence=False):
        args=[str(a.sci_python) if a.sci_python else sys.executable,'-I','-B',str(P/'scripts/sci_schema_probe.py'),'--source',str(a.sci_source),'--package',str(P)]
        if check_evidence:args+=['--check-evidence']
        proc=subprocess.run(args,capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=120,env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1'})
        if proc.returncode:
            print(proc.stderr,file=sys.stderr)
            raise SystemExit('Installed SCI schema check failed. Select its approved runtime with --sci-python; do not install SCI dependencies into scientific environments as a workaround.')
        result=json.loads(proc.stdout);assert result['package_version']==manifest['version'] and not result['scientific_execution']
        return result
    if a.sci_source:
        strict_check()
        strict='PASSED';checks.append('Installed SCI strict schema, exact leaf tool grants and disabled automatic matching passed')
        print('PASS installed SCI strict schema')
    run('contract_fixtures',['tests/test_contract.py'])
    run('dependency_catalog',['tests/test_dependencies.py'])
    policy=run('model_policy_tests',['tests/test_model_policy.py'])
    policy_match=re.search(r'Ran (\d+) tests',policy.stdout+policy.stderr)
    policy_count=int(policy_match.group(1)) if policy_match else None
    model_cli=run('model_policy_cli',['scripts/model_policy.py','tests/policy_request.json'])
    if model_cli.returncode==0:assert json.loads(model_cli.stdout)['scientific_execution'] is False
    run('setup_plan_cli',['scripts/setup_plan.py','--profile','cbe','--write-root',str(P/'tests'),'--prefix',str(P/'tests/planned_cbe_env')])
    tests=run('harness_tests',['tests/test_harness.py'])
    match=re.search(r'Ran (\d+) tests',tests.stdout+tests.stderr)
    unit_count=int(match.group(1)) if match else None
    pre=run('request_cli',['scripts/request_contract.py','tests/synthetic_request.json'])
    if pre.returncode==0:assert json.loads(pre.stdout)['scientific_execution'] is False
    auditor=run('harness_cli',['scripts/harness_audit.py','tests/synthetic_harness_record.json','--validate-schema'])
    if auditor.returncode==0:
        result=json.loads(auditor.stdout);assert result['structural_schema_checked'] and not result['model_readiness_verified'] and not result['scientific_execution']
    run('core_dependency_metadata',['scripts/check_dependencies.py','--profile','core'])
    if a.cbe_rnafold:
        native=subprocess.run([str(a.cbe_rnafold),'--version'],capture_output=True,text=True, encoding="utf-8", errors="replace",timeout=30)
        ok=native.returncode==0 and native.stdout.strip()=='RNAfold 2.5.1'
        (P/'tests/rnafold_metadata.log').write_text(native.stdout+native.stderr, encoding="utf-8")
        details['rnafold_metadata']={'returncode':native.returncode,'observed':native.stdout.strip(),'scope':'Version only; no RNA feature generation'}
        if ok:checks.append('RNAfold2.5.1 executable version passed')
        else:failures.append('RNAfold metadata')
    if a.cbe_python:run('cbe_dependency_metadata',['scripts/check_dependencies.py','--profile','cbe','--python',str(a.cbe_python)])
    if a.rfcombined_rscript:run('rfcombined_dependency_metadata',['scripts/check_dependencies.py','--profile','rfcombined','--rscript',str(a.rfcombined_rscript)])
    hp=run('harness_dependency_metadata',['scripts/check_dependencies.py','--profile',a.qa_profile,'--python',sys.executable])
    if hp.returncode==0:details['harness_dependency_metadata']['metadata']=json.loads(hp.stdout)
    from jsonschema import Draft202012Validator
    for rel in ['references/run-record.schema.json','references/request-result.schema.json']:
        Draft202012Validator.check_schema(json.loads((P/rel).read_text(encoding="utf-8-sig")))
    checks.append('Both JSON Schemas validated as Draft 2020-12')
    recipes=list((P/'dependencies').glob('environment-*.yml'))
    for recipe in recipes:
        doc=yaml.safe_load(recipe.read_text(encoding="utf-8-sig"));assert doc['channels']==(['conda-forge','bioconda'] if recipe.name=='environment-cbe.yml' else ['conda-forge'])
        if recipe.name=='environment-rfcombined.yml':assert all(isinstance(x,str) for x in doc['dependencies'])
        else:assert isinstance(doc['dependencies'][-1]['pip'],list)
    checks.append(str(len(recipes))+' environment recipes parsed; no solver or installation performed')
    # Preserve prior revision evidence, including past live behavior, without reasserting it.
    previous=json.loads((P/'tests/validation.json').read_text(encoding="utf-8-sig"))
    if previous.get('package_version')!=manifest['version']:
        archive=P/'tests/history'/('validation-v'+previous['package_version']+'.json')
        if not archive.exists():
            archive.parent.mkdir(exist_ok=True);archive.write_text(json.dumps(previous,indent=2)+'\n',encoding="utf-8")
    report={'package_id':manifest['id'],'package_version':manifest['version'],
            'local':{'status':'failed' if failures else 'passed','environment':'Python'+platform.python_version()+'; '+platform.system()+'; approved existing harness interpreter; local software/metadata QA only','checks':checks or ['No checks passed'],'strict_installed_schema':strict,'qa_dependency_profile':a.qa_profile,'unit_tests_executed':unit_count,'original_request_fixtures':8,'model_policy_csv_fixtures':16,'model_policy_unit_tests_executed':policy_count,'model_policy_test_log':'tests/model_policy_tests.log','environment_recipes_parsed':len(recipes),'details':details,'failed_checks':failures},
            'integrated':{'status':'pending','tested_commit':None,'environment':'Revised package not installed/enabled in an owning profile; installer grants and exact-dev-commit integration not tested','checks':[]},
            'live_behavioral':{'status':'not_run_for_this_revision','scope':'No delegated/installed-agent or native scientific execution performed for version '+manifest['version'],'historical_evidence':['tests/history/validation-v1.1.0.json','tests/history/validation-v1.2.0.json'],'scientific_execution':False},
            'not_tested':['Clean environment reconstruction or public-wheel availability','Native CRISPR model features/checkpoints/genomes and scientific outputs','Revised live LLM behavior and owning-profile installation','External provider authorization or remote jobs']}
    (P/'tests/validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding="utf-8")
    if failures:raise SystemExit('QA failures retained in tests/*.log; no scientific result claimed')
    if a.sci_source:strict_check(check_evidence=True)
    # Relative-path checksum inventory; not an installer lock or a publisher attestation.
    files=sorted(f for f in P.rglob('*') if f.is_file() and not f.is_symlink() and f.name!='PROVENANCE.sha256' and '__pycache__' not in f.parts)
    target=P/'tests/PROVENANCE.sha256';target.write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(P))+'\n' for f in files),encoding="utf-8")
    for line in target.read_text(encoding="utf-8-sig").splitlines():
        expected,name=line.split('  ',1);assert hashlib.sha256((P/name).read_bytes()).hexdigest()==expected,name
    if a.sci_source:strict_check()
    print(json.dumps({'package_version':manifest['version'],'strict_schema':strict,'harness_unit_tests':unit_count,'request_fixtures':8,'model_policy_csv_fixtures':16,'checksum_entries_verified':len(files),'scientific_execution':False,'live_agent_tested':False,'clean_install_tested':False},indent=2))
if __name__=='__main__':main()
