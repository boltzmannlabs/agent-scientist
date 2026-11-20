"""Inert dependency catalog/recipe consistency tests, not installation or scientific validation."""
import sys

sys.dont_write_bytecode = True  # imported by CI runners; never leave bytecode in the package tree
import csv
import importlib.util
import json
from pathlib import Path
P=Path(__file__).resolve().parents[1]
d=json.loads((P/'dependencies.json').read_text(encoding="utf-8-sig"))
assert d['package_id']=='application-aware-grna-designer' and d['package_version']=='1.3.0'
assert d['core']['third_party_pip_dependencies']==[]
assert d['installation_policy']['implicit_install'] is False
for name,profile in d['profiles'].items():
    if 'R_observed' in profile:
        with open(P/profile['package_file'], encoding='utf-8-sig') as f:
            actual={r['package']:r['observed_version'] for r in csv.DictReader(f)}
        assert actual==profile['observed_distribution_versions']
        continue
    actual={}
    for rel in profile['requirements_files']:
        for line in (P/rel).read_text(encoding="utf-8-sig").splitlines():
            if line and not line.startswith('#'):
                package,version=line.split('==',1)
                assert package not in actual
                actual[package]=version
    assert actual==profile['observed_distribution_versions'],name
    if 'environment_file' in profile:
        text=(P/profile['environment_file']).read_text(encoding="utf-8-sig")
        assert 'python='+profile['python_observed'] in text
        assert 'requirements-'+name+'.txt' in text
    assert profile['clean_install_tested'] is False
spec=importlib.util.spec_from_file_location('dependency_checker',P/'scripts/check_dependencies.py')
assert spec is not None and spec.loader is not None
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r=d['profiles']['editing']
synthetic={'python':r['python_observed'],'packages':dict(r['observed_distribution_versions'])}
assert m.check_python('editing',synthetic)['status']=='PASS_METADATA_ONLY'
del synthetic['packages']['torch']
assert m.check_python('editing',synthetic)['status']=='DEPENDENCY_MISMATCH'
synthetic={'python':'0.0.0','packages':dict(r['observed_distribution_versions'])}
assert m.check_python('editing',synthetic)['status']=='DEPENDENCY_MISMATCH'
print('PASS dependency catalog and '+str(len(d['profiles']))+' separate profile inventories; 3 synthetic software-metadata checker cases')
print('No packages installed; no models executed; clean environment reconstruction NOT tested')
