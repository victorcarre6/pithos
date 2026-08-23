import json
import os
import socket
import threading
import uuid
from pathlib import Path

import pytest

from pithos_runner.state import read_state
from pithos_telegram.broker import LOOP_WARNING, TelegramBroker
from pithos_telegram.server import TelegramBrokerServer


RUN_ID = "run-20260823T120000Z-a1b2c3"


class FakeAPI:
    def __init__(self):
        self.messages = []
        self.pending = []

    def send(self, user_id, text):
        self.messages.append((user_id, text))
        return {"message_id": len(self.messages)}

    def updates(self, offset):
        return [update for update in self.pending if update["update_id"] >= offset]


def _update(update_id, text, user_id="42"):
    return {
        "update_id": update_id,
        "message": {"from": {"id": int(user_id)}, "chat": {"id": int(user_id)}, "text": text},
    }


def test_allowed_message_is_sent_once_and_journaled_without_recipient(tmp_path):
    api = FakeAPI()
    broker = TelegramBroker(api, "42", tmp_path)
    request = {"request_id": "request-1", "run_id": RUN_ID, "kind": "WARNING", "text": "Blocked."}

    first = broker.send(request)
    duplicate = broker.send(request)

    assert first["message_id"] == 1
    assert duplicate["duplicate"] is True
    assert api.messages == [("42", "[WARNING] Blocked.")]
    event = json.loads((tmp_path / "runs" / RUN_ID / "events.jsonl").read_text())
    assert event["payload"] == {"kind": "WARNING", "request_id": "request-1"}
    assert "user_id" not in event["payload"]
    assert "recipient" not in event["payload"]

    restarted = TelegramBroker(api, "42", tmp_path)
    assert restarted.send(request)["duplicate"] is True


def test_unknown_kind_and_rate_excess_are_refused(tmp_path):
    broker = TelegramBroker(FakeAPI(), "42", tmp_path, rate_limit=1)

    with pytest.raises(ValueError, match="allowed kind"):
        broker.send({"request_id": "a", "run_id": RUN_ID, "kind": "RAW", "text": "x"})
    broker.send({"request_id": "b", "run_id": RUN_ID, "kind": "INFO", "text": "x"})
    with pytest.raises(RuntimeError, match="rate limit"):
        broker.send({"request_id": "c", "run_id": RUN_ID, "kind": "INFO", "text": "y"})


def test_unauthorized_user_and_resume_are_refused(tmp_path):
    api = FakeAPI()
    broker = TelegramBroker(api, "42", tmp_path)

    assert broker.handle_update(_update(1, "/pause", "99"))["reason"] == "unauthorized"
    assert broker.handle_update(_update(2, "/resume"))["reason"] == "unsupported command"
    assert api.messages == []


def test_pause_stop_latest_status_and_answer_use_controlled_paths(tmp_path):
    api = FakeAPI()
    broker = TelegramBroker(api, "42", tmp_path)
    (tmp_path / "latest.md").write_text("latest report")

    broker.handle_update(_update(1, "/pause"))
    broker.handle_update(_update(2, "/status"))
    broker.handle_update(_update(3, "/latest"))
    broker.handle_update(_update(4, f"/answer {RUN_ID} proceed"))
    broker.handle_update(_update(5, "/stop"))

    state = read_state(tmp_path / "runtime" / "state.json")
    assert state["paused"] is True
    assert "stop requested" in state["reason"]
    assert "latest report" in api.messages[2][1]
    answer = json.loads((tmp_path / "runtime" / "answers.jsonl").read_text())
    assert answer["answer"] == "proceed"


def test_poll_offset_makes_updates_idempotent_across_restarts(tmp_path):
    api = FakeAPI()
    api.pending = [_update(10, "/pause")]
    TelegramBroker(api, "42", tmp_path).poll_once()
    TelegramBroker(api, "42", tmp_path).poll_once()

    assert len(api.messages) == 1


def test_direct_duplicate_update_is_claimed_before_a_second_action(tmp_path):
    api = FakeAPI()
    broker = TelegramBroker(api, "42", tmp_path)
    update = _update(20, "/pause")

    first = broker.handle_update(update)
    duplicate = broker.handle_update(update)

    assert first["ok"] is True
    assert duplicate["duplicate"] is True
    assert len(api.messages) == 1


def test_loop_warning_has_exact_contract():
    assert LOOP_WARNING == "[WARNING] Boucle récursive infinie détectée."


def test_socket_exposes_only_validated_requests_with_private_permissions(tmp_path):
    api = FakeAPI()
    broker = TelegramBroker(api, "42", tmp_path)
    socket_path = Path("/private/tmp") / f"pithos-telegram-{uuid.uuid4().hex[:8]}.sock"
    request = {"request_id": "socket-1", "run_id": RUN_ID, "kind": "INFO", "text": "Ready."}

    with TelegramBrokerServer(socket_path, broker) as server:
        thread = threading.Thread(target=server.handle_request)
        thread.start()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path))
            client.sendall(json.dumps(request).encode() + b"\n")
            response = json.loads(client.makefile().readline())
        thread.join()

        assert response["ok"] is True
        assert os.stat(socket_path).st_mode & 0o777 == 0o600
