"""Author one harness-rendered acceptance oracle from a bounded model contract.

The model never contributes executable code. It only selects, from the
human-approved target files, a target function name and a few numeric
input/output cases. The harness renders the actual assertions, requires two
independent generations to agree on every kept case, and refuses any oracle
that does not fail against the current (unfixed) workspace: an oracle that
already passes cannot prove anything about the requested change.
"""

import json
import math
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


MAX_CASES = 4
MAX_ARGS = 6
MAX_LIST_LENGTH = 8
AGREEMENT_TOLERANCE = 1e-6
_FUNCTION_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,63}")


class OracleSpecError(ValueError):
    """The model's proposed contract could not be trusted or rendered."""


class OracleAuthor:
    """Bind oracle authoring to one mission's project config and validator."""

    def __init__(self, model, project, workspace, output_path, validator, timeout=45, attempts=3, opener=None):
        self.model = model
        self.project = project
        self.workspace = Path(workspace)
        self.output_path = Path(output_path)
        self.validator = validator
        self.timeout = timeout
        self.attempts = attempts
        self.opener = opener

    def __call__(self, state):
        target_files = self.project.get("target_files") or []
        sources = {}
        for relative in target_files:
            path = self.workspace / relative
            if path.is_file():
                sources[relative] = path.read_text(encoding="utf-8", errors="replace")

        if not sources:
            return False, "author_oracle found no readable target_files"

        try:
            path, reason = author_oracle(
                self.model,
                self.project.get("title", ""),
                self.project.get("description", ""),
                sources,
                self.output_path,
                self.workspace,
                timeout=self.timeout,
                attempts=self.attempts,
                opener=self.opener,
            )
        except OracleSpecError as error:
            return False, f"author_oracle failed: {error}"

        self.validator.command = [sys.executable, str(path)]

        return True, reason


def author_oracle(model, title, description, sources, output_path, workspace, timeout=45, attempts=3, opener=None):
    """Author, render and red-check one oracle; return (path, reason) or raise OracleSpecError."""

    allowed_files = sorted(sources)
    output_path = Path(output_path)
    reasons = []
    for attempt in range(1, attempts + 1):
        try:
            # deliberately different sampling temperatures: a systematic misunderstanding tends to survive
            # a low-temperature replay, but genuine independence needs the two calls to actually diverge
            primary = _request_spec(model, title, description, sources, allowed_files, timeout, opener, temperature=0.15)
            check = _request_spec(model, title, description, sources, allowed_files, timeout, opener, temperature=0.6)
            _require_same_target(primary, check)
            cases = _agreeing_cases(primary["cases"], check["cases"])
            if not cases:
                reasons.append(f"attempt {attempt}: no case survived cross-generation agreement")
                continue
        except OracleSpecError as error:
            reasons.append(f"attempt {attempt}: {error}")
            continue

        script = _render_script(primary["target_file"], primary["target_function"], cases)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(script, encoding="utf-8")

        red = _run_script(output_path, workspace, timeout)
        if red.returncode == 0:
            reasons.append(f"attempt {attempt}: generated oracle already passes on current code (not red)")
            continue

        return output_path, (
            f"oracle authored for {primary['target_function']} in {primary['target_file']} "
            f"with {len(cases)} agreeing case(s), confirmed red"
        )

    raise OracleSpecError("; ".join(reasons) or "no attempt produced a usable oracle")


def _request_spec(model, title, description, sources, allowed_files, timeout, opener, temperature=0.2):
    listing = "\n\n".join(
        f"### {relative}\n```python\n{content[:4000]}\n```" for relative, content in sources.items()
    )
    prompt = (
        "Tu proposes un contrat de test d'acceptation pour la tâche suivante. Choisis UNE seule fonction déjà "
        f"définie dans les fichiers ci-dessous et 1 à {MAX_CASES} cas d'entrée/sortie numériques concrets qui "
        "vérifient le comportement attendu. N'invente aucun code, aucune fonction, aucun fichier absent de la "
        "liste. Réponds uniquement avec l'objet JSON demandé.\n\n"
        f"Titre : {title}\nDescription : {description}\n\n{listing}"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": _spec_schema(allowed_files),
        "options": {"num_predict": 400, "temperature": temperature},
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    open_request = opener or urllib.request.urlopen
    try:
        with open_request(request, timeout=timeout) as response:
            body = json.load(response)
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise OracleSpecError("oracle generation request failed") from error

    try:
        raw = json.loads(str(body.get("response", "")))
    except json.JSONDecodeError as error:
        raise OracleSpecError("oracle contract is not structured JSON") from error

    return _validate_spec(raw, sources, allowed_files)


def _spec_schema(allowed_files):
    number_or_vector = {
        "anyOf": [
            {"type": "number"},
            {"type": "array", "items": {"type": "number"}, "maxItems": MAX_LIST_LENGTH},
        ]
    }

    return {
        "type": "object",
        "properties": {
            "target_file": {"type": "string", "enum": allowed_files},
            "target_function": {"type": "string"},
            "cases": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_CASES,
                "items": {
                    "type": "object",
                    "properties": {
                        "args": {"type": "array", "items": number_or_vector, "maxItems": MAX_ARGS},
                        "expect": number_or_vector,
                    },
                    "required": ["args", "expect"],
                },
            },
        },
        "required": ["target_file", "target_function", "cases"],
    }


def _validate_spec(raw, sources, allowed_files):
    if not isinstance(raw, dict):
        raise OracleSpecError("oracle contract must be a JSON object")

    target_file = raw.get("target_file")
    if target_file not in allowed_files:
        raise OracleSpecError(f"oracle target_file {target_file!r} is not an approved target file")

    target_function = raw.get("target_function")
    if not isinstance(target_function, str) or not _FUNCTION_NAME.fullmatch(target_function):
        raise OracleSpecError("oracle target_function is not a valid identifier")
    if not re.search(rf"(?m)^\s*def\s+{re.escape(target_function)}\s*\(", sources[target_file]):
        raise OracleSpecError(f"oracle target_function {target_function!r} is not defined in {target_file}")

    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise OracleSpecError("oracle contract requires at least one case")

    cleaned = []
    for case in cases[:MAX_CASES]:
        if not isinstance(case, dict):
            raise OracleSpecError("oracle case must be a JSON object")
        args = case.get("args")
        if not isinstance(args, list) or not (1 <= len(args) <= MAX_ARGS):
            raise OracleSpecError("oracle case args must be a short non-empty list")
        cleaned.append(
            {
                "args": [_numeric_value(value) for value in args],
                "expect": _numeric_value(case.get("expect")),
            }
        )

    return {"target_file": target_file, "target_function": target_function, "cases": cleaned}


def _numeric_value(value):
    if isinstance(value, bool):
        raise OracleSpecError("oracle numeric value cannot be a boolean")
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise OracleSpecError("oracle numeric value must be finite")
        return float(value)
    if isinstance(value, list) and len(value) <= MAX_LIST_LENGTH:
        return tuple(_numeric_value(item) for item in value)

    raise OracleSpecError("oracle value must be a finite number or a short list of numbers")


def _require_same_target(primary, check):
    if primary["target_file"] != check["target_file"] or primary["target_function"] != check["target_function"]:
        raise OracleSpecError("two independent generations disagreed on the target function")


def _agreeing_cases(primary_cases, check_cases):
    agreeing = [
        case
        for case in primary_cases
        if any(_close(case["args"], other["args"]) and _close(case["expect"], other["expect"]) for other in check_cases)
    ]

    return agreeing[:MAX_CASES]


def _close(actual, expected):
    if isinstance(actual, (list, tuple)) or isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)) or not isinstance(expected, (list, tuple)):
            return False
        if len(actual) != len(expected):
            return False

        return all(_close(a, e) for a, e in zip(actual, expected))

    return math.isclose(actual, expected, rel_tol=1e-6, abs_tol=AGREEMENT_TOLERANCE)


def _render_script(target_file, function, cases):
    parent = str(Path(target_file).parent)
    module = Path(target_file).stem
    cases_literal = repr([{"args": tuple(case["args"]), "expect": case["expect"]} for case in cases])

    return f'''#!/usr/bin/env python3
"""Harness-rendered acceptance oracle.

The model selected only a target function and numeric input/output cases,
cross-checked across two independent generations; this script is composed
and executed by the harness. No model-authored code runs here.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / {parent!r}))

from {module} import {function}


def _close(actual, expected):
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, (list, tuple)) or len(actual) != len(expected):
            return False
        return all(_close(a, e) for a, e in zip(actual, expected))
    return isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-9)


CASES = {cases_literal}

for index, case in enumerate(CASES):
    result = {function}(*case["args"])
    if not _close(result, case["expect"]):
        raise AssertionError(
            f"case {{index}}: {function}(*{{case['args']!r}}) == {{result!r}}, expected {{case['expect']!r}}"
        )

print("generated oracle: PASS ({len(cases)} case(s))")
'''


def _run_script(path, workspace, timeout):
    command = [sys.executable, str(path)]

    return subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=timeout, check=False)
