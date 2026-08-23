"""Credential-free client for the narrow broker socket."""

import json
import socket
from pathlib import Path


def send_request(socket_path: Path, request: dict) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(5)
        client.connect(str(socket_path))
        client.sendall(json.dumps(request).encode() + b"\n")
        response = json.loads(client.makefile().readline())
    if not response.get("ok"):
        raise RuntimeError(response.get("error", "Telegram broker refused request"))

    return response
