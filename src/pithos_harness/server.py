"""Unix socket transport for harness promotion requests."""

import json
import os
import socketserver
from pathlib import Path

from .broker import HarnessBroker
from .manager import HarnessError
from .validation import ResourceValidationError


class RequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        try:
            request = json.loads(self.rfile.readline())
            response = self.server.broker.handle(request)
        except (json.JSONDecodeError, HarnessError, OSError, ResourceValidationError) as error:
            response = {"ok": False, "error": str(error)}
        self.wfile.write(json.dumps(response).encode() + b"\n")


class HarnessBrokerServer(socketserver.UnixStreamServer):
    def __init__(self, socket_path: Path, broker: HarnessBroker) -> None:
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.unlink(missing_ok=True)
        self.broker = broker
        self.socket_path = socket_path
        super().__init__(str(socket_path), RequestHandler)
        os.chmod(socket_path, 0o600)

    def server_close(self) -> None:
        super().server_close()
        self.socket_path.unlink(missing_ok=True)
