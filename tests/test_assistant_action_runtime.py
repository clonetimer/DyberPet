"""Approval, replay, audit and scope tests for the local action runtime."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.action_runtime import ActionDenied, ActionRuntime
from DyberPet.assistant.files import PetWorkspace


class ActionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = PetWorkspace(root / "workspace")
        self.runtime = ActionRuntime(
            self.workspace, root / "audit.sqlite3", approval_ttl=30)

    def execute_approved(self, action, arguments):
        plan = self.runtime.prepare(action, arguments)
        self.assertTrue(plan["approval_required"])
        self.assertTrue(self.runtime.approve(plan["request_id"], True))
        return self.runtime.execute(plan["request_id"])

    def test_write_is_blocked_until_explicit_approval(self):
        plan = self.runtime.prepare("create_note", {
            "name": "hello.md", "content": "hello"
        })
        with self.assertRaisesRegex(ActionDenied, "not been approved"):
            self.runtime.execute(plan["request_id"])
        self.assertFalse((self.workspace.root / "hello.md").exists())

    def test_create_note_requires_approval_and_never_overwrites(self):
        result = self.execute_approved("create_note", {
            "name": "hello.md", "content": "first"
        })
        path = Path(result["result"]["path"])
        self.assertEqual(path.read_text(encoding="utf-8"), "first")
        with self.assertRaises(ActionDenied):
            self.runtime.prepare("create_note", {"name": "hello.md", "content": "second"})
        self.assertEqual(path.read_text(encoding="utf-8"), "first")

    def test_denial_consumes_request_and_leaves_workspace_unchanged(self):
        plan = self.runtime.prepare("create_file", {"name": "denied.txt", "content": "x"})
        self.assertFalse(self.runtime.approve(plan["request_id"], False))
        with self.assertRaises(ActionDenied):
            self.runtime.execute(plan["request_id"])
        self.assertFalse((self.workspace.root / "denied.txt").exists())

    def test_approval_is_one_shot_and_replay_is_rejected(self):
        plan = self.runtime.prepare("create_note", {"name": "once.md", "content": "x"})
        self.runtime.approve(plan["request_id"], True)
        self.runtime.execute(plan["request_id"])
        with self.assertRaises(ActionDenied):
            self.runtime.execute(plan["request_id"])

    def test_approval_expires(self):
        with patch("DyberPet.assistant.action_runtime.time.monotonic", return_value=10.0):
            plan = self.runtime.prepare("create_note", {"name": "expired.md", "content": "x"})
        with patch("DyberPet.assistant.action_runtime.time.monotonic", return_value=41.0):
            with self.assertRaisesRegex(ActionDenied, "expired"):
                self.runtime.approve(plan["request_id"], True)
        self.assertFalse((self.workspace.root / "expired.md").exists())

    def test_read_file_requires_approval_and_returns_utf8_text(self):
        path = self.workspace.create("analysis.md", "first line\nsecond line")
        plan = self.runtime.prepare("read_file", {"name": path.name})
        with self.assertRaises(ActionDenied):
            self.runtime.execute(plan["request_id"])
        self.runtime.approve(plan["request_id"], True)
        result = self.runtime.execute(plan["request_id"])
        self.assertEqual(result["result"]["content"], "first line\nsecond line")
        self.assertNotIn("first line", repr(self.runtime.audit_log()))

    def test_read_file_rejects_content_changed_after_user_approval(self):
        path = self.workspace.create("mutable.md", "approved content")
        plan = self.runtime.prepare("read_file", {"name": path.name})
        self.runtime.approve(plan["request_id"], True)
        path.write_text("changed after preview", encoding="utf-8")
        with self.assertRaisesRegex(ActionDenied, "changed after approval"):
            self.runtime.execute(plan["request_id"])

    def test_read_file_rejects_binary_invalid_utf8_and_large_context(self):
        (self.workspace.root / "binary.txt").write_bytes(bytes([255]))
        plan = self.runtime.prepare("read_file", {"name": "binary.txt"})
        self.runtime.approve(plan["request_id"], True)
        with self.assertRaisesRegex(ActionDenied, "UTF-8"):
            self.runtime.execute(plan["request_id"])
        (self.workspace.root / "large.md").write_text("x" * 16001, encoding="utf-8")
        plan = self.runtime.prepare("read_file", {"name": "large.md"})
        self.runtime.approve(plan["request_id"], True)
        with self.assertRaisesRegex(ActionDenied, "16,000"):
            self.runtime.execute(plan["request_id"])

    def test_only_registered_actions_are_accepted(self):
        with self.assertRaises(ActionDenied):
            self.runtime.prepare("run_shell", {"command": "whoami"})
        with self.assertRaises(ActionDenied):
            self.runtime.prepare("read_arbitrary_path", {"path": "C:/secret"})

    def test_path_traversal_and_large_content_are_rejected(self):
        with self.assertRaises(ValueError):
            self.runtime.prepare("create_note", {"name": "../outside.md", "content": "x"})
        with self.assertRaises(ActionDenied):
            self.runtime.prepare("create_note", {"name": "huge.md", "content": "x" * 300_000})

    def test_trash_restore_roundtrip_requires_separate_approvals(self):
        self.workspace.create("roundtrip.txt", "safe")
        trashed = self.execute_approved("trash_file", {"name": "roundtrip.txt"})
        self.assertFalse((self.workspace.root / "roundtrip.txt").exists())
        restored = self.execute_approved("restore_file", {"key": trashed["result"]["trash_key"]})
        self.assertEqual(Path(restored["result"]["path"]).read_text(encoding="utf-8"), "safe")

    def test_restore_collision_is_rejected_before_approval(self):
        self.workspace.create("collision.txt", "original")
        key = self.workspace.soft_delete("collision.txt")
        self.workspace.create("collision.txt", "new")
        with self.assertRaises(ActionDenied):
            self.runtime.prepare("restore_file", {"key": key})
        self.assertEqual((self.workspace.root / "collision.txt").read_text(), "new")

    def test_audit_records_prepared_approved_executed_and_denied(self):
        plan = self.runtime.prepare("create_note", {"name": "audit.md", "content": "x"})
        self.runtime.approve(plan["request_id"], True)
        self.runtime.execute(plan["request_id"])
        denied = self.runtime.prepare("create_file", {"name": "no.txt", "content": "x"})
        self.runtime.approve(denied["request_id"], False)
        statuses = [row["status"] for row in self.runtime.audit_log(limit=20)]
        self.assertIn("prepared", statuses)
        self.assertIn("approved", statuses)
        self.assertIn("executed", statuses)
        self.assertIn("denied", statuses)

    def test_audit_does_not_store_file_contents(self):
        self.execute_approved("create_note", {"name": "private.md", "content": "secret body"})
        serialized = repr(self.runtime.audit_log(limit=20))
        self.assertNotIn("secret body", serialized)

    def test_workspace_switch_invalidates_pending_approvals(self):
        plan = self.runtime.prepare("create_note", {"name": "pending.md", "content": "x"})
        other = PetWorkspace(Path(self.temp.name) / "other")
        self.runtime.set_workspace(other)
        with self.assertRaises(ActionDenied):
            self.runtime.approve(plan["request_id"], True)
