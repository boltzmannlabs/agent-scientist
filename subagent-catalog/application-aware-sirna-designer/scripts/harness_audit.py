"""Offline run-evidence checks, never scientific inference or an authorization grant.
No artifact reads unless --verify-artifacts and an explicit --artifact-root are supplied.
A PASS means record consistency, not that features, biology or model readiness are verified.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re

FRESH = {'FRESH_NATIVE_INFERENCE', 'NATIVE_CONTROL_REPLAY'}
CACHED = {'HASH_BOUND_CACHE_REUSE', 'IDENTICAL_INPUT_SCORE_REUSE', 'AUTHOR_SCORE_REPLAY'}
KINDS = FRESH | CACHED | {'METRIC_REEXECUTION', 'SOFTWARE_READINESS_CHECK', 'NOT_RUN'}
CLASSES = {'METADATA_PREFLIGHT_ONLY', 'PACKAGE_CHECK_ONLY', 'NATIVE_INFERENCE',
           'NATIVE_CONTROL_REPLAY', 'METRIC_REEXECUTION', 'AUTHOR_SCORE_REPLAY',
           'SOFTWARE_READINESS_ONLY', 'SENSITIVITY_ANALYSIS', 'NO_EXECUTION'}
SHA = re.compile(r'^[a-f0-9]{64}$')

def is_int(value):
    return type(value) is int and value >= 0

def valid_sha(value):
    return isinstance(value, str) and SHA.fullmatch(value) is not None

def audit(record):
    errors = []
    warnings = []
    def need(condition, message):
        if not condition:
            errors.append(message)
    if not isinstance(record, dict):
        return result(['Run record must be an object'], [], 0)
    need(record.get('schema_version') == 2 and type(record.get('schema_version')) is int,
         'schema_version must be integer 2; legacy records require explicit migration')
    for field in ['run_id', 'config_id']:
        need(isinstance(record.get(field), str) and bool(record[field].strip()), field+' must be nonempty text')
    need(record.get('task_id') in {f'{i:03d}' for i in range(1,12)} if isinstance(record.get('task_id'), str) else False, 'Invalid exact task identifier')
    need(record.get('mode') in ['DESIGN','EVALUATE','EXPLORATORY','BENCHMARK','AUDIT'], 'Invalid mode')
    need(record.get('status') in ['NEEDS_INPUT','REVIEW_ONLY','INACTIVE','BLOCKED','PARTIAL','COMPLETED'], 'Invalid status')
    need(record.get('execution_class') in CLASSES if isinstance(record.get('execution_class'), str) else False, 'Invalid execution_class')
    need('best_design' in record and record['best_design'] is None, 'best_design must be explicitly null')
    need(record.get('experimental_validation') is False, 'experimental_validation must be explicitly false')
    for field in ['artifacts','missing_inputs','limitations']:
        need(isinstance(record.get(field),list),field+' must be an array')
    for field in ['missing_inputs','limitations']:
        if isinstance(record.get(field),list):
            need(all(isinstance(x,str) for x in record[field]),field+' entries must be strings')
    stages = record.get('stages', [])
    if not isinstance(stages,list):
        stages=[];errors.append('stages must be an array')
    stage_by_name = {}
    native_passes = 0
    for index, stage in enumerate(stages):
        prefix=f'stage {index}: '
        if not isinstance(stage,dict):
            errors.append(prefix+'must be an object');continue
        name=stage.get('name')
        need(isinstance(name,str) and bool(name.strip()),prefix+'name required')
        if isinstance(name,str):
            need(name not in stage_by_name,prefix+'duplicate stage name');stage_by_name[name]=stage
        status=stage.get('status');kind=stage.get('execution_kind')
        if not isinstance(kind,str):
            kind=None
        need(status in ['PASS','FAIL','NOT_RUN'],prefix+'invalid status')
        need(kind in KINDS if isinstance(kind,str) else False,prefix+'invalid execution_kind')
        need(isinstance(stage.get('reason'),str) and bool(stage['reason'].strip()),prefix+'reason required')
        if status=='PASS':
            need(kind!='NOT_RUN',prefix+'NOT_RUN cannot pass')
        if kind=='NOT_RUN':
            need(status=='NOT_RUN',prefix+'unrun stage cannot have a native outcome')
        if status=='NOT_RUN':
            need(kind=='NOT_RUN',prefix+'mark unexecuted stages with NOT_RUN execution_kind')
        if kind in FRESH and status=='PASS':
            native_passes+=1
            need(stage.get('exit_code')==0 and type(stage.get('exit_code')) is int,prefix+'fresh native PASS requires exit_code 0')
            need(stage.get('native_forward_pass') is True,prefix+'fresh native PASS requires actual native_forward_pass')
            need(is_int(stage.get('observed_rows')),prefix+'observed_rows required')
        if kind in CACHED:
            need(stage.get('native_forward_pass') is False,prefix+'cached/author scores are not a fresh forward pass')
            need(valid_sha(stage.get('score_source_sha256')),prefix+'cached scores require score_source_sha256')
        for field in ['expected_rows','observed_rows']:
            if field in stage:
                need(is_int(stage[field]),prefix+field+' must be a nonnegative integer, not bool')
        if status=='PASS' and 'expected_rows' in stage and 'observed_rows' in stage:
            need(stage['expected_rows']==stage['observed_rows'],prefix+'declared input/output cardinality mismatch')
        if kind not in FRESH and stage.get('native_forward_pass') is True:
            errors.append(prefix+'non-native execution cannot claim a forward pass')
        if stage.get('feature_integrity')=='SYNTHETIC_OR_RANDOM' and status=='PASS' and kind in FRESH:
            errors.append(prefix+'random/synthetic learned inputs cannot yield a valid native PASS')
        if stage.get('inference_mode')=='native_train_mode':
            warnings.append(prefix+'active training/dropout mode: fixed seed does not remove subset/order dependence')
    if record.get('execution_class') in ['NATIVE_INFERENCE','NATIVE_CONTROL_REPLAY']:
        need(native_passes>0,'Native execution class requires at least one completed actual native stage')
    if record.get('status')=='COMPLETED':
        need(bool(stages) and all(isinstance(s,dict) and s.get('status')=='PASS' for s in stages),'COMPLETED record has failed/unrun/no stages; retain PARTIAL/BLOCKED')
    provenance=record.get('provenance')
    if not isinstance(provenance,dict):
        provenance={};errors.append('provenance object required')
    need(valid_sha(provenance.get('configuration_sha256')),'configuration_sha256 required')
    for flag in ['pretrained_only','training_performed','previously_examined_labels']:
        need(type(provenance.get(flag)) is bool,'provenance.'+flag+' must be explicitly boolean')
    if provenance.get('pretrained_only') is True:
        need(provenance.get('training_performed') is False,'Pretrained-only scope cannot silently train a replacement')
    need(type(provenance.get('unique_scientific_cohorts')) is int and provenance['unique_scientific_cohorts']>=0,'unique_scientific_cohorts must be a nonnegative integer')
    comparison=record.get('comparison')
    if not isinstance(comparison,dict):
        comparison={};errors.append('comparison object required')
    relations=['cohort_relation','endpoint_relation','protocol_relation']
    for field in relations:
        need(comparison.get(field) in ['MATCHED','DIFFERENT','UNKNOWN','NOT_APPLICABLE'], 'comparison.'+field+' must be declared')
    need('matched_protocol_delta' in comparison,'matched_protocol_delta must be explicitly null unless matched')
    delta=comparison.get('matched_protocol_delta')
    if delta is not None:
        need(type(delta) in [int,float] and math.isfinite(delta),'Comparison delta must be finite numeric or null')
        need(all(comparison.get(f)=='MATCHED' for f in relations),'Numeric matched-protocol delta requires matched cohort, endpoint and protocol')
    artifacts=record.get('artifacts')
    if not isinstance(artifacts,list):
        artifacts=[]
    publication=record.get('publication')
    need(publication in ['history','benchmark','not_applicable'],'publication location must be explicit')
    benchmark=record.get('benchmark')
    if not isinstance(benchmark,dict):
        benchmark={};errors.append('benchmark object required')
    need(type(benchmark.get('measured_labels')) is bool,'benchmark.measured_labels must be explicit')
    eligible=benchmark.get('native_stage_names',[])
    need(isinstance(eligible,list) and all(isinstance(x,str) for x in eligible),'native_stage_names must be a string array')
    if publication=='benchmark':
        need(record.get('fixture_kind')!='SYNTHETIC_METADATA_ONLY','Synthetic metadata fixtures cannot be published as measured benchmarks')
        need(benchmark.get('measured_labels') is True,'Published benchmark needs measured labels, not proxy/synthetic truth')
        need(isinstance(eligible,list) and bool(eligible),'Completed-only benchmark needs explicit completed native endpoint stage names')
        need(isinstance(benchmark.get('label_rule'),str) and bool(benchmark['label_rule'].strip()),'Benchmark label_rule required; do not conflate cutoff conventions')
        if isinstance(eligible,list):
            for name in eligible:
                stage=stage_by_name.get(name,{}) if isinstance(name,str) else {}
                need(stage.get('status')=='PASS' and stage.get('execution_kind') in list(FRESH),'Benchmark endpoint must have actually completed native inference')
                need(stage.get('feature_integrity')=='VERIFIED_NATIVE','Benchmark endpoint requires verified native feature provenance')
                need(is_int(stage.get('observed_rows')) and stage.get('observed_rows',0)>0,'Benchmark endpoint has no observed rows')
        need(any(isinstance(a,dict) and a.get('kind')=='native_predictions' and valid_sha(a.get('sha256')) for a in artifacts),'Benchmark needs a hash-bound native prediction artifact')
    for a in artifacts:
        need(isinstance(a,dict) and isinstance(a.get('path'),str) and bool(a.get('path')) and isinstance(a.get('kind'),str),'Artifact path/kind required')
        if isinstance(a,dict) and 'sha256' in a:
            need(valid_sha(a['sha256']),'Invalid artifact SHA-256')
    return result(errors,warnings,native_passes)

def result(errors,warnings,native_passes):
    return {'status':'PASS_RECORD_CONSISTENCY_ONLY' if not errors else 'FAIL_RECORD_CONSISTENCY',
            'errors':errors,'warnings':warnings,'completed_native_stages_declared':native_passes,
            'scientific_execution':False,'model_readiness_verified':False,'authorization_granted':False}

def verify_artifacts(record, root, verify_images=False):
    root=Path(root).resolve(strict=True)
    errors=[];checked=[]
    if not isinstance(record.get('artifacts'),list) or not record['artifacts']:
        return {'status':'FAIL_ARTIFACT_INTEGRITY','errors':['No artifacts declared for requested verification'],'checked':[],'scientific_execution':False,'model_readiness_verified':False}
    for a in record['artifacts']:
        if not isinstance(a,dict) or not isinstance(a.get('path'),str) or not valid_sha(a.get('sha256')):
            errors.append('Artifact verification requires explicit path and SHA-256');continue
        try:
            raw=Path(a['path'])
            path=(raw if raw.is_absolute() else root/raw).resolve(strict=True)
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError('Artifact outside approved root or not a regular file')
            h=hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
            if h.hexdigest()!=a['sha256']:raise ValueError('Artifact checksum mismatch')
            row={'path':a['path'],'sha256_verified':True}
            if 'data_rows' in a:
                if not is_int(a['data_rows']) or path.suffix.lower() not in ['.csv','.tsv']:
                    raise ValueError('data_rows requires a nonnegative integer and a header-bearing CSV/TSV')
                with path.open(newline='',encoding='utf-8') as csv_stream:
                    reader=csv.reader(csv_stream,delimiter='\t' if path.suffix.lower()=='.tsv' else ',')
                    next(reader,None)
                    count=sum(1 for fields in reader if fields)
                if count!=a['data_rows']:raise ValueError('Artifact CSV/TSV row-count mismatch')
                row['data_rows_verified']=count
            if verify_images and path.suffix.lower() in ['.png','.jpg','.jpeg']:
                from PIL import Image,ImageStat
                with Image.open(path) as im:im.verify()
                with Image.open(path) as im:
                    if min(im.size)<=0 or max(ImageStat.Stat(im.convert('RGB')).stddev)==0:raise ValueError('Empty/constant raster image')
                    row.update(image_decoded=True,width=im.width,height=im.height)
            checked.append(row)
        except (OSError,ValueError,ImportError,csv.Error) as exc:
            errors.append(str(exc))
    return {'status':'PASS_ARTIFACT_INTEGRITY_ONLY' if not errors else 'FAIL_ARTIFACT_INTEGRITY','errors':errors,'checked':checked,'scientific_execution':False,'model_readiness_verified':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('record',type=Path)
    p.add_argument('--validate-schema',action='store_true',help='Optional jsonschema structural validation of the packaged v2 contract')
    p.add_argument('--verify-artifacts',action='store_true')
    p.add_argument('--artifact-root',type=Path)
    p.add_argument('--verify-images',action='store_true',help='Optional Pillow decode/nonconstant-raster check; not visual or biological validation')
    p.add_argument('--output',type=Path,help='Exclusive-create a new JSON report; never overwrite')
    a=p.parse_args()
    if a.verify_artifacts != (a.artifact_root is not None) or (a.verify_images and not a.verify_artifacts):
        p.error('Artifact reads require both --verify-artifacts and --artifact-root; image checks also require them')
    with a.record.open(encoding='utf-8') as f:record=json.load(f)
    r=audit(record)
    if a.validate_schema:
        try:
            from jsonschema import Draft202012Validator
            schema_path=Path(__file__).resolve().parents[1]/'references/run-record.schema.json'
            with schema_path.open(encoding='utf-8') as f:schema=json.load(f)
            errors=Draft202012Validator(schema).iter_errors(record)
            r['errors'].extend('Schema constraint '+str(e.validator)+' at '+('/'.join(map(str,e.path)) or '<record>') for e in errors)
            r['structural_schema_checked']=True
        except ImportError:
            r['errors'].append('Optional jsonschema dependency unavailable; use an approved harness environment')
            r['structural_schema_checked']=False
        if r['errors']:r['status']='FAIL_RECORD_CONSISTENCY'
    if a.verify_artifacts and not r['errors']:
        r['artifact_verification']=verify_artifacts(record,a.artifact_root,a.verify_images)
        if r['artifact_verification']['errors']:r['status']='FAIL_RECORD_CONSISTENCY'
    if a.output:
        with a.output.open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps(r,indent=2))
    return 0 if r['status']=='PASS_RECORD_CONSISTENCY_ONLY' else 2
if __name__=='__main__':
    raise SystemExit(main())
