"""Native gait dispatch and TTS speech-start visual synchronization contracts."""
import ast
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from DyberPet.assistant.character_motion import is_authored_gait_frame
from DyberPet.assistant.speech_sync import available_talk_action
from DyberPet.assistant.native_groups import load_runtime_group_snapshot


class TalkActionSelectionTests(unittest.TestCase):
    def test_only_real_unlocked_talk_action_selected(self):
        self.assertEqual(available_talk_action({
            "wave": {"unlocked": True, "act_type": "random_act"},
            "说话动作": {"unlocked": True, "act_type": "random_act"},
        }), "说话动作")
        self.assertEqual(available_talk_action({
            "talk_loop": {"unlocked": True, "act_type": "customized"}}), "talk_loop")
        self.assertIsNone(available_talk_action({
            "talk_loop": {"unlocked": True, "act_type": "customized"}},
            playable_groups={"another_group"}))
        self.assertEqual(available_talk_action({
            "talk": {"unlocked": True, "act_type": "random_act"}},
            playable_groups={"talk"}), "talk")

    def test_no_action_fabricated_from_wrong_names_or_locked_actions(self):
        self.assertIsNone(available_talk_action({
            "talk": {"unlocked": False, "act_type": "random_act"},
            "talking-cow": {"unlocked": True, "act_type": "random_act"},
            "speaking": {"unlocked": True, "act_type": "removed"},
            "hello": {"unlocked": True, "act_type": "random_act"}}))
        self.assertIsNone(available_talk_action({}))


def method_from_source(filename, class_name, method, global_vars):
    src = Path(__file__).resolve().parents[1] / "DyberPet" / filename
    tree = ast.parse(src.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == class_name)
    func = next(n for n in cls.body
                if isinstance(n, ast.FunctionDef) and n.name == method)
    namespace = dict(global_vars)
    exec(compile(ast.Module(body=[func], type_ignores=[]), str(src), "exec"),
         namespace)
    return namespace[method]


class Emitter:
    def __init__(self):
        self.items = []

    def emit(self, *args):
        self.items.append(args)


class NativeGaitSignalTests(unittest.TestCase):
    def test_actual_worker_moves_only_native_gait_to_paced_channel(self):
        impl = method_from_source("modules.py", "Animation_worker", "_move", {
            "QAction": object,
            "is_authored_gait_frame": is_authored_gait_frame,
        })
        frames = [object() for _ in range(4)]
        native = types.SimpleNamespace(
            images=frames, direction="right", frame_move=5)
        worker = types.SimpleNamespace(
            pet_conf=types.SimpleNamespace(right=native, left=None),
            sig_move_anim=Emitter(), sig_move_native_gait=Emitter())
        impl(worker, native)
        self.assertEqual(worker.sig_move_native_gait.items, [(5, 0.0)])
        self.assertEqual(worker.sig_move_anim.items, [])
        other = types.SimpleNamespace(
            images=frames, direction="right", frame_move=7)
        impl(worker, other)
        self.assertEqual(worker.sig_move_anim.items, [(7, 0.0)])
        native.images = [frames[0]] * 4
        impl(worker, native)
        self.assertEqual(worker.sig_move_anim.items[-1], (5, 0.0))
        self.assertEqual(len(worker.sig_move_native_gait.items), 1)


class ActualPetDispatchGateTests(unittest.TestCase):
    def test_live_group_dispatch_rechecks_current_persona_and_loaded_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            roles = root / "res" / "role"
            for role, action in (("GugaArt", "wave"), ("DoroArt", "jump")):
                folder = roles / role
                folder.mkdir(parents=True)
                (folder / "pet_conf.json").write_text(json.dumps({
                    "random_act": [{"name": "打招呼", "act_list": [action]},
                                   {"name": "自定义游戏", "act_list": [action]}]}),
                    encoding="utf-8")
            options = {
                role: {"打招呼": {"unlocked": True, "act_type": "random_act"},
                       "自定义游戏": {"unlocked": True, "act_type": "random_act"},
                       "其他附件": {"unlocked": True, "act_type": "accessory_act"}}
                for role in ("GugaArt", "DoroArt")
            }
            settings = types.SimpleNamespace(
                act_data=types.SimpleNamespace(allAct_params=options))
            method = method_from_source(
                "DyberPet.py", "PetWidget", "_assistant_play_action",
                {"settings": settings, "Path": Path, "basedir": td,
                 "load_runtime_group_snapshot": load_runtime_group_snapshot})
            played = []
            pet = types.SimpleNamespace(
                curr_pet_name="GugaArt",
                pet_conf=types.SimpleNamespace(act_dict={"wave": object()}),
                _show_act=played.append)
            method(pet, "打招呼")
            method(pet, "自定义游戏")
            method(pet, "其他附件")  # unlocked, but NOT an executable actlist
            method(pet, "wave")  # raw sprites cannot be dispatched as group
            self.assertEqual(played, ["打招呼", "自定义游戏"])
            settings.act_data.allAct_params["GugaArt"]["打招呼"]["unlocked"] = False
            method(pet, "打招呼")
            self.assertEqual(len(played), 2)
            pet.curr_pet_name = "DoroArt"
            pet.pet_conf.act_dict = {"jump": object()}
            method(pet, "打招呼")  # misleading title cannot execute Doro jump
            self.assertEqual(len(played), 2)
            method(pet, "自定义游戏")  # still a valid unlocked miscellaneous group
            self.assertEqual(played[-1], "自定义游戏")
            self.assertEqual(len(played), 3)
            pet.pet_conf.act_dict = {}  # archive replaced, native bytes absent
            method(pet, "自定义游戏")
            self.assertEqual(len(played), 3)
            pet.curr_pet_name = "GugaArt"
            pet.pet_conf.act_dict = {"wave": object()}
            (roles / "GugaArt" / "pet_conf.json").unlink()
            method(pet, "自定义游戏")  # removal between menu display and click
            self.assertEqual(len(played), 3)


class SavedPetInteractionShortcutTests(unittest.TestCase):
    def test_context_menu_replays_only_saved_and_current_native_group(self):
        from DyberPet.assistant.role_interactions import requested_action
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "res" / "role" / "OriginalCreator"
            d.mkdir(parents=True)
            (d / "pet_conf.json").write_text(json.dumps({
                "random_act": [{"name": "打招呼", "act_list": ["wave"]}]}),
                encoding="utf-8")
            state = {"OriginalCreator": {
                "打招呼": {"act_type": "random_act", "unlocked": True}}}
            prefs = {"interaction_favorites": {"OriginalCreator": "greet"}}
            method = method_from_source(
                "DyberPet.py", "PetWidget", "_assistant_play_saved_favorite",
                {"settings": types.SimpleNamespace(
                    act_data=types.SimpleNamespace(allAct_params=state)),
                 "load_assistant_preferences": lambda: prefs,
                 "load_runtime_group_snapshot": load_runtime_group_snapshot,
                 "requested_action": requested_action,
                 "Path": Path, "basedir": td})
            pet = types.SimpleNamespace(
                curr_pet_name="OriginalCreator",
                pet_conf=types.SimpleNamespace(act_dict={"wave": object()}),
                _assistant_play_action=MagicMock(),
                _assistant_notice_bubble=MagicMock())
            method(pet)
            pet._assistant_play_action.assert_called_once_with("打招呼")
            pet._assistant_play_action.reset_mock()
            state["OriginalCreator"]["打招呼"]["unlocked"] = False
            method(pet)
            pet._assistant_play_action.assert_not_called()
            pet._assistant_notice_bubble.assert_called()
            state["OriginalCreator"]["打招呼"]["unlocked"] = True
            pet.pet_conf.act_dict.clear()
            method(pet)
            pet._assistant_play_action.assert_not_called()
            pet.curr_pet_name = "UnrelatedRole"
            method(pet)
            pet._assistant_play_action.assert_not_called()

    def test_saved_interaction_shortcut_is_reachable_from_real_context_menu(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet" / "DyberPet.py").read_text(encoding="utf-8")
        self.assertIn("self.tr('播放本角色已保存的互动')", source)
        self.assertIn("triggered=self._assistant_play_saved_favorite", source)

class ActualPetSpeechBridgeTests(unittest.TestCase):
    def test_tts_start_matches_character_and_real_unlocked_action(self):
        start = method_from_source(
            "DyberPet.py", "PetWidget", "_assistant_speech_started",
            {"available_talk_action": available_talk_action,
             "load_runtime_group_snapshot": lambda *args: ({"talk"}, []),
             "Path": Path, "basedir": "/unused"})
        end = method_from_source(
            "DyberPet.py", "PetWidget", "_assistant_speech_finished", {})
        class State:
            pass
        settings = State()
        settings.act_data = types.SimpleNamespace(allAct_params={
            "Doro": {"wave": {"unlocked": True, "act_type": "random_act"},
                     "talk": {"unlocked": True, "act_type": "random_act"}}})
        # Update function globals, exactly as a real PetWidget module does.
        start.__globals__["settings"] = settings
        pet = types.SimpleNamespace(
            curr_pet_name="Doro",
            pet_conf=types.SimpleNamespace(act_dict={"talk": object()}),
            _assistant_reply_bubble=MagicMock(),
            _assistant_play_action=MagicMock())
        start(pet, "派蒙", "not this pet")
        pet._assistant_reply_bubble.assert_not_called()
        start(pet, "Doro", "你好")
        pet._assistant_reply_bubble.assert_called_once_with("你好")
        pet._assistant_play_action.assert_called_once_with("talk")
        self.assertTrue(pet._assistant_voice_active)
        end(pet, "Doro")
        self.assertFalse(pet._assistant_voice_active)

    def test_voice_must_not_dispatch_customized_or_accessory_talk_without_actlist(self):
        source = method_from_source(
            "DyberPet.py", "PetWidget", "_assistant_speech_started",
            {"available_talk_action": available_talk_action,
             "load_runtime_group_snapshot": lambda *args: (frozenset(), []),
             "Path": Path, "basedir": "/unused"})
        source.__globals__["settings"] = types.SimpleNamespace(
            act_data=types.SimpleNamespace(allAct_params={
                "Doro": {"talk": {"unlocked": True, "act_type": "accessory_act"},
                         "talk_loop": {"unlocked": True, "act_type": "customized"}}}))
        pet = types.SimpleNamespace(
            curr_pet_name="Doro", pet_conf=types.SimpleNamespace(
                act_dict={"talk": object()}),
            _assistant_reply_bubble=MagicMock(), _assistant_play_action=MagicMock())
        source(pet, "Doro", "测试语音")
        pet._assistant_reply_bubble.assert_called_once_with("测试语音")
        pet._assistant_play_action.assert_not_called()

    def test_tts_without_speaking_sprite_does_not_invent_one(self):
        impl = method_from_source(
            "DyberPet.py", "PetWidget", "_assistant_speech_started",
            {"available_talk_action": available_talk_action,
             "load_runtime_group_snapshot": lambda *args: (frozenset(), []),
             "Path": Path, "basedir": "/unused"})
        impl.__globals__["settings"] = types.SimpleNamespace(
            act_data=types.SimpleNamespace(allAct_params={
                "派蒙": {"jump": {"unlocked": True, "act_type": "random_act"}}}))
        pet = types.SimpleNamespace(
            curr_pet_name="派蒙",
            pet_conf=types.SimpleNamespace(act_dict={"jump": object()}),
            _assistant_reply_bubble=MagicMock(),
            _assistant_play_action=MagicMock())
        impl(pet, "派蒙", "短回复")
        pet._assistant_reply_bubble.assert_called_once()
        pet._assistant_play_action.assert_not_called()


if __name__ == "__main__":
    unittest.main()
