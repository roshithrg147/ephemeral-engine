"""Unit tests verifying Phase 4.5.2 Public Workflow Capability Sanitization and Context Boundary Enforcement."""

from __future__ import annotations

import unittest

from src.capabilities.workflow_filter import CapabilityFilter
from src.context_broker import ContextBroker, ContextItem
from src.disclosure_guard import DisclosureAction, DisclosureGuard
from src.exceptions.security import ContextPolicyViolation
from src.memory import SessionRecord, session_registry
from src.memory_gateway import MemoryGateway
from src.reliability.recovery_manager import RecoveryManager
from src.security.principal import Principal
from src.security_context import SecurityContextResolver
from src.services.prompt_manager import PromptManager
from src.workflow_policy import WorkflowClass


class TestPublicWorkflowIsolation(unittest.IsolatedAsyncioTestCase):

    def setUp(self) -> None:
        self.dev_principal = Principal(
            canonical_id="firebase:dev-user",
            provider="firebase",
            provider_subject="dev-user",
            internal_user_id="u-dev",
            tenant_id="tenant-a",
            membership_id="m-dev",
            role="operator",
            permissions=frozenset({"runtime:read", "session:create", "session:read", "session:burn"}),
            email="dev@example.com",
        )
        self.public_sec_ctx = SecurityContextResolver.resolve(
            self.dev_principal, requested_workflow="PUBLIC_CHAT"
        )
        self.maint_sec_ctx = SecurityContextResolver.resolve(
            self.dev_principal, requested_workflow="MAINTENANCE"
        )

    # TEST 1 — Capability isolation
    def test_1_capability_isolation(self) -> None:
        manifest = CapabilityFilter.filter_manifest(self.public_sec_ctx)

        self.assertIn("conversation", manifest.allowed_capabilities)
        self.assertIn("general_reasoning", manifest.allowed_capabilities)

        for forbidden in ["read_file", "list_files", "save_file", "search_repository", "run_command", "burn_session"]:
            self.assertNotIn(forbidden, manifest.allowed_capabilities)
            self.assertIn(forbidden, manifest.forbidden_capabilities)

        tools = CapabilityFilter.filter_manifest(self.public_sec_ctx).allowed_tools
        self.assertNotIn("read_file", tools)
        self.assertNotIn("list_files", tools)
        self.assertNotIn("search_repository", tools)

    # TEST 2 — Prompt isolation
    def test_2_prompt_isolation(self) -> None:
        prompt_mgr = PromptManager()
        pub_system_prompt = prompt_mgr.build_orchestrator_system_prompt("lt-context", self.public_sec_ctx)
        pub_synthesis_prompt = prompt_mgr.build_synthesis_prompt(
            long_term_context="lt-context",
            user_prompt="Hello",
            model_2_response="Resp A",
            model_1_response="Resp B",
            sec_ctx=self.public_sec_ctx,
        )
        pub_json_prompt = prompt_mgr.json_response_system_prompt(self.public_sec_ctx)

        forbidden_terms = [
            "list_files",
            "read_file",
            "save_file",
            "run_command",
            "burn_session",
            "WORKSPACE EVIDENCE RULE",
            "CRITICAL PHASE GATING RULE",
            "codebase",
            "repository",
        ]
        for term in forbidden_terms:
            self.assertNotIn(term, pub_system_prompt)
            self.assertNotIn(term, pub_synthesis_prompt)
            self.assertNotIn(term, pub_json_prompt)

    # TEST 3 — Context isolation
    def test_3_context_isolation(self) -> None:
        maint_item = ContextItem(
            content="src/security/config.py contains API key definitions",
            source="repository",
            classification="MAINTENANCE",
            tenant_id="tenant-a",
            allowed_workflows=frozenset({WorkflowClass.MAINTENANCE}),
        )

        with self.assertRaises(ContextPolicyViolation):
            ContextBroker.filter_and_wrap_context(self.public_sec_ctx, [maint_item])

    # TEST 4 — Memory isolation
    def test_4_memory_isolation(self) -> None:
        memory_items = [
            {"id": "1", "content": "Public user preference", "namespace": "public", "tenant_id": "tenant-a"},
            {"id": "2", "content": "Maintenance code index", "namespace": "maintenance", "tenant_id": "tenant-a"},
            {"id": "3", "content": "Operator telemetry log", "namespace": "operator", "tenant_id": "tenant-a"},
            {"id": "4", "content": "Audit security trail", "namespace": "security-audit", "tenant_id": "tenant-a"},
        ]

        filtered = MemoryGateway.filter_memory_for_read(self.public_sec_ctx, memory_items)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "1")
        self.assertEqual(filtered[0]["namespace"], "public")

    # TEST 5 — Internal capability question
    def test_5_internal_capability_question(self) -> None:
        question_response = "I can help you navigate the project's codebase, list files, retrieve code, and inspect security modules."

        res = DisclosureGuard.inspect(self.public_sec_ctx, question_response)

        self.assertEqual(res.action, DisclosureAction.BLOCK)
        self.assertEqual(res.cleaned_text, DisclosureGuard.SAFE_PUBLIC_BOUNDARY_RESPONSE)
        self.assertNotIn("list_files", res.cleaned_text)
        self.assertNotIn("codebase", res.cleaned_text)

    # TEST 6 — Architecture leakage
    def test_6_architecture_leakage(self) -> None:
        arch_response = "The system uses ContextBroker before CapabilityBroker and runs reinitialize_session in security_context.py."

        res = DisclosureGuard.inspect(self.public_sec_ctx, arch_response)

        self.assertEqual(res.action, DisclosureAction.BLOCK)
        self.assertEqual(res.cleaned_text, DisclosureGuard.SAFE_PUBLIC_BOUNDARY_RESPONSE)
        self.assertNotIn("ContextBroker", res.cleaned_text)
        self.assertNotIn("CapabilityBroker", res.cleaned_text)

    # TEST 7 — Recovery sanitization
    async def test_7_recovery_sanitization(self) -> None:
        session_id = "test-rec-sanitization-session"
        await session_registry.flush_session(session_id)

        maint_session = SessionRecord(
            session_id=session_id,
            tenant_id="tenant-a",
            owner_subject="firebase:dev-user",
            security_context=self.maint_sec_ctx,
        )

        recovered = await RecoveryManager.reinitialize_session(
            session=maint_session,
            session_id=session_id,
            tenant_id="tenant-a",
            owner_subject="firebase:dev-user",
            workflow="PUBLIC_CHAT",
            sec_ctx=self.public_sec_ctx,
        )

        self.assertEqual(recovered.security_context.workflow, WorkflowClass.PUBLIC_CHAT)
        self.assertFalse(recovered.security_context.allow_internal_disclosure())
        self.assertNotIn("read_file", recovered.security_context.workflow_policy.allowed_tools)

        await session_registry.flush_session(session_id)


if __name__ == "__main__":
    unittest.main()
