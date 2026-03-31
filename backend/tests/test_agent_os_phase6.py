from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services import agent_monitor  # noqa: E402
from app.services import agent_registry  # noqa: E402
from app.services import agents_service  # noqa: E402
from app.services import event_bus as bus  # noqa: E402
from app.services import tool_registry as reg  # noqa: E402
from app.services import workflow_engine  # noqa: E402


class AgentOsPhase6DbMixin(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmpdir = tempfile.TemporaryDirectory()
        tmp_root = Path(self._tmpdir.name)

        self._original_monitor_db = agent_monitor.DB_PATH
        self._original_registry_db = agent_registry.DB_PATH
        self._original_event_bus_db = bus.DB_PATH
        self._original_workflow_db = workflow_engine.DB_PATH
        self._original_tool_registry_db = reg.DB_PATH

        self._original_limit_seed = agent_monitor._LIMIT_SEED_DONE
        self._original_agent_seed = agent_registry._BUILTIN_AGENTS_SEEDED
        self._original_workflow_seed = workflow_engine._BUILTIN_WORKFLOWS_SEEDED
        self._original_tool_seed = reg._BUILTIN_SEEDED

        agent_monitor.DB_PATH = tmp_root / "agent_monitor.db"
        agent_registry.DB_PATH = tmp_root / "agent_registry.db"
        bus.DB_PATH = tmp_root / "event_bus.db"
        workflow_engine.DB_PATH = tmp_root / "workflow_engine.db"
        reg.DB_PATH = tmp_root / "tool_registry.db"

        agent_monitor._LIMIT_SEED_DONE = False
        agent_registry._BUILTIN_AGENTS_SEEDED = False
        workflow_engine._BUILTIN_WORKFLOWS_SEEDED = False
        reg._BUILTIN_SEEDED = False

        agent_monitor._init_db()
        agent_registry._init_db()
        bus._init_db()
        workflow_engine._init_db()
        reg._init_db()

        agent_registry.seed_builtin_agents()
        reg.seed_builtin_tools()
        workflow_engine.seed_builtin_workflows()
        agent_monitor.seed_default_limits()

    def tearDown(self) -> None:
        agent_monitor.DB_PATH = self._original_monitor_db
        agent_registry.DB_PATH = self._original_registry_db
        bus.DB_PATH = self._original_event_bus_db
        workflow_engine.DB_PATH = self._original_workflow_db
        reg.DB_PATH = self._original_tool_registry_db

        agent_monitor._LIMIT_SEED_DONE = self._original_limit_seed
        agent_registry._BUILTIN_AGENTS_SEEDED = self._original_agent_seed
        workflow_engine._BUILTIN_WORKFLOWS_SEEDED = self._original_workflow_seed
        reg._BUILTIN_SEEDED = self._original_tool_seed

        self._tmpdir.cleanup()
        super().tearDown()

    def _metric_rows(self, metric_type: str) -> list[sqlite3.Row]:
        con = sqlite3.connect(str(agent_monitor.DB_PATH))
        con.row_factory = sqlite3.Row
        try:
            return con.execute(
                "SELECT * FROM agent_metrics WHERE metric_type = ? ORDER BY id ASC",
                (metric_type,),
            ).fetchall()
        finally:
            con.close()

    def _details(self, row: sqlite3.Row) -> dict:
        return json.loads(row["details_json"] or "{}")


class ToolRegistryConvergenceTest(AgentOsPhase6DbMixin):
    def test_direct_tool_execution_emits_canonical_event_and_metric(self) -> None:
        reg.register_tool(name="test-tool", handler=lambda args: {"ok": True, "echo": args.get("input", "")})

        result = reg.execute_tool(
            "test-tool",
            {"input": "hello"},
            source="api",
            source_agent_id="tool-registry",
            run_id="direct-run",
        )
        self.assertTrue(result["ok"])

        reg.update_tool("test-tool", {"enabled": False})
        blocked = reg.execute_tool(
            "test-tool",
            {"input": "blocked"},
            source="api",
            source_agent_id="tool-registry",
            run_id="direct-run-disabled",
        )
        self.assertFalse(blocked["ok"])
        self.assertIn("disabled", blocked.get("error", ""))

        events, _ = bus.list_events(event_type="tool.executed", source_agent_id="tool-registry", limit=10)
        matching = [event for event in events if event["payload"].get("tool_name") == "test-tool"]
        self.assertGreaterEqual(len(matching), 2)
        latest_payload = matching[0]["payload"]
        self.assertIn("result_summary", latest_payload)
        self.assertEqual(latest_payload["source"], "api")
        self.assertIn("run_id", latest_payload)

        metric_rows = self._metric_rows("tool.execution")
        test_rows = [row for row in metric_rows if self._details(row).get("tool_name") == "test-tool"]
        self.assertGreaterEqual(len(test_rows), 2)
        self.assertTrue(any(self._details(row).get("source") == "api" for row in test_rows))


class WorkflowToolConvergenceTest(AgentOsPhase6DbMixin):
    def test_workflow_tool_step_uses_registry_native_execution(self) -> None:
        reg.register_tool(name="test-workflow-tool", handler=lambda args: {"ok": True, "items": [{"text": args.get("query", "")}]})
        current = agent_monitor.ensure_agent_limit(agent_monitor.WORKFLOW_ENGINE_AGENT_ID)
        agent_monitor.update_agent_limit(
            agent_monitor.WORKFLOW_ENGINE_AGENT_ID,
            {
                "max_runs_per_hour": current["max_runs_per_hour"],
                "max_execution_seconds": current["max_execution_seconds"],
                "max_context_tokens": current["max_context_tokens"],
                "allowed_tools": [*current["allowed_tools"], "test-workflow-tool"],
            },
        )

        workflow_engine.create_workflow_template(
            {
                "id": "test.workflow.phase6",
                "name": "Phase 6 Tool Workflow",
                "graph": {
                    "entry_step": "tool-step",
                    "steps": [
                        {
                            "id": "tool-step",
                            "type": "tool",
                            "tool_name": "test-workflow-tool",
                            "input_map": {"query": "$.input.query"},
                            "save_as": "tool_result",
                            "next": None,
                            "config": {"label": "Tool"},
                        }
                    ],
                },
            }
        )

        run = workflow_engine.start_workflow_run(
            workflow_id="test.workflow.phase6",
            workflow_input={"query": "phase6"},
            context={"num_ctx": 256},
            trigger_source="test",
        )

        self.assertEqual(run["status"], "completed")
        self.assertTrue(run["step_results"]["tool_result"]["ok"])

        events, _ = bus.list_events(event_type="tool.executed", source_agent_id="test.workflow.phase6", limit=10)
        self.assertEqual(len(events), 1)
        payload = events[0]["payload"]
        self.assertEqual(payload["tool_name"], "test-workflow-tool")
        self.assertEqual(payload["workflow_id"], "test.workflow.phase6")
        self.assertEqual(payload["step_id"], "tool-step")
        self.assertEqual(payload["source"], "workflow")

        metric_rows = self._metric_rows("tool.execution")
        self.assertEqual(len(metric_rows), 1)
        details = self._details(metric_rows[0])
        self.assertEqual(details["tool_name"], "test-workflow-tool")
        self.assertEqual(details["source"], "workflow")


class AgentOsIntegrationChainTest(AgentOsPhase6DbMixin):
    @staticmethod
    def _plan() -> dict:
        return {
            "route": "chat",
            "tools": ["memory_search"],
            "temporal": {
                "mode": "none",
                "requires_web": False,
                "freshness_sensitive": False,
                "years": [],
            },
            "web_plan": {
                "is_multi_intent": False,
                "subqueries": [],
                "passes": [],
                "pass_count": 1,
                "overflow_applied": False,
                "uncovered_subqueries": [],
            },
        }

    def test_agent_run_tool_event_workflow_and_monitoring_chain(self) -> None:
        reg.register_tool(
            name="search_memory",
            handler=lambda args: {"ok": True, "count": 1, "items": [{"text": f"Memory for {args.get('query', '')}"}]},
            category="memory",
        )

        with patch.object(agents_service.PlannerV2Service, "plan", return_value=self._plan()), \
             patch.object(agents_service, "run_chat", return_value={"ok": True, "answer": "hello from agent"}), \
             patch.object(agents_service, "observe_dialogue", return_value={"ok": True}), \
             patch.object(agents_service, "_get_and_clear_attachments", return_value=""), \
             patch.object(agents_service, "_maybe_generate_files", return_value=""), \
             patch.object(agents_service, "_maybe_auto_exec_python", side_effect=lambda user_input, answer, timeline, enabled=True: answer), \
             patch.object(agents_service, "pick_model_for_route", return_value="test-model"), \
             patch.object(agents_service, "_should_recall_memory_context", return_value=False), \
             patch.object(agents_service, "extract_and_save", return_value={"ok": True}), \
             patch.object(agents_service, "get_relevant_context", return_value=[]), \
             patch.object(agents_service, "get_cached", return_value=None), \
             patch.object(agents_service, "set_cached", return_value=None), \
             patch.object(agents_service, "should_cache", return_value=False), \
             patch.object(agents_service._HISTORY, "start_run", return_value={"run_id": "agent-run-1"}), \
             patch.object(agents_service._HISTORY, "finish_run", return_value=None):
            result = agents_service.run_agent(
                model_name="test-model",
                profile_name="Universal",
                user_input="Who am I?",
                session_id="phase6-session",
                use_memory=True,
                use_library=False,
                use_web_search=False,
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["meta"]["run_id"], "agent-run-1")

        agent_events, _ = bus.list_events(source_agent_id="builtin-universal", limit=10)
        event_types = [event["event_type"] for event in agent_events]
        self.assertIn("agent.run.started", event_types)
        self.assertIn("agent.run.completed", event_types)

        tool_events, _ = bus.list_events(event_type="tool.executed", source_agent_id="builtin-universal", limit=10)
        self.assertEqual(len(tool_events), 1)
        tool_payload = tool_events[0]["payload"]
        self.assertEqual(tool_payload["tool_name"], "search_memory")
        self.assertEqual(tool_payload["source"], "agent_run")
        self.assertEqual(tool_payload["run_id"], "agent-run-1")

        dashboard = agent_monitor.get_agent_os_dashboard()
        self.assertEqual(dashboard["total_agent_runs"], 1)
        self.assertEqual(dashboard["blocked_runs"], 0)

        tool_metric_rows = self._metric_rows("tool.execution")
        self.assertEqual(len(tool_metric_rows), 1)
        tool_details = self._details(tool_metric_rows[0])
        self.assertEqual(tool_details["tool_name"], "search_memory")
        self.assertEqual(tool_details["source"], "agent_run")

        run_metric_rows = self._metric_rows("agent.run")
        self.assertEqual(len(run_metric_rows), 1)


if __name__ == "__main__":
    unittest.main()
