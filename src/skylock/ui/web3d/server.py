"""Embedded HTTP server for serving 3D WebGL assets locally."""

from __future__ import annotations

import functools
import http.server
import logging
import socket
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def get_static_assets_path() -> Path:
    """Resolve the directory containing static 3D WebGL assets."""
    if hasattr(sys, "_MEIPASS"):
        # PyInstaller bundled location
        base = Path(sys._MEIPASS) / "skylock" / "ui" / "web3d" / "static"
        if base.exists():
            return base

    # Development source location
    dev_path = Path(__file__).parent / "static"
    return dev_path.resolve()


class _QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Quiet static file handler with correct MIME types for 3D assets."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".js": "application/javascript",
        ".mjs": "application/javascript",
        ".json": "application/json",
        ".wasm": "application/wasm",
    }

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """Suppress standard HTTP request logging to stdout."""

    def end_headers(self) -> None:
        """Add CORS and caching headers."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()


class Embedded3DServer:
    """Lightweight local HTTP server for serving Three.js WebGL assets."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.requested_port = port
        self.port = 0
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._assets_dir = get_static_assets_path()

    @property
    def assets_dir(self) -> Path:
        """Directory path being served."""
        return self._assets_dir

    def start(self) -> int:
        """Start the embedded server on a daemon thread. Returns the bound port."""
        if self._server is not None:
            return self.port

        handler = functools.partial(
            _QuietHTTPHandler,
            directory=str(self._assets_dir),
        )

        # Bind to host and port (0 selects an available OS ephemeral port)
        self._server = http.server.ThreadingHTTPServer((self.host, self.requested_port), handler)
        self.port = self._server.server_address[1]

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="Embedded3DServerThread",
        )
        self._thread.start()
        logger.info("Embedded 3D server running on http://%s:%d", self.host, self.port)
        return self.port

    def get_url(self, path: str = "index.html") -> str:
        """Get the full HTTP URL for the requested path."""
        if self.port == 0:
            self.start()
        clean_path = path.lstrip("/")
        return f"http://{self.host}:{self.port}/{clean_path}"

    def stop(self) -> None:
        """Stop and shutdown the embedded HTTP server."""
        if self._server is not None:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception as e:
                logger.debug("Error stopping embedded 3D server: %s", e)
            finally:
                self._server = None
                self._thread = None
                self.port = 0

    def is_alive(self) -> bool:
        """Check if server socket is actively listening."""
        if self._server is None or self.port == 0:
            return False
        try:
            with socket.create_connection((self.host, self.port), timeout=0.5):
                return True
        except OSError:
            return False
