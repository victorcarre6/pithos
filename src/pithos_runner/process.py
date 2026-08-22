"""Monitor a process group, stream its logs and detect recursive tool loops."""

import json
import os
import queue
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class MonitoredOutcome:
    """Describe why a monitored process stopped."""

    exit_code: int | None
    timed_out: bool
    loop_detected: bool
    externally_stopped: bool
    repeated_signature: str | None


def _stream_reader(name: str, stream, output_queue: queue.Queue) -> None:
    try:
        for line in iter(stream.readline, ""):
            output_queue.put((name, line))
    finally:
        output_queue.put((name, None))


def _tool_signature(line: str) -> str | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None
    if event.get("type") != "tool_execution_start":
        return None

    signature = {
        "tool": event.get("toolName"),
        "args": event.get("args"),
    }

    return json.dumps(signature, sort_keys=True, separators=(",", ":"))


def _terminate_group(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return

    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()


def run_monitored(
    command: list[str],
    cwd: Path,
    environment: dict[str, str],
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
    repeat_limit: int,
    heartbeat_seconds: float = 30,
    on_heartbeat: Callable[[], None] | None = None,
    stop_requested: Callable[[], bool] | None = None,
    on_loop_detected: Callable[[], None] | None = None,
) -> MonitoredOutcome:
    """Stream a child group until completion, timeout or repeated identical tools."""

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )
    output_queue = queue.Queue()
    streams = {
        "stdout": (process.stdout, stdout_path),
        "stderr": (process.stderr, stderr_path),
    }
    for name, (stream, _) in streams.items():
        thread = threading.Thread(target=_stream_reader, args=(name, stream, output_queue), daemon=True)
        thread.start()

    started_at = time.monotonic()
    next_heartbeat = started_at + heartbeat_seconds
    closed_streams = set()
    last_signature = None
    repeat_count = 0
    timed_out = False
    loop_detected = False
    externally_stopped = False

    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        files = {"stdout": stdout_file, "stderr": stderr_file}

        while len(closed_streams) < len(streams):
            now = time.monotonic()
            if on_heartbeat and now >= next_heartbeat and process.poll() is None:
                on_heartbeat()
                next_heartbeat = now + heartbeat_seconds
            if now - started_at >= timeout_seconds:
                timed_out = True
                _terminate_group(process)
            if stop_requested and stop_requested() and process.poll() is None:
                externally_stopped = True
                _terminate_group(process)

            try:
                name, line = output_queue.get(timeout=0.25)
            except queue.Empty:
                if process.poll() is not None and timed_out:
                    continue
                continue

            if line is None:
                closed_streams.add(name)
                continue

            files[name].write(line)
            files[name].flush()

            if name != "stdout":
                continue
            signature = _tool_signature(line)
            if signature is None:
                continue
            if signature == last_signature:
                repeat_count += 1
            else:
                last_signature = signature
                repeat_count = 1
            if repeat_count >= repeat_limit:
                loop_detected = True
                if on_loop_detected:
                    try:
                        on_loop_detected()
                    except (OSError, RuntimeError):
                        pass
                _terminate_group(process)

    if process.poll() is None:
        process.wait()

    interrupted = timed_out or loop_detected or externally_stopped
    exit_code = None if interrupted else process.returncode

    return MonitoredOutcome(
        exit_code,
        timed_out,
        loop_detected,
        externally_stopped,
        last_signature if loop_detected else None,
    )
