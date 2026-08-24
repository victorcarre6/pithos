"""Minimal native Ollama API client with no model-management mutations."""

import json
import urllib.error
import urllib.request
from time import monotonic


class OllamaError(RuntimeError):
    """Report an Ollama transport or protocol failure."""

    def __init__(self, message, payload=None, chunks=None):
        super().__init__(message)
        self.payload = payload
        self.chunks = chunks or []


def _http_error_detail(error):
    """Return the server error message carried by an HTTP failure."""

    body = error.read().decode(errors="replace").strip()
    if not body:
        return str(error)

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError:
        return body

    return decoded.get("error") or body


class OllamaClient:
    """Call the local Ollama API and control only model residency."""

    def __init__(self, base_url="http://127.0.0.1:11434", opener=None):
        self.base_url = base_url.rstrip("/")
        self.opener = opener or urllib.request.urlopen

    def version(self):
        """Return the Ollama server version."""

        return self._request("GET", "/api/version", timeout=5)

    def models(self):
        """Return locally installed models without pulling anything."""

        response = self._request("GET", "/api/tags", timeout=10)

        return response.get("models", [])

    def running_models(self):
        """Return models currently resident in memory."""

        response = self._request("GET", "/api/ps", timeout=10)

        return response.get("models", [])

    def show(self, model):
        """Return exact metadata for one already installed model."""

        return self._request("POST", "/api/show", {"model": model}, timeout=30)

    def assert_installed(self, model):
        """Reject a model absent from the local Ollama catalogue."""

        installed = {item.get("name") or item.get("model") for item in self.models()}
        if model not in installed:
            available = ", ".join(sorted(name for name in installed if name))
            raise OllamaError(f"model {model!r} is not installed; available: {available}")

    def unload(self, model):
        """Request immediate eviction of one installed model."""

        payload = {
            "model": model,
            "prompt": "",
            "keep_alive": 0,
            "stream": False,
        }

        return self._request("POST", "/api/generate", payload, timeout=30)

    def chat(self, model, messages, timeout, format_schema=None, tools=None, options=None, on_chunk=None):
        """Execute one non-streaming chat attempt and retain native timings."""

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": "30m",
            "options": {"temperature": 0, **(options or {})},
        }
        if format_schema is not None:
            payload["format"] = format_schema
        if tools is not None:
            payload["tools"] = tools

        started = monotonic()
        response = self._stream_chat(payload, timeout, started, on_chunk or (lambda chunk: None))

        return payload, response

    def _stream_chat(self, payload, timeout, started, on_chunk):
        """Aggregate Ollama NDJSON while retaining timing of the first signals."""

        body = json.dumps(payload).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        chunks = []
        content = []
        thinking = []
        tool_calls = []
        first_chunk_seconds = None
        first_content_seconds = None
        deadline = started + timeout

        try:
            with self.opener(request, timeout=timeout) as response:
                for raw_line in response:
                    if not raw_line.strip():
                        continue
                    if monotonic() >= deadline:
                        message = f"POST /api/chat exceeded {timeout} second wall-clock timeout"

                        raise OllamaError(message, payload=payload, chunks=chunks)
                    chunk = json.loads(raw_line)
                    if not isinstance(chunk, dict):
                        raise OllamaError("POST /api/chat returned a non-object stream chunk")
                    elapsed = monotonic() - started
                    first_chunk_seconds = first_chunk_seconds or elapsed
                    message = chunk.get("message") or {}
                    if message.get("content") or message.get("thinking") or message.get("tool_calls"):
                        first_content_seconds = first_content_seconds or elapsed
                    content.append(message.get("content", ""))
                    thinking.append(message.get("thinking", ""))
                    tool_calls.extend(message.get("tool_calls") or [])
                    chunks.append(chunk)
                    on_chunk(chunk)
        except urllib.error.HTTPError as error:
            detail = _http_error_detail(error)
            message = f"POST /api/chat failed: HTTP {error.code}: {detail}"

            raise OllamaError(message, payload=payload, chunks=chunks) from error
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise OllamaError(f"POST /api/chat failed: {error}", payload=payload, chunks=chunks) from error

        if not chunks:
            raise OllamaError("POST /api/chat returned an empty stream")
        aggregate = dict(chunks[-1])
        aggregate["message"] = {
            "role": "assistant",
            "content": "".join(content),
            "thinking": "".join(thinking),
            "tool_calls": tool_calls,
        }
        aggregate["client_duration_seconds"] = monotonic() - started
        aggregate["time_to_first_chunk_seconds"] = first_chunk_seconds
        aggregate["time_to_first_content_seconds"] = first_content_seconds
        aggregate["stream_chunk_count"] = len(chunks)
        aggregate["stream_chunks"] = chunks

        return aggregate

    def _request(self, method, path, payload=None, timeout=30):
        """Send one JSON request and validate the response object."""

        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )

        try:
            with self.opener(request, timeout=timeout) as response:
                decoded = json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = _http_error_detail(error)
            message = f"{method} {path} failed: HTTP {error.code}: {detail}"

            raise OllamaError(message) from error
        except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise OllamaError(f"{method} {path} failed: {error}") from error

        if not isinstance(decoded, dict):
            raise OllamaError(f"{method} {path} returned a non-object response")

        return decoded
