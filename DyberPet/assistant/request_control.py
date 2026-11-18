"""Cooperative cancellation for explicitly local HTTP requests.

The caller may request cancellation from another thread. Only socket shutdown
runs there; the request's worker still owns response and connection cleanup.
"""
from __future__ import annotations

import http.client
import socket
import threading
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
        # holding their own read lock. Shutdown wakes the worker's blocking I/O.
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


@contextmanager
def cancellable_response(request, *, timeout, cancel_token: CancellationToken):
    """Open one proxy-free HTTP connection, never following redirects.

    The local TCP connection attempt has a maximum three-second timeout. Once
    connected, cancellation can interrupt request/header/body I/O by shutting
    down the bound socket. DNS/OS connect itself is not forcefully interrupted.
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
