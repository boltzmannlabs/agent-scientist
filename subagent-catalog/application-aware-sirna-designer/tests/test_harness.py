"""Synthetic metadata/artifact QA only. No guide design, scientific model or invented efficacy."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from typing import Any
P=Path(__file__).resolve().parents[1]

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,P/file)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
H=load('harness_audit','scripts/harness_audit.py')
C=load('request_contract','scripts/request_contract.py')
D=load('dependency_check','scripts/check_dependencies.py')

def record():
    return json.loads((P/'tests/synthetic_record.json').read_text(encoding="utf-8-sig"))
def native_declaration():
    # Declared fields for code-branch tests; not actual model results.
    r=record();r['execution_class']='NATIVE_INFERENCE'
    r['stages']=[{'name':'synthetic_native_declaration','status':'PASS','reason':'Synthetic metadata branch test; no native model executed','execution_kind':'FRESH_NATIVE_INFERENCE','native_forward_pass':True,'exit_code':0,'expected_rows':2,'observed_rows':2,'feature_integrity':'VERIFIED_NATIVE','inference_mode':'eval'}]
    return r

class RecordTests(unittest.TestCase):
    def test_software_fixture_exact_expected(self):
        self.assertEqual(H.audit(record()),json.loads((P/'tests/expected_record.json').read_text(encoding="utf-8-sig")))
    def test_legacy_record_is_not_silently_promoted(self):
        r=record();r.pop('schema_version');self.assertTrue(H.audit(r)['errors'])
    def test_exact_task_tokens(self):
        r=record();r['task_id']='2';self.assertTrue(H.audit(r)['errors'])
    def test_required_provenance(self):
        r=record();r['provenance']={};self.assertTrue(H.audit(r)['errors'])
    def test_pretrained_only_blocks_new_training(self):
        r=record();r['provenance']['training_performed']=True;self.assertTrue(H.audit(r)['errors'])
    def test_native_class_requires_actual_declared_stage(self):
        r=record();r['execution_class']='NATIVE_INFERENCE';self.assertTrue(H.audit(r)['errors'])
    def test_consistent_declared_native_metadata_does_not_certify_readiness(self):
        a=H.audit(native_declaration());self.assertEqual(a['errors'],[]);self.assertFalse(a['scientific_execution']);self.assertFalse(a['model_readiness_verified'])
    def test_native_exit_failure(self):
        r=native_declaration();r['stages'][0]['exit_code']=1;self.assertTrue(H.audit(r)['errors'])
    def test_native_forward_flag_required(self):
        r=native_declaration();r['stages'][0]['native_forward_pass']=False;self.assertTrue(H.audit(r)['errors'])
    def test_cardinality_mismatch(self):
        r=native_declaration();r['stages'][0]['observed_rows']=1;self.assertTrue(H.audit(r)['errors'])
    def test_boolean_counts_are_not_integers(self):
        r=native_declaration();r['stages'][0]['observed_rows']=True;self.assertTrue(H.audit(r)['errors'])
    def test_cached_score_is_not_fresh_native(self):
        r=native_declaration();r['execution_class']='AUTHOR_SCORE_REPLAY';s=r['stages'][0];s['execution_kind']='HASH_BOUND_CACHE_REUSE';s['score_source_sha256']=r['provenance']['configuration_sha256'];self.assertTrue(H.audit(r)['errors'])
        s['native_forward_pass']=False;self.assertEqual(H.audit(r)['errors'],[])
    def test_cache_requires_hash(self):
        r=native_declaration();r['execution_class']='AUTHOR_SCORE_REPLAY';s=r['stages'][0];s.update(execution_kind='AUTHOR_SCORE_REPLAY',native_forward_pass=False);self.assertTrue(H.audit(r)['errors'])
    def test_random_learned_features_block_native_pass(self):
        r=native_declaration();r['stages'][0]['feature_integrity']='SYNTHETIC_OR_RANDOM';self.assertTrue(H.audit(r)['errors'])
    def test_native_dropout_warning(self):
        r=native_declaration();r['stages'][0]['inference_mode']='native_train_mode';a=H.audit(r);self.assertEqual(a['errors'],[]);self.assertTrue(a['warnings'])
    def test_completed_record_cannot_hide_unrun_stage(self):
        r=record();r['stages'][0].update(status='NOT_RUN',execution_kind='NOT_RUN');self.assertTrue(H.audit(r)['errors'])
        r.update(status='BLOCKED',execution_class='NO_EXECUTION');self.assertEqual(H.audit(r)['errors'],[])
    def test_contextual_comparison_has_no_matched_delta(self):
        r=record();r['comparison'].update(cohort_relation='DIFFERENT',matched_protocol_delta=0.1);self.assertTrue(H.audit(r)['errors'])
    def test_nonfinite_delta_rejected(self):
        r=record();r['comparison'].update(cohort_relation='MATCHED',endpoint_relation='MATCHED',protocol_relation='MATCHED',matched_protocol_delta=float('nan'));self.assertTrue(H.audit(r)['errors'])
    def test_software_only_cannot_enter_completed_benchmarks(self):
        r=record();r['publication']='benchmark';self.assertTrue(H.audit(r)['errors'])
    def test_synthetic_metadata_never_becomes_measured_benchmark(self):
        r=native_declaration();r['publication']='benchmark';r['benchmark']={'measured_labels':True,'native_stage_names':['synthetic_native_declaration'],'label_rule':'synthetic metadata declaration, not measured truth'};self.assertTrue(H.audit(r)['errors'])
    def test_malformed_metadata_types_do_not_crash(self):
        for value in [None,[],{},True,7]:
            r=record();r['stages'][0]['execution_kind']=value;self.assertTrue(H.audit(r)['errors'])
        self.assertTrue(H.audit(None)['errors']);r=record();r.update(publication='benchmark',artifacts=None);self.assertTrue(H.audit(r)['errors'])
    def test_metadata_audit_does_not_read_artifacts(self):
        r=record();r['artifacts']=[{'path':'not-read.txt','kind':'fixture','sha256':r['provenance']['configuration_sha256']}]
        with patch.object(Path,'open',side_effect=AssertionError('Unexpected artifact read')):
            self.assertEqual(H.audit(r)['errors'],[])
    def test_schema_fixture_and_rejection_shapes(self):
        try:from jsonschema import Draft202012Validator
        except ImportError:self.skipTest('Optional harness jsonschema unavailable')
        schema=json.loads((P/'references/run-record.schema.json').read_text(encoding="utf-8-sig"));Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(record())
        reject=json.loads((P/'references/request-result.schema.json').read_text(encoding="utf-8-sig"));validator=Draft202012Validator(reject)
        for value in [None,{'task_id':[],'mode':'AUDIT'},{'task_id':'001','mode':'AUDIT','modality':'siRNA'}]:validator.validate(C.preflight(value))

class ArtifactTests(unittest.TestCase):
    def checkfile(self,path) -> dict[str,Any]:
        return {'path':path.name,'kind':'synthetic_artifact','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    def test_empty_verification_is_not_artifact_integrity_pass(self):
        with tempfile.TemporaryDirectory() as temp:self.assertTrue(H.verify_artifacts(record(),Path(temp))['errors'])
    def test_real_hash_and_csv_row_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);f=root/'metadata.csv';f.write_text('id,value\na,metadata\nb,metadata\n', encoding="utf-8");a=self.checkfile(f);a['data_rows']=2
            self.assertFalse(H.verify_artifacts({'artifacts':[a]},root)['errors'])
            a['data_rows']=3;self.assertTrue(H.verify_artifacts({'artifacts':[a]},root)['errors'])
    def test_wrong_hash_and_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            parent=Path(temp);root=parent/'allowed';root.mkdir();f=root/'value.txt';f.write_text('metadata only', encoding="utf-8");a=self.checkfile(f);f.write_text('changed metadata', encoding="utf-8")
            self.assertTrue(H.verify_artifacts({'artifacts':[a]},root)['errors'])
            outside=parent/'outside.txt';outside.write_text('not an approved artifact', encoding="utf-8");a=self.checkfile(outside);a['path']='../outside.txt'
            self.assertTrue(H.verify_artifacts({'artifacts':[a]},root)['errors'])
    def test_symlink_outside_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            parent=Path(temp);root=parent/'allowed';root.mkdir();outside=parent/'outside.txt';outside.write_text('metadata', encoding="utf-8");(root/'link.txt').symlink_to(outside);a=self.checkfile(outside);a['path']='link.txt'
            self.assertTrue(H.verify_artifacts({'artifacts':[a]},root)['errors'])
    def test_raster_decode_and_nonconstant_pixels(self):
        try:from PIL import Image
        except ImportError:self.skipTest('Optional Pillow unavailable')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);p=root/'qa.png';im=Image.new('RGB',(4,4),'white');im.putpixel((0,0),(0,0,0));im.save(p)
            self.assertFalse(H.verify_artifacts({'artifacts':[self.checkfile(p)]},root,True)['errors'])
    def test_cli_artifact_reads_need_explicit_root_and_output_is_exclusive(self):
        args=[sys.executable,'-B',str(P/'scripts/harness_audit.py'),str(P/'tests/synthetic_record.json')]
        p=subprocess.run(args+['--verify-artifacts'],capture_output=True,text=True, encoding="utf-8", errors="replace");self.assertEqual(p.returncode,2)
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'audit.json';p=subprocess.run(args+['--output',str(output)],capture_output=True,text=True, encoding="utf-8", errors="replace");self.assertEqual(p.returncode,0,p.stderr);old=output.read_bytes()
            p=subprocess.run(args+['--output',str(output)],capture_output=True,text=True, encoding="utf-8", errors="replace");self.assertNotEqual(p.returncode,0);self.assertEqual(output.read_bytes(),old)


if __name__=="__main__":unittest.main(verbosity=2)
