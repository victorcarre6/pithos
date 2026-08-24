"""Unix socket transport keeping host credentials outside the Pi process."""

import json
import os
import socketserver
from pathlib import Path

from .broker import GitBroker
from .policy import PolicyViolation


class BrokerRequestHandler(socketserver.StreamRequestHandler):
    """Process one JSON request per socket connection."""

    def handle(self) -> None:
        line = self.rfile.readline()
        if not line:
            return

        try:
            request = json.loads(line)
            response = self.server.broker.handle(request)
        except (json.JSONDecodeError, OSError, RuntimeError, PolicyViolation) as error:
            response = {"ok": False, "error": str(error)}

        self.wfile.write(json.dumps(response).encode() + b"\n")


class GitBrokerServer(socketserver.UnixStreamServer):
    """Bind a credential-free Unix socket to one configured broker."""

    def __init__(self, socket_path: Path, broker: GitBroker) -> None:
        socket_path.parent.mkdir(parents=True, exist_ok=True)
        socket_path.unlink(missing_ok=True)
        self.broker = broker
        self.socket_path = socket_path
        super().__init__(str(socket_path), BrokerRequestHandler)
        os.chmod(socket_path, 0o600)

    def server_close(self) -> None:
        super().server_close()
        self.socket_path.unlink(missing_ok=True)
