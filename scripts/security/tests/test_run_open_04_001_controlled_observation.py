import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "run_open_04_001_controlled_observation.py"
SPEC = importlib.util.spec_from_file_location("run_open_04_001_controlled_observation", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RunOpen04001ControlledObservationTest(unittest.TestCase):
    def test_all_profiles_b_and_c_meet_fixed_thresholds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auth, seed, traffic, thresholds = self.files(root)
            observation, policy = MODULE.run(auth, seed, traffic, thresholds)
            self.assertTrue(observation["thresholdsPassed"])
            self.assertEqual(0, observation["legacyDecisionReadCount"])
            self.assertEqual(0, observation["totals"]["AGENT_WIDER_THAN_AUTH"])
            self.assertEqual(0, observation["totals"]["UNMAPPABLE"])
            self.assertEqual(100, observation["profiles"][0]["phaseB"]["resolutionCount"])
            self.assertIn("code-a", policy["fieldPolicies"])

    def test_rollback_drill_policy_is_a_strict_tightening(self):
        policy = {"fieldPolicies": {"code-a": {
            "displayableFields": {"employee": ["email", "name"]},
            "filterableFields": {"employee": ["email", "name"]},
            "allowedOperators": {}, "allowedFunctions": {},
        }}}
        drill = MODULE.build_tightening_drill_policy(policy)
        self.assertEqual(["email"], drill["fieldPolicies"]["code-a"]["displayableFields"]["employee"])
        self.assertEqual(["email", "name"], policy["fieldPolicies"]["code-a"]["displayableFields"]["employee"])

    def test_missing_profile_and_widening_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            auth, seed, traffic, thresholds = self.files(root)
            traffic.write_text(json.dumps({
                "schemaVersion": MODULE.TRAFFIC_SCHEMA,
                "permissionCodes": [],
                "iterationsPerProfilePerPhase": 100,
                "negativeCases": sorted(MODULE.NEGATIVE_CASES),
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "cover"):
                MODULE.run(auth, seed, traffic, thresholds)

    @staticmethod
    def files(root):
        auth = root / "auth.yml"
        seed = root / "seed.yml"
        traffic = root / "traffic.json"
        thresholds = root / "thresholds.json"
        auth.write_text("""
auth:
  rbac:
    roles:
      role-a: {permission-profile: profile-a, permission-codes: [code-a]}
    permission-profiles:
      profile-a:
        filterable-fields: {employee: [name]}
        displayable-fields: {employee: [name]}
        allowed-operators: {}
        allowed-functions: {}
""", encoding="utf-8")
        seed.write_text("""
field-policies:
  code-a:
    filterable-fields: {employee: [name]}
    displayable-fields: {employee: [name]}
    allowed-operators: {}
    allowed-functions: {}
""", encoding="utf-8")
        traffic.write_text(json.dumps({
            "schemaVersion": MODULE.TRAFFIC_SCHEMA,
            "permissionCodes": ["code-a"],
            "iterationsPerProfilePerPhase": 100,
            "negativeCases": sorted(MODULE.NEGATIVE_CASES),
        }), encoding="utf-8")
        thresholds.write_text(json.dumps({
            "schemaVersion": MODULE.THRESHOLDS_SCHEMA,
            "minimumPerProfilePerPhase": 100,
        }), encoding="utf-8")
        return auth, seed, traffic, thresholds


if __name__ == "__main__":
    unittest.main()
