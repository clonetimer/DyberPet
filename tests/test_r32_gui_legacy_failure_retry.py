"""R32 old Windows batch log can be safely reused in GUI without trusted URLs."""
from __future__ import annotations
import ast
from pathlib import Path
import unittest


class R32LegacyReportGui(unittest.TestCase):
    def test_gui_old_cli_report_opt_in_action_and_reason_progress(self):
        path = Path(__file__).resolve().parents[1] / "DyberPet/DyberSettings/CharCardUI.py"
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        for expected in (
            "def _retryFailedFromPreviousReport(self):",
            "read_failed_profiles_from_report(Path(source))",
            "plan_personal_sources(root, only_profiles=failed)",
            'if r["status"] == "ready_for_opt_in"',
            "self._startCreatorBulkImport(only_profiles=targets)",
            "旧报告中的任意 URL、脚本、来源键都会被忽略",
            'info.get("failure_class"',
            'info.get("reason"',
            'info.get("has_next_pinned_source")',
            "已安装角色与存档不会覆盖",
        ):
            self.assertIn(expected,text)

    def test_script_and_frozen_zip_have_retry_guards(self):
        root = Path(__file__).resolve().parents[1]
        build = (root/"tools/build_personal65_windows.ps1").read_text(encoding="utf-8")
        verify = (root/"tools/verify_personal_portable.py").read_text(encoding="utf-8")
        script = (root/"tools/Retry-Failed-Roles.ps1").read_text(encoding="utf-8")
        self.assertIn("Retry-Failed-Roles.ps1",build)
        self.assertIn("Retry-Failed-Roles.cmd",build)
        self.assertIn("Retry-Failed-Roles.cmd",verify)
        self.assertIn("--retry-failed-from $prior",script)
        self.assertIn("--role-root $roles",script)
        self.assertNotIn("Remove-Item",script)


if __name__=="__main__":
    unittest.main()
