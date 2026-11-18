"""Validation and real workspace execution tests for reviewed task plans."""
import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.action_runtime import ActionDenied, ActionRuntime
from DyberPet.assistant.files import PetWorkspace, WorkspaceError
from DyberPet.assistant.task_plan import (
    TaskPlan, TaskPlanError, TaskSession, TaskStep, parse_task_plan,
)


def plan_text(*steps, title="整理笔记"):
    return json.dumps({
        "version": 1,
        "title": title,
        "steps": [{"action": action, "name": name, "content": content}
                  for action, name, content in steps],
    }, ensure_ascii=False)


class TaskPlanTests(unittest.TestCase):
    def test_plan_and_steps_preserve_exact_valid_text_and_are_immutable(self):
        plan = parse_task_plan(plan_text(("create_note", "笔记.MD", "第一行\r\n第二行\n")))
        self.assertEqual(plan.title, "整理笔记")
        self.assertEqual(plan.steps, (TaskStep("create_note", "笔记.MD", "第一行\r\n第二行\n"),))
        with self.assertRaises(FrozenInstanceError):
            plan.title = "changed"
        with self.assertRaises(FrozenInstanceError):
            plan.steps[0].content = "changed"

    def test_rejects_non_protocol_json(self):
        valid = plan_text(("create_file", "report.csv", "name,value\n"))
        cases = (
            None, b"{}", "{", "[]", "null", "\ufeff" + valid, valid + " extra",
            "```json\n" + valid + "\n```", valid.replace('"version": 1', '"version": 2'),
            valid.replace('"version": 1', '"version": true'),
            valid.replace('"version": 1', '"version": 1.0'),
            valid.replace('"version": 1', '"version": NaN'),
            valid.replace('"version": 1', '"version": "1"'),
            valid.replace('"version": 1, ', ''),
            valid.replace('"version": 1', '"version": 1, "extra": 0'),
            valid.replace('"version": 1', '"version": 2, "version": 1'),
            valid.replace('"name": "report.csv"', '"name": "bad.csv", "name": "report.csv"'),
            valid.replace('"name": "report.csv"', '"name": "report.csv", "extra": 0'),
            valid.replace('"name": "report.csv"', '"name": 42'),
            valid.replace('"content": "name,value\\n"', '"content": []'),
            valid.replace('"content": "name,value\\n"', '"content": "\\ud800"'),
            valid.replace('"name": "report.csv"', '"name": "bad\\ud800.csv"'),
            valid.replace('"title": "整理笔记"', '"title": "bad\\ud800"'),
            valid.replace('"title": "整理笔记"', '"title": false'),
            '{"version":1,"title":"a","steps":{}}',
            '{"version":1,"title":"a","steps":[1]}',
            "[" * 2000 + "]" * 2000,
        )
        for case in cases:
            with self.subTest(case=str(case)[:180]), self.assertRaises(TaskPlanError):
                parse_task_plan(case)

    def test_rejects_unsafe_field_values_and_canonical_name_collisions(self):
        cases = (
            plan_text(("trash_file", "old.txt", "")),
            plan_text(("create_note", "report.csv", "")),
            plan_text(("create_file", "secret.exe", "")),
            plan_text(("create_file", "../outside.md", "")),
            plan_text(("create_file", "C:\\outside.md", "")),
            plan_text(("create_file", "./inside.md", "")),
            plan_text(("create_file", "CON.txt", "")),
            plan_text(("create_file", ".hidden.md", "")),
            plan_text(("create_file", " note.md ", "")),
            plan_text(("create_file", "note\x7f.md", "")),
            plan_text(("create_file", "note\u202e.md", "")),
            plan_text(("create_file", "one.md", ""), title=""),
            plan_text(("create_file", "one.md", ""), title="\n "),
            plan_text(("create_file", "one.md", ""), title="bad\x85title"),
            plan_text(("create_file", "one.md", ""), title="bad\u200btitle"),
            plan_text(("create_file", "Straße.md", ""), ("create_note", "STRASSE.MD", "")),
        )
        for case in cases:
            with self.subTest(case=case), self.assertRaises(TaskPlanError):
                parse_task_plan(case)

    def test_enforces_inclusive_character_count_and_raw_utf8_byte_limits(self):
        valid = plan_text(("create_file", "first.md", "文" * 8000),
                          ("create_file", "second.md", "😀" * 8000),
                          ("create_file", "third.md", ""),
                          ("create_file", "fourth.md", ""),
                          ("create_file", "fifth.md", ""), title="文" * 120)
        bounded = valid + " " * (128 * 1024 - len(valid.encode("utf-8")))
        self.assertEqual(len(parse_task_plan(bounded).steps), 5)
        cases = (
            bounded + " ",
            plan_text(("create_file", "one.md", ""), title="x" * 121),
            plan_text(),
            plan_text(*(("create_file", f"{i}.md", "") for i in range(6))),
            plan_text(("create_file", "one.md", "x" * 8001)),
            plan_text(("create_file", "one.md", "x" * 8000),
                      ("create_file", "two.md", "x" * 8000),
                      ("create_file", "three.md", "x")),
        )
        for case in cases:
            with self.subTest(case=case[:160]), self.assertRaises(TaskPlanError):
                parse_task_plan(case)

    def test_direct_construction_cannot_bypass_validation_or_mutate_steps_collection(self):
        step = TaskStep("create_note", "note.md", "content")
        steps = [step]
        plan = TaskPlan("title", steps)
        steps.clear()
        self.assertEqual(plan.steps, (step,))
        for args in (("trash_file", "note.md", ""), ("create_note", " n.md ", ""),
                     ("create_file", "file.txt", "\udfff"), ("create_note", "note.md", 1)):
            with self.subTest(args=args), self.assertRaises(TaskPlanError):
                TaskStep(*args)
        for title, invalid_steps in (("\ud800", (step,)), ("title", ()),
                                     ("title", ({"name": "note.md"},)),
                                     ("title", (step, TaskStep("create_file", "NOTE.MD", "")))):
            with self.subTest(title=title, steps=invalid_steps), self.assertRaises(TaskPlanError):
                TaskPlan(title, invalid_steps)


class TaskSessionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.workspace = PetWorkspace(self.root / "workspace")
        self.runtime = ActionRuntime(self.workspace, self.root / "audit.sqlite3", approval_ttl=30)
        self.plan = parse_task_plan(plan_text(
            ("create_note", "first.md", "原样\r\nline two\n"),
            ("create_file", "second.csv", "a,b\n1,2\n"),
        ))
        self.session = TaskSession(self.plan, self.runtime)

    def test_each_file_requires_its_own_approval_for_the_exact_reviewed_content(self):
        self.assertEqual(self.session.state, "ready")
        self.assertEqual(self.session.completed, ())
        self.assertEqual(self.session.error, "")
        self.assertEqual(self.runtime.audit_log(), [])
        first = self.session.prepare_next()
        first_id = first["request_id"]
        self.assertEqual(self.session.state, "awaiting_approval")
        self.assertEqual((first["index"], first["total"], first["action"], first["name"],
                          first["content"], first["target"]),
                         (0, 2, "create_note", "first.md", "原样\r\nline two\n",
                          str(self.workspace.root / "first.md")))
        self.assertIn(str(self.workspace.root / "first.md"), first["preview"])
        self.assertEqual(self.workspace.list_files(), [])
        self.assertEqual([row["request_id"] for row in self.runtime.audit_log()], [first_id])

        first.update(request_id="forged", content="replaced", name="replacement.md")
        result = self.session.decide(first_id, True)
        self.assertEqual(self.session.state, "ready")
        self.assertEqual(self.workspace.list_files(), ["first.md"])
        self.assertEqual((self.workspace.root / "first.md").read_bytes(),
                         "原样\r\nline two\n".encode("utf-8"))
        self.assertEqual(self.session.completed, (result,))
        result["result"]["name"] = "changed"
        self.session.completed[0]["result"]["name"] = "also changed"
        self.assertEqual(self.session.completed[0]["result"]["name"], "first.md")

        second = self.session.prepare_next()
        self.assertNotEqual(second["request_id"], first_id)
        self.assertEqual((second["index"], second["total"], second["name"]), (1, 2, "second.csv"))
        self.assertEqual(self.workspace.list_files(), ["first.md"])
        self.session.decide(second["request_id"], True)
        self.assertEqual(self.session.state, "completed")
        self.assertEqual([item["result"]["name"] for item in self.session.completed],
                         ["first.md", "second.csv"])
        self.assertEqual((self.workspace.root / "second.csv").read_bytes(), b"a,b\n1,2\n")

    def test_replayed_token_cannot_approve_current_or_completed_step(self):
        first = self.session.prepare_next()
        self.session.decide(first["request_id"], True)
        second = self.session.prepare_next()
        with self.assertRaises(TaskPlanError):
            self.session.decide(first["request_id"], True)
        self.assertEqual(self.session.state, "failed")
        self.assertTrue(self.session.error)
        self.assertEqual(self.workspace.list_files(), ["first.md"])
        with self.assertRaises(ActionDenied):
            self.runtime.approve(second["request_id"], True)

    def test_truthy_values_are_declines_and_cancel_keeps_completed_files(self):
        first = self.session.prepare_next()
        self.session.decide(first["request_id"], True)
        second = self.session.prepare_next()
        self.assertIsNone(self.session.decide(second["request_id"], 1))
        self.session.cancel()
        self.session.cancel()
        self.assertEqual(self.session.state, "cancelled")
        self.assertEqual([item["result"]["name"] for item in self.session.completed], ["first.md"])
        self.assertEqual(self.workspace.list_files(), ["first.md"])
        self.assertEqual(self.runtime.audit_log()[0]["status"], "denied")

    def test_cancelling_pending_plan_revokes_only_its_request(self):
        separate = self.runtime.prepare("create_file", {"name": "outside-plan.md"})
        first = self.session.prepare_next()
        self.session.cancel()
        self.session.cancel()
        self.assertEqual(self.session.state, "cancelled")
        with self.assertRaises(ActionDenied):
            self.runtime.approve(first["request_id"], True)
        self.assertEqual(self.workspace.list_files(), [])
        self.runtime.approve(separate["request_id"], True)
        self.runtime.execute(separate["request_id"])
        self.assertEqual(self.workspace.list_files(), ["outside-plan.md"])

    def test_collision_during_execution_keeps_prior_work_and_closes_plan(self):
        first = self.session.prepare_next()
        self.session.decide(first["request_id"], True)
        second = self.session.prepare_next()
        collision = self.workspace.create("second.csv", "external write")
        with self.assertRaisesRegex(WorkspaceError, "already exists"):
            self.session.decide(second["request_id"], True)
        self.assertEqual(self.session.state, "failed")
        self.assertIn("already exists", self.session.error)
        self.assertEqual([item["result"]["name"] for item in self.session.completed], ["first.md"])
        self.assertEqual(collision.read_bytes(), b"external write")

    def test_collision_during_prepare_closes_plan_without_consuming_pending_slots(self):
        path = self.workspace.create("first.md", "existing")
        with self.assertRaisesRegex(ActionDenied, "already exists"):
            self.session.prepare_next()
        self.assertEqual(self.session.state, "failed")
        self.assertEqual(self.session.completed, ())
        self.assertEqual(path.read_bytes(), b"existing")
        self.assertEqual(self.runtime.audit_log(), [])

    def test_expiry_fails_session_without_writing_any_files(self):
        with patch("DyberPet.assistant.action_runtime.time.monotonic", return_value=10.0):
            first = self.session.prepare_next()
        with patch("DyberPet.assistant.action_runtime.time.monotonic", return_value=41.0):
            with self.assertRaisesRegex(ActionDenied, "expired"):
                self.session.decide(first["request_id"], True)
        self.assertEqual(self.session.state, "failed")
        self.assertEqual(self.session.completed, ())
        self.assertEqual(self.workspace.list_files(), [])

    def test_workspace_replacement_rejects_prepared_plan_even_for_same_root(self):
        first = self.session.prepare_next()
        self.runtime.set_workspace(PetWorkspace(self.workspace.root))
        with self.assertRaises(ActionDenied):
            self.session.decide(first["request_id"], True)
        self.assertEqual(self.session.state, "failed")
        self.assertEqual(self.workspace.list_files(), [])

    def test_reassigned_original_workspace_does_not_revive_unprepared_plan(self):
        other = PetWorkspace(self.root / "other")
        self.runtime.set_workspace(other)
        self.runtime.set_workspace(self.workspace)
        with self.assertRaises(ActionDenied):
            self.session.prepare_next()
        self.assertEqual(self.session.state, "failed")
        self.assertEqual(self.workspace.list_files(), [])
        self.assertEqual(other.list_files(), [])

    def test_global_invalidation_closes_an_unprepared_plan(self):
        self.runtime.invalidate_pending()
        with self.assertRaises(ActionDenied):
            self.session.prepare_next()
        self.assertEqual(self.session.state, "failed")
        self.assertEqual(self.workspace.list_files(), [])

    def test_audit_failure_after_file_creation_counts_as_completed_step(self):
        first = self.session.prepare_next()
        original_record = self.runtime._record

        def fail_completion_audit(request_id, action, target, status, detail):
            if status == "executed":
                raise OSError("audit volume unavailable")
            original_record(request_id, action, target, status, detail)

        with patch.object(self.runtime, "_record", side_effect=fail_completion_audit):
            result = self.session.decide(first["request_id"], True)
        self.assertIn("audit volume unavailable", result["audit_warning"])
        self.assertEqual(self.session.completed, (result,))
        self.assertEqual(self.session.state, "ready")
        self.assertEqual(self.workspace.list_files(), ["first.md"])
