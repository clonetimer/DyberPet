"""Cooperative cancellation for explicitly local HTTP requests.

The caller may request cancellation from another thread. Only socket shutdown
runs there; the request's worker still owns response and connection cleanup.
"""
from __future__ import annotations

import http.client
import io
import select
import socket
import threading
import time
import urllib.parse
from contextlib import contextmanager


class RequestCancelled(RuntimeError):
    """The user or the owning conversation cancelled this request."""


class CancellationToken:
    def __init__(self):
        self._lock = threading.Lock()
        self._cancelled = False
        self._sockets = set()

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def raise_if_cancelled(self):
        if self.cancelled:
            raise RequestCancelled("请求已停止")

    def cancel(self):
        with self._lock:
            if self._cancelled:
                return
            self._cancelled = True
            sockets = tuple(self._sockets)
        # Do not close buffered response readers across threads: they can be
        # holding their own read lock. Shutdown can wake native I/O; response
        # reads also poll cancellation when the OS does not wake their wait.
        for connection_socket in sockets:
            try:
                connection_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    @contextmanager
    def _bind_socket(self, connection_socket):
        with self._lock:
            if self._cancelled:
                raise RequestCancelled("请求已停止")
            self._sockets.add(connection_socket)
        try:
            self.raise_if_cancelled()
            yield
        finally:
            with self._lock:
                self._sockets.discard(connection_socket)


class _ResponseReader(io.RawIOBase):
    """Wait for response data without timing out the HTTP buffer on each poll."""

    def __init__(self, connection_socket, raw, cancel_token, timeout):
        super().__init__()
        self._socket = connection_socket
        self._raw = raw
        self._cancel_token = cancel_token
        self._timeout = timeout

    def readable(self):
        return True

    def fileno(self):
        return self._raw.fileno()

    def readinto(self, buffer):
        self._checkClosed()
        self._cancel_token.raise_if_cancelled()
        if not buffer:
            return 0
        deadline = time.monotonic() + self._timeout
        while True:
            self._cancel_token.raise_if_cancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout("timed out")
            ready, _, _ = select.select([self._socket], [], [], min(0.1, remaining))
            self._cancel_token.raise_if_cancelled()
            if ready:
                # The socket is nonblocking. SocketIO returns None for a false
                # readiness indication instead of poisoning its timeout state.
                count = self._raw.readinto(buffer)
                self._cancel_token.raise_if_cancelled()
                if count is not None:
                    return count

    def close(self):
        if self.closed:
            return
        try:
            self._raw.close()
        finally:
            super().close()


class _ResponseSocket:
    """Supply HTTPResponse with a buffered, cancellation-aware socket reader."""

    def __init__(self, connection_socket, cancel_token, timeout):
        self._socket = connection_socket
        self._cancel_token = cancel_token
        self._timeout = timeout

    def makefile(self, mode):
        # Keep a real SocketIO reference: getresponse() may close the owning
        # connection for HTTP/1.0 or Connection: close before the body is read.
        raw = self._socket.makefile(mode, buffering=0)
        try:
            return io.BufferedReader(_ResponseReader(
                self._socket, raw, self._cancel_token, self._timeout))
        except BaseException:
            raw.close()
            raise


@contextmanager
def cancellable_response(request, *, timeout, cancel_token: CancellationToken):
    """Open one proxy-free HTTP connection, never following redirects.

    The local TCP connection attempt has a maximum three-second timeout. Once
    connected, cancellation shuts down the bound socket. Response headers and
    body also poll cancellation while waiting for data, independent of OS
    shutdown wakeups. DNS/OS connect itself is not forcefully interrupted.
    """
    cancel_token.raise_if_cancelled()
    parsed = urllib.parse.urlsplit(request.full_url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.port is None):
        raise ValueError("Only local HTTP service URLs with an explicit port are supported")
    connection = http.client.HTTPConnection(
        parsed.hostname, parsed.port, timeout=min(timeout, 3.0))
    try:
        cancel_token.raise_if_cancelled()
        connection.connect()
        connection_socket = connection.sock
        with cancel_token._bind_socket(connection_socket):
            connection_socket.settimeout(timeout)
            cancel_token.raise_if_cancelled()
            connection.request(request.get_method(), parsed.path or "/", body=request.data,
                               headers=dict(request.header_items()))
            cancel_token.raise_if_cancelled()
            # Request writes retain their existing timeout. Only response reads
            # use nonblocking I/O behind the normal HTTP parser and buffer.
            connection_socket.setblocking(False)

            def make_response(response_socket, *args, **kwargs):
                return http.client.HTTPResponse(_ResponseSocket(
                    response_socket, cancel_token, timeout), *args, **kwargs)

            connection.response_class = make_response
            response = connection.getresponse()
            try:
                cancel_token.raise_if_cancelled()
                yield response
                cancel_token.raise_if_cancelled()
            finally:
                response.close()
    except Exception:
        # Shutdown may manifest as EOF, connection reset or a partial response.
        # All are cancellation when this request's token has been cancelled.
        cancel_token.raise_if_cancelled()
        raise
    finally:
        connection.close()
