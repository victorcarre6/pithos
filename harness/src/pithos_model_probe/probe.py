"""Probe text generation, structured output, roles and tool calling."""

import platform
from datetime import UTC, datetime
from typing import Callable

from .client import OllamaClient, ProbeResponse


def _timings(response: ProbeResponse) -> dict:
    body = response.body
    eval_count = body.get("eval_count", 0)
    eval_duration = body.get("eval_duration", 0)
    decode_tokens_per_second = None

    if eval_count and eval_duration:
        decode_tokens_per_second = eval_count / (eval_duration / 1_000_000_000)

    return {
        "client_elapsed_seconds": round(response.elapsed_seconds, 3),
        "total_duration_ns": body.get("total_duration"),
        "load_duration_ns": body.get("load_duration"),
        "prompt_eval_count": body.get("prompt_eval_count"),
        "prompt_eval_duration_ns": body.get("prompt_eval_duration"),
        "eval_count": eval_count,
        "eval_duration_ns": eval_duration,
        "decode_tokens_per_second": round(decode_tokens_per_second, 3) if decode_tokens_per_second else None,
    }


def _result(name: str, response: ProbeResponse, passed: bool, evidence: dict) -> dict:
    timings = _timings(response)
    decode_speed = timings["decode_tokens_per_second"]

    return {
        "name": name,
        "passed": passed,
        "speed_passed": decode_speed is None or decode_speed >= 1.0,
        "timings": timings,
        "evidence": evidence,
        "raw_response": response.body,
    }


def probe_text(client: OllamaClient, model: str) -> dict:
    response = client.post(
        "/api/chat",
        {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: PITHOS_TEXT_OK"}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 32},
        },
    )
    content = response.body.get("message", {}).get("content", "").strip()

    return _result("text", response, content == "PITHOS_TEXT_OK", {"content": content})


def probe_developer_role(client: OllamaClient, model: str) -> dict:
    response = client.post(
        "/api/chat",
        {
            "model": model,
            "messages": [
                {"role": "developer", "content": "Reply with exactly: PITHOS_DEVELOPER_OK"},
                {"role": "user", "content": "Follow the developer instruction."},
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 32},
        },
    )
    content = response.body.get("message", {}).get("content", "").strip()

    return _result("developer_role", response, content == "PITHOS_DEVELOPER_OK", {"content": content})


def probe_structured_output(client: OllamaClient, model: str) -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["status", "value"],
        "properties": {
            "status": {"const": "ok"},
            "value": {"const": 42},
        },
    }
    response = client.post(
        "/api/chat",
        {
            "model": model,
            "messages": [{"role": "user", "content": "Return the requested object."}],
            "format": schema,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 64},
        },
    )
    content = response.body.get("message", {}).get("content", "")
    parsed = None

    try:
        import json

        parsed = json.loads(content)
    except (TypeError, ValueError):
        pass

    passed = parsed == {"status": "ok", "value": 42}

    return _result("structured_output", response, passed, {"content": content, "parsed": parsed})


def probe_tool_call(client: OllamaClient, model: str) -> dict:
    response = client.post(
        "/api/chat",
        {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": "Call record_probe exactly once with value 42. Do not answer in plain text.",
                }
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "record_probe",
                        "description": "Record the probe integer.",
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["value"],
                            "properties": {"value": {"type": "integer"}},
                        },
                    },
                }
            ],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 128},
        },
    )
    message = response.body.get("message", {})
    tool_calls = message.get("tool_calls", [])
    matching_calls = [
        call
        for call in tool_calls
        if call.get("function", {}).get("name") == "record_probe"
        and call.get("function", {}).get("arguments") == {"value": 42}
    ]
    passed = len(tool_calls) == 1 and len(matching_calls) == 1

    return _result(
        "tool_call",
        response,
        passed,
        {
            "content": message.get("content", ""),
            "tool_calls": tool_calls,
        },
    )


def run_probe(
    client: OllamaClient,
    model: str,
    on_progress: Callable[[dict], None] | None = None,
    previous_result: dict | None = None,
) -> dict:
    """Run non-destructive API probes and checkpoint after every scenario."""

    version = client.get("/api/version").body
    model_processes_before = client.get("/api/ps").body
    result = previous_result or {
        "schema_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model,
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
        "ollama": version,
        "model_processes_before": model_processes_before,
        "model_processes_after": None,
        "complete": False,
        "passed": False,
        "minimum_decode_tokens_per_second": 1.0,
        "scenarios": [],
    }

    probes = [
        ("text", probe_text),
        ("developer_role", probe_developer_role),
        ("structured_output", probe_structured_output),
        ("tool_call", probe_tool_call),
    ]
    for scenario in result["scenarios"]:
        timings = scenario.get("timings") or {}
        decode_speed = timings.get("decode_tokens_per_second")
        scenario.setdefault("speed_passed", decode_speed is None or decode_speed >= 1.0)

    completed_names = {scenario["name"] for scenario in result["scenarios"]}

    for name, probe in probes:
        if name in completed_names:
            continue

        try:
            scenario = probe(client, model)
        except RuntimeError as error:
            scenario = {
                "name": name,
                "passed": False,
                "speed_passed": False,
                "timings": None,
                "evidence": {"error": str(error)},
                "raw_response": None,
            }

        result["scenarios"].append(scenario)
        if on_progress:
            on_progress(result)

    result["model_processes_after"] = client.get("/api/ps").body
    result["complete"] = True
    result["passed"] = all(
        scenario["passed"] and scenario["speed_passed"]
        for scenario in result["scenarios"]
    )
    if on_progress:
        on_progress(result)

    return result
