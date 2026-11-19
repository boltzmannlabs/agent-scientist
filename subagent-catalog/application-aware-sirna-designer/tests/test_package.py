"""Non-scientific contract, setup and asset QA. No siRNA sequences, models or network."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from typing import Any
import importlib
P=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(P/'scripts'))
C=importlib.import_module('request_contract')
D=importlib.import_module('check_dependencies')
S=importlib.import_module('setup_requirements')
B=importlib.import_module('check_bindings')

def base() -> dict[str,Any]:
    return {'mode':'DESIGN','task_id':'001','safety_context':'noninfectious_human_research','organism':'human','modality':'siRNA'}

class Routing(unittest.TestCase):
    def test_fixed_csv_cases(self):
        expected=json.loads((P/'tests/expected.json').read_text(encoding="utf-8-sig"))
        with (P/'tests/sample.csv').open(newline='') as f:rows=list(csv.DictReader(f))
        self.assertEqual(set(expected['statuses']),{r['case_id'] for r in rows})
        for row in rows:
            with self.subTest(case=row['case_id']):
                result=C.preflight(row);self.assertEqual(result['status'],expected['statuses'][row['case_id']]);self.assertFalse(result['scientific_execution']);self.assertFalse(result['authorization_granted'])
    def test_reject_unhashable_and_nonobject_inputs(self):
        for value in [None,[],7,{'mode':[]},{'mode':'DESIGN','task_id':{}}]:self.assertEqual(C.preflight(value)['status'],'INVALID_REQUEST')
    def test_exact_ids_not_repaired(self):
        r=base();r['task_id']='01';self.assertEqual(C.preflight(r)['status'],'INVALID_REQUEST')
    def test_context_never_defaults_to_safe(self):
        r=base();r.pop('safety_context');self.assertIn('safety_context',C.preflight(r)['missing_inputs'])
    def test_safety_precedes_modality(self):
        r=base();r.update(safety_context='pathogen',modality='Cas13');self.assertEqual(C.preflight(r)['status'],'REVIEW_ONLY')
    def test_sirna_is_not_crispr_or_aso(self):
        for m in ['Cas13','CRISPR','ASO',True,[]]:
            r=base();r['modality']=m;self.assertEqual(C.preflight(r)['status'],'OUT_OF_SCOPE')
    def test_clinical_request_not_activated(self):
        r=base();r['clinical_use']=True;self.assertEqual(C.preflight(r)['status'],'REVIEW_ONLY')
    def test_allele_cns_and_orthogonal_requirements(self):
        for task,field in [('004','verified_variant_manifest'),('007','isoform_objective'),('011','orthogonal_evidence_manifest')]:
            r=base();r['task_id']=task;self.assertIn(field,C.preflight(r)['missing_inputs'])
    def test_boolean_paths_do_not_supply_inputs(self):
        r=base();r.update(reference_manifest=True,setup_report=7);self.assertIn('reference_manifest',C.preflight(r)['missing_inputs']);self.assertIn('setup_report',C.preflight(r)['missing_inputs'])
    def test_metadata_completion_does_not_grant_readiness(self):
        r=base()
        for key in C.preflight(r)['missing_inputs']:r[key]='metadata-pointer-not-permission'
        out=C.preflight(r);self.assertEqual(out['status'],'METADATA_COMPLETE_REQUIRES_NATIVE_AND_PARENT_CHECKS');self.assertFalse(out['authorization_granted'])
    def test_evaluate_does_not_generate(self):
        r=base();r.update(mode='EVALUATE',requested_properties='efficacy');out=C.preflight(r);self.assertNotIn('generation',out['required_stages']);self.assertIn('candidate_manifest',out['missing_inputs'])
    def test_benchmark_needs_labels_and_exclusion(self):
        r=base();r['mode']='BENCHMARK';out=C.preflight(r);self.assertIn('measured_label_manifest',out['missing_inputs']);self.assertIn('split_exclusion_manifest',out['missing_inputs'])
    def test_malformed_json_cli_is_structured(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'bad.json';p.write_text('{', encoding="utf-8");result=subprocess.run([sys.executable,'-B',str(P/'scripts/request_contract.py'),str(p)],capture_output=True,text=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode,2);self.assertEqual(json.loads(result.stdout)['status'],'INVALID_REQUEST')
    def test_task_application_copy_matches(self):
        master=json.loads((P/'references/applications.json').read_text(encoding="utf-8-sig"))['applications'];copy=json.loads((P/'skills/application-aware-sirna-workflow/references/application-map.json').read_text(encoding="utf-8-sig"))['applications'];self.assertEqual(master,copy)

class Dependencies(unittest.TestCase):
    def test_exact_profiles_not_model_readiness(self):
        for name,req in D.CATALOG.items():
            if name=='biotools':continue
            o={'python':req.get('python_observed','3.12.0'),'packages':req['packages']};out=D.compare(name,o);self.assertEqual(out['status'],'PASS_METADATA_ONLY');self.assertFalse(out['model_readiness_verified'])
    def test_missing_packages_and_wrong_python_fail(self):
        o={'python':'3.12.0','packages':{}};self.assertEqual(D.compare('rnai',o)['status'],'DEPENDENCY_MISMATCH')
    def test_duplicate_metadata_is_not_erased(self):
        req=D.CATALOG['qa'];o={'python':req['python_observed'],'packages':req['packages'],'duplicate_metadata':{'pyyaml':['old','effective']}};self.assertEqual(D.compare('qa',o)['duplicate_metadata'],o['duplicate_metadata'])
    def test_requirement_files_match_catalog(self):
        for name,req in D.CATALOG.items():
            if name=='biotools':continue
            values=[x for x in (P/('dependencies/requirements-'+name+'.txt')).read_text(encoding="utf-8-sig").splitlines() if x and not x.startswith('#')];self.assertEqual(values,[k+'=='+v for k,v in req['packages'].items()])

class Setup(unittest.TestCase):
    def plan(self,root,profile='core',**kwargs):return S.make_plan(profile,sys.executable,root/'fresh-env',root,**kwargs)
    def test_plan_has_no_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan=self.plan(root);self.assertEqual(plan['status'],'PLAN_ONLY');self.assertFalse((root/'fresh-env').exists())
    def test_apply_requires_approval_before_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):S.apply(self.plan(root))
            self.assertFalse((root/'fresh-env').exists())
    def test_existing_prefix_never_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'fresh-env').mkdir()
            with self.assertRaises(ValueError):self.plan(root)
    def test_root_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):S.make_plan('core',sys.executable,root.parent/'outside-env',root)
    def test_native_install_needs_offline_or_network_choice(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(S,'probe',return_value={'python':D.CATALOG['qa']['python_observed'],'prefix':str(root/'runtime'),'base_prefix':str(root/'runtime')}):
                with self.assertRaises(ValueError):self.plan(root,'qa')
    def test_credential_bearing_index_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with patch.object(S,'probe',return_value={'python':D.CATALOG['qa']['python_observed'],'prefix':str(root/'runtime'),'base_prefix':str(root/'runtime')}):
                with self.assertRaises(ValueError):self.plan(root,'qa',allow_network=True,index_url='https'+':'+chr(47)*2+'example:secret@example.invalid/simple')
    def test_changed_requirements_hash_blocks_apply(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan=self.plan(root);plan['requirements_sha256']='0'*64
            with self.assertRaises(ValueError):S.apply(plan,True)
            self.assertFalse((root/'fresh-env').exists())
    def test_incomplete_setup_keeps_receipt_and_clears_inherited_pip_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan=self.plan(root)
            with patch.dict(S.os.environ,{'PIP_TARGET':'unapproved-destination'}),patch.object(S.subprocess,'run',side_effect=OSError('Synthetic launch-failure fixture')) as process:
                out=S.apply(plan,True)
            self.assertEqual(out['status'],'SOFTWARE_SETUP_FAILED');self.assertIsNone(out['steps'][0]['returncode']);self.assertEqual(out['steps'][0]['exception_type'],'OSError');self.assertNotIn('PIP_TARGET',process.call_args.kwargs['env']);self.assertTrue((root/'fresh-env/setup-receipt.json').is_file());self.assertEqual(process.call_count,1)
    def test_actual_offline_core_setup_and_refuse_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan=self.plan(root);out=S.apply(plan,True)
            self.assertEqual(out['status'],'SOFTWARE_SETUP_VERIFIED_ONLY');self.assertFalse(out['model_readiness_verified']);self.assertTrue((root/'fresh-env/setup-receipt.json').is_file())
            self.assertNotIn('pip install',' '.join(' '.join(c) for c in plan['commands']))
            with self.assertRaises(ValueError):S.apply(plan,True)

class Assets(unittest.TestCase):
    def make(self,root):
        f=root/'inert-metadata.txt';f.write_text('Synthetic software asset fixture, not model weights or scientific data', encoding="utf-8")
        return {'assets':[{'id':k,'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'license_reviewed':True} for k in D.CATALOG['rnai']['assets']]}
    def test_empty_template_blocks(self):
        obj=json.loads((P/'dependencies/bindings.example.json').read_text(encoding="utf-8-sig"));self.assertTrue(B.check_bindings(obj,'rnai')['errors'])
    def test_metadata_check_does_not_open_declared_asset(self):
        with tempfile.TemporaryDirectory() as temp:
            obj=self.make(Path(temp))
            with patch.object(Path,'open',side_effect=AssertionError('unapproved read')):out=B.check_bindings(obj,'rnai')
            self.assertEqual(out['status'],'METADATA_COMPLETE_NO_ASSET_READS')
    def test_actual_hash_checks_do_not_certify_native_readiness(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=B.check_bindings(self.make(root),'rnai',[root],True);self.assertEqual(out['status'],'PASS_ASSET_INTEGRITY_ONLY');self.assertFalse(out['model_readiness_verified'])
    def test_checksum_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);obj=self.make(root);(root/'inert-metadata.txt').write_text('changed', encoding="utf-8");self.assertTrue(B.check_bindings(obj,'rnai',[root],True)['errors'])
    def test_outside_root_and_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);allowed=root/'allowed';allowed.mkdir();obj=self.make(root);self.assertTrue(B.check_bindings(obj,'rnai',[allowed],True)['errors'])
            (allowed/'link').symlink_to(root/'inert-metadata.txt')
            for a in obj['assets']:a['path']=str(allowed/'link')
            self.assertTrue(B.check_bindings(obj,'rnai',[allowed],True)['errors'])
    def test_missing_license_review_is_not_fixed_by_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            obj=self.make(Path(temp));obj['assets'][0]['license_reviewed']=False;self.assertTrue(B.check_bindings(obj,'rnai')['errors'])
    def test_duplicate_asset_ids_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            obj=self.make(Path(temp));obj['assets'].append(obj['assets'][0]);self.assertTrue(B.check_bindings(obj,'rnai')['errors'])
if __name__=='__main__':unittest.main(verbosity=2)
