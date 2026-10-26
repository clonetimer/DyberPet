"""Headless Qt smoke of actual assistant dialog, with no microphone or model."""
import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError:
    QApplication = QMessageBox = None


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt smoke CI")
class AssistantQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dialog = PetAssistantDialog("咕嘎", Path(self.tmp.name) / "files")
        self.addCleanup(self.dialog.close)

    def test_dialog_persona_and_file_actions_exist(self):
        self.assertEqual(self.dialog.persona.currentData(), "guga")
        self.assertFalse(self.dialog.ppl_enabled.isChecked())
        self.assertTrue(self.dialog.workspace.root.is_dir())
        self.dialog.set_character("Doro")
        self.assertEqual(self.dialog.persona.currentData(), "doro")

    def test_readiness_button_is_read_only_and_does_not_touch_microphone(self):
        self.assertIn("本机功能自检", self.dialog.readiness_button.text())
        with patch("DyberPet.assistant.ui.inspect_readiness") as report, \
             patch.object(QMessageBox, "information") as display:
            report.return_value = {"checks": [
                {"feature": "语音播报", "status": "disabled", "detail": "未启用"}]}
            self.dialog.readiness_button.click()
            self.assertTrue(display.called)
            self.assertEqual(report.call_count, 1)
            self.assertFalse(report.call_args.kwargs["ppl_enabled"])
            self.assertIn("只读", display.call_args.args[2])
        self.assertIsNone(self.dialog._job)

    def test_role_interaction_export_is_explicit_and_never_claims_human_qa(self):
        import json
        from tools import character_interaction_coverage
        file_path = Path(self.tmp.name) / "role_interaction_audit.json"
        result = {
            "role": "咕嘎", "status": "imported_artist_claim_not_verified",
            "on_disk_action_names": ["wave"],
            "installed_action_categories": ["greet"],
            "currently_unlocked_categories": ["greet"],
            "missing_categories": ["sleep"],
            "art_likeness_qa_passed": False,
        }
        self.dialog.set_actions(["wave"])
        with patch.object(character_interaction_coverage, "inspect_selected_role_interactions",
                          return_value=result) as checker, \
             patch("DyberPet.assistant.ui.QFileDialog.getSaveFileName",
                   return_value=("", "")) as picker:
            self.dialog.interaction_export_button.click()
            self.assertEqual(checker.call_count, 1)
            self.assertEqual(checker.call_args.kwargs["unlocked_actions"], {"wave"})
            self.assertEqual(picker.call_count, 1)
            self.assertFalse(file_path.exists())

        with patch.object(character_interaction_coverage, "inspect_selected_role_interactions",
                          return_value=result), \
             patch("DyberPet.assistant.ui.QFileDialog.getSaveFileName",
                   return_value=(str(file_path), "JSON Files (*.json)")):
            self.dialog.interaction_export_button.click()
        saved = json.loads(file_path.read_text("utf-8"))
        self.assertEqual(saved["role"], "咕嘎")
        self.assertEqual(saved["currently_unlocked_categories"], ["greet"])
        self.assertFalse(saved["human_original_likeness_verified"])
        self.assertFalse(saved["manual_playback_verified"])
        self.assertIn("不代表人工原设验收", self.dialog.status.text())
        self.dialog.set_character("Doro")
        with patch.object(character_interaction_coverage, "inspect_selected_role_interactions",
                          return_value={**result, "role": "Doro"}) as checker, \
             patch("DyberPet.assistant.ui.QFileDialog.getSaveFileName",
                   return_value=(str(file_path.with_suffix(".txt")), "Text")):
            self.dialog.interaction_export_button.click()
            self.assertEqual(checker.call_args.args[1], "Doro")
            self.assertFalse(file_path.with_suffix(".txt").exists())

    def test_exact_persona_changes_with_imported_role_identity(self):
        import json
        root = Path(self.tmp.name) / "personal_roles"
        root.mkdir()
        for folder, character in (("SourceKaveh", "genshin_kaveh"),
                                  ("SourceKirara", "genshin_kirara")):
            d = root / folder
            d.mkdir()
            (d / "PERSONAL_IMPORT.json").write_text(
                json.dumps({"selected_profile": character}), encoding="utf-8")
        self.dialog.role_root = root
        self.dialog._prefs["personas"].pop("SourceKaveh", None)
        self.dialog._prefs["personas"].pop("SourceKirara", None)
        self.dialog.set_character("SourceKaveh")
        self.assertEqual(self.dialog.persona.currentData(), "genshin_kaveh")
        self.dialog.set_character("SourceKirara")
        self.assertEqual(self.dialog.persona.currentData(), "genshin_kirara")
        self.assertLessEqual(self.dialog.persona.count(), 10)
        self.assertEqual(self.dialog.persona.findData("genshin_kaveh"), -1)
        self.dialog.set_character("UnmappedCharacter")
        self.assertEqual(self.dialog.persona.currentData(), "companion")
        self.assertEqual(self.dialog.persona.findData("genshin_kirara"), -1)

    def test_current_role_gap_button_reads_only_selected_role_and_zeroes_stale_actions(self):
        self.assertIn("互动缺口", self.dialog.interaction_audit_button.text())
        self.dialog.set_actions(["wave"])
        report = {
            "role": "咕嘎", "status": "imported_artist_claim_not_verified",
            "on_disk_action_names": ["wave"],
            "installed_action_categories": ["greet"],
            "currently_unlocked_categories": ["greet"],
            "missing_categories": ["sleep"],
            "art_likeness_qa_passed": False,
        }
        from tools import character_interaction_coverage  # ensure lazy-loaded module exists
        with patch.object(character_interaction_coverage, "inspect_selected_role_interactions",
                          return_value=report) as inspector, \
             patch.object(QMessageBox, "information") as message:
            self.dialog.interaction_audit_button.click()
            self.assertEqual(inspector.call_count, 1)
            self.assertEqual(inspector.call_args.args[1], "咕嘎")
            self.assertEqual(inspector.call_args.kwargs["unlocked_actions"], {"wave"})
            self.assertIsInstance(inspector.call_args.kwargs["runtime_group_plan"], list)
            self.assertIn("打招呼", message.call_args.args[2])
            self.assertIn("未人工核验", message.call_args.args[2])
            self.dialog.set_character("Doro")
            self.dialog.interaction_audit_button.click()
            self.assertEqual(inspector.call_args.args[1], "Doro")
            self.assertEqual(inspector.call_args.kwargs["unlocked_actions"], set())

    def test_preview_reuses_actual_local_role_frames_and_marks_demo_as_demo(self):
        root = Path(self.tmp.name) / "pet_roles"
        folder = root / "咕嘎"
        folder.mkdir(parents=True)
        self.dialog.role_root = root
        with patch("DyberPet.DyberSettings.mascot_preview_dialog.MascotActionPreview") as preview:
            self.dialog.action_preview_button.click()
            self.assertEqual(preview.call_count, 1)
            self.assertEqual(preview.call_args.args[0].resolve(), folder.resolve())
            self.assertFalse(preview.call_args.kwargs["original_demo"])
            preview.return_value.exec.assert_called_once()
            (folder / "BUILTIN_MASCOT_DEMO.json").write_text("{}", encoding="utf-8")
            self.dialog.action_preview_button.click()
            self.assertTrue(preview.call_args.kwargs["original_demo"])

    def test_real_group_commands_are_routed_to_petwidget_not_frame_names(self):
        from DyberPet.assistant.native_groups import runtime_group_interactions
        commands = []
        self.dialog.action_requested.connect(commands.append)
        params = {
            label: {"unlocked": True, "act_type": "random_act"}
            for label in ("打招呼", "左右散步", "蹦一蹦")}
        groups = [{"name": "打招呼", "act_list": ["wave"]},
                  {"name": "左右散步", "act_list": ["left_walk", "right_walk"]},
                  {"name": "蹦一蹦", "act_list": ["jump"]}]
        plan = runtime_group_interactions(params, groups,
                                          {"wave", "left_walk", "right_walk", "jump"})
        self.dialog.set_actions(list(params), verified_group_interactions=plan)
        self.assertTrue(self.dialog.interaction_button.isEnabled())
        self.dialog.interaction_button.click()
        self.assertEqual(commands, ["打招呼"])
        self.dialog.interaction_menu.setCurrentIndex(
            self.dialog.interaction_menu.findData("walk"))
        self.dialog.favorite_action_button.click()
        self.dialog.play_favorite_button.click()
        self.assertEqual(commands, ["打招呼", "左右散步"])
        plan = runtime_group_interactions(params, groups, {"wave", "jump"})
        self.dialog.set_actions(list(params), verified_group_interactions=plan)
        self.assertFalse(self.dialog.play_favorite_button.isEnabled())
        self.dialog.play_favorite_interaction()
        self.assertEqual(len(commands), 2)

    def test_character_specific_manual_actions_use_only_unlocked_animation(self):
        requests = []
        self.dialog.action_requested.connect(requests.append)
        self.dialog.set_actions(["wave", "jump", "idle", "lookaround"])
        self.assertTrue(self.dialog.interaction_button.isEnabled())
        self.assertEqual(self.dialog.interaction_menu.currentData(), "greet")
        self.dialog.interaction_button.click()
        self.assertEqual(requests, ["wave"])
        idx = self.dialog.interaction_menu.findData("talk")
        self.assertGreaterEqual(idx, 0)
        self.dialog.interaction_menu.setCurrentIndex(idx)
        self.assertFalse(self.dialog.interaction_button.isEnabled())
        self.dialog.play_manual_interaction()
        self.assertEqual(requests, ["wave"])
        self.dialog.set_character("Doro")
        self.assertFalse(self.dialog.interaction_button.isEnabled())
        self.dialog.play_manual_interaction()
        self.assertEqual(requests, ["wave"])
        self.dialog.set_actions(["左右散步", "打招呼"])
        self.assertTrue(self.dialog.interaction_button.isEnabled())
        self.dialog.interaction_menu.setCurrentIndex(
            self.dialog.interaction_menu.findData("walk"))
        self.dialog.interaction_button.click()
        self.assertEqual(requests, ["wave", "左右散步"])

    def test_favorite_real_interaction_never_borrows_a_previous_role_action(self):
        requests = []
        self.dialog.action_requested.connect(requests.append)
        self.assertFalse(self.dialog.play_favorite_button.isEnabled())
        self.dialog.set_actions(["wave", "jump"])
        self.dialog.favorite_action_button.click()
        self.assertEqual(self.dialog._prefs["interaction_favorites"]["咕嘎"], "greet")
        self.dialog.play_favorite_button.click()
        self.assertEqual(requests, ["wave"])
        self.dialog.set_actions(["jump"])
        self.assertFalse(self.dialog.play_favorite_button.isEnabled())
        self.dialog.play_favorite_interaction()
        self.assertEqual(requests, ["wave"])
        self.dialog.set_character("Doro")
        self.dialog.set_actions(["wave"])
        self.assertFalse(self.dialog.play_favorite_button.isEnabled())
        self.dialog.favorite_action_button.click()
        self.dialog.play_favorite_button.click()
        self.assertEqual(requests, ["wave", "wave"])
        self.dialog.set_character("咕嘎")
        self.assertFalse(self.dialog.play_favorite_button.isEnabled())
        self.dialog.set_actions(["wave"])
        self.dialog.play_favorite_button.click()
        self.assertEqual(requests, ["wave", "wave", "wave"])

    def test_random_real_interaction_uses_only_current_role_and_avoids_repeats(self):
        received = []
        self.dialog.action_requested.connect(received.append)
        self.assertFalse(self.dialog.random_action_button.isEnabled())
        self.dialog.set_actions(["wave", "jump", "idle"])
        self.assertTrue(self.dialog.random_action_button.isEnabled())
        self.dialog.random_action_button.click()
        self.dialog.random_action_button.click()
        self.assertEqual(set(received), {"wave", "jump"})
        self.assertNotEqual(received[0], received[1])
        self.dialog.set_character("Doro")
        self.assertFalse(self.dialog.random_action_button.isEnabled())
        self.dialog.play_random_interaction()
        self.assertEqual(len(received), 2)
        self.dialog.set_actions(["climb"])
        self.dialog.random_action_button.click()
        self.assertEqual(received[-1], "climb")
        self.assertEqual(self.dialog._last_random_action, "climb")

    def test_bubble_signals_and_stale_character_responses(self):
        replies, notices = [], []
        self.dialog.reply_ready.connect(replies.append)
        self.dialog.action_notice.connect(notices.append)
        self.dialog._message_reply(("咕嘎", "好耶，文件准备好了！"))
        self.assertEqual(replies, ["好耶，文件准备好了！"])
        self.dialog._notice("已创建文件")
        self.assertEqual(notices, ["已创建文件"])
        self.dialog.set_character("Doro")
        self.dialog._message_reply(("咕嘎", "old persona text"))
        self.assertEqual(len(replies), 1)
        self.assertNotIn("old persona text", self.dialog.chat_log.toPlainText())

    def test_speech_lifecycle_only_reports_selected_character(self):
        started, stopped = [], []
        self.dialog.speech_started.connect(
            lambda name, message: started.append((name, message)))
        self.dialog.speech_finished.connect(stopped.append)
        self.dialog._last_reply = "这个是测试回复"
        with patch.object(self.dialog, "_submit"):
            self.dialog.read_reply()
        self.assertEqual(started, [])  # signal waits for real local TTS engine
        self.dialog._on_voice_engine_ready("咕嘎", "这个是测试回复")
        self.assertEqual(started, [("咕嘎", "这个是测试回复")])
        self.assertEqual(self.dialog._speaking_session[0], "咕嘎")
        self.dialog._job_finished()
        self.assertEqual(stopped, ["咕嘎"])
        self.assertIsNone(self.dialog._speaking_session)
        self.dialog._last_reply = "旧角色语音"
        with patch.object(self.dialog, "_submit"):
            self.dialog.read_reply()
            self.dialog.set_character("Doro")
        self.assertEqual(stopped, ["咕嘎", "咕嘎"])
        self.assertIsNone(self.dialog._speaking_session)

    def test_speech_engine_failure_retains_text_bubble(self):
        visible = []
        self.dialog.reply_ready.connect(visible.append)
        self.dialog.bubble_enabled.setChecked(True)
        self.dialog._last_reply = "可以展示的回答"
        with patch.object(self.dialog, "_submit"):
            self.dialog.read_reply()
        self.assertEqual(visible, [])
        self.dialog._job_error("no sound engine")
        self.assertEqual(visible, ["可以展示的回答"])
        self.assertIsNone(self.dialog._speaking_session)

    def test_speech_failure_removes_visual_speaking_state(self):
        end_events = []
        self.dialog.speech_finished.connect(end_events.append)
        self.dialog._last_reply = "test"
        with patch.object(self.dialog, "_submit"):
            self.dialog.read_reply()
        self.dialog._job_error("local TTS unavailable")
        self.assertEqual(end_events, ["咕嘎"])
        self.assertIn("local TTS unavailable", self.dialog.status.text())

    def test_motion_toggle_is_user_controlled(self):
        updates = []
        self.dialog.motion_toggled.connect(updates.append)
        self.assertTrue(self.dialog.motion_enabled.isChecked())
        self.dialog.motion_enabled.setChecked(False)
        self.assertEqual(updates, [False])
        with patch("DyberPet.assistant.ui.save_preferences") as saved:
            self.dialog.save_preferences()
        self.assertIs(saved.call_args.args[0]["motion_enabled"], False)

    def test_save_preferences_without_transcript(self):
        self.dialog.message.setText("private chat")
        self.dialog.llm_model.setText("local-model")
        with patch("DyberPet.assistant.ui.save_preferences") as saved:
            self.dialog.save_preferences()
        sent = saved.call_args.args[0]
        self.assertEqual(sent["llm_model"], "local-model")
        self.assertEqual(sent["personas"]["咕嘎"], "guga")
        self.assertNotIn("private chat", str(sent))

    def test_user_authorized_folder_session_only_and_reset(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as staging:
            specific = Path(staging) / "MyPetNotes"
            specific.mkdir()
            with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                       return_value=str(specific)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.No):
                self.dialog.grant_session_folder()
            self.assertNotEqual(self.dialog.workspace.root, specific)
            with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                       return_value=str(specific)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Yes):
                self.dialog.grant_session_folder()
            self.assertEqual(self.dialog.workspace.root, specific.resolve())
            self.dialog.workspace.create("pet.txt", "local")
            self.dialog.reset_workspace()
            self.assertNotEqual(self.dialog.workspace.root, specific.resolve())
            self.assertEqual((specific / "pet.txt").read_text(), "local")

    def test_unlocked_animation_signal_and_dialog_close_revokes_grant(self):
        chosen = []
        self.dialog.action_requested.connect(chosen.append)
        self.dialog.set_actions(["游戏互动", "挥手", "挥手"])
        self.assertEqual(self.dialog.action_menu.count(), 3)
        self.dialog.action_menu.setCurrentIndex(
            self.dialog.action_menu.findData("挥手"))
        self.dialog._notice("已恢复文件")
        self.assertEqual(chosen, ["挥手"])
        self.dialog._ppl_snapshot = "private PPL snapshot"
        self.dialog._last_reply = "private reply"
        with tempfile.TemporaryDirectory(dir=Path.home()) as home_temp:
            specific = Path(home_temp) / "Files"
            specific.mkdir()
            with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                       return_value=str(specific)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Yes):
                self.dialog.grant_session_folder()
            self.assertEqual(self.dialog.workspace.root, specific.resolve())
            self.dialog.close()
            self.assertNotEqual(self.dialog.workspace.root, specific.resolve())
            self.assertEqual(self.dialog._last_reply, "")
            self.assertEqual(self.dialog._ppl_snapshot, "")

    def test_character_presets_and_role_scoped_audio_controls(self):
        self.dialog.set_character("Doro")
        self.assertEqual(self.dialog.persona.currentData(), "doro")
        self.assertFalse(self.dialog.guga_preview.isHidden())
        self.assertIn("Doro", self.dialog.guga_sample_label.text())
        self.dialog.set_character("派蒙")
        self.assertEqual(self.dialog.persona.currentData(), "paimon")
        self.assertFalse(self.dialog.guga_audit.isHidden())
        self.dialog.set_character("纳西妲")
        self.assertEqual(self.dialog.persona.currentData(), "nahida")
        self.dialog.set_character("阿丽莎")
        self.assertEqual(self.dialog.persona.currentData(), "arrisa")
        self.dialog.set_character("Kitty")
        self.assertEqual(self.dialog.persona.currentData(), "companion")
        self.assertTrue(self.dialog.guga_preview.isHidden())

    def test_other_character_sound_dialog_no_auto_permission(self):
        self.dialog.set_character("Doro")
        with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName",
                   return_value=("/tmp/doro.wav", "WAV")), patch(
                   "PySide6.QtWidgets.QInputDialog.getText",
                   side_effect=[("Demo Creator", True), ("https://example.com/clip", True)]), patch(
                   "PySide6.QtWidgets.QMessageBox.warning",
                   return_value=QMessageBox.StandardButton.No), patch(
                   "DyberPet.assistant.ui.register_character_audio") as register:
            self.dialog.select_character_sample()
        register.assert_not_called()

    def test_other_character_audit_reads_only_current_install(self):
        self.dialog.set_character("派蒙")
        with patch("DyberPet.assistant.ui.read_character_audio", return_value=None), patch(
                "DyberPet.assistant.ui.inspect_character_role", return_value={
                    "action_coverage": {"idle": {"available": True},
                                        "speak": {"available": False}},
                    "issues": ["Missing speaking animation"],
                    "runtime_motion_policy": {"kind": "hover"},
                }) as inspector, patch(
                "PySide6.QtWidgets.QMessageBox.information") as dialog:
            self.dialog.audit_character()
        inspector.assert_called_once_with(
            self.dialog.role_root / "派蒙", "派蒙", None)
        self.assertIn("未核实", dialog.call_args.args[2])

    def test_mini_paimon_audit_recognizes_native_follow_mode(self):
        import json
        with tempfile.TemporaryDirectory() as td:
            parent = Path(td) / "res"
            role = parent / "role"
            root = parent / "pet" / "Paimon"
            role.mkdir(parents=True)
            (root / "action").mkdir(parents=True)
            (root / "pet_conf.json").write_text(
                json.dumps({"width": 64, "height": 64, "default": "idle",
                            "follow_main_x": True, "follow_main_y": False}),
                encoding="utf-8")
            (root / "act_conf.json").write_text(
                json.dumps({"idle": {"images": "idle"}}), encoding="utf-8")
            self.dialog.role_root = role
            with patch("PySide6.QtWidgets.QMessageBox.information") as msg:
                self.dialog.audit_mini_paimon()
            self.assertIn("可用", msg.call_args.args[2])
            self.assertIn("尚未", msg.call_args.args[2])
            self.assertIn("Paimon", msg.call_args.args[2])
            # The existing two-axis follower owns vertical placement.
            (root / "pet_conf.json").write_text(
                json.dumps({"width": 64, "height": 64, "default": "idle",
                            "follow_main_x": True, "follow_main_y": True}),
                encoding="utf-8")
            with patch("PySide6.QtWidgets.QMessageBox.information") as msg:
                self.dialog.audit_mini_paimon()
            self.assertIn("不启用", msg.call_args.args[2])

    def test_missing_mini_paimon_is_not_misreported_as_main_role(self):
        with tempfile.TemporaryDirectory() as td:
            self.dialog.role_root = Path(td) / "res" / "role"
            self.dialog.audit_mini_paimon()
            self.assertIn("没有检测到派蒙迷你宠物", self.dialog.status.text())

    def test_guga_role_audit_reports_missing_or_manual_verification(self):
        role = self.dialog.role_root / self.dialog.character_name
        with patch("DyberPet.assistant.ui.inspect_guga_role", return_value={
            "action_coverage": {"idle": {"available": True},
                                "speak": {"available": False}},
            "issues": ["Missing speaking animation"],
        }) as engine, patch("DyberPet.assistant.ui.load_local_clip",
                             return_value=None), patch(
                             "PySide6.QtWidgets.QMessageBox.information") as alert:
            self.dialog.audit_guga()
        engine.assert_called_once_with(role, None)
        self.assertIn("尚未核实", alert.call_args.args[2])
        self.dialog.set_character("Doro")
        engine.reset_mock()
        with patch("DyberPet.assistant.ui.inspect_guga_role") as not_called:
            self.dialog.audit_guga()
            not_called.assert_not_called()

    def test_guga_sample_ui_does_not_claim_to_be_tts_or_licensed(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "synthetic.wav"
            with wave.open(str(clip), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(16000)
                stream.writeframes(bytes(6400))
            self.assertTrue(self.dialog._is_guga())
            with patch("PySide6.QtWidgets.QFileDialog.getOpenFileName",
                       return_value=(str(clip), "WAV")), patch(
                       "PySide6.QtWidgets.QInputDialog.getText",
                       side_effect=[("Synthetic Creator", True),
                                    ("https://example.com/fixture", True)]), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Yes), patch(
                       "DyberPet.assistant.ui.record_local_clip",
                       return_value={"creator": "Synthetic Creator"}) as register:
                self.dialog.select_guga_sample()
            self.assertEqual(register.call_count, 1)
            self.assertTrue(register.call_args.kwargs["acknowledged_local_rights"])
            self.assertIn("尚未认证", self.dialog.status.text())
            self.dialog.set_character("Doro")
            self.assertFalse(self.dialog._is_guga())
            self.assertFalse(self.dialog.guga_preview.isHidden())

    def test_create_requires_confirmation(self):
        with patch("PySide6.QtWidgets.QInputDialog.getText",
                   return_value=("note.txt", True)), patch(
                       "PySide6.QtWidgets.QInputDialog.getMultiLineText",
                       return_value=("hello", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.question",
                       return_value=QMessageBox.StandardButton.No):
            self.dialog.create_file()
        self.assertEqual(self.dialog.workspace.list_files(), [])
        with patch("PySide6.QtWidgets.QInputDialog.getText",
                   return_value=("note.txt", True)), patch(
                       "PySide6.QtWidgets.QInputDialog.getMultiLineText",
                       return_value=("hello", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.question",
                       return_value=QMessageBox.StandardButton.Yes):
            self.dialog.create_file()
        self.assertEqual(self.dialog.workspace.list_files(), ["note.txt"])

    def test_delete_requires_confirmation_and_supports_restore(self):
        self.dialog.workspace.create("pet.md", "hello")
        with patch("PySide6.QtWidgets.QInputDialog.getItem",
                   return_value=("pet.md", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.No):
            self.dialog.delete_file()
        self.assertEqual(self.dialog.workspace.list_files(), ["pet.md"])
        with patch("PySide6.QtWidgets.QInputDialog.getItem",
                   return_value=("pet.md", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Yes):
            self.dialog.delete_file()
        self.assertEqual(self.dialog.workspace.list_files(), [])
        record = self.dialog.workspace.deleted_files()[0]
        with patch("PySide6.QtWidgets.QInputDialog.getItem",
                   return_value=(record, True)):
            self.dialog.restore_file()
        self.assertEqual(self.dialog.workspace.list_files(), ["pet.md"])


if __name__ == "__main__":
    unittest.main()
