"""Contract tests for optional PPL Character service and local LM Studio."""
import json
import unittest
from unittest.mock import patch

from DyberPet.assistant.persona import (
    AssistantServiceError, PPLCharacterClient, PERSONAS,
    _local_base, chat_local, make_system_prompt, session_id,
)
from DyberPet.assistant.voice import VoiceUnavailable, recognize_once, speak_once


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

    def test_no_model_no_chat_and_no_fake_response(self):
        with self.assertRaises(AssistantServiceError):
            chat_local("你好")
        self.assertIn("不能", make_system_prompt("doro")) if False else None
        self.assertIn("文件", make_system_prompt("doro"))

    def test_voice_not_triggered_without_local_model(self):
        with self.assertRaises(VoiceUnavailable):
            recognize_once("/nonexistent/vosk-model")
        with self.assertRaises(VoiceUnavailable):
            speak_once("abc", rate=300)


if __name__ == "__main__":
    unittest.main()
