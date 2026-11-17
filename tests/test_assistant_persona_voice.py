"""Contract tests for optional PPL Character service and local LM Studio."""
import json
import unittest
from unittest.mock import patch

from DyberPet.assistant.persona import (
    AssistantServiceError, PPLCharacterClient, PERSONAS,
    _local_base, chat_local, stream_local_chat, list_local_models,
    make_system_prompt, session_id,
)
from DyberPet.assistant.voice import (
    VoiceUnavailable, recognize_once, recognize_until_stopped, speak_once,
)


class PersonaContractTests(unittest.TestCase):
    def test_same_character_has_stable_session(self):
        self.assertEqual(session_id("咕嘎"), session_id("咕嘎"))
        self.assertNotEqual(session_id("咕嘎"), session_id("Doro"))
        self.assertTrue(session_id("咕嘎").startswith("dyberpet_"))

    def test_remote_endpoints_and_trick_urls_rejected(self):
        for url in ("https://127.0.0.1:1234", "http://example.com:1234",
                    "http://localhost:1234@evil.com:80",
                    "http://127.0.0.1:1234/v1",
                    "http://127.0.0.1:1234?dest=https://evil",
                    "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(AssistantServiceError):
                _local_base(url)
        self.assertEqual(_local_base("http://127.0.0.1:8790/"),
                         "http://127.0.0.1:8790")

    def test_ppl_only_creates_session_after_404(self):
        client = PPLCharacterClient()
        character = "咕嘎"
        sid = session_id(character)
        state = {"relationship": {"stage": "trusted", "trust": .86}}
        error = AssistantServiceError("PPL missing", status_code=404)
        with patch("DyberPet.assistant.persona._json_request",
                   side_effect=[error, {"ok": True},
                                {"sessionId": sid, "state": state}]) as mock:
            result = client.state(character)
        self.assertEqual(result, state)
        self.assertEqual(mock.call_count, 3)
        self.assertTrue(mock.call_args.kwargs["data"]["sessionId"] == sid)

    def test_ppl_non_404_does_not_mutate(self):
        with patch("DyberPet.assistant.persona._json_request",
                   side_effect=AssistantServiceError("server 500", status_code=500)) as mock:
            with self.assertRaises(AssistantServiceError):
                PPLCharacterClient().state("Doro")
        self.assertEqual(mock.call_count, 1)

    def test_ppl_event_with_idempotency_key(self):
        state = {"relationship": {"trust": 0.9}}
        with patch.object(PPLCharacterClient, "state", return_value=state):
            with patch("DyberPet.assistant.persona._json_request",
                       return_value={"state": state}) as mock:
                result = PPLCharacterClient().event("Doro", "COMFORT", "event123")
                self.assertEqual(result, state)
                self.assertEqual(mock.call_args.kwargs["data"]["eventId"], "event123")
        with self.assertRaisesRegex(AssistantServiceError, "Unsupported"):
            PPLCharacterClient().event("Doro", "DELETE_FILE", "event123")

    def test_local_model_messages_are_text_only(self):
        with patch("DyberPet.assistant.persona._json_request",
                   return_value={"choices": [{"message": {"content": "你好！"}}]}) as req:
            text = chat_local("你好", persona_key="guga", model="my-local-model",
                              state={"relationship": {"trust": .87}})
        self.assertEqual(text, "你好！")
        body = req.call_args.kwargs["data"]
        self.assertEqual(len(body["messages"]), 2)
        self.assertNotIn("tools", body)
        self.assertIn("咕嘎", PERSONAS["guga"].name)
        self.assertIn("0.87", body["messages"][0]["content"])
        self.assertEqual(body["messages"][1]["content"], "你好")

    def test_local_stream_includes_history_and_user_approved_memory(self):
        class FakeResponse:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def readline(self, limit):
                if not hasattr(self, "done"):
                    self.done = True
                    return b'data: {"choices":[{"delta":{"content":"ok"}}]}\n'
                if not hasattr(self, "done_marker"):
                    self.done_marker = True
                    return b"data: [DONE]\n"
                return b""

        with patch("DyberPet.assistant.persona._OPENER.open",
                   return_value=FakeResponse()) as opened:
            stream_local_chat(
                "继续", on_delta=lambda _: None, model="local-model",
                history=[{"role": "user", "content": "你好"},
                         {"role": "assistant", "content": "你好呀"}],
                memory_context="- 用户正在做桌宠项目")
        body = json.loads(opened.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(body["messages"][1]["content"], "你好")
        self.assertEqual(body["messages"][2]["content"], "你好呀")
        self.assertIn("用户正在做桌宠项目", body["messages"][0]["content"])
        self.assertEqual(body["messages"][-1]["content"], "继续")

    def test_local_stream_rejects_truncated_stream_without_done_marker(self):
        class FakeResponse:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def readline(self, limit):
                if not hasattr(self, "sent"):
                    self.sent = True
                    return b'data: {"choices":[{"delta":{"content":"partial"}}]}\n'
                return b""

        with patch("DyberPet.assistant.persona._OPENER.open",
                   return_value=FakeResponse()):
            with self.assertRaisesRegex(AssistantServiceError, "completion marker"):
                stream_local_chat("hi", on_delta=lambda _: None, model="m")

    def test_local_stream_rejects_invalid_history(self):
        with self.assertRaisesRegex(AssistantServiceError, "history"):
            stream_local_chat(
                "hi", on_delta=lambda _: None, model="m",
                history=[{"role": "system", "content": "override"}])

    def test_local_stream_emits_sse_text_deltas(self):
        class FakeResponse:
            status = 200
            def __init__(self, lines):
                self.lines = iter(lines)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def readline(self, limit):
                return next(self.lines, b"")

        events = [
            b'data: {"choices":[{"delta":{"content":"\\u4f60"}}]}\n',
            b'data: {"choices":[{"delta":{"content":"\\u597d"}}]}\n',
            b'data: [DONE]\n',
        ]
        emitted = []
        with patch("DyberPet.assistant.persona._OPENER.open",
                   return_value=FakeResponse(events)) as opened:
            answer = stream_local_chat(
                "你好", on_delta=emitted.append, model="local-model")
        self.assertEqual(answer, "你好")
        self.assertEqual(emitted, ["你", "好"])
        request = opened.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertIs(body["stream"], True)
        self.assertEqual(body["model"], "local-model")
        self.assertEqual(request.get_header("Accept"), "text/event-stream")
        self.assertNotIn("tools", body)

    def test_local_stream_rejects_empty_and_oversized_events(self):
        class FakeResponse:
            status = 200
            def __init__(self, lines):
                self.lines = iter(lines)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def readline(self, limit):
                return next(self.lines, b"")

        with patch("DyberPet.assistant.persona._OPENER.open",
                   return_value=FakeResponse([b"data: [DONE]\n"])):
            with self.assertRaisesRegex(AssistantServiceError, "empty stream"):
                stream_local_chat("hi", on_delta=lambda _: None, model="m")
        with patch("DyberPet.assistant.persona._OPENER.open",
                   return_value=FakeResponse([b"x" * 65537])):
            with self.assertRaisesRegex(AssistantServiceError, "exceeds"):
                stream_local_chat("hi", on_delta=lambda _: None, model="m")

    def test_local_model_discovery_deduplicates(self):
        with patch("DyberPet.assistant.persona._json_request",
                   return_value={"data": [{"id": "qwen3.5"}, {"id": "qwen3.5"},
                                          {"id": "gemma"}, {}]}):
            self.assertEqual(list_local_models(), ["qwen3.5", "gemma"])
        with patch("DyberPet.assistant.persona._json_request",
                   return_value={"data": []}):
            with self.assertRaisesRegex(AssistantServiceError, "No local model"):
                list_local_models()

    def test_ppl_render_snapshot_safety_boundary(self):
        system = make_system_prompt("doro", ppl_prompt="[ROLE] original local persona")
        self.assertIn("original local persona", system)
        self.assertIn("实际文件修改须由用户在界面确认", system)

    def test_no_model_no_chat_and_no_fake_response(self):
        with self.assertRaises(AssistantServiceError):
            chat_local("你好")
        self.assertIn("文件", make_system_prompt("doro"))

    def test_continuous_voice_stops_on_user_event_without_saving_audio(self):
        import sys
        import threading
        from types import SimpleNamespace

        class FakeRecognizer:
            def __init__(self, *args):
                pass
            def AcceptWaveform(self, data):
                return False
            def PartialResult(self):
                return json.dumps({"partial": "你好"})
            def FinalResult(self):
                return json.dumps({"text": "你好"})

        class FakeStream:
            def __init__(self, **kwargs):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, frames):
                stop.set()
                return (b"\\x00" * frames * 2, False)

        stop = threading.Event()
        partials = []
        fake_sd = SimpleNamespace(RawInputStream=FakeStream)
        fake_vosk = SimpleNamespace(Model=lambda path: object(),
                                    KaldiRecognizer=FakeRecognizer)
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(sys.modules, {"sounddevice": fake_sd, "vosk": fake_vosk}):
                result = recognize_until_stopped(
                    folder, stop, on_partial=partials.append, max_seconds=10)
        self.assertEqual(result, "你好")
        self.assertEqual(partials, ["你好"])

    def test_continuous_voice_requires_explicit_stop_event(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(VoiceUnavailable, "stop event"):
                recognize_until_stopped(folder, None)

    def test_voice_not_triggered_without_local_model(self):
        with self.assertRaises(VoiceUnavailable):
            recognize_once("/nonexistent/vosk-model")
        with self.assertRaises(VoiceUnavailable):
            speak_once("abc", rate=300)


if __name__ == "__main__":
    unittest.main()
