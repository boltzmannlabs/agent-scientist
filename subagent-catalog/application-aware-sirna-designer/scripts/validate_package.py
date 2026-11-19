"""Package QA only. No native scientific model, network, profile installation or live LLM.
Core is stdlib; optional QA and strict installed-SCI checks are explicitly reported.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
P=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sci-source',type=Path);p.add_argument('--sci-python',type=Path);a=p.parse_args()
    if bool(a.sci_source)!=bool(a.sci_python):p.error('Strict SDK checks need both approved --sci-source and --sci-python')
    manifest=json.loads((P/'manifest.yaml').read_text())
    checks=[];details={};failures=[]
    def strict(evidence=False):
        args=[str(a.sci_python),'-I','-B',str(P/'scripts/sci_schema_probe.py'),'--source',str(a.sci_source),'--package',str(P)]
        if evidence:args+=['--check-evidence']
        proc=subprocess.run(args,capture_output=True,text=True,timeout=120,env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1'})
        if proc.returncode:
            print(proc.stderr,file=sys.stderr);raise SystemExit('Strict installed SCI check failed; no runtime repair/install attempted')
        return json.loads(proc.stdout)
    if a.sci_source:
        result=strict();assert result['package_version']==manifest['version'];checks.append('Installed SCI strict schema/disabled automatic matching/leaf grants passed');print('PASS installed SCI schema')
    def run(name,args,expected=0):
        proc=subprocess.run([sys.executable,'-B']+args,cwd=P,capture_output=True,text=True,timeout=180,env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1'})
        (P/'tests'/(name+'.log')).write_text(proc.stdout+proc.stderr)
        details[name]={'returncode':proc.returncode,'expected_returncode':expected,'scope':'Local software/metadata QA, not model inference'}
        if proc.returncode==expected:checks.append(name+' passed');print('PASS '+name)
        else:failures.append(name);print('FAIL '+name)
        return proc
    tests=run('unit_tests',['-m','unittest','discover','-s','tests','-p','test_*.py','-v'])
    match=re.search(r'Ran (\d+) tests',tests.stdout+tests.stderr);test_count=int(match.group(1)) if match else None
    skip_match=re.search(r'skipped=(\d+)',tests.stdout+tests.stderr);skipped=int(skip_match.group(1)) if skip_match else 0
    run('request_cli',['scripts/request_contract.py','tests/sample_request.json'])
    run('record_cli',['scripts/harness_audit.py','tests/synthetic_record.json'])
    run('core_metadata',['scripts/check_dependencies.py','--profile','core','--python',sys.executable])
    blocked=run('empty_bindings',['scripts/check_bindings.py','dependencies/bindings.example.json','--profile','rnai'],2)
    assert json.loads(blocked.stdout)['model_readiness_verified'] is False
    optional={}
    if importlib.util.find_spec('jsonschema') is not None:
        from jsonschema import Draft202012Validator
        for f in ['run-record.schema.json','request-result.schema.json']:
            Draft202012Validator.check_schema(json.loads((P/'references'/f).read_text()))
        run('schema_record_cli',['scripts/harness_audit.py','tests/synthetic_record.json','--validate-schema']);optional['jsonschema']='PASSED'
    else:optional['jsonschema']='NOT_RUN_MISSING_OPTIONAL_DEPENDENCY'
    if importlib.util.find_spec('yaml') is not None:
        import yaml
        recipe=yaml.safe_load((P/'dependencies/environment-biotools.yml').read_text());assert recipe['channels']==['conda-forge','bioconda'];optional['conda_recipe_parsed']='PASSED_NO_SOLVER_OR_INSTALL'
    else:optional['conda_recipe_parsed']='NOT_RUN_MISSING_OPTIONAL_DEPENDENCY'
    with (P/'tests/sample.csv').open(newline='') as f:fixture_count=sum(1 for _ in csv.DictReader(f))
    config_sha=hashlib.sha256((P/'tests/synthetic_config.json').read_bytes()).hexdigest()
    assert json.loads((P/'tests/synthetic_record.json').read_text())['provenance']['configuration_sha256']==config_sha
    checks.append('Synthetic config/record identity verified; no scientific scores')
    report={'package_id':manifest['id'],'package_version':manifest['version'],
        'local':{'status':'failed' if failures else 'passed','environment':'Python'+platform.python_version()+' '+platform.system()+'; approved existing interpreter; local QA only','checks':checks,'unit_tests_executed':test_count,'unit_tests_skipped':skipped,'metadata_request_fixtures':fixture_count,'strict_installed_schema':'PASSED' if a.sci_source else 'NOT_RUN_NO_APPROVED_SDK','optional_checks':optional,'actual_offline_core_setup_test':'PASSED' if tests.returncode==0 and 'test_actual_offline_core_setup_and_refuse_reuse' in tests.stderr else 'NOT_VERIFIED','details':details,'failed_checks':failures},
        'integrated':{'status':'pending','tested_commit':None,'environment':'No owning-profile installation, exact-dev-commit integration or revised live LLM execution','checks':[]},
        'scientific_execution':False,'native_models_tested':False,'model_readiness_verified':False,'third_party_dependency_clean_install_tested':False,'model_assets_bundled':False,
        'limits':['Core setup test created a real disposable stdlib-only venv and verified it; this is not native model setup','Optional QA may skip if dependencies are absent; no skipped check is called passed','Native assets, exact references, applicable features, source/egress permissions, licenses and real fixtures remain prerequisites','Historical measured summaries are not package-generated results']}
    (P/'tests/validation.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise SystemExit('Package QA failed; inspect retained tests/*.log')
    if a.sci_source:strict(evidence=True)
    files=sorted(f for f in P.rglob('*') if f.is_file() and not f.is_symlink() and f.name!='PROVENANCE.sha256' and '__pycache__' not in f.parts)
    target=P/'tests/PROVENANCE.sha256'
    target.write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(P))+'\n' for f in files))
    for line in target.read_text().splitlines():
        sha,name=line.split('  ',1);assert hashlib.sha256((P/name).read_bytes()).hexdigest()==sha,name
    if a.sci_source:strict()
    print(json.dumps({'package_version':manifest['version'],'unit_tests':test_count,'unit_tests_skipped':skipped,'request_fixtures':fixture_count,'strict_schema':report['local']['strict_installed_schema'],'checksum_entries_verified':len(files),'actual_offline_core_setup_test':report['local']['actual_offline_core_setup_test'],'scientific_execution':False,'live_agent_tested':False},indent=2))
if __name__=='__main__':main()
