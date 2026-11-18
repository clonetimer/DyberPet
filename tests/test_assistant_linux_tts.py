"""Linux eSpeak NG process playback contracts; no physical audio is required."""
import subprocess
import threading
import unittest
from unittest.mock import patch

from DyberPet.assistant.speech import speak_interruptible
from DyberPet.assistant.voice_errors import VoiceUnavailable


class _Input:
    def __init__(self):
        self.payload = bytearray()
        self.closed = False

    def write(self, value):
        self.payload.extend(value)
        return len(value)

    def close(self):
        self.closed = True

    def getvalue(self):
        return bytes(self.payload)


class _Process:
    def __init__(self, *, stop_event=None, return_code=0, stop_on_wait=False):
        self.stdin = _Input()
        self.return_code = return_code
        self.stop_event = stop_event
        self.stop_on_wait = stop_on_wait
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self):
        return self.return_code

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.stop_on_wait and self.wait_calls == 1:
            if self.stop_event is not None:
                self.stop_event.set()
            raise subprocess.TimeoutExpired("espeak-ng", timeout)
        return self.return_code

    def terminate(self):
        self.terminated = True
        self.return_code = -15

    def kill(self):
        self.killed = True
        self.return_code = -9


class LinuxEspeakProcessTests(unittest.TestCase):
    def run_linux(self, text, stop_event, *, process_factory=None, **kwargs):
        processes = []
        calls = []

        def popen(args, **popen_kwargs):
            calls.append((args, popen_kwargs))
            process = (process_factory(stop_event) if process_factory else
                       _Process(stop_event=stop_event))
            processes.append(process)
            return process

        with patch("DyberPet.assistant.speech.sys.platform", "linux"), \
                patch("DyberPet.assistant.speech.shutil.which", return_value="/usr/bin/espeak-ng"), \
                patch("DyberPet.assistant.speech.subprocess.Popen", side_effect=popen):
            result = speak_interruptible(text, stop_event, **kwargs)
        return result, processes, calls

    def test_full_reply_uses_utf8_stdin_voice_rate_and_reports_all_chunks(self):
        progress, ready = [], []
        result, processes, calls = self.run_linux(
            "甲" * 1200, threading.Event(), voice_id="cmn", rate=155,
            on_ready=lambda: ready.append("ready"),
            on_progress=lambda current, total: progress.append((current, total)))
        self.assertTrue(result)
        self.assertEqual(len(processes), 3)
        self.assertEqual([p.stdin.getvalue().decode("utf-8") for p in processes],
                         ["甲" * 500, "甲" * 500, "甲" * 200])
        self.assertTrue(all(p.stdin.closed for p in processes))
        self.assertEqual(ready, ["ready"])
        self.assertEqual(progress, [(1, 3), (2, 3), (3, 3)])
        for args, options in calls:
            self.assertEqual(args, ["/usr/bin/espeak-ng", "-s", "155",
                                    "-v", "cmn", "--stdin"])
            self.assertIs(options["stdout"], subprocess.DEVNULL)
            self.assertIs(options["stderr"], subprocess.DEVNULL)
            self.assertIs(options["stdin"], subprocess.PIPE)

    def test_stop_terminates_current_process_and_does_not_start_next_chunk(self):
        stop = threading.Event()
        result, processes, calls = self.run_linux(
            "甲" * 1200, stop,
            process_factory=lambda event: _Process(
                stop_event=event, return_code=None, stop_on_wait=True))
        self.assertFalse(result)
        self.assertEqual(len(processes), 1)
        self.assertTrue(processes[0].terminated)
        self.assertEqual(len(calls), 1)

    def test_nonzero_exit_is_not_reported_as_success(self):
        with patch("DyberPet.assistant.speech.sys.platform", "linux"), \
                patch("DyberPet.assistant.speech.shutil.which", return_value="/usr/bin/espeak-ng"), \
                patch("DyberPet.assistant.speech.subprocess.Popen",
                      return_value=_Process(return_code=2)):
            with self.assertRaisesRegex(VoiceUnavailable, "exit 2"):
                speak_interruptible("你好", threading.Event())

    def test_missing_executable_has_actionable_linux_guidance(self):
        with patch("DyberPet.assistant.speech.sys.platform", "linux"), \
                patch("DyberPet.assistant.speech.shutil.which", return_value=None):
            with self.assertRaisesRegex(VoiceUnavailable, "apt install espeak-ng"):
                speak_interruptible("你好", threading.Event())

    def test_stop_before_start_does_not_spawn_a_child(self):
        stop = threading.Event()
        stop.set()
        with patch("DyberPet.assistant.speech.sys.platform", "linux"), \
                patch("DyberPet.assistant.speech.shutil.which", return_value="/usr/bin/espeak-ng"), \
                patch("DyberPet.assistant.speech.subprocess.Popen") as popen:
            self.assertFalse(speak_interruptible("你好", stop))
        popen.assert_not_called()

    def test_invalid_voice_id_is_rejected_without_process_start(self):
        with patch("DyberPet.assistant.speech.sys.platform", "linux"), \
                patch("DyberPet.assistant.speech.shutil.which", return_value="/usr/bin/espeak-ng"), \
                patch("DyberPet.assistant.speech.subprocess.Popen") as popen:
            with self.assertRaisesRegex(VoiceUnavailable, "Invalid Linux system voice ID"):
                speak_interruptible("你好", threading.Event(), voice_id="-help")
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
