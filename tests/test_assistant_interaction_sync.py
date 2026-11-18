"""Voice phases must use silent, installed actions without taking user control.

These tests execute the real PetWidget bridge and Interaction_worker methods.
Only Qt signals, widgets, and image objects are replaced at their boundaries;
selection, dispatch, native animation state, and completion remain production
code. The tiny frames below are fixtures, not third-party artwork.
"""
import ast
import importlib
import math
from pathlib import Path
import random
import sys
import types
import unittest
from functools import lru_cache
from unittest.mock import patch

from DyberPet.assistant.speech_sync import available_talk_action


@lru_cache(maxsize=None)
def _source_class(filename, class_name):
    source = Path(__file__).resolve().parents[1] / "DyberPet" / filename
    tree = ast.parse(source.read_text(encoding="utf-8"))
    return source, next(node for node in tree.body
                        if isinstance(node, ast.ClassDef)
                        and node.name == class_name)


def _method(filename, class_name, method_name, namespace):
    source, cls = _source_class(filename, class_name)
    method = next((node for node in cls.body
                   if isinstance(node, ast.FunctionDef)
                   and node.name == method_name), None)
    if method is None:
        raise AssertionError(f"{class_name}.{method_name} is not implemented")
    globals_ = dict(namespace)
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), "exec"),
         globals_)
    return globals_[method_name]


class _Signal:
    def __init__(self):
        self.items = []
        self.slots = []

    def connect(self, slot):
        self.slots.append(slot)

    def emit(self, *args):
        self.items.append(args)
        for slot in self.slots:
            slot(*args)


def _action(name):
    return types.SimpleNamespace(
        images=[name + "-0", name + "-1"], frame_refresh=0.02, act_num=1,
        direction=None, frame_move=0, anchor=[0, 0])


class _NativePet:
    """Use the real native dispatch without importing the desktop entry point."""

    def __init__(self, sync):
        options = {
            name: {"act_type": "random_act", "unlocked": True,
                   "special_act": False, "in_playlist": True,
                   "act_prob": 1.0, "status_type": [0, 0]}
            for name in ("listen_loop", "思考", "talk")
        }
        self.conf = types.SimpleNamespace(
            petname="Doro", act_name=["listen_loop", "思考", "talk"],
            act_sound=[[], [], []], act_type=[[0, 0], [0, 0], [0, 0]],
            random_act=[[_action("listen")], [_action("think")], [_action("talk")]],
            acc_name=[], accessory_act={}, custom_act={}, interact_speed=20)
        self.settings = types.SimpleNamespace(
            petname="Doro", act_data=types.SimpleNamespace(
                allAct_params={"Doro": options}),
            pet_data=types.SimpleNamespace(hp_tier=3),
            draging=0, onfloor=1, focus_timer_on=False,
            defaultAct={"Doro": None}, bubble_on=True,
            playid=0, act_id=0, current_act=None, previous_act=None,
            current_img="idle", previous_img="idle", tunable_scale=1,
            current_anchor=[0, 0], previous_anchor=[0, 0])
        globals_ = {"settings": self.settings, "math": math,
                    "random": random, "QAction": object,
                    "available_interaction_action": sync.available_interaction_action,
                    "available_talk_action": available_talk_action}
        self.worker = types.SimpleNamespace(
            pet_conf=self.conf, interact=None, act_name=None,
            interact_altered=False, is_paused=False, is_killed=False,
            first_acc=False, sig_setimg_inter=_Signal(),
            sig_move_inter=_Signal(), sig_interact_note=_Signal(),
            sig_act_finished=_Signal(), stop_trackMouse=_Signal(),
            hptier=[0, 50, 80, 100])
        for name in ("start_interact", "_get_animation_type", "run", "animat",
                     "img_from_act", "empty_interact", "stop_interact", "_move"):
            function = _method("modules.py", "Interaction_worker", name, globals_)
            setattr(self.worker, name, types.MethodType(function, self.worker))
        self.animation = types.SimpleNamespace(is_paused=False, is_killed=False)
        for name in ("pause", "resume"):
            function = _method("modules.py", "Animation_worker", name, globals_)
            setattr(self.animation, name, types.MethodType(function, self.animation))
        self.worker.sig_act_finished.connect(self.animation.resume)
        self.frames = []
        self.worker.sig_setimg_inter.connect(
            lambda: self.frames.append(self.settings.current_img))
        self.bubbles = []
        self.pet = types.SimpleNamespace(
            curr_pet_name="Doro", pet_conf=self.conf, is_follow_mouse=False,
            workers={"Interaction": self.worker, "Animation": self.animation},
            register_bubbleText=self.bubbles.append,
            _pet_assistant=types.SimpleNamespace(
                bubble_enabled=types.SimpleNamespace(isChecked=lambda: True)))
        for name in ("_assistant_interaction_changed", "_assistant_play_action",
                     "_show_act", "_assistant_notice_bubble",
                     "_assistant_reply_bubble", "_assistant_speech_started",
                     "_assistant_speech_finished"):
            function = _method("DyberPet.py", "PetWidget", name, globals_)
            setattr(self.pet, name, types.MethodType(function, self.pet))

    def phase(self, phase, character="Doro"):
        self.pet._assistant_interaction_changed(character, phase)

    def finish_animation(self):
        for _ in range(20):
            if self.worker.interact is None:
                return
            self.worker.run()
        raise AssertionError("Native test action did not complete")


class ActualPetInteractionTests(unittest.TestCase):
    def setUp(self):
        try:
            sync = importlib.import_module("DyberPet.assistant.interaction_sync")
        except ModuleNotFoundError as exc:
            if exc.name != "DyberPet.assistant.interaction_sync":
                raise
            self.fail("Silent native assistant interaction feedback is not implemented")
        self.native = _NativePet(sync)

    def assert_fallback(self, native):
        self.assertIsNone(native.worker.interact)
        self.assertFalse(native.animation.is_paused)
        self.assertEqual(native.settings.current_img, "idle")
        self.assertEqual(native.worker.sig_interact_note.items, [])
        self.assertEqual(len(native.bubbles), 1)

    def test_listening_plays_loaded_silent_frames_once(self):
        n = self.native
        n.phase("listening")
        self.assertEqual((n.worker.interact, n.worker.act_name),
                         ("animat", "listen_loop"))
        self.assertTrue(n.animation.is_paused)
        n.finish_animation()
        self.assertEqual(n.frames, ["listen-0"])
        self.assertFalse(n.animation.is_paused)
        self.assertEqual(n.worker.sig_interact_note.items, [])
        self.assertEqual(n.bubbles, [])
        n.phase("listening")
        self.assertIsNone(n.worker.interact)
        self.assertEqual(n.worker.sig_act_finished.items, [()])

    def test_next_phase_and_next_turn_use_their_own_native_clip(self):
        n = self.native
        for phase in ("listening", "thinking", "listening"):
            n.phase(phase)
            n.finish_animation()
        self.assertEqual(n.frames, ["listen-0", "think-0", "listen-0"])
        self.assertEqual(n.worker.sig_interact_note.items, [])

    def test_loaded_sound_list_overrules_empty_metadata_sound(self):
        n = self.native
        n.settings.act_data.allAct_params["Doro"]["listen_loop"]["sound"] = []
        n.conf.act_sound[0] = ["greeting_voice"]
        n.phase("listening")
        self.assert_fallback(n)

    def test_missing_or_ambiguous_loaded_sound_is_not_assumed_silent(self):
        for sounds in (None, [], [None], [""], [{}], [False]):
            with self.subTest(sounds=sounds):
                self.setUp()
                n = self.native
                n.conf.act_sound = sounds
                n.phase("listening")
                self.assert_fallback(n)

    def test_locked_unloaded_unrenderable_or_unsupported_action_falls_back(self):
        def locked(n):
            n.settings.act_data.allAct_params["Doro"]["listen_loop"]["unlocked"] = False

        def stale(n):
            n.conf.act_name[0] = "removed"

        def empty_frames(n):
            n.conf.random_act[0][0].images = []

        def not_a_listening_action(n):
            n.settings.act_data.allAct_params["Doro"] = {
                "talk": n.settings.act_data.allAct_params["Doro"]["talk"]}

        def unsupported(n):
            n.settings.act_data.allAct_params["Doro"]["listen_loop"]["act_type"] = "removed"

        for mutate in (locked, stale, empty_frames, not_a_listening_action, unsupported):
            with self.subTest(case=mutate.__name__):
                self.setUp()
                n = self.native
                mutate(n)
                n.phase("listening")
                self.assert_fallback(n)

    def test_insufficient_satiety_does_not_enter_native_error_notification_path(self):
        n = self.native
        n.settings.pet_data.hp_tier = 1
        n.conf.act_type[0] = [2, 0]
        n.phase("listening")
        self.assert_fallback(n)

    def test_invalid_native_frames_or_timing_cannot_pause_the_pet(self):
        for attribute, value in (
                ("images", [None]),
                ("images", [types.SimpleNamespace(isNull=lambda: True)]),
                ("frame_refresh", 0), ("frame_refresh", float("nan")),
                ("act_num", 0), ("act_num", 1.5)):
            with self.subTest(attribute=attribute, value=value):
                self.setUp()
                n = self.native
                setattr(n.conf.random_act[0][0], attribute, value)
                n.phase("listening")
                self.assert_fallback(n)

    def test_active_user_interactions_are_preserved_including_after_idle(self):
        for interact, action in (("mousedrag", None), ("followTarget", "mouse"),
                                 ("animat", "user_selected"), ("patpat", None),
                                 ("customized", "user_selected"),
                                 ("native_action", "wave"), ("use_item", "berry")):
            with self.subTest(interact=interact):
                self.setUp()
                n = self.native
                n.worker.interact, n.worker.act_name = interact, action
                n.phase("listening")
                n.phase("thinking")
                n.phase("idle")
                self.assertEqual((n.worker.interact, n.worker.act_name),
                                 (interact, action))
                self.assertFalse(n.animation.is_paused)
                self.assertEqual(n.worker.sig_act_finished.items, [])
                self.assertEqual(n.worker.stop_trackMouse.items, [])

    def test_drag_fall_follow_focus_and_selected_default_keep_animation(self):
        cases = ("drag", "fall", "follow", "focus", "default")
        for case in cases:
            with self.subTest(case=case):
                self.setUp()
                n = self.native
                if case == "drag":
                    n.settings.draging = 1
                elif case == "fall":
                    n.settings.onfloor = 0
                elif case == "follow":
                    n.pet.is_follow_mouse = True
                elif case == "focus":
                    n.settings.focus_timer_on = True
                else:
                    n.settings.defaultAct["Doro"] = "user_selected"
                n.phase("listening")
                self.assert_fallback(n)

    def test_paused_or_stopped_native_animation_is_not_restarted_by_feedback(self):
        for attribute in ("is_paused", "is_killed"):
            with self.subTest(attribute=attribute):
                self.setUp()
                n = self.native
                setattr(n.animation, attribute, True)
                n.phase("listening")
                self.assertIsNone(n.worker.interact)
                self.assertTrue(getattr(n.animation, attribute))
                self.assertEqual(n.worker.sig_act_finished.items, [])
                self.assertEqual(len(n.bubbles), 1)

    def test_wrong_character_and_unknown_phase_cannot_override_current_state(self):
        n = self.native
        n.phase("idle")
        state = n.pet._assistant_interaction_state
        n.phase("listening", "派蒙")
        n.phase("ready")
        self.assertEqual(n.pet._assistant_interaction_state, state)
        self.assertIsNone(n.worker.interact)
        self.assertEqual(n.bubbles, [])

    def test_state_bubble_is_once_per_entry_and_respects_both_preferences(self):
        for global_on, dialog_on in ((True, True), (False, True), (True, False)):
            with self.subTest(global_on=global_on, dialog_on=dialog_on):
                self.setUp()
                n = self.native
                n.conf.act_sound[0] = ["audible"]
                n.settings.bubble_on = global_on
                n.pet._pet_assistant.bubble_enabled.isChecked = lambda: dialog_on
                n.phase("listening")
                n.phase("listening")
                self.assertEqual(len(n.bubbles), int(global_on and dialog_on))
                n.phase("idle")
                n.phase("listening")
                self.assertEqual(len(n.bubbles), 2 * int(global_on and dialog_on))
                self.assertIsNone(n.worker.interact)

    def test_speaking_and_stopping_leave_existing_speech_path_sole_owner(self):
        n = self.native
        n.phase("speaking")
        self.assertIsNone(n.worker.interact)
        self.assertEqual(n.bubbles, [])
        n.pet._assistant_speech_started("Doro", "你好")
        n.phase("speaking")
        self.assertEqual(n.worker.act_name, "talk")
        self.assertTrue(n.pet._assistant_voice_active)
        n.phase("stopping")
        n.phase("idle")
        self.assertTrue(n.pet._assistant_voice_active)
        self.assertEqual(n.worker.act_name, "talk")
        n.pet._assistant_speech_finished("Doro")
        self.assertFalse(n.pet._assistant_voice_active)
        n.finish_animation()
        self.assertEqual(n.frames, ["talk-0"])
        self.assertEqual(n.bubbles, [{"message": "你好", "timeout": 6}])

    def test_idle_releases_phase_without_stopping_native_feedback_animation(self):
        n = self.native
        n.phase("listening")
        n.phase("idle")
        self.assertEqual(n.pet._assistant_interaction_state, ("Doro", "idle"))
        self.assertEqual(n.worker.act_name, "listen_loop")
        self.assertEqual(n.worker.sig_act_finished.items, [])
        n.finish_animation()
        self.assertFalse(n.animation.is_paused)

    def test_stale_worker_or_role_context_cannot_dispatch_action(self):
        for case in ("worker", "role", "config", "missing_worker"):
            with self.subTest(case=case):
                self.setUp()
                n = self.native
                if case == "worker":
                    n.worker.pet_conf = types.SimpleNamespace(petname="派蒙")
                elif case == "role":
                    n.settings.petname = "派蒙"
                elif case == "config":
                    n.conf.petname = "派蒙"
                else:
                    n.pet.workers.pop("Interaction")
                n.phase("listening")
                self.assert_fallback(n)

    def test_existing_assistant_window_connects_phase_to_real_native_dispatch(self):
        n = self.native

        class Dialog:
            def __init__(self, *_args, **_kwargs):
                for name in ("reply_ready", "action_notice", "action_requested",
                             "motion_toggled", "speech_started", "speech_finished",
                             "interaction_changed"):
                    setattr(self, name, _Signal())
                self.motion_enabled = types.SimpleNamespace(isChecked=lambda: True)
                self.bubble_enabled = types.SimpleNamespace(isChecked=lambda: True)

            def show(self):
                pass

            raise_ = activateWindow = show

        ui = types.ModuleType("DyberPet.assistant.ui")
        ui.PetAssistantDialog = Dialog
        n.pet._pet_assistant = None
        n.pet._sync_assistant_actions = lambda: None
        n.pet._set_character_motion_enabled = lambda _enabled: None
        show = _method("DyberPet.py", "PetWidget", "_show_pet_assistant",
                       {"basedir": "/native-test"})
        with patch.dict(sys.modules, {"DyberPet.assistant.ui": ui}):
            show(n.pet)
        n.pet._pet_assistant.interaction_changed.emit("Doro", "listening")
        n.finish_animation()
        self.assertEqual(n.frames, ["listen-0"])
        self.assertEqual(n.worker.sig_interact_note.items, [])


if __name__ == "__main__":
    unittest.main()
