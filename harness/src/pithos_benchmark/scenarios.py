"""Load and evaluate declarative benchmark scenarios."""

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Scenario:
    """One versioned deterministic benchmark scenario."""

    id: str
    title: str
    suite: str
    kind: str
    timeout_seconds: int
    messages: list
    expected: dict
    format_schema: dict | None = None
    tools: list | None = None
    options: dict | None = None
    synthetic_tokens: int | None = None
    version: int = 1


def load_scenarios(root: Path, suite: str):
    """Load validated YAML scenarios in stable path order."""

    scenarios = []
    for path in sorted(root.glob("**/*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        scenario = Scenario(
            id=data["id"],
            title=data["title"],
            suite=data["suite"],
            kind=data["kind"],
            timeout_seconds=data.get("timeout_seconds", 900),
            messages=data["messages"],
            expected=data["expected"],
            format_schema=data.get("format_schema"),
            tools=data.get("tools"),
            options=data.get("options"),
            synthetic_tokens=data.get("synthetic_tokens"),
            version=data.get("version", 1),
        )
        if scenario.synthetic_tokens:
            scenario = _with_synthetic_context(scenario)
        if (suite == "full" and scenario.suite != "context") or scenario.suite == suite:
            scenarios.append(scenario)

    identifiers = [scenario.id for scenario in scenarios]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("scenario identifiers must be unique")

    return scenarios


def _with_synthetic_context(scenario):
    """Generate a deterministic long prompt whose actual token count Ollama reports."""

    filler = "pithos " * scenario.synthetic_tokens
    prompt = (
        "Remember both boundary markers. START_PITHOS_CONTEXT "
        f"{filler}"
        "END_PITHOS_CONTEXT. Reply with exactly PITHOS_CONTEXT_OK."
    )

    return Scenario(
        id=scenario.id,
        title=scenario.title,
        suite=scenario.suite,
        kind=scenario.kind,
        timeout_seconds=scenario.timeout_seconds,
        messages=[{"role": "user", "content": prompt}],
        expected=scenario.expected,
        format_schema=scenario.format_schema,
        tools=scenario.tools,
        options=scenario.options,
        synthetic_tokens=scenario.synthetic_tokens,
        version=scenario.version,
    )


def evaluate(scenario: Scenario, response: dict):
    """Evaluate native response effects without trusting prose claims."""

    message = response.get("message") or {}
    content = message.get("content", "")
    expected = scenario.expected
    evidence = {}

    if "exact_text" in expected:
        evidence["actual_text"] = content.strip()
        passed = content.strip() == expected["exact_text"]
    elif "json" in expected:
        try:
            parsed = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            parsed = None
        evidence["actual_json"] = parsed
        passed = parsed == expected["json"]
    elif "tool" in expected:
        calls = message.get("tool_calls") or []
        evidence["tool_calls"] = calls
        passed = _tool_matches(calls, expected["tool"])
    else:
        raise ValueError(f"scenario {scenario.id} has no supported expectation")

    return passed, evidence


def _tool_matches(calls, expected):
    """Match one tool name and its exact arguments."""

    if len(calls) != 1:
        return False
    function = calls[0].get("function") or {}

    return function.get("name") == expected["name"] and function.get("arguments") == expected["arguments"]
