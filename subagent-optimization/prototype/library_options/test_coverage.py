import unittest
from prototype.library_options.coverage import plan


def index(libraries):
    return {"schema_version": 1, "scope_id": "ARTIFICIAL_TEST_SCOPE",
            "libraries": [{"id": k, "lookup_ids": list(v)} for k, v in libraries.items()],
            "lookup_dimensions": {k: {"radius": 1, "mode": "GROW"}
                                  for values in libraries.values() for k in values}}


class CoverageTests(unittest.TestCase):
    def test_marginal_coverage_can_favor_smaller_library_and_preserves_input(self):
        inputs = {"already_in_plan": ["a", "b", "c"],
                  "large": ["a", "b", "c", "d"], "small": ["e", "f"]}
        source = index(inputs)
        result = plan(source, ["already_in_plan"])
        chosen = result["selected_additions"][0]
        initial = set(inputs["already_in_plan"])
        self.assertEqual(len(set(inputs[chosen]) - initial),
                         max(len(set(v) - initial) for k, v in inputs.items() if k != "already_in_plan"))
        self.assertLess(len(inputs[chosen]), len(inputs["large"]))
        self.assertEqual(result["planned_union_lookup_count"], len(initial | set(inputs[chosen])))
        self.assertEqual(plan(source, ["already_in_plan"], strategy="largest_library")["selected_additions"], ["large"])
        self.assertEqual(source, index(inputs))
        self.assertFalse(result["execution_approved"])

    def test_aliases_do_not_add_material_and_bad_initial_state_is_rejected(self):
        source = index({"first": ["a", "b"], "renamed_copy": ["a", "b"], "other": ["c"]})
        result = plan(source, additions=10)
        self.assertEqual(result["planned_union_lookup_count"], len(source["lookup_dimensions"]))
        self.assertNotIn("renamed_copy", result["selected_additions"])
        self.assertTrue(all(r["additional_lookup_tuples"] > 0 for r in result["rounds"]))
        with self.assertRaises(ValueError): plan(source, ["unknown"])
        with self.assertRaises(ValueError): plan(source, ["first", "first"])


if __name__ == "__main__":
    unittest.main()
