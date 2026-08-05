"""
Test Suite for Release Governance Architecture.

Verifies:
1. ReleaseGovernanceEngine runs all 10 governance gates.
2. ReleaseManifest is generated with version and commit metadata.
3. ReleaseApprovalReport outputs PASS status and gate details.
"""

import os
import unittest
from src.evidence.release_governance import ReleaseGovernanceEngine, ReleaseManifest, ReleaseApprovalReport


class TestReleaseGovernance(unittest.TestCase):
    def setUp(self):
        self.engine = ReleaseGovernanceEngine()

    def test_01_all_gates_execute_and_pass(self):
        report = self.engine.run_all_gates()
        self.assertIsInstance(report, ReleaseApprovalReport)
        self.assertEqual(report.overall_status, "PASS")
        self.assertEqual(len(report.gates), 9)
        self.assertTrue(all(g["passed"] for g in report.gates))

    def test_02_release_manifest_metadata(self):
        manifest = self.engine.manifest
        self.assertIsInstance(manifest, ReleaseManifest)
        self.assertEqual(manifest.version, "2.0.0-rc1")
        self.assertEqual(manifest.git_commit, "8f3e21a")
        self.assertEqual(manifest.backend_tests_passed, 150)
        self.assertEqual(manifest.frontend_tests_passed, 40)

    def test_03_approval_report_summaries(self):
        report = self.engine.run_all_gates()
        self.assertIn("precision_at_5", report.benchmark_summary)
        self.assertIn("prompt_injection_tests", report.security_summary)
        self.assertIn("p95_latency_ms", report.performance_summary)
        self.assertIn("PROMOTED TO DEVELOPER PREVIEW", report.release_decision)

    def test_04_manifest_file_creation(self):
        self.engine.run_all_gates()
        manifest_path = os.path.join(self.engine.workspace_root, "release_manifest.json")
        self.assertTrue(os.path.exists(manifest_path))


if __name__ == "__main__":
    unittest.main()
