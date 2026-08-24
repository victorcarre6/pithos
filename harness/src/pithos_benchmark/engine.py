"""Benchmark campaign orchestration and permissive gates."""

import json
import re
import statistics
import threading
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pithos_capability_probe.runner import PiConfiguration, run_scenario
from pithos_capability_probe.scenarios import SCENARIOS

from .ollama import OllamaClient, OllamaError
from .endurance import ENDURANCE_SCENARIO
from .resources import ResourceSampler, environment_snapshot
from .scenarios import evaluate, load_scenarios
from .storage import BenchmarkStorage


def _utc_now():
    """Return a timezone-aware ISO timestamp."""

    return datetime.now(timezone.utc).isoformat()


def _campaign_id(model):
    """Build one sortable filesystem-safe campaign identifier."""

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")

    return f"benchmark-{timestamp}-{slug}-{uuid4().hex[:6]}"


@dataclass(frozen=True)
class BenchmarkConfiguration:
    """Inputs that make one benchmark campaign interpretable."""

    model: str
    logs_root: Path
    scenarios_root: Path
    results_root: Path | None = None
    suite: str = "full"
    attempts: int = 3
    minimum_tokens_per_second: float = 0.05
    ollama_url: str = "http://127.0.0.1:11434"
    pi_config_dir: Path | None = None
    pi_executable: str = "pi"
    timeout_override_seconds: int | None = None


class BenchmarkEngine:
    """Run scenarios, retain failures and export complete evidence."""

    def __init__(self, configuration: BenchmarkConfiguration, client=None, on_event=None):
        self.configuration = configuration
        self.client = client or OllamaClient(configuration.ollama_url)
        self.on_event = on_event or (lambda event: None)
        self.campaign_id = _campaign_id(configuration.model)
        self.storage = None
        self.results = []
        self._stop = threading.Event()

    def request_stop(self):
        """Stop safely before the next attempt without discarding the active one."""

        self._stop.set()

    def run(self):
        """Execute one bounded campaign and return its final manifest."""

        configuration = self.configuration
        self.client.assert_installed(configuration.model)
        try:
            return self._run_campaign()
        finally:
            self.client.unload(configuration.model)

    def _run_campaign(self):
        """Run the campaign body while `run` owns final model eviction."""

        configuration = self.configuration
        scenarios = load_scenarios(configuration.scenarios_root, configuration.suite)
        self.storage = BenchmarkStorage(configuration.logs_root, self.campaign_id)
        started_at = _utc_now()
        environment = environment_snapshot()
        environment["ollama"] = self.client.version()
        environment["installed_model"] = self._model_metadata()
        environment["ollama_show"] = self.client.show(configuration.model)
        environment["resident_models_before"] = self.client.running_models()
        self.storage.write_json("environment.json", environment)
        self._prepare_pi_config(environment["ollama_show"])
        self._clear_resident_models(environment["resident_models_before"])

        self._emit("campaign.started", {"model": configuration.model, "scenario_count": len(scenarios)})
        for scenario in scenarios:
            if self._stop.is_set():
                break
            if self._should_skip(scenario):
                self._emit("scenario.skipped", {"scenario_id": scenario.id, "reason": "speed gate"})
                continue
            self._run_scenario(scenario)

        manifest = self._manifest(started_at, scenarios)
        self.storage.write_json("manifest.json", manifest)
        self.storage.write_json("summary.json", self._summary())
        self._write_markdown_summary(manifest)
        self._emit("campaign.finished", {"status": manifest["status"]})
        self.storage.project()
        if configuration.results_root:
            self.storage.export(configuration.results_root)

        return manifest

    def _run_scenario(self, scenario):
        """Run all requested attempts for one scenario."""

        self._emit(
            "scenario.started",
            {"scenario_id": scenario.id, "title": scenario.title, "suite": scenario.suite},
        )
        for attempt_number in range(1, self.configuration.attempts + 1):
            if self._stop.is_set():
                self._emit("scenario.stopped", {"scenario_id": scenario.id, "reason": "safe stop requested"})
                break
            attempt_id = f"{scenario.id}-a{attempt_number}"
            relative_root = Path("attempts") / scenario.id / f"attempt-{attempt_number}"
            self._emit(
                "attempt.started",
                {"scenario_id": scenario.id, "attempt": attempt_number, "attempt_id": attempt_id},
            )
            if scenario.kind == "native":
                result = self._run_native(scenario, attempt_id, attempt_number, relative_root)
            elif scenario.kind == "pi":
                result = self._run_pi(scenario, attempt_id, attempt_number, relative_root)
            else:
                raise ValueError(f"unsupported scenario kind: {scenario.kind}")
            self.results.append(result)
            self._emit("attempt.finished", result)

    def _run_native(self, scenario, attempt_id, attempt_number, relative_root):
        """Run one native Ollama scenario with resource sampling."""

        root = self.storage.campaign_root / relative_root
        sampler = ResourceSampler(
            root / "resources.jsonl",
            self.client,
            on_sample=lambda sample: self._emit("resource.sample", sample),
        )
        timeout = self.configuration.timeout_override_seconds or scenario.timeout_seconds
        sampler.start()
        error = None
        try:
            request, response = self.client.chat(
                self.configuration.model,
                scenario.messages,
                timeout,
                format_schema=scenario.format_schema,
                tools=scenario.tools,
                options=scenario.options,
                on_chunk=lambda chunk: self.storage.append_json(relative_root / "response.stream.jsonl", chunk),
            )
            passed, evidence = evaluate(scenario, response)
        except Exception as caught:
            request = caught.payload if isinstance(caught, OllamaError) else None
            response = None
            passed = False
            evidence = {}
            error = f"{type(caught).__name__}: {caught}"
        finally:
            sampler.stop()

        if request is not None:
            self.storage.write_json(relative_root / "request.json", request)
        if response is not None:
            self.storage.write_json(relative_root / "response.json", response)
        measurements = _native_measurements(response or {})
        measurements.update(_resource_measurements(root / "resources.jsonl"))
        result = {
            "attempt_id": attempt_id,
            "scenario_id": scenario.id,
            "scenario_version": scenario.version,
            "attempt_number": attempt_number,
            "kind": scenario.kind,
            "passed": passed,
            "error": error,
            "evidence": evidence,
            "duration_seconds": measurements.get("client_duration_seconds"),
            "decode_tokens_per_second": measurements.get("decode_tokens_per_second"),
            "measurements": measurements,
        }
        self.storage.write_json(relative_root / "result.json", result)

        return result

    def _run_pi(self, scenario, attempt_id, attempt_number, relative_root):
        """Run one existing Pi capability scenario and retain external effects."""

        pi_name = scenario.expected["pi_scenario"]
        pi_scenario = ENDURANCE_SCENARIO if pi_name == "benchmark_endurance" else SCENARIOS[pi_name]
        timeout = self.configuration.timeout_override_seconds or scenario.timeout_seconds
        pi_configuration = PiConfiguration(
            executable=self.configuration.pi_executable,
            provider="ollama",
            model=self.configuration.model,
            timeout_seconds=timeout,
            config_dir=self.storage.campaign_root / "pi-config",
        )
        result_root = self.storage.campaign_root / relative_root
        raw = run_scenario(result_root, pi_scenario, pi_configuration)
        passed = raw["process_success"] and raw["protocol_success"] and raw["task_success"]
        result = {
            "attempt_id": attempt_id,
            "scenario_id": scenario.id,
            "scenario_version": scenario.version,
            "attempt_number": attempt_number,
            "kind": scenario.kind,
            "passed": passed,
            "error": None,
            "evidence": raw,
            "duration_seconds": None,
            "decode_tokens_per_second": None,
            "measurements": {},
        }
        self.storage.write_json(relative_root / "result.json", result)

        return result

    def _should_skip(self, scenario):
        """Skip only expensive suites after a clearly impractical speed result."""

        if scenario.suite not in {"agentic", "endurance"}:
            if scenario.suite != "context":
                return False
            context_results = [result for result in self.results if result["scenario_id"].startswith("context.")]
            if not context_results:
                return False
            previous_id = context_results[-1]["scenario_id"]
            previous = [result for result in context_results if result["scenario_id"] == previous_id]

            return len(previous) == self.configuration.attempts and not any(result["passed"] for result in previous)
        speeds = [
            result["decode_tokens_per_second"]
            for result in self.results
            if result["scenario_id"] == "native.text-exact" and result["decode_tokens_per_second"] is not None
        ]
        if not speeds:
            return False

        return statistics.median(speeds) < self.configuration.minimum_tokens_per_second

    def _model_metadata(self):
        """Return the exact installed model record selected for the run."""

        for model in self.client.models():
            name = model.get("name") or model.get("model")
            if name == self.configuration.model:
                return model

        return None

    def _clear_resident_models(self, resident_models):
        """Evict every resident model before the controlled cold phase."""

        for item in resident_models:
            name = item.get("name") or item.get("model")
            if name:
                self.client.unload(name)

    def _prepare_pi_config(self, model_details):
        """Generate a campaign-local Pi catalogue for the selected Ollama model."""

        source = self.configuration.pi_config_dir
        destination = self.storage.campaign_root / "pi-config"
        destination.mkdir()
        settings = source / "settings.json" if source else None
        if settings and settings.is_file():
            shutil.copy2(settings, destination / "settings.json")
        else:
            default_settings = {
                "httpIdleTimeoutMs": 3_600_000,
                "retry": {"enabled": False, "provider": {"timeoutMs": 3_600_000, "maxRetries": 0}},
            }
            (destination / "settings.json").write_text(
                json.dumps(default_settings, indent=2) + "\n",
                encoding="utf-8",
            )
        model_info = model_details.get("model_info") or {}
        context_values = [
            value
            for key, value in model_info.items()
            if key.endswith(".context_length") and isinstance(value, int)
        ]
        context_window = max(context_values, default=4096)
        models = {
            "providers": {
                "ollama": {
                    "baseUrl": f"{self.configuration.ollama_url.rstrip('/')}/v1",
                    "api": "openai-completions",
                    "apiKey": "ollama-local",
                    "models": [
                        {
                            "id": self.configuration.model,
                            "name": f"Benchmark {self.configuration.model}",
                            "reasoning": False,
                            "input": ["text"],
                            "contextWindow": context_window,
                            "maxTokens": min(4096, context_window),
                            "cost": {
                                "input": 0,
                                "output": 0,
                                "cacheRead": 0,
                                "cacheWrite": 0,
                            },
                        }
                    ],
                }
            }
        }
        (destination / "models.json").write_text(json.dumps(models, indent=2) + "\n", encoding="utf-8")

    def _summary(self):
        """Aggregate pass rate and timing without hiding individual attempts."""

        passed = sum(result["passed"] for result in self.results)
        speeds = [result["decode_tokens_per_second"] for result in self.results]
        measured_speeds = [speed for speed in speeds if speed is not None]

        return {
            "attempts": len(self.results),
            "passed": passed,
            "failed": len(self.results) - passed,
            "pass_rate": passed / len(self.results) if self.results else 0,
            "median_decode_tokens_per_second": statistics.median(measured_speeds) if measured_speeds else None,
        }

    def _manifest(self, started_at, scenarios):
        """Describe exact campaign inputs and final state."""

        return {
            "schema_version": 1,
            "campaign_id": self.campaign_id,
            "model": self.configuration.model,
            "suite": self.configuration.suite,
            "attempts_per_scenario": self.configuration.attempts,
            "minimum_tokens_per_second": self.configuration.minimum_tokens_per_second,
            "timeout_override_seconds": self.configuration.timeout_override_seconds,
            "started_at": started_at,
            "finished_at": _utc_now(),
            "status": "stopped" if self._stop.is_set() else "completed",
            "scenario_versions": {scenario.id: scenario.version for scenario in scenarios},
            "summary": self._summary(),
        }

    def _write_markdown_summary(self, manifest):
        """Write a concise human-readable report beside machine data."""

        summary = manifest["summary"]
        speed = summary["median_decode_tokens_per_second"]
        speed_text = "not measured" if speed is None else f"{speed:.3f} token/s"
        content = (
            f"# Benchmark {manifest['model']}\n\n"
            f"- Campaign: `{manifest['campaign_id']}`\n"
            f"- Suite: `{manifest['suite']}`\n"
            f"- Attempts: **{summary['attempts']}**\n"
            f"- Passed: **{summary['passed']}**\n"
            f"- Failed: **{summary['failed']}**\n"
            f"- Median decode speed: **{speed_text}**\n"
        )
        path = self.storage.campaign_root / "summary.md"
        path.write_text(content, encoding="utf-8")

    def _emit(self, event_type, payload):
        """Persist and publish one live benchmark event."""

        event = {
            "schema_version": 1,
            "benchmark_id": self.campaign_id,
            "timestamp": _utc_now(),
            "type": event_type,
            "payload": payload,
        }
        self.storage.event(event)
        self.on_event(event)


def _native_measurements(response):
    """Normalize Ollama nanosecond counters and retain raw counts."""

    measurements = {
        "client_duration_seconds": response.get("client_duration_seconds"),
        "time_to_first_chunk_seconds": response.get("time_to_first_chunk_seconds"),
        "time_to_first_content_seconds": response.get("time_to_first_content_seconds"),
        "stream_chunk_count": response.get("stream_chunk_count"),
        "total_duration_seconds": _seconds(response.get("total_duration")),
        "load_duration_seconds": _seconds(response.get("load_duration")),
        "prompt_eval_count": response.get("prompt_eval_count"),
        "prompt_eval_duration_seconds": _seconds(response.get("prompt_eval_duration")),
        "eval_count": response.get("eval_count"),
        "eval_duration_seconds": _seconds(response.get("eval_duration")),
        "done_reason": response.get("done_reason"),
    }
    eval_count = measurements["eval_count"]
    eval_duration = measurements["eval_duration_seconds"]
    prompt_count = measurements["prompt_eval_count"]
    prompt_duration = measurements["prompt_eval_duration_seconds"]
    measurements["decode_tokens_per_second"] = eval_count / eval_duration if eval_count and eval_duration else None
    measurements["prompt_tokens_per_second"] = (
        prompt_count / prompt_duration if prompt_count and prompt_duration else None
    )

    return measurements


def _seconds(nanoseconds):
    """Convert an optional Ollama nanosecond duration."""

    return nanoseconds / 1_000_000_000 if nanoseconds is not None else None


def _resource_measurements(path):
    """Aggregate useful peaks while leaving all raw samples intact."""

    samples = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                samples.append(json.loads(line))
    if not samples:
        return {}

    return {
        "resource_sample_count": len(samples),
        "peak_cpu_percent": max(sample["cpu_percent"] for sample in samples),
        "peak_memory_used_bytes": max(sample["memory_used_bytes"] for sample in samples),
        "minimum_memory_available_bytes": min(sample["memory_available_bytes"] for sample in samples),
        "peak_swap_used_bytes": max(sample["swap_used_bytes"] for sample in samples),
    }
