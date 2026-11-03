import copy
import unittest
from audit import AuditError, Chem, audit_bytes, compare_bytes, digest, normalization_policy_id, verify_review_binding


@unittest.skipIf(Chem is None, "RDKit is not installed; chemical-identity checks not performed")
class StructuralAuditTests(unittest.TestCase):
    def test_order_duplicates_metadata_and_smiles_serialization_do_not_create_new_set(self):
        a = b"SMILES,source\nCCO,first\nCCN,second\nCCO,again\n"
        b = b"SMILES,note\nNCC,x\nOCC,y\n"
        comparison = compare_bytes(a, b)
        self.assertFalse(comparison["byte_identical"])
        self.assertTrue(comparison["normalized_set_equal"])
        self.assertFalse(comparison["normalized_sequence_equal"])
        self.assertEqual(comparison["intersection_count"], 2)
        self.assertEqual(comparison["actual_fragment_equivalence"], "not_established")
        result = audit_bytes(a)
        self.assertEqual((result["row_count"], result["canonical_unique_count"], result["duplicate_rows"]), (3, 2, 1))

    def test_partial_overlap_is_not_set_equivalence(self):
        d = compare_bytes(b"SMILES\nCCO\nCCN\n", b"SMILES\nCCO\nCCC\n")
        self.assertFalse(d["normalized_set_equal"])
        self.assertEqual(d["intersection_count"], 1)

    def test_trailing_tokens_are_not_silently_interpreted_as_a_name(self):
        for value in ("CCO CCN", "CCO ethanol", "CCO\tCCN"):
            d = audit_bytes(("SMILES\n" + value + "\n").encode())
            self.assertFalse(d["normalized_identity_complete"])
            self.assertIsNone(d["normalized_input_set_sha256"])

    def test_global_stereo_configuration_is_part_of_policy_identity(self):
        original = Chem.GetAllowNontetrahedralChirality()
        try:
            first = normalization_policy_id()
            Chem.SetAllowNontetrahedralChirality(not original)
            self.assertNotEqual(first, normalization_policy_id())
        finally:
            Chem.SetAllowNontetrahedralChirality(original)

    def test_extended_stereo_is_not_qualified_under_either_global_setting(self):
        original = Chem.GetAllowNontetrahedralChirality()
        try:
            for setting in (True, False):
                Chem.SetAllowNontetrahedralChirality(setting)
                d = audit_bytes(b"SMILES\nF[Pt@SP1](Cl)(Br)I\n")
                self.assertFalse(d["normalized_identity_complete"])
                self.assertEqual(d["unsupported_rows"][0]["reason"], "extended_stereo_requires_review")
        finally:
            Chem.SetAllowNontetrahedralChirality(original)

    def test_discarded_impossible_tetrahedral_tag_requires_review(self):
        d = audit_bytes(b"SMILES\nC[C@H](F)F\n")
        self.assertFalse(d["normalized_identity_complete"])
        self.assertIn("discarded_chiral_annotation", d["unsupported_rows"][0]["reason"])

    def test_assigned_enantiomers_and_unspecified_stereo_remain_distinct(self):
        d = audit_bytes(b"SMILES\nC[C@H](F)Cl\nC[C@@H](F)Cl\nCC(F)Cl\n")
        self.assertTrue(d["normalized_identity_complete"])
        self.assertEqual(d["canonical_unique_count"], 3)

    def test_formal_charge_and_isotopes_are_not_neutralized_or_merged(self):
        d = audit_bytes(b"SMILES\nCCN\nCC[NH3+]\nC\n[13CH4]\n")
        self.assertEqual(d["canonical_unique_count"], 4)

    def test_salt_components_preserved_and_marked_for_review(self):
        a = audit_bytes(b"SMILES\nCC[NH3+].[Cl-]\nCC[NH3+]\n")
        self.assertEqual(a["canonical_unique_count"], 2)
        self.assertEqual(a["multicomponent_rows"], [1])
        self.assertTrue(a["structure_scope_needs_review"])

    def test_tautomers_are_not_standardized_to_one_identity(self):
        d = audit_bytes(b"SMILES\nCC(=O)C\nC=C(O)C\n")
        self.assertEqual(d["canonical_unique_count"], 2)

    def test_invalid_row_prevents_clean_identity_instead_of_being_hidden(self):
        d = audit_bytes(b"SMILES\nCCO\nTHIS_IS_NOT_A_MOLECULE\n")
        self.assertEqual(d["invalid_rows"], [2])
        self.assertFalse(d["normalized_identity_complete"])
        self.assertIsNone(d["normalized_input_set_sha256"])
        c = compare_bytes(b"SMILES\ninvalid\n", b"SMILES\nCCO\n")
        self.assertIsNone(c["normalized_set_equal"])
        self.assertIsNone(c["intersection_count"])

    def test_unsupported_extensions_or_dummy_queries_never_get_clean_identity(self):
        for value in ("CC |atomProp:0.foo.bar|", "*CC", "[CH2]C"):
            d = audit_bytes(("SMILES\n" + value + "\n").encode())
            self.assertFalse(d["normalized_identity_complete"])
            self.assertIsNone(d["normalized_input_set_sha256"])
            self.assertFalse(d["available_for_policy"])

    def test_smi_is_inspectable_but_not_public_csv_ready(self):
        d = audit_bytes(b"CCO\nCCN\n", "smi")
        self.assertEqual(d["canonical_unique_count"], 2)
        self.assertFalse(d["public_input_format_ready"])

    def test_empty_library_has_no_qualified_identity(self):
        d = audit_bytes(b"SMILES\n")
        self.assertEqual(d["row_count"], 0)
        self.assertIsNone(d["normalized_input_set_sha256"])
        self.assertTrue(d["structure_scope_needs_review"])

    def test_csv_schema_is_explicit_and_unambiguous(self):
        for data in (b"smiles\nCCO\n", b"SMILES,SMILES\nCCO,CCN\n", b"SMILES,x\nCCO\n"):
            with self.assertRaises(AuditError): audit_bytes(data)

    def test_readiness_never_fabricates_review_and_structures_are_not_exported(self):
        d = audit_bytes(b"SMILES\nCCO\n")
        self.assertFalse(d["available_for_policy"])
        self.assertFalse(d["capability_card_reviewed"])
        self.assertEqual(d["approval_status"], "not_reviewed")
        self.assertFalse(d["scoring_or_model_execution"])
        self.assertNotIn("canonical_smiles", d)


class ReviewBindingTests(unittest.TestCase):
    def subject(self):
        return {key: "fixture-" + key for key in
                ("asset_content_sha256", "normalized_input_set_sha256", "normalization_policy_id",
                 "family_definition_sha256", "context_definition_sha256", "annotation_mapping_sha256")}

    def test_missing_review_is_not_approval(self):
        d = verify_review_binding(self.subject(), None)
        self.assertEqual(d["status"], "needs_review")
        self.assertFalse(d["available_for_policy"])

    def test_missing_immutable_subject_is_explicit(self):
        d = verify_review_binding({}, {"decision": "approved"})
        self.assertEqual(d["reason"], "incomplete_immutable_subject")

    def test_changed_asset_context_family_or_mapping_invalidates_old_review(self):
        subject = self.subject()
        review = {"subject_sha256": digest(subject), "reviewer_identity": "TEST_REVIEWER", "decision": "approved"}
        for key in subject:
            changed = copy.deepcopy(subject); changed[key] = "changed"
            d = verify_review_binding(changed, review)
            self.assertEqual(d["status"], "rejected")
            self.assertFalse(d["available_for_policy"])

    def test_matching_record_is_only_binding_not_authenticated_human_approval(self):
        subject = self.subject()
        review = {"subject_sha256": digest(subject), "reviewer_identity": "TEST_REVIEWER", "decision": "approved"}
        d = verify_review_binding(subject, review)
        self.assertEqual(d["status"], "binding_matches")
        self.assertEqual(d["reason"], "review_authority_not_authenticated")
        self.assertFalse(d["available_for_policy"])


if __name__ == "__main__":
    unittest.main()
