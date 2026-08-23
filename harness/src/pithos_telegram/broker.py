"""Validate, deliver and journal the narrow Telegram capability."""

import json
import re
import time
from collections import deque
from pathlib import Path

from pithos_runner.events import EventWriter
from pithos_runner.state import read_state, write_state


MESSAGE_PREFIXES = {
    "INFO": "[INFO]",
    "WARNING": "[WARNING]",
    "QUESTION": "[QUESTION]",
    "STOP_PROPOSAL": "[STOP_PROPOSAL]",
    "EMERGENCY": "[EMERGENCY]",
}
LOOP_WARNING = "[WARNING] Boucle récursive infinie détectée."
RUN_ID_PATTERN = re.compile(r"^run-[0-9]{8}T[0-9]{6}Z-[a-z0-9]{6}$")


class TelegramBroker:
    """Expose one recipient and a fixed set of messages and commands."""

    def __init__(self, api, user_id: str, logs_root: Path, rate_limit: int = 10) -> None:
        if not user_id.strip():
            raise ValueError("Telegram user id is required")

        self.api = api
        self.user_id = user_id.strip()
        self.logs_root = logs_root
        self.rate_limit = rate_limit
        self.sent_at = deque()
        self.seen_requests = set()
        self.seen_updates = set()
        self.offset_path = logs_root / "runtime" / "telegram-offset.json"
        self.answers_path = logs_root / "runtime" / "answers.jsonl"
        self.requests_path = logs_root / "runtime" / "telegram-requests.jsonl"
        self.updates_path = logs_root / "runtime" / "telegram-updates.jsonl"
        if self.requests_path.exists():
            for line in self.requests_path.read_text(encoding="utf-8").splitlines():
                request = json.loads(line)
                if request.get("result") == "sent":
                    self.seen_requests.add(request["request_id"])
        if self.updates_path.exists():
            for line in self.updates_path.read_text(encoding="utf-8").splitlines():
                self.seen_updates.add(int(json.loads(line)["update_id"]))

    def send(self, request: dict) -> dict:
        """Deliver one idempotent, rate-limited message to the configured user."""

        request_id = str(request.get("request_id", "")).strip()
        run_id = str(request.get("run_id", "")).strip()
        kind = str(request.get("kind", ""))
        text = str(request.get("text", "")).strip()
        if not request_id or not run_id or kind not in MESSAGE_PREFIXES or not text:
            raise ValueError("request_id, run_id, allowed kind and text are required")
        if request_id in self.seen_requests:
            return {"ok": True, "duplicate": True}

        now = time.monotonic()
        while self.sent_at and now - self.sent_at[0] >= 60:
            self.sent_at.popleft()
        if len(self.sent_at) >= self.rate_limit:
            raise RuntimeError("Telegram rate limit reached")

        message = f"{MESSAGE_PREFIXES[kind]} {text}"
        try:
            result = self.api.send(self.user_id, message)
        except RuntimeError:
            self._append_record(
                self.requests_path,
                {"request_id": request_id, "run_id": run_id, "result": "failed"},
            )
            self._event(run_id, "telegram.failed", {"kind": kind, "request_id": request_id})
            raise
        self.sent_at.append(now)
        self.seen_requests.add(request_id)
        self._append_record(
            self.requests_path,
            {"request_id": request_id, "run_id": run_id, "result": "sent"},
        )
        self._event(run_id, "telegram.sent", {"kind": kind, "request_id": request_id})

        return {"ok": True, "duplicate": False, "message_id": result.get("message_id")}

    def handle_update(self, update: dict) -> dict:
        """Apply one allowlisted command once and attribute it to its update id."""

        update_id = int(update["update_id"])
        if update_id in self.seen_updates:
            return {"ok": True, "duplicate": True, "update_id": update_id}
        self.seen_updates.add(update_id)
        self._append_record(
            self.updates_path,
            {"update_id": update_id, "command": None, "result": "claimed"},
        )
        message = update.get("message") or {}
        sender = str((message.get("from") or {}).get("id", ""))
        chat = str((message.get("chat") or {}).get("id", ""))
        text = str(message.get("text", "")).strip()
        if sender != self.user_id or chat != self.user_id:
            self._append_record(
                self.updates_path,
                {"update_id": update_id, "command": None, "result": "unauthorized"},
            )
            return {"ok": False, "reason": "unauthorized"}

        command, _, arguments = text.partition(" ")
        if command == "/status":
            response = json.dumps(read_state(self.logs_root / "runtime" / "state.json"))
        elif command == "/latest":
            latest = self.logs_root / "latest.md"
            response = latest.read_text(encoding="utf-8")[-3500:] if latest.exists() else "No report."
        elif command in {"/pause", "/stop"}:
            reason = f"{command[1:]} requested by Telegram update {update_id}"
            write_state(self.logs_root / "runtime" / "state.json", True, reason)
            response = reason
        elif command == "/answer":
            run_id, separator, answer = arguments.partition(" ")
            if not separator or not RUN_ID_PATTERN.fullmatch(run_id) or not answer.strip():
                return {"ok": False, "reason": "usage: /answer <run_id> <message>"}
            self.answers_path.parent.mkdir(parents=True, exist_ok=True)
            record = {"update_id": update_id, "run_id": run_id, "answer": answer.strip()}
            with self.answers_path.open("a", encoding="utf-8") as answers:
                answers.write(json.dumps(record, separators=(",", ":")) + "\n")
                answers.flush()
            response = f"Answer recorded for {run_id}."
            self._event(
                run_id,
                "telegram.answer",
                {"update_id": update_id, "answer": answer.strip()},
            )
        else:
            self._append_record(
                self.updates_path,
                {"update_id": update_id, "command": command, "result": "unsupported"},
            )
            return {"ok": False, "reason": "unsupported command"}

        self.api.send(self.user_id, response)
        self._append_record(
            self.updates_path,
            {"update_id": update_id, "command": command, "result": "applied"},
        )

        return {"ok": True, "update_id": update_id}

    def poll_once(self) -> int:
        offset = self._read_offset()
        for update in self.api.updates(offset):
            update_id = int(update["update_id"])
            self.handle_update(update)
            offset = max(offset, update_id + 1)
            self._write_offset(offset)

        return offset

    def _event(self, run_id: str, event_type: str, payload: dict) -> None:
        path = self.logs_root / "runs" / run_id / "events.jsonl"
        EventWriter(path, run_id, source="telegram-broker").append(event_type, payload)

    def _read_offset(self) -> int:
        try:
            return int(json.loads(self.offset_path.read_text())["offset"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            return 0

    def _write_offset(self, offset: int) -> None:
        self.offset_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.offset_path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"offset": offset}) + "\n")
        temporary.replace(self.offset_path)

    def _append_record(self, path: Path, record: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record, separators=(",", ":")) + "\n")
            output.flush()
