"""Inert policy/installation-plan regressions; not scientific or live-agent validation."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
P=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);assert spec is not None and spec.loader is not None
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
policy=module('pub_policy',P/'skills/publication-calibrated-crispr/scripts/policy.py')
setup=module('setup_plan',P/'scripts/setup_plan.py')
BASE={'task_id':'006','model_id':'DEEPPRIME_PE2','endpoint':'prime_intended','organism_context':'human_research','cell':'HEK293T','editor':'PE2','scaffold':'conventional','research_opt_in':False}
class Tests(unittest.TestCase):
    def test_all_sixteen_csv_cases(self):
        expected={x['case_id']:x for x in json.loads((P/'tests/expected.json').read_text(encoding="utf-8-sig"))['policy_cases']}
        with open(P/'tests/sample.csv',encoding='utf-8-sig', newline='') as f:rows=list(csv.DictReader(f))
        self.assertEqual(len(rows),16);self.assertEqual(set(expected),{r['case_id'] for r in rows})
        for row in rows:
            with self.subTest(case=row['case_id']):
                request={k:v for k,v in row.items() if k!='case_id' and v!=''}
                self.assertIn(request['research_opt_in'],['true','false']);request['research_opt_in']=request['research_opt_in']=='true'
                result=policy.resolve(request)
                for k,v in expected[row['case_id']].items():
                    if k!='case_id':self.assertEqual(result[k],v)
    def test_invalid_inputs(self):
        for bad in [None,[],42,dict(BASE,task_id=6),dict(BASE,model_id=[]),dict(BASE,research_opt_in='true')]:
            with self.subTest(bad=bad):self.assertEqual(policy.resolve(bad)['status'],'INVALID_REQUEST')
    def test_unknown_context_not_clearance(self):
        r=policy.resolve(dict(BASE,organism_context=''))
        self.assertEqual(r['status'],'NEEDS_INPUT');self.assertFalse(r['authorization_granted'])
    def test_missing_context_parameter(self):
        r=policy.resolve(dict(BASE,scaffold=''));self.assertEqual(r['status'],'NEEDS_INPUT')
    def test_no_permission_from_fixture_flags(self):
        r=policy.resolve(dict(BASE,approved=True,source_upload_allowed=True))
        self.assertFalse(r['authorization_granted']);self.assertFalse(r['scientific_execution']);self.assertFalse(r['model_readiness_verified'])
    def test_task_endpoint_mismatch(self):
        self.assertEqual(policy.resolve(dict(BASE,task_id='005'))['status'],'TASK_MODEL_MISMATCH')
        self.assertEqual(policy.resolve(dict(BASE,endpoint='purity'))['status'],'LABEL_CONCORDANCE_REQUIRED')
    def test_unseen_cell_not_invented(self):
        self.assertEqual(policy.resolve(dict(BASE,cell='U2OS'))['status'],'CONTEXT_MISMATCH')
    def test_standalone_skill_resources(self):
        for f in ['references/model-policy.json','references/benchmark-evidence.json','scripts/policy.py']:
            self.assertTrue((P/'skills/publication-calibrated-crispr'/f).is_file())
    def test_setup_plan_never_installs(self):
        with tempfile.TemporaryDirectory(prefix='policy_fixture_',dir=P/'tests') as tmp:
            root=Path(tmp);target=root/'new_env';r=setup.plan('cbe',target,root)
            self.assertFalse(target.exists());self.assertFalse(r['installation_executed']);self.assertFalse(r['authorization_granted']);self.assertEqual(len(r['commands']),2)
    def test_setup_outside_root_rejected(self):
        with tempfile.TemporaryDirectory(prefix='policy_fixture_',dir=P/'tests') as tmp:
            root=Path(tmp)
            with self.assertRaises(ValueError):setup.plan('cbe',root.parent/'outside',root)
            with self.assertRaises(ValueError):setup.plan('cbe',root,root)
    def test_setup_existing_prefix_rejected(self):
        with tempfile.TemporaryDirectory(prefix='policy_fixture_',dir=P/'tests') as tmp:
            root=Path(tmp);existing=root/'existing';existing.mkdir()
            with self.assertRaises(ValueError):setup.plan('cbe',existing,root)
    def test_legacy_setup_is_manual(self):
        with tempfile.TemporaryDirectory(prefix='policy_fixture_',dir=P/'tests') as tmp:
            root=Path(tmp);r=setup.plan('crispria',root/'legacy',root)
            self.assertEqual(r['status'],'MANUAL_SOURCE_SETUP_REQUIRED');self.assertEqual(r['commands'],[])
if __name__=='__main__':unittest.main(verbosity=2)
