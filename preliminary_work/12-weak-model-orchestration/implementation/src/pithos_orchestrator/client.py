"""Send one credential-free request to a host broker socket."""

import json
import socket
from pathlib import Path


def send_request(socket_path, request):
    """Send one JSON request and reject broker-level failures."""

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(60)
        client.connect(str(Path(socket_path)))
        client.sendall(json.dumps(request).encode() + b"\n")
        response = json.loads(client.makefile().readline())
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "broker refused request"))

    return response
