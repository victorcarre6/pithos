"""Translate Pi JSON-mode events into stable Pithos event domains."""

import json
import re

from .events import EventWriter


TEST_COMMAND = re.compile(r"(^|\s)(pytest|vitest|jest|npm test|npm run test|pnpm test|yarn test)(\s|$)")
DEPENDENCY_COMMAND = re.compile(r"(^|\s)(pip|pip3|uv|poetry|npm|pnpm|yarn)\s+(install|add)(\s|$)")
NETWORK_COMMAND = re.compile(r"(^|\s)(curl|wget|git clone)(\s|$)")


class PiEventAdapter:
    """Project complete Pi lifecycle events while retaining their raw payloads."""

    def __init__(self, writer: EventWriter) -> None:
        self.writer = writer
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.tool_calls = 0
        self.tool_failures = 0
        self.pending_tools = {}

    def consume_line(self, line: str) -> None:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self.writer.append("pi.protocol_error", {"line": line.rstrip("\n")})
            return
        if not isinstance(event, dict):
            self.writer.append("pi.protocol_error", {"value": event})
            return

        event_type = event.get("type")
        raw_type = str(event_type or "unknown").lower()
        raw_type = re.sub(r"[^a-z0-9_]+", "_", raw_type).strip("_") or "unknown"
        self.writer.append(f"pi.{raw_type}", {"event": event})
        if event_type == "message_end":
            self._message(event.get("message") or {})
        elif event_type == "tool_execution_start":
            self._tool_started(event)
        elif event_type == "tool_execution_end":
            self._tool_finished(event)

    def metrics(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "tool_calls": self.tool_calls,
            "tool_failures": self.tool_failures,
        }

    def _message(self, message: dict) -> None:
        role = str(message.get("role", "unknown"))
        usage = message.get("usage") or {}
        self.input_tokens += int(usage.get("input") or 0)
        self.output_tokens += int(usage.get("output") or 0)
        self.total_tokens += int(usage.get("totalTokens") or 0)
        payload = {
            "role": role,
            "content": _text_content(message.get("content")),
            "message": message,
        }
        action = "response" if role == "assistant" else "message"
        self.writer.append(f"model.{action}", payload)

    def _tool_started(self, event: dict) -> None:
        self.tool_calls += 1
        self.pending_tools[event.get("toolCallId")] = {
            "tool_name": event.get("toolName"),
            "arguments": event.get("args") or {},
        }
        payload = {
            "tool_call_id": event.get("toolCallId"),
            "tool_name": event.get("toolName"),
            "arguments": event.get("args"),
        }
        self.writer.append("tool.started", payload)

    def _tool_finished(self, event: dict) -> None:
        pending = self.pending_tools.pop(event.get("toolCallId"), {})
        is_error = bool(event.get("isError"))
        if is_error:
            self.tool_failures += 1
        payload = {
            "tool_call_id": event.get("toolCallId"),
            "tool_name": event.get("toolName") or pending.get("tool_name"),
            "arguments": event.get("args") or pending.get("arguments") or {},
            "is_error": is_error,
            "result": event.get("result"),
        }
        self.writer.append("tool.finished", payload)
        self._tool_effect(event, payload)

    def _tool_effect(self, event: dict, payload: dict) -> None:
        tool_name = str(payload.get("tool_name", "")).lower()
        arguments = payload["arguments"]
        if tool_name in {"write", "edit"}:
            file_payload = {
                "tool_name": tool_name,
                "path": arguments.get("path"),
                "is_error": payload["is_error"],
            }
            self.writer.append("file.changed", file_payload)
        if tool_name not in {"bash", "shell", "exec"}:
            return

        command = str(arguments.get("command") or arguments.get("cmd") or "")
        command_payload = {
            "command": command,
            "is_error": payload["is_error"],
            "result": payload["result"],
        }
        self.writer.append("command.finished", command_payload)
        if TEST_COMMAND.search(command):
            self.writer.append("test.finished", command_payload)
        if DEPENDENCY_COMMAND.search(command):
            self.writer.append("dependency.installed", command_payload)
            self.writer.append("network.requested", command_payload)
        elif NETWORK_COMMAND.search(command):
            self.writer.append("network.requested", command_payload)


def _text_content(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    texts = [str(block.get("text", "")) for block in content if block.get("type") == "text"]

    return "\n".join(texts)
