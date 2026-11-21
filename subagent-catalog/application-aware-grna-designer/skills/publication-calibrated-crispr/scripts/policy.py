"""Offline metadata policy only. No sequence scoring, installs, network or permission grants."""
import argparse
import json
from pathlib import Path
POLICY=json.loads((Path(__file__).resolve().parents[1]/'references/model-policy.json').read_text(encoding="utf-8-sig"))

def resolve(request):
    result={'scientific_execution':False,'model_readiness_verified':False,'authorization_granted':False,'production_default_changed':False}
    def out(status,**kw):return dict(result,status=status,**kw)
    if not isinstance(request,dict):return out('INVALID_REQUEST')
    if any(k in request and not isinstance(request[k],str) for k in ['task_id','endpoint','model_id','organism_context','cell','editor','nuclease','scaffold']):return out('INVALID_REQUEST')
    if 'research_opt_in' in request and type(request['research_opt_in']) is not bool:return out('INVALID_REQUEST')
    task=request.get('task_id')
    if task not in {f'{i:03d}' for i in range(1,14)}:return out('INVALID_REQUEST')
    # This obvious marker never substitutes for parent review of the actual biological request.
    context=request.get('organism_context','')
    if context.casefold()=='pathogen':return out('REVIEW_ONLY')
    if not context:return out('NEEDS_INPUT',missing_inputs=['organism_context'])
    model=request.get('model_id');endpoint=request.get('endpoint')
    if not model or not endpoint:return out('NEEDS_INPUT',missing_inputs=[k for k in ['model_id','endpoint'] if not request.get(k)])
    records=[r for r in POLICY['models'] if r['id']==model]
    if not records:return out('NO_VERIFIED_MODEL_POLICY')
    r=records[0]
    if task!=r['task_id']:return out('TASK_MODEL_MISMATCH')
    if endpoint!=r['endpoint']:return out('LABEL_CONCORDANCE_REQUIRED',expected_endpoint=r['endpoint'])
    missing=[k for k in r['required_context'] if not request.get(k)]
    if missing:return out('NEEDS_INPUT',missing_inputs=missing)
    mismatches=[k for k,allowed in r['required_context'].items() if request[k] not in allowed]
    if mismatches:return out('CONTEXT_MISMATCH',mismatched_fields=mismatches)
    if r['id']=='CRISPRON_CBE' and request.get('research_opt_in') is not True:return out('RESEARCH_OPT_IN_REQUIRED')
    selected=r['default'];decision=r['candidate_policy']
    if r['id']=='RS3_SEQUENCE':
        if request.get('research_opt_in') is True:selected=r['candidate'];decision='RESEARCH_CANDIDATE_ONLY'
        else:decision='RETAIN_RELEASED_REFERENCE'
    return out('POLICY_ONLY_REQUIRES_PARENT_AND_NATIVE_CHECKS',model_id=model,profile=r['profile'],recommendation=selected,decision=decision,limitations=r['interpretation'],native_checks_required=['exact editor/system/tracr/scaffold and endpoint contract','original features and genuine sequence context','source/weights/checkpoints and historical training exposure','approved isolated runtime and measured-label evaluation','actual biological safety/source/egress/execution authorization'])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('request',type=Path,help='Approved request metadata JSON file')
    args=parser.parse_args()
    try:request=json.loads(args.request.read_text(encoding="utf-8-sig"))
    except (ValueError,UnicodeError):request=None
    result=resolve(request);print(json.dumps(result,indent=2))
    return 2 if result['status']=='INVALID_REQUEST' else 0
if __name__=='__main__':raise SystemExit(main())
