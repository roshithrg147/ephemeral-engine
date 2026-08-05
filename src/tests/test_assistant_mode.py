import unittest
from unittest.mock import MagicMock
from src.services.prompt_manager import PromptManager
from src.main import _apply_phase_gate


class TestAssistantMode(unittest.TestCase):
    def test_prompt_manager_coding_mode(self):
        prompt = PromptManager.build_orchestrator_system_prompt("lt_context", assistant_mode="coding")
        self.assertIn("CRITICAL PHASE GATING RULE (Architect-First)", prompt)
        self.assertNotIn("GENERAL ASSISTANT MODE", prompt)

    def test_prompt_manager_general_mode(self):
        prompt = PromptManager.build_orchestrator_system_prompt("lt_context", assistant_mode="general")
        self.assertNotIn("CRITICAL PHASE GATING RULE (Architect-First)", prompt)
        self.assertIn("GENERAL ASSISTANT MODE", prompt)

    def test_apply_phase_gate_bypasses_in_general_mode(self):
        record = MagicMock()
        record.metadata_registry = {"assistant_mode": "general", "development_phase": 0}

        resp, action_type, payload = _apply_phase_gate(
            record=record,
            response_text="Research response",
            action_type="save_file",
            payload={"file_path": "src/App.tsx", "file_content": "// code"},
        )
        self.assertEqual(resp, "Research response")
        self.assertEqual(action_type, "save_file")
        self.assertEqual(payload, {"file_path": "src/App.tsx", "file_content": "// code"})


if __name__ == "__main__":
    unittest.main()
