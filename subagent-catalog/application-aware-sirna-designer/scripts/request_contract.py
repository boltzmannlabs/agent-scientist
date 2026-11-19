"""Inert metadata routing only: no sequence reads, design, scoring or authorization."""
import argparse
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
APPS={x['task_id']:x for x in json.loads((P/'references/applications.json').read_text())['applications']}
MODES={'SETUP','AUDIT','DESIGN','EVALUATE','EXPLORATORY','BENCHMARK'}

def present(x):return isinstance(x,str) and bool(x.strip())
def preflight(r):
    def result(status,missing=(),required=(),notes=()):
        return {'status':status,'missing_inputs':list(missing),'required_stages':list(required),'notes':list(notes),'scientific_execution':False,'authorization_granted':False}
    if not isinstance(r,dict):return result('INVALID_REQUEST',notes=['JSON object required'])
    mode=r.get('mode');task=r.get('task_id')
    if not isinstance(mode,str) or mode not in MODES:return result('INVALID_REQUEST',notes=['Exact uppercase mode required'])
    if mode in {'SETUP','AUDIT'}:
        return result('SETUP_FIRST' if mode=='SETUP' else 'AUDIT_ONLY',notes=['Inspect current provider/tools, approved executables, asset permissions and setup plan; no scientific execution'])
    if not isinstance(task,str) or task not in APPS:return result('INVALID_REQUEST',notes=['Exact task ID 001 through 011 required'])
    # Conservative routing is not a comprehensive biomedical risk assessment.
    if r.get('safety_context')!='noninfectious_human_research':
        return result('REVIEW_ONLY' if present(r.get('safety_context')) else 'NEEDS_INPUT',missing=[] if present(r.get('safety_context')) else ['safety_context'],notes=['No pathogen, pest, infection-enabling host-factor or unreviewed nonhuman sequence work'])
    organism=r.get('organism')
    if not present(organism):return result('NEEDS_INPUT',['organism'])
    if organism not in {'human','Homo sapiens'}:return result('REVIEW_ONLY',notes=['Human models are not validated for this organism'])
    if r.get('clinical_use') is True:return result('REVIEW_ONLY',notes=['No clinical prescription, safety assurance or order-ready designs'])
    modality=r.get('modality')
    if modality is not None and (not isinstance(modality,str) or modality not in {'siRNA','RNAi'}):return result('OUT_OF_SCOPE',notes=['siRNA specialist, not CRISPR/Cas13/ASO'])
    fields=['objective','output_root','provider_decision','source_permission_record','setup_report']
    if mode in {'DESIGN','EXPLORATORY','EVALUATE','BENCHMARK'}:fields+=['target_gene','transcript_accession','reference_manifest']
    if mode in {'DESIGN','EXPLORATORY'}:fields+=['requirement_brief','frozen_gate_manifest','generation_backend','native_fixture_record']
    if mode in {'EVALUATE','BENCHMARK'}:fields+=['candidate_manifest','requested_properties','native_fixture_record']
    if mode=='BENCHMARK':fields+=['measured_label_manifest','label_rule','split_exclusion_manifest']
    if task=='004':fields+=['verified_variant_manifest','allele_objective']
    if task=='007':fields+=['isoform_objective','cns_expression_manifest']
    if task=='011':fields+=['orthogonal_evidence_manifest']
    missing=[f for f in fields if not present(r.get(f))]
    props=r.get('requested_properties')
    required=['reference_identity','native_readiness']
    if mode in {'DESIGN','EXPLORATORY'}:required+=['generation','efficacy','structure','both_strand_specificity','seed_toxicity','immune_hazard','physicochemical','requirement_ranking','panel_diversity']
    elif present(props):required+=['requested_properties_only']
    if task=='004':required+=['allele_discrimination']
    if task=='007':required+=['isoform_and_tissue_context']
    if task=='011':required+=['orthogonal_context']
    return result('NEEDS_INPUT' if missing else 'METADATA_COMPLETE_REQUIRES_NATIVE_AND_PARENT_CHECKS',missing,required,[APPS[task]['requirements'],'String paths/receipts are not permission or proof that a native fixture ran'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('request',type=Path);a=p.parse_args()
    try:r=json.loads(a.request.read_text());out=preflight(r)
    except (OSError,ValueError,UnicodeError):out={'status':'INVALID_REQUEST','missing_inputs':[],'required_stages':[],'notes':['Unreadable or malformed JSON'],'scientific_execution':False,'authorization_granted':False}
    print(json.dumps(out,indent=2));return 2 if out['status'] in {'INVALID_REQUEST','OUT_OF_SCOPE'} else 0
if __name__=='__main__':raise SystemExit(main())
