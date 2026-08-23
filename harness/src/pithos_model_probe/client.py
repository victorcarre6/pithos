"""Small Ollama client used by the model capability probe."""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeResponse:
    """Keep the decoded response and client-observed duration together."""

    body: dict
    elapsed_seconds: float


class OllamaClient:
    """Call the local Ollama API with explicit timeouts."""

    def __init__(self, base_url: str, timeout_seconds: int) -> None:

        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get(self, path: str) -> ProbeResponse:
        return self._request("GET", path, None)

    def post(self, path: str, payload: dict) -> ProbeResponse:
        return self._request("POST", path, payload)

    def _request(self, method: str, path: str, payload: dict | None) -> ProbeResponse:
        request_body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method=method,
        )

        started_at = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.load(response)
        except (urllib.error.URLError, TimeoutError) as error:
            raise RuntimeError(f"Ollama request failed: {error}") from error

        elapsed_seconds = time.monotonic() - started_at

        return ProbeResponse(body=body, elapsed_seconds=elapsed_seconds)

