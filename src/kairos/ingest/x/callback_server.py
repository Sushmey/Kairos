"""Local HTTP server for OAuth redirect callback."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


@dataclass
class OAuthCallbackResult:
    code: str | None = None
    state: str | None = None
    error: str | None = None
    error_description: str | None = None


class OAuthCallbackListener:
    """Listen for a single OAuth redirect, then stop."""

    def __init__(self, *, host: str, port: int, path: str):
        self.host = host
        self.port = port
        self.path = path
        self.result = OAuthCallbackResult()
        self._ready = threading.Event()
        self._done = threading.Event()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler_cls = self._make_handler()
        self._server = HTTPServer((self.host, self.port), handler_cls)
        self._server.timeout = 0.5

        def serve() -> None:
            assert self._server is not None
            self._ready.set()
            while not self._done.is_set():
                self._server.handle_request()
                if self.result.code or self.result.error:
                    self._done.set()
                    break
            self._server.server_close()

        self._thread = threading.Thread(target=serve, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=5.0):
            raise TimeoutError(
                f"Failed to start OAuth callback listener on http://{self.host}:{self.port}{self.path}"
            )

    def wait(self, timeout: float = 300.0) -> OAuthCallbackResult:
        if not self._thread:
            raise RuntimeError("OAuth callback listener not started")
        if not self._done.wait(timeout=timeout):
            self._done.set()
            raise TimeoutError(
                f"Timed out waiting for OAuth callback on http://{self.host}:{self.port}{self.path}"
            )
        self._thread.join(timeout=2.0)
        return self.result

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        expected_path = self.path
        listener = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path != expected_path:
                    self.send_error(404, "Not found")
                    return

                params = parse_qs(parsed.query, keep_blank_values=False)
                listener.result = OAuthCallbackResult(
                    code=_first(params, "code"),
                    state=_first(params, "state"),
                    error=_first(params, "error"),
                    error_description=_first(params, "error_description"),
                )

                body = (
                    b"Authorization complete. You can close this tab and return to the terminal."
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format: str, *args: object) -> None:
                return

        return Handler


def _first(params: dict[str, list[str]], key: str) -> str | None:
    values = params.get(key)
    return values[0] if values else None


def wait_for_oauth_callback(
    *,
    host: str,
    port: int,
    path: str,
    timeout: float = 300.0,
) -> OAuthCallbackResult:
    """Block until X redirects to the local callback URL or timeout."""
    listener = OAuthCallbackListener(host=host, port=port, path=path)
    listener.start()
    return listener.wait(timeout=timeout)
