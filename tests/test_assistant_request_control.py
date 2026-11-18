"""Cancellation contracts against a real loopback HTTP server, not a model."""
import json
import http.client
import os
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from DyberPet.assistant.persona import (
    AssistantServiceError, PPLCharacterClient, _json_request, session_id,
    stream_local_chat,
)
from DyberPet.assistant.task_planner import generate_task_plan
from DyberPet.assistant.request_control import CancellationToken, RequestCancelled


def _delta(text):
    return ("data: " + json.dumps({"choices": [{"delta": {"content": text}}]})
            + "\n\n").encode("utf-8")


def _plan_response():
    plan = {"version": 1, "title": "记录", "steps": [
        {"action": "create_note", "name": "记录.md", "content": "实际内容"}]}
    return json.dumps({"choices": [{"finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(plan, ensure_ascii=False)}}]},
        ensure_ascii=False).encode("utf-8")


class RequestCancellationTests(unittest.TestCase):
    def setUp(self):
        self.tokens = []
        self.workers = []
        self.requests = []
        self.arrived = threading.Event()
        self.disconnected = threading.Event()
        self.release = threading.Event()
        self.mode = "json"
        self.body = b'{"ok":true}'
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                self.handle_request()

            def do_POST(self):
                self.handle_request()

            def handle_request(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length else b""
                owner.requests.append((self.command, self.path, body))
                if owner.mode == "ppl_create" and self.command == "GET":
                    response = b'{}'
                    self.send_response(200 if self.path == "/health" else 404)
                    self.send_header("Content-Length", str(len(response)))
                    self.end_headers()
                    self.wfile.write(response)
                    return
                if owner.mode == "inert_headers":
                    owner.arrived.set()
                    owner.release.wait()
                    return
                if owner.mode in ("stall_headers", "ppl_create"):
                    owner.arrived.set()
                    self.wait_for_disconnect()
                    return
                if owner.mode == "redirect":
                    self.send_response(302)
                    self.send_header("Location", owner.endpoint + "/redirected")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if owner.mode == "error":
                    self.send_response(503)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Connection", "close")
                if owner.mode == "chunked_sse":
                    self.send_header("Transfer-Encoding", "chunked")
                elif owner.mode in ("stall_json", "inert_json"):
                    self.send_header("Content-Length", str(len(owner.body) + 100))
                elif owner.mode not in ("stall_sse", "inert_sse", "slow_sse", "sse"):
                    self.send_header("Content-Length", str(len(owner.body)))
                self.end_headers()
                try:
                    if owner.mode in ("stall_sse", "inert_sse"):
                        self.wfile.write(_delta("第一段"))
                    elif owner.mode in ("slow_sse", "chunked_sse"):
                        for fragment in (_delta("第一段")[:8],
                                         _delta("第一段")[8:],
                                         _delta("第二段"), b"data: [DONE]\n\n"):
                            if owner.mode == "chunked_sse":
                                self.wfile.write(("{:X}\r\n".format(len(fragment))).encode()
                                                 + fragment + b"\r\n")
                            else:
                                self.wfile.write(fragment)
                            self.wfile.flush()
                            time.sleep(.15)
                        if owner.mode == "chunked_sse":
                            self.wfile.write(b"0\r\n\r\n")
                    elif owner.mode == "sse":
                        self.wfile.write(owner.body)
                    else:
                        self.wfile.write(owner.body)
                    self.wfile.flush()
                    owner.arrived.set()
                    if owner.mode in ("stall_sse", "stall_json"):
                        self.wait_for_disconnect()
                    elif owner.mode in ("inert_sse", "inert_json"):
                        owner.release.wait()
                except (BrokenPipeError, ConnectionResetError):
                    owner.disconnected.set()

            def wait_for_disconnect(self):
                self.connection.settimeout(3)
                try:
                    if self.connection.recv(1) == b"":
                        owner.disconnected.set()
                except ConnectionResetError:
                    owner.disconnected.set()
                except socket.timeout:
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.endpoint = "http://127.0.0.1:" + str(self.server.server_port)
        self.server_thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True)
        self.server_thread.start()
        self.addCleanup(self.shutdown)

    def shutdown(self):
        self.release.set()
        for token in self.tokens:
            token.cancel()
        for worker in self.workers:
            worker.join(timeout=3)
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)

    def token(self):
        token = CancellationToken()
        self.tokens.append(token)
        return token

    def start_request(self, operation):
        result = {}

        def run():
            try:
                result["value"] = operation()
            except Exception as exc:
                result["error"] = exc

        worker = threading.Thread(target=run, daemon=True)
        self.workers.append(worker)
        worker.start()
        return worker, result

    def assert_cancelled(self, token, worker, result):
        token.cancel()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive(), "Cancellation left the worker blocked")
        self.assertIsInstance(result.get("error"), RequestCancelled)
        self.assertNotIn("value", result)
        self.assertTrue(self.disconnected.wait(1), "The server still sees an open request")

    def stream(self, token, on_delta):
        return stream_local_chat("问题", model="local-model", base_url=self.endpoint,
                                 on_delta=on_delta, cancel_token=token, timeout=10)

    def test_cancelled_before_request_does_not_contact_service(self):
        token = self.token()
        token.cancel()
        token.cancel()
        self.assertTrue(token.cancelled)
        with self.assertRaises(RequestCancelled):
            self.stream(token, lambda _: self.fail("Unexpected text after cancellation"))
        with self.assertRaises(RequestCancelled):
            generate_task_plan("创建记录", model="local-model", base_url=self.endpoint,
                               cancel_token=token)
        self.assertEqual(self.requests, [])

    def test_cancel_interrupts_waiting_for_response_headers(self):
        self.mode = "stall_headers"
        token = self.token()
        worker, result = self.start_request(lambda: self.stream(token, lambda _: None))
        self.assertTrue(self.arrived.wait(2))
        self.assert_cancelled(token, worker, result)

    def test_cancel_while_connection_is_being_registered_sends_no_request(self):
        token = self.token()
        connected, release = threading.Event(), threading.Event()
        original_connect = http.client.HTTPConnection.connect

        def pause_after_connect(connection):
            original_connect(connection)
            connected.set()
            release.wait(2)

        with patch("DyberPet.assistant.request_control.http.client.HTTPConnection.connect",
                   pause_after_connect):
            worker, result = self.start_request(lambda: self.stream(token, lambda _: None))
            try:
                self.assertTrue(connected.wait(2))
                token.cancel()
            finally:
                release.set()
            worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertIsInstance(result.get("error"), RequestCancelled)
        self.assertEqual(self.requests, [])

    def test_cancel_interrupts_stream_after_visible_prefix(self):
        self.mode = "stall_sse"
        token = self.token()
        pieces = []
        received = threading.Event()

        def on_delta(piece):
            pieces.append(piece)
            received.set()

        worker, result = self.start_request(lambda: self.stream(token, on_delta))
        self.assertTrue(received.wait(2))
        self.assert_cancelled(token, worker, result)
        self.assertEqual(pieces, ["第一段"])

    def test_cancel_interrupts_structured_json_body(self):
        self.mode = "stall_json"
        self.body = b'{"choices":['
        token = self.token()
        worker, result = self.start_request(lambda: generate_task_plan(
            "创建记录", model="local-model", base_url=self.endpoint, cancel_token=token))
        self.assertTrue(self.arrived.wait(2))
        self.assert_cancelled(token, worker, result)

    def test_cancel_does_not_depend_on_os_shutdown_waking_response_reader(self):
        # An inert peer does not close in response to our FIN. Some platforms
        # also leave the current timeout-mode read blocked after local shutdown.
        for mode in ("inert_headers", "inert_sse", "inert_json"):
            with self.subTest(mode=mode):
                self.mode = mode
                self.arrived.clear()
                self.release.clear()
                token = self.token()
                pieces = []
                operation = (lambda: _json_request(
                    self.endpoint + "/json", cancel_token=token, timeout=10))
                if mode != "inert_json":
                    operation = lambda: self.stream(token, pieces.append)
                worker, result = self.start_request(operation)
                self.assertTrue(self.arrived.wait(2))
                try:
                    # Replace only the platform wakeup boundary. HTTP and the
                    # cancellation token remain real; the server stays held.
                    with patch.object(socket.socket, "shutdown", new=lambda *_args: None):
                        token.cancel()
                    worker.join(timeout=1)
                    self.assertFalse(worker.is_alive(),
                                     "Cancel is waiting for peer data or the read timeout")
                    self.assertIsInstance(result.get("error"), RequestCancelled)
                    self.assertNotIn("value", result)
                    self.assertFalse(self.release.is_set())
                    if mode == "inert_sse":
                        self.assertLessEqual(len(pieces), 1)
                finally:
                    self.release.set()
                    worker.join(timeout=2)

    def test_polling_keeps_fragmented_stream_intact_across_quiet_intervals(self):
        self.mode = "slow_sse"
        token = self.token()
        pieces = []
        self.assertEqual(self.stream(token, pieces.append), "第一段第二段")
        self.assertEqual(pieces, ["第一段", "第二段"])

    def test_polling_preserves_http_chunk_framing(self):
        self.mode = "chunked_sse"
        pieces = []
        self.assertEqual(self.stream(self.token(), pieces.append), "第一段第二段")
        self.assertEqual(pieces, ["第一段", "第二段"])

    def test_polling_preserves_requested_response_timeout(self):
        self.mode = "inert_headers"
        token = self.token()
        started = time.monotonic()
        try:
            with self.assertRaises(AssistantServiceError) as raised:
                _json_request(self.endpoint + "/json", cancel_token=token, timeout=.2)
            self.assertEqual(raised.exception.code, "timeout")
            self.assertGreaterEqual(time.monotonic() - started, .15)
            self.assertFalse(token.cancelled)
            self.assertFalse(self.release.is_set())
        finally:
            self.release.set()

    def test_cancellation_in_delta_callback_never_returns_completed_answer(self):
        self.mode = "sse"
        self.body = _delta("第一段") + _delta("不应送达") + b"data: [DONE]\n\n"
        token = self.token()
        pieces = []

        def on_delta(piece):
            pieces.append(piece)
            token.cancel()

        with self.assertRaises(RequestCancelled):
            self.stream(token, on_delta)
        self.assertEqual(pieces, ["第一段"])

    def test_cancellation_during_json_decode_does_not_publish_result(self):
        token = self.token()

        def decode(text):
            token.cancel()
            return json.loads(text)

        with self.assertRaises(RequestCancelled):
            _json_request(self.endpoint + "/json", cancel_token=token, json_decoder=decode)

    def test_ppl_missing_session_creation_uses_the_same_cancellation(self):
        self.mode = "ppl_create"
        token = self.token()
        worker, result = self.start_request(lambda: PPLCharacterClient(self.endpoint).state(
            "Doro", cancel_token=token))
        self.assertTrue(self.arrived.wait(2))
        self.assert_cancelled(token, worker, result)
        self.assertEqual([(method, path) for method, path, _ in self.requests], [
            ("GET", "/v1/sessions/" + session_id("Doro")),
            ("GET", "/health"), ("POST", "/v1/sessions")])

    def test_fresh_request_after_cancellation_returns_valid_plan(self):
        self.mode = "stall_headers"
        token = self.token()
        worker, result = self.start_request(lambda: self.stream(token, lambda _: None))
        self.assertTrue(self.arrived.wait(2))
        self.assert_cancelled(token, worker, result)
        self.mode, self.body = "json", _plan_response()
        plan = generate_task_plan("创建记录", model="local-model", base_url=self.endpoint,
                                  cancel_token=self.token())
        self.assertEqual(plan.steps[0].name, "记录.md")
        self.assertEqual(plan.steps[0].content, "实际内容")

    def test_cancel_enabled_transport_ignores_proxies_and_blocks_redirects(self):
        token = self.token()
        with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1",
                                     "HTTP_PROXY": "http://127.0.0.1:1",
                                     "NO_PROXY": "", "no_proxy": ""}):
            self.assertEqual(_json_request(self.endpoint + "/json", cancel_token=token),
                             {"ok": True})
        self.mode = "redirect"
        with self.assertRaises(AssistantServiceError):
            _json_request(self.endpoint + "/redirect", cancel_token=token)
        self.assertEqual([path for _, path, _ in self.requests], ["/json", "/redirect"])
        with self.assertRaises(AssistantServiceError):
            stream_local_chat("问题", model="m", base_url="http://example.com:80",
                              on_delta=lambda _: None, cancel_token=token)
        self.assertEqual(len(self.requests), 2)

    def test_cancel_enabled_transport_preserves_limits_and_http_status(self):
        token = self.token()
        self.body = b" " * (512 * 1024 + 1)
        with self.assertRaises(AssistantServiceError):
            _json_request(self.endpoint + "/large", cancel_token=token)
        self.mode, self.body = "sse", b"data: " + b"x" * 65537 + b"\n\n"
        with self.assertRaises(AssistantServiceError):
            self.stream(token, lambda _: self.fail("Oversized data must not be delivered"))
        self.mode = "error"
        with self.assertRaises(AssistantServiceError) as raised:
            _json_request(self.endpoint + "/error", cancel_token=token)
        self.assertEqual(raised.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
