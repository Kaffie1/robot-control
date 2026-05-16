from __future__ import annotations

import unittest
from unittest import mock

from backend.agent.common.confirmation_utils import (
    get_pending_confirmation,
    get_playbook_input,
    resolve_pending_confirmation_reply,
)
from backend.agent.playbooks import bt_executor, executor
from backend.agent.playbooks.loader import load_playbooks
from backend.agent.playbooks.schema import validate_playbook_spec


class BehaviourTreePlaybookTests(unittest.TestCase):
    def test_all_playbooks_validate(self) -> None:
        playbooks = load_playbooks()
        self.assertGreaterEqual(len(playbooks), 4)
        for playbook in playbooks:
            validate_playbook_spec(playbook)

    def test_call_playbook_can_resume_parent_flow(self) -> None:
        parent = {
            "id": "parent",
            "title": "parent",
            "root": {
                "type": "sequence",
                "name": "root",
                "children": [
                    {
                        "type": "selector",
                        "name": "ensure_a",
                        "children": [
                            {"type": "condition", "name": "check_a", "tool_name": "fake", "assert_ref": "rule_a"},
                            {"type": "call_playbook", "name": "fix_a", "playbook_id": "child"},
                        ],
                    },
                    {"type": "condition", "name": "check_b", "tool_name": "fake", "assert_ref": "rule_b"},
                ],
            },
        }
        child = {
            "id": "child",
            "title": "child",
            "root": {
                "type": "sequence",
                "name": "child_root",
                "children": [
                    {"type": "condition", "name": "child_fix", "tool_name": "fake", "assert_ref": "rule_child"},
                ],
            },
        }

        def fake_run_script_step(step: dict, tool_context: dict | None) -> dict:
            playbook_id = (tool_context or {}).get("playbook_id")
            name = step.get("name")
            mapping = {
                ("parent", "check_a"): {"passed": False, "output": "missing"},
                ("parent", "check_b"): {"passed": True, "output": "continued"},
                ("child", "child_fix"): {"passed": True, "output": "fixed"},
            }
            payload = mapping[(playbook_id, name)]
            return {
                "name": name,
                "tool_name": "fake",
                "arguments": {},
                "output": payload["output"],
                "assert_ref": step.get("assert_ref", ""),
                "passed": payload["passed"],
                "failure_action": "",
                "failure_message": "",
                "failure_playbook_id": "",
            }

        def fake_find_playbook_by_id(playbook_id: str) -> dict | None:
            return {"child": child}.get(playbook_id)

        with mock.patch.object(executor, "run_script_step", side_effect=fake_run_script_step):
            with mock.patch.object(executor, "find_playbook_by_id", side_effect=fake_find_playbook_by_id):
                with mock.patch.object(bt_executor, "find_playbook_by_id", side_effect=fake_find_playbook_by_id):
                    result = executor.execute_playbook(parent, tool_context={"session": {"chat_state": {}}})

        self.assertTrue(result.get("passed"))
        self.assertEqual(["check_a", "fix_a", "check_b"], [step.get("name") for step in result.get("steps", [])])
        self.assertEqual(1, len(result.get("sub_playbooks") or []))

    def test_confirmation_store_as_is_preserved(self) -> None:
        playbook = {
            "id": "confirm-demo",
            "title": "confirm-demo",
            "root": {
                "type": "sequence",
                "name": "root",
                "children": [
                    {
                        "type": "action",
                        "name": "approve_restart",
                        "tool_name": "fake",
                        "require_confirmation": True,
                        "confirmation": {
                            "when": "before",
                            "mode": "approve",
                            "message": "是否继续？",
                            "output": {"store_as": "approved", "type": "boolean"},
                        },
                    }
                ],
            },
        }

        def fake_run_script_step(step: dict, tool_context: dict | None) -> dict:
            approved = get_playbook_input(tool_context, "approved")
            if approved is None:
                return {
                    "name": step.get("name"),
                    "tool_name": "fake",
                    "arguments": {},
                    "output": "",
                    "assert_ref": "",
                    "passed": False,
                    "pending_confirmation": True,
                    "confirmation": {
                        "type": "clarify",
                        "mode": "approve",
                        "message": "是否继续？",
                        "question": "是否继续？",
                        "input": {},
                        "options": [],
                        "count": 0,
                        "output": {"store_as": "approved", "type": "boolean"},
                    },
                }
            return {
                "name": step.get("name"),
                "tool_name": "fake",
                "arguments": {},
                "output": "done",
                "assert_ref": "",
                "passed": True,
                "failure_action": "",
                "failure_message": "",
                "failure_playbook_id": "",
            }

        tool_context = {"session": {"chat_state": {}}}
        with mock.patch.object(executor, "run_script_step", side_effect=fake_run_script_step):
            first = executor.execute_playbook(playbook, tool_context=tool_context)

        self.assertTrue(first.get("pending_confirmation"))
        pending = get_pending_confirmation(tool_context)
        self.assertEqual("approved", pending.get("store_as"))

        reply = resolve_pending_confirmation_reply("确认", tool_context)
        self.assertTrue(reply.get("resolved"))
        self.assertTrue(get_playbook_input(tool_context, "approved"))


if __name__ == "__main__":
    unittest.main()
