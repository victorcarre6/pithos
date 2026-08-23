"""Mode-0600 Unix socket exposing only outbound Telegram messages."""

import json
import os
import socketserver
from pathlib import Path


class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            response = self.server.broker.send(json.loads(self.rfile.readline()))
        except (ValueError, RuntimeError, json.JSONDecodeError) as error:
            response = {"ok": False, "error": str(error)}
        self.wfile.write(json.dumps(response).encode() + b"\n")


class TelegramBrokerServer(socketserver.UnixStreamServer):
    def __init__(self, path: Path, broker) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        self.broker = broker
        self.path = path
        super().__init__(str(path), RequestHandler)
        os.chmod(path, 0o600)

    def server_close(self) -> None:
        super().server_close()
        self.path.unlink(missing_ok=True)
