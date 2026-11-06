"""Portable native outcome identity tests; no SDK, model or science execution."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from workflow.native_episode import unique_json, validate_outcome


class NativeEpisodeTests(unittest.TestCase):
    def setUp(self):
        self.schema=json.loads((Path(__file__).parents[1]/'specialist/optimization-v1/outcome.schema.json').read_text())
        self.assignment={'assignment_id':'assignment','episode_id':'episode','input_digest':'a'*64,
            'parent_options':[{'candidate_id':'candidate','admissible':True}],
            'library_options':[{'library_id':'library','admitted':True}],
            'helper_summaries':{'rows':[{'candidate_id':'candidate'}],'qualified_candidate_ids':[],
                'eligible_actions':[{'action_key':'b'*64,'parent_candidate_id':'candidate','library_id':'library'}]},
            'pending_jobs':[]}
        self.outcome={'schema_version':1,'assignment_id':'assignment','episode_id':'episode','input_digest':'a'*64,
            'status':'blocked','chosen_action':{'kind':'generate','parent_id':'candidate','library_id':'library','action_key':'b'*64},
            'evidence_ids':['candidate'],'final_candidate_ids':[],'pending_jobs':[],'artifact_refs':[],
            'rationale':'Compare a new parent using actual evidence.','stop_reason':'Scientific execution unavailable.',
            'limitations':['Planning qualification only.'],'information_requests':[]}

    def test_bound_proposal_passes_without_becoming_execution_or_success(self):
        answer=validate_outcome(self.assignment,self.outcome,self.schema)
        self.assertEqual(answer,self.outcome)
        self.assertIsNot(answer,self.outcome)
        for field,value in [('assignment_id','other'),('evidence_ids',['invented']),('final_candidate_ids',['candidate'])]:
            wrong=deepcopy(self.outcome); wrong[field]=value
            with self.assertRaises(ValueError): validate_outcome(self.assignment,wrong,self.schema)

    def test_host_mediated_action_request_requires_explicit_allowance_and_open_evidence_state(self):
        assignment=deepcopy(self.assignment)
        assignment['capability_contract']={'execution_mode':'host_mediated'}
        assignment['resources']={'scientific_submission_allowance_this_episode':1}
        request=deepcopy(self.outcome); request['status']='action_requested'
        self.assertEqual(validate_outcome(assignment,request,self.schema)['status'],'action_requested')
        # A prior blocked recommendation remains blocked; no execution is inferred.
        self.assertEqual(validate_outcome(assignment,self.outcome,self.schema)['status'],'blocked')
        variants=[]
        wrong=deepcopy(assignment); wrong['capability_contract']['execution_mode']='planning_only'; variants.append(wrong)
        for allowance in (0,-1,1.0,True,None):
            wrong=deepcopy(assignment); wrong['resources']['scientific_submission_allowance_this_episode']=allowance; variants.append(wrong)
        wrong=deepcopy(assignment); wrong['pending_jobs']=[{'job_name':'Fragment_Based_Optimization','doc_id':'actual-fixture','status':'pending'}]; variants.append(wrong)
        for field,value in [('qualified_candidate_ids',['candidate']),('evaluation_blockers',['unresolved']),('assignment_frozen',True)]:
            wrong=deepcopy(assignment); wrong['helper_summaries'][field]=value; variants.append(wrong)
        for wrong in variants:
            with self.subTest(assignment=wrong):
                with self.assertRaises(ValueError): validate_outcome(wrong,request,self.schema)

    def test_unknown_action_and_fake_job_are_rejected_and_json_is_strict(self):
        wrong=deepcopy(self.outcome); wrong['chosen_action']['action_key']='c'*64
        with self.assertRaises(ValueError): validate_outcome(self.assignment,wrong,self.schema)
        wrong=deepcopy(self.outcome); wrong['pending_jobs']=[{'job_name':'Fragment_Based_Optimization','doc_id':'invented','status':'pending'}]
        with self.assertRaises(ValueError): validate_outcome(self.assignment,wrong,self.schema)
        for text in ['{"x":1,"x":2}','{"x":NaN}']:
            with self.assertRaises(ValueError): unique_json(text)


if __name__=='__main__': unittest.main()
