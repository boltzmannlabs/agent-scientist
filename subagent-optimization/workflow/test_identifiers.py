"""Lossless model presentation checks; no SDK, prediction or scientific jobs."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator, ValidationError
from workflow.identifiers import (DERIVED_RULE, digest, expand_outcome, present_assignment,
                                   restore_assignment, wire_outcome_schema)


def assignment():
    cid='candidate-'+'1'*64; form='canonical-isomeric-'+'1'*64; obs='obs-'+'e'*64
    other='candidate-'+'2'*64
    value={'task':{'starting_candidates':[{'id':cid,'form_id':form,'representation':'CCO'},
                    {'id':'CCO','form_id':'user-form','representation':'CCO'},
                    {'id':'M001','form_id':'literal-form','representation':'CCN'}],
                  'initial_observations':[{'id':obs,'candidate_id':cid,'form_id':form,'value':-8.26}]},
        'helper_summaries':{'rows':[{'candidate_id':cid,'form_id':form,'values':{'qed':.8087858633072859,'lipophilicity':-8.26},'evidence_ids':[obs]}],
            'qualified_candidate_ids':[], 'pareto_parent_ids':[cid],
            'eligible_actions':[{'action_key':'a'*64,'parent_candidate_id':cid,'library_id':'library'}],
            'attempted_actions':[{'action_key':'b'*64}],
            'measurements':[{'records':[{'id':obs,'candidate_id':cid,'form_id':form,'endpoint':'qed','value':.8087858633072859}]}],
            'nonparent_identity_columns':['candidate_id','representation','form_id_override'],
            'nonparent_identities':[[other,'CC(=O)O',None]], 'nonparent_form_rule':DERIVED_RULE,
            'molecular_table':{'columns':['candidate_id','form_id','representation','value'],
                               'records':[[cid,form,'CCO',.8087858633072859]]},
            'candidate_forms':{cid:{'candidate_id':cid,'form_id':form,'representation':'CCO'}},
            'source_columns':{'candidate_id':cid,'description':'M999 '+cid},
            'notes':{'candidate_id':cid},'description':cid},
        'parent_options':[{'candidate_id':cid,'form_id':form,'representation':'CCO','admissible':True},
                          {'candidate_id':'CCO','form_id':'user-form','representation':'CCO','admissible':True},
                          {'candidate_id':'M001','form_id':'literal-form','representation':'CCN','admissible':True}],
        'library_options':[{'library_id':'library','content_sha256':'a'*64,'admitted':True}],
        'prior_actions':[{'action_key':'b'*64,'parent_id':cid}],
        'pending_jobs':[],'capability_contract':{'execution_mode':'host_mediated'},
        'resources':{'scientific_submission_allowance_this_episode':1},
        'assignment_id':'assignment','episode_id':'episode'}
    value['task_digest']=digest(value['task'])
    value['input_digest']=digest(value)
    return value


class IdentifierTests(unittest.TestCase):
    def test_roundtrip_bijection_and_scientific_facts_are_unchanged(self):
        original=assignment(); before=deepcopy(original)
        wire, manifest=present_assignment(original)
        self.assertEqual(original,before)
        self.assertEqual(restore_assignment(wire,manifest),original)
        self.assertEqual(len(manifest['alias_to_canonical']),len(set(manifest['alias_to_canonical'].values())))
        self.assertEqual(wire['helper_summaries']['rows'][0]['values'],original['helper_summaries']['rows'][0]['values'])
        self.assertEqual(wire['parent_options'][0]['representation'],'CCO')
        self.assertEqual(wire['library_options'][0]['content_sha256'],'a'*64)
        self.assertNotEqual(wire['task_digest'],original['task_digest'])
        self.assertEqual(present_assignment(dict(reversed(list(original.items()))))[1]['mapping_sha256'],manifest['mapping_sha256'])

    def test_user_labels_structures_and_untrusted_columns_are_not_replaced(self):
        original=assignment(); wire,manifest=present_assignment(original)
        self.assertEqual(wire['parent_options'][1]['candidate_id'],'CCO')
        self.assertEqual(wire['parent_options'][1]['representation'],'CCO')
        self.assertEqual(wire['parent_options'][2]['candidate_id'],'M001')
        self.assertNotIn('M001',manifest['alias_to_canonical'])
        for field in ('source_columns','notes','description'):
            self.assertEqual(wire['helper_summaries'][field],original['helper_summaries'][field])

    def test_typed_tables_and_derived_form_identity_remain_available(self):
        original=assignment(); wire,manifest=present_assignment(original)
        h=wire['helper_summaries']
        row=h['molecular_table']['records'][0]
        self.assertEqual(row[0],wire['parent_options'][0]['candidate_id'])
        self.assertTrue(row[1].startswith('F'))
        record=h['measurements'][0]['records'][0]
        self.assertEqual(record['id'],h['rows'][0]['evidence_ids'][0])
        self.assertEqual(record['value'],original['helper_summaries']['measurements'][0]['records'][0]['value'])
        self.assertEqual(row[2:],original['helper_summaries']['molecular_table']['records'][0][2:])
        self.assertEqual(h['nonparent_identities'][0][1:],original['helper_summaries']['nonparent_identities'][0][1:])
        pair=h['presentation']['identifier_aliases']['derived_nonparent_form_aliases'][0]
        self.assertEqual(pair[0],h['nonparent_identities'][0][0])
        self.assertEqual(manifest['alias_to_canonical'][pair[1]],'canonical-isomeric-'+'2'*64)

    def test_wire_outcome_expands_and_schema_relaxation_is_action_key_only(self):
        original=assignment(); wire,manifest=present_assignment(original)
        schema=json.loads((Path(__file__).parents[1]/'specialist/optimization-v1/outcome.schema.json').read_text())
        before=deepcopy(schema); wire_schema=wire_outcome_schema(schema)
        self.assertEqual(schema,before)
        action=wire['helper_summaries']['eligible_actions'][0]
        outcome={'schema_version':1,'assignment_id':'assignment','episode_id':'episode','input_digest':wire['input_digest'],
            'status':'action_requested','chosen_action':{'kind':'generate','parent_id':action['parent_candidate_id'],'library_id':'library','action_key':action['action_key']},
            'evidence_ids':[wire['helper_summaries']['rows'][0]['evidence_ids'][0]],'final_candidate_ids':[],
            'pending_jobs':[],'artifact_refs':[],'rationale':'Literal M999 in prose is not an identity reference.',
            'stop_reason':'Host execution requested.','limitations':[],'information_requests':[]}
        Draft202012Validator(wire_schema).validate(outcome)
        bad_digest=deepcopy(outcome); bad_digest['input_digest']='A001'
        with self.assertRaises(ValidationError): Draft202012Validator(wire_schema).validate(bad_digest)
        with self.assertRaises(ValidationError): Draft202012Validator(schema).validate(outcome)
        restored=expand_outcome(outcome,manifest)
        Draft202012Validator(schema).validate(restored)
        self.assertEqual(restored['chosen_action']['action_key'],'a'*64)
        self.assertEqual(restored['chosen_action']['parent_id'],original['parent_options'][0]['candidate_id'])
        self.assertEqual(restored['input_digest'],original['input_digest'])
        self.assertEqual(restored['rationale'],outcome['rationale'])
        for value in ['M999','E001']:
            bad=deepcopy(outcome); bad['chosen_action']['parent_id']=value
            with self.assertRaises(ValueError): expand_outcome(bad,manifest)
        bad=deepcopy(outcome); bad['chosen_action']['parent_id']='M001'
        self.assertEqual(expand_outcome(bad,manifest)['chosen_action']['parent_id'],'M001')

    def test_map_changes_and_scientific_fact_tampering_are_rejected(self):
        original=assignment(); wire,manifest=present_assignment(original)
        bad=deepcopy(manifest); key=next(iter(bad['alias_to_canonical'])); bad['alias_to_canonical'][key]='candidate-'+'9'*64
        with self.assertRaises(ValueError): restore_assignment(wire,bad)
        changed=deepcopy(wire); changed['helper_summaries']['rows'][0]['values']['lipophilicity']=0
        changed['input_digest']=digest({k:v for k,v in changed.items() if k!='input_digest'})
        attacker=deepcopy(manifest); attacker['wire_input_digest']=changed['input_digest']
        with self.assertRaises(ValueError): restore_assignment(changed,attacker)


if __name__=='__main__': unittest.main()
