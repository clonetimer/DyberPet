"""Model discovery and diagnostic contracts against a real loopback service."""
import importlib
import json
import os
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from DyberPet.assistant.persona import (
    AssistantServiceError, _json_request, _local_base, list_local_models, stream_local_chat,
)
from DyberPet.assistant.request_control import CancellationToken, RequestCancelled


class ModelDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.tokens = []
        self.workers = []
        self.arrived = threading.Event()
        self.disconnected = threading.Event()
        self.mode = "json"
        self.status = 200
        self.body = b'{"data":[{"id":"local-chat"}]}'
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self):
                self.respond()

            def do_POST(self):
                self.respond()

            def respond(self):
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length) if length else b""
                owner.requests.append((self.command, self.path, body))
                if owner.mode == "stall_headers":
                    owner.arrived.set()
                    self.wait_for_disconnect()
                    return
                self.send_response(owner.status)
                self.send_header("Connection", "close")
                self.send_header("Content-Type", "application/json")
                if 300 <= owner.status < 400:
                    self.send_header("Location", owner.endpoint + "/redirected")
                length = len(owner.body) + (100 if owner.mode == "stall_body" else 0)
                self.send_header("Content-Length", str(length))
                self.end_headers()
                try:
                    self.wfile.write(owner.body)
                    self.wfile.flush()
                    owner.arrived.set()
                    if owner.mode == "stall_body":
                        self.wait_for_disconnect()
                except (BrokenPipeError, ConnectionResetError):
                    owner.disconnected.set()

            def wait_for_disconnect(self):
                self.connection.settimeout(6)
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
        for token in self.tokens:
            token.cancel()
        for worker in self.workers:
            worker.join(timeout=2)
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)

    def token(self):
        token = CancellationToken()
        self.tokens.append(token)
        return token

    def discover(self, token=None, endpoint=None):
        options = {} if token is None else {"cancel_token": token}
        return list_local_models(endpoint or self.endpoint, **options)

    def assert_service_error(self, code, operation, status=None):
        with self.assertRaises(AssistantServiceError) as raised:
            operation()
        self.assertEqual(getattr(raised.exception, "code", None), code)
        self.assertEqual(raised.exception.status_code, status)
        return raised.exception

    def test_get_lists_server_visible_models_without_a_request_body(self):
        self.assertEqual(self.discover(), ["local-chat"])
        self.assertEqual(self.requests, [("GET", "/v1/models", b"")])

    def test_discovery_with_cancellation_preserves_get_protocol(self):
        self.assertEqual(self.discover(self.token()), ["local-chat"])
        self.assertEqual(self.requests, [("GET", "/v1/models", b"")])

    def test_model_ids_are_deduplicated_trimmed_and_safe_for_display(self):
        self.body = json.dumps({"data": [
            {"id": " qwen/local "}, {"id": "qwen/local"}, {"id": "本地模型"},
            {"id": ""}, {"id": 7}, {}, None, {"id": "x" * 121},
            {"id": "bad\nmodel"}, {"id": "\ttrimmed-control"},
            {"id": "hidden\x00model"}, {"id": "bad\x7fmodel"},
            {"id": "bad\u0085model"}, {"id": "bad\u202emodel"},
            {"id": "bad\u2028model"}, {"id": "bad\ud800model"},
            {"id": "a" * 120},
        ]}).encode("utf-8")
        self.assertEqual(self.discover(), ["qwen/local", "本地模型", "a" * 120])

    def test_discovery_inspects_only_first_hundred_rows(self):
        self.body = json.dumps({"data": [{"id": "model-" + str(i)}
                                           for i in range(101)]}).encode("utf-8")
        models = self.discover()
        self.assertEqual(len(models), 100)
        self.assertEqual(models[0], "model-0")
        self.assertEqual(models[-1], "model-99")

    def test_invalid_json_utf8_or_model_list_has_response_code(self):
        for payload in (b"not json", b"\xff", b"[]", b"{}", b'{"data":{}}',
                        b"[" * 1100 + b"]" * 1100):
            for token in (None, self.token()):
                with self.subTest(payload=payload[:20], cancellable=token is not None):
                    self.body = payload
                    self.assert_service_error("response", lambda: self.discover(token))

    def test_response_size_remains_bounded(self):
        self.body = b" " * (512 * 1024 + 1)
        for token in (None, self.token()):
            with self.subTest(cancellable=token is not None):
                self.assert_service_error("response", lambda: self.discover(token))

    def test_no_valid_models_is_distinct_from_invalid_response(self):
        for rows in ([], [{"id": ""}], [{"id": "bad\nmodel"}]):
            with self.subTest(rows=rows):
                self.body = json.dumps({"data": rows}).encode("utf-8")
                self.assert_service_error("no_models", self.discover)

    def test_nonlocal_and_malformed_urls_have_one_safe_error_type(self):
        for endpoint in (
            "https://127.0.0.1:1234", "http://example.com:1234",
            "http://127.0.0.2:1234", "http://localhost:1234@evil.example:80",
            "http://localhost:1234/v1", "http://localhost:1234?key=secret",
            "http://localhost:1234#fragment", "http://localhost", "file:///tmp/a",
            "http://[::1:1234", "http://[bad-ipv6]:1234",
            "http://localhost:no-port", "http://localhost:65536",
            "http://localhost:0", "http://local\nhost:1234", None,
        ):
            with self.subTest(endpoint=endpoint):
                self.assert_service_error(
                    "invalid_endpoint", lambda: list_local_models(endpoint))
        self.assertEqual(self.requests, [])

    def test_proxies_are_ignored_in_both_transports(self):
        with patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:1",
                                     "HTTP_PROXY": "http://127.0.0.1:1",
                                     "ALL_PROXY": "http://127.0.0.1:1",
                                     "all_proxy": "http://127.0.0.1:1",
                                     "NO_PROXY": "", "no_proxy": ""}):
            self.assertEqual(self.discover(), ["local-chat"])
            self.assertEqual(self.discover(self.token()), ["local-chat"])
        self.assertEqual(len(self.requests), 2)

    def test_local_address_rejects_ambiguous_authority_before_connecting(self):
        for endpoint in ("http://@localhost:1234", "http://:@localhost:1234",
                         "http://[::1]unexpected:1234"):
            with self.subTest(endpoint=endpoint):
                self.assert_service_error("invalid_endpoint", lambda: _local_base(endpoint))
        self.assertEqual(_local_base("http://[::1]:1234/"), "http://[::1]:1234")

    def test_redirects_are_categorized_and_never_followed(self):
        self.body = b""
        for status in (300, 301, 302, 303, 304, 307, 308):
            for token in (None, self.token()):
                with self.subTest(status=status, cancellable=token is not None):
                    self.status = status
                    self.assert_service_error("redirect", lambda: self.discover(token), status)
        self.assertTrue(self.requests)
        self.assertEqual({path for _, path, _ in self.requests}, {"/v1/models"})

    def test_http_failure_preserves_status_without_exposing_response_body(self):
        self.body = b'{"error":"secret-server-body API_KEY=private-token"}'
        for status in (204, 401, 403, 404, 429, 503):
            for token in (None, self.token()):
                with self.subTest(status=status, cancellable=token is not None):
                    self.status = status
                    error = self.assert_service_error(
                        "http", lambda: self.discover(token), status)
                    self.assertNotIn("secret-server-body", str(error))
                    self.assertNotIn("private-token", str(error))

    def test_refused_connection_has_distinct_error_code(self):
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            endpoint = "http://127.0.0.1:" + str(reserved.getsockname()[1])
            for token in (None, self.token()):
                with self.subTest(cancellable=token is not None):
                    self.assert_service_error(
                        "connection", lambda: self.discover(token, endpoint))

    def test_header_timeout_is_distinct_from_refused_connection(self):
        self.mode = "stall_headers"
        for token in (None, self.token()):
            with self.subTest(cancellable=token is not None):
                self.assert_service_error("timeout", lambda: _json_request(
                    self.endpoint + "/v1/models", timeout=0.08, cancel_token=token))

    def test_pre_cancelled_discovery_never_contacts_service(self):
        token = self.token()
        token.cancel()
        with self.assertRaises(RequestCancelled):
            self.discover(token)
        self.assertEqual(self.requests, [])

    def test_cancellation_interrupts_waiting_headers_and_partial_body(self):
        for mode in ("stall_headers", "stall_body"):
            with self.subTest(mode=mode):
                self.mode = mode
                self.arrived.clear()
                self.disconnected.clear()
                token = self.token()
                result = {}

                def run():
                    try:
                        result["value"] = self.discover(token)
                    except Exception as exc:
                        result["error"] = exc

                worker = threading.Thread(target=run, daemon=True)
                self.workers.append(worker)
                worker.start()
                self.assertTrue(self.arrived.wait(1), str(result.get("error")))
                token.cancel()
                worker.join(timeout=2)
                self.assertFalse(worker.is_alive(), "Cancelled discovery left a blocked worker")
                self.assertIsInstance(result.get("error"), RequestCancelled)
                self.assertNotIn("value", result)
                self.assertTrue(self.disconnected.wait(1))

    def test_stream_http_errors_use_the_same_diagnostic_categories(self):
        self.body = b'{"error":"private-response"}'
        for status, code in ((302, "redirect"), (401, "http"), (503, "http")):
            for token in (None, self.token()):
                with self.subTest(status=status, cancellable=token is not None):
                    self.status = status
                    self.assert_service_error(code, lambda: stream_local_chat(
                        "hello", model="model", base_url=self.endpoint,
                        on_delta=lambda _: None, cancel_token=token), status)

    def test_stream_error_event_never_copies_server_details_into_exception(self):
        self.body = b'data: {"error":{"message":"private-server-response"}}\n\n'
        with self.assertRaises(AssistantServiceError) as raised:
            stream_local_chat("hello", model="model", base_url=self.endpoint,
                              on_delta=lambda _: None)
        self.assertNotIn("private-server-response", str(raised.exception))


class ServiceDiagnosticsTests(unittest.TestCase):
    def hint(self, error):
        try:
            module = importlib.import_module("DyberPet.assistant.service_diagnostics")
        except ModuleNotFoundError:
            self.fail("Service diagnostics must provide actionable safe Chinese hints")
        return module.service_error_hint(error)

    def test_old_error_constructor_keeps_protocol_detail(self):
        error = AssistantServiceError("Local model stream ended before the completion marker")
        hint = self.hint(error)
        self.assertIn("completion marker", hint)
        self.assertLessEqual(len(hint), 400)
        self.assertTrue(any("\u4e00" <= char <= "\u9fff" for char in hint))
        self.assertEqual(getattr(error, "code", None), "service")

    def test_categories_give_next_steps_without_raw_details(self):
        cases = (
            ("invalid_endpoint", "地址"), ("connection", "启动"),
            ("timeout", "重试"), ("response", "响应"),
            ("redirect", "重定向"), ("no_models", "模型"),
        )
        for code, expected in cases:
            with self.subTest(code=code):
                error = AssistantServiceError("private-server-response", code=code)
                hint = self.hint(error)
                self.assertIn(expected, hint)
                self.assertNotIn("private-server-response", hint)
                self.assertLessEqual(len(hint), 400)

    def test_authentication_hint_never_recommends_disabling_authentication(self):
        for status in (401, 403):
            with self.subTest(status=status):
                hint = self.hint(AssistantServiceError("private-response", status_code=status))
                self.assertIn(str(status), hint)
                self.assertIn("认证", hint)
                self.assertNotIn("关闭", hint)
                self.assertNotIn("禁用", hint)
                self.assertNotIn("private-response", hint)

    def test_http_status_hints_retain_status_and_action(self):
        for status, expected in ((404, "兼容"), (429, "稍后"), (503, "日志")):
            with self.subTest(status=status):
                hint = self.hint(AssistantServiceError("private-response", status_code=status))
                self.assertIn(str(status), hint)
                self.assertIn(expected, hint)
                self.assertNotIn("private-response", hint)

    def test_generic_detail_is_bounded_single_line_and_redacts_credentials(self):
        error = AssistantServiceError(
            "Protocol mismatch\nAuthorization: Bearer private-token "
            "http://user:password@localhost:1234?api_key=private-key "
            "API_KEY=private-api-key " + "detail " * 200)
        hint = self.hint(error)
        self.assertIn("Protocol mismatch", hint)
        for secret in ("private-token", "password", "private-key", "private-api-key"):
            self.assertNotIn(secret, hint)
        self.assertNotIn("\n", hint)
        self.assertLessEqual(len(hint), 400)


if __name__ == "__main__":
    unittest.main()
