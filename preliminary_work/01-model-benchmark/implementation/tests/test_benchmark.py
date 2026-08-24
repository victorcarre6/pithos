import json
import asyncio
import sqlite3
import urllib.error
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pithos_benchmark.ollama as ollama_module
from pithos_benchmark.dashboard import create_app
from pithos_benchmark.engine import BenchmarkConfiguration, BenchmarkEngine, _native_measurements
from pithos_benchmark.ollama import OllamaClient, OllamaError
from pithos_benchmark.scenarios import Scenario, evaluate, load_scenarios
from pithos_benchmark.tui import BenchmarkApp


class FakeOllama:
    def __init__(self, speed=2.0):
        self.speed = speed
        self.unloads = []

    def version(self):
        return {"version": "test"}

    def models(self):
        return [{"name": "fixture:latest", "size": 1234, "digest": "sha256:test"}]

    def running_models(self):
        return []

    def show(self, model):
        return {"model_info": {"fixture.context_length": 8192}}

    def assert_installed(self, model):
        if model != "fixture:latest":
            raise OllamaError("missing")

    def unload(self, model):
        self.unloads.append(model)
        return {"done": True}

    def chat(self, model, messages, timeout, format_schema=None, tools=None, options=None, on_chunk=None):
        eval_duration = int(2 / self.speed * 1_000_000_000)
        request = {
            "model": model,
            "messages": messages,
            "format": format_schema,
            "tools": tools,
            "options": options,
        }
        response = {
            "message": {"content": "PITHOS_TEXT_OK"},
            "eval_count": 2,
            "eval_duration": eval_duration,
            "prompt_eval_count": 4,
            "prompt_eval_duration": 1_000_000_000,
            "client_duration_seconds": 0.01,
            "done_reason": "stop",
        }
        if on_chunk:
            on_chunk(response)

        return request, response


class StreamResponse:
    def __init__(self, chunks):
        self.chunks = [json.dumps(chunk).encode() + b"\n" for chunk in chunks]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def __iter__(self):
        return iter(self.chunks)


def _scenario(path, suite="smoke"):
    path.write_text(
        "\n".join(
            [
                "version: 1",
                "id: native.text-exact",
                "title: Exact text",
                f"suite: {suite}",
                "kind: native",
                "messages:",
                "  - role: user",
                "    content: Reply exactly.",
                "expected:",
                "  exact_text: PITHOS_TEXT_OK",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_native_measurements_preserve_counts_and_rates():
    measurements = _native_measurements(
        {
            "eval_count": 4,
            "eval_duration": 2_000_000_000,
            "prompt_eval_count": 6,
            "prompt_eval_duration": 3_000_000_000,
        }
    )

    assert measurements["decode_tokens_per_second"] == 2
    assert measurements["prompt_tokens_per_second"] == 2
    assert measurements["eval_count"] == 4


def test_ollama_client_aggregates_stream_and_preserves_chunks():
    chunks = [
        {"message": {"thinking": "check "}, "done": False},
        {"message": {"content": "PITHOS_"}, "done": False},
        {
            "message": {"content": "TEXT_OK"},
            "done": True,
            "eval_count": 2,
            "eval_duration": 1_000_000_000,
        },
    ]
    client = OllamaClient(opener=lambda request, timeout: StreamResponse(chunks))

    request, response = client.chat("fixture", [{"role": "user", "content": "test"}], 10)

    assert request["stream"] is True
    assert response["message"]["content"] == "PITHOS_TEXT_OK"
    assert response["message"]["thinking"] == "check "
    assert response["stream_chunk_count"] == 3
    assert response["stream_chunks"] == chunks


def test_ollama_client_preserves_http_error_detail():
    def fail(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            500,
            "Internal Server Error",
            {},
            BytesIO(b'{"error":"model architecture is unsupported"}'),
        )

    client = OllamaClient(opener=fail)

    with pytest.raises(OllamaError, match="HTTP 500: model architecture is unsupported"):
        client.chat("fixture", [{"role": "user", "content": "test"}], 10)


def test_ollama_client_enforces_wall_clock_timeout(monkeypatch):
    chunks = [
        {"message": {"thinking": "still working"}, "done": False},
        {"message": {"content": "too late"}, "done": True},
    ]
    times = iter((0.0, 0.5))
    monkeypatch.setattr(ollama_module, "monotonic", lambda: next(times))
    client = OllamaClient(opener=lambda request, timeout: StreamResponse(chunks))

    with pytest.raises(OllamaError, match="exceeded 0.5 second wall-clock timeout"):
        client.chat("fixture", [{"role": "user", "content": "test"}], 0.5)


def test_scenario_evaluates_exact_json_and_native_tool():
    structured = Scenario("json", "JSON", "protocol", "native", 10, [], {"json": {"status": "ok"}})
    tool = Scenario(
        "tool",
        "Tool",
        "protocol",
        "native",
        10,
        [],
        {"tool": {"name": "read_fixture", "arguments": {"path": "fixture.txt"}}},
    )

    assert evaluate(structured, {"message": {"content": '{"status":"ok"}'}})[0] is True
    response = {
        "message": {
            "tool_calls": [
                {"function": {"name": "read_fixture", "arguments": {"path": "fixture.txt"}}}
            ]
        }
    }
    assert evaluate(tool, response)[0] is True


def test_engine_runs_three_attempts_projects_and_exports(tmp_path):
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    _scenario(scenarios / "text.yaml")
    results = tmp_path / "versioned"
    configuration = BenchmarkConfiguration(
        model="fixture:latest",
        logs_root=tmp_path / "logs",
        scenarios_root=scenarios,
        results_root=results,
    )
    client = FakeOllama()

    manifest = BenchmarkEngine(configuration, client=client).run()
    campaign_root = tmp_path / "logs" / "benchmarks" / manifest["campaign_id"]

    assert manifest["summary"]["attempts"] == 3
    assert manifest["summary"]["passed"] == 3
    assert "timeout_override_seconds" in manifest
    assert client.unloads == ["fixture:latest"]
    assert len(list(campaign_root.glob("attempts/*/*/result.json"))) == 3
    pi_models = json.loads((campaign_root / "pi-config" / "models.json").read_text(encoding="utf-8"))
    assert pi_models["providers"]["ollama"]["models"][0]["id"] == "fixture:latest"
    assert pi_models["providers"]["ollama"]["models"][0]["contextWindow"] == 8192
    assert (results / manifest["campaign_id"] / "manifest.json").is_file()
    assert not (results / manifest["campaign_id"] / "benchmark.db").exists()
    exported_events = (results / manifest["campaign_id"] / "events.jsonl").read_text(encoding="utf-8")
    assert '"type":"campaign.finished"' in exported_events
    index = json.loads((results.parent / "index.json").read_text(encoding="utf-8"))
    assert index["campaigns"][0]["campaign_id"] == manifest["campaign_id"]
    with sqlite3.connect(campaign_root / "benchmark.db") as connection:
        assert connection.execute("SELECT count(*) FROM attempts").fetchone()[0] == 3


def test_engine_retains_failed_attempts(tmp_path):
    scenarios = tmp_path / "scenarios"
    scenarios.mkdir()
    _scenario(scenarios / "text.yaml")
    client = FakeOllama()
    original_chat = client.chat

    def wrong_chat(*args, **kwargs):
        request, response = original_chat(*args, **kwargs)
        response["message"]["content"] = "wrong"

        return request, response

    client.chat = wrong_chat
    configuration = BenchmarkConfiguration("fixture:latest", tmp_path / "logs", scenarios)

    manifest = BenchmarkEngine(configuration, client=client).run()

    assert manifest["summary"]["failed"] == 3


def test_expensive_suite_is_not_skipped_without_a_speed_measurement(tmp_path):
    configuration = BenchmarkConfiguration("fixture:latest", tmp_path / "logs", tmp_path)
    engine = BenchmarkEngine(configuration, client=FakeOllama())
    scenario = Scenario("agentic.test", "Agentic", "agentic", "pi", 10, [], {})

    assert engine._should_skip(scenario) is False


def test_dashboard_lists_attempts_and_rejects_traversal(tmp_path):
    campaign = tmp_path / "benchmarks" / "benchmark-safe"
    attempt = campaign / "attempts" / "text" / "attempt-1"
    attempt.mkdir(parents=True)
    manifest = {
        "campaign_id": "benchmark-safe",
        "model": "fixture:latest",
        "suite": "smoke",
        "summary": {"attempts": 1, "passed": 1},
    }
    (campaign / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (campaign / "summary.json").write_text(json.dumps(manifest["summary"]), encoding="utf-8")
    (attempt / "result.json").write_text(json.dumps({"attempt_id": "one"}), encoding="utf-8")
    client = TestClient(create_app(tmp_path))

    assert client.get("/api/campaigns").json()["count"] == 1
    assert len(client.get("/api/campaigns/benchmark-safe").json()["attempts"]) == 1
    assert client.get("/api/campaigns/benchmark-safe/artifact/../../manifest.json").status_code == 404


def test_dashboard_reads_versioned_copy_when_logs_are_absent(tmp_path):
    versioned = tmp_path / "versioned" / "benchmark-git"
    versioned.mkdir(parents=True)
    manifest = {
        "campaign_id": "benchmark-git",
        "model": "fixture:latest",
        "suite": "smoke",
        "summary": {"attempts": 0, "passed": 0},
    }
    (versioned / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (versioned / "summary.json").write_text(json.dumps(manifest["summary"]), encoding="utf-8")
    client = TestClient(create_app(tmp_path / "missing-logs", versioned.parent))

    assert client.get("/api/health").json()["data"] == "available"
    assert client.get("/api/campaigns").json()["items"][0]["campaign_id"] == "benchmark-git"


def test_loader_rejects_duplicate_scenario_ids(tmp_path):
    _scenario(tmp_path / "one.yaml")
    _scenario(tmp_path / "two.yaml")

    with pytest.raises(ValueError, match="unique"):
        load_scenarios(tmp_path, "full")


def test_context_suite_generates_payload_and_stays_out_of_standard_full(tmp_path):
    (tmp_path / "context.yaml").write_text(
        (
            "version: 1\n"
            "id: context.004k\n"
            "title: Context\n"
            "suite: context\n"
            "kind: native\n"
            "synthetic_tokens: 10\n"
            "options:\n"
            "  num_ctx: 4096\n"
            "messages:\n"
            "  - role: user\n"
            "    content: generated\n"
            "expected:\n"
            "  exact_text: PITHOS_CONTEXT_OK\n"
        ),
        encoding="utf-8",
    )

    context = load_scenarios(tmp_path, "context")

    assert load_scenarios(tmp_path, "full") == []
    assert context[0].messages[0]["content"].count("a ") == 10
    assert context[0].options == {"num_ctx": 4096}


def test_tui_renders_live_attempt_and_resource_sample(tmp_path):
    class Storage:
        campaign_root = tmp_path / "campaign"

    class Engine:
        campaign_id = "benchmark-tui"
        configuration = type("Configuration", (), {"model": "fixture:latest", "attempts": 1})()
        results = []
        storage = Storage()
        on_event = None

        def run(self):
            self.on_event(
                {
                    "timestamp": "2026-08-23T12:00:00+00:00",
                    "type": "campaign.started",
                    "payload": {"model": "fixture:latest", "scenario_count": 1},
                }
            )
            self.on_event(
                {
                    "timestamp": "2026-08-23T12:00:01+00:00",
                    "type": "resource.sample",
                    "payload": {"cpu_percent": 12.5, "memory_percent": 50.0, "swap_percent": 2.0},
                }
            )
            result = {
                "scenario_id": "native.text-exact",
                "attempt_number": 1,
                "passed": True,
                "duration_seconds": 1.5,
                "decode_tokens_per_second": 2.0,
            }
            self.results.append(result)
            self.on_event(
                {
                    "timestamp": "2026-08-23T12:00:02+00:00",
                    "type": "attempt.finished",
                    "payload": result,
                }
            )

            return {"summary": {"passed": 1, "failed": 0}}

        def request_stop(self):
            pass

    async def exercise():
        app = BenchmarkApp(Engine())
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(0.2)

            assert app.query_one("#attempts").row_count == 1
            assert "50.0%" in str(app.query_one("#metric-values").render())
            assert "CAMPAIGN COMPLETE" in str(app.query_one("#current").render())

    asyncio.run(exercise())
