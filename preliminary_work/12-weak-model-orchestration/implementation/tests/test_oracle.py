import io
import json

import pytest

from pithos_orchestrator.oracle import OracleAuthor, OracleSpecError, _request_spec, author_oracle
from pithos_orchestrator.state import MissionState


def _write_module(workspace, body):
    module = workspace / "src" / "module.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(body, encoding="utf-8")

    return {"src/module.py": body}


def _opener_yielding(payloads):
    iterator = iter(payloads)

    def opener(request, timeout):
        body = {"response": json.dumps(next(iterator))}

        return io.BytesIO(json.dumps(body).encode())

    return opener


def test_author_oracle_confirms_red_when_two_generations_agree(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x\n")
    payload = {"target_file": "src/module.py", "target_function": "add_one", "cases": [{"args": [2], "expect": 3}]}
    opener = _opener_yielding([payload, payload])

    path, reason = author_oracle(
        "fake-model", "Add one", "Fix add_one", sources, [], tmp_path / "oracle.py", tmp_path, opener=opener
    )

    assert path.is_file()
    assert "add_one" in reason
    assert "confirmed red" in reason


def test_author_oracle_binds_and_mutates_the_validator(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x\n")
    payload = {"target_file": "src/module.py", "target_function": "add_one", "cases": [{"args": [2], "expect": 3}]}
    opener = _opener_yielding([payload, payload])

    class RecordingValidator:
        command = ["python", "-c", "raise SystemExit(1)"]

    validator = RecordingValidator()
    project = {"title": "Add one", "description": "Fix add_one", "target_files": ["src/module.py"]}
    author = OracleAuthor("fake-model", project, tmp_path, tmp_path / "oracle.py", validator, opener=opener)

    success, reason = author(state=MissionState("run-1", "exp"))

    assert success is True
    assert validator.command[0] != "python"
    assert validator.command[1].endswith("oracle.py")


def test_author_oracle_targets_the_active_todo_item_and_gets_its_own_oracle_file(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x\n\n\ndef sub_one(x):\n    return x\n")
    payload = {"target_file": "src/module.py", "target_function": "sub_one", "cases": [{"args": [2], "expect": 1}]}
    opener = _opener_yielding([payload, payload])

    class RecordingValidator:
        command = ["python", "-c", "raise SystemExit(1)"]

    validator = RecordingValidator()
    project = {"title": "Rush title", "description": "Rush description", "target_files": ["src/module.py"]}
    author = OracleAuthor("fake-model", project, tmp_path, tmp_path / "oracle.py", validator, opener=opener)
    state = MissionState(
        "run-1",
        "exp",
        todo=[
            {"title": "Fix add_one", "description": "...", "target_files": ["src/module.py"], "status": "done"},
            {"title": "Fix sub_one", "description": "...", "target_files": ["src/module.py"], "status": "pending"},
        ],
        todo_index=1,
    )

    success, reason = author(state=state)

    assert success is True
    assert "sub_one" in reason
    assert validator.command[1].endswith("oracle-02.py")
    assert not (tmp_path / "oracle.py").is_file()


def test_author_oracle_rejects_disagreeing_generations(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x\n")
    primary = {"target_file": "src/module.py", "target_function": "add_one", "cases": [{"args": [2], "expect": 3}]}
    check = {"target_file": "src/module.py", "target_function": "add_one", "cases": [{"args": [2], "expect": 4}]}
    opener = _opener_yielding([primary, check])

    with pytest.raises(OracleSpecError, match="cross-generation agreement"):
        author_oracle(
            "fake-model",
            "Add one",
            "Fix add_one",
            sources,
            [],
            tmp_path / "oracle.py",
            tmp_path,
            attempts=1,
            opener=opener,
        )


def test_request_spec_constrains_a_function_explicitly_named_by_the_task(tmp_path):
    sources = _write_module(tmp_path, "def old(x):\n    return x\n\n\ndef wanted(x):\n    return x\n")
    payload = {"target_file": "src/module.py", "target_function": "wanted", "cases": [{"args": [2], "expect": 3}]}
    captured = []

    def opener(request, timeout):
        captured.append(json.loads(request.data))
        body = {"response": json.dumps(payload)}

        return io.BytesIO(json.dumps(body).encode())

    _request_spec(
        "fake-model",
        "Fix wanted",
        "Change wanted(x).",
        sources,
        ["src/module.py"],
        45,
        opener,
        "wanted",
    )

    [request] = captured
    assert request["format"]["properties"]["target_function"]["enum"] == ["wanted"]


def test_author_oracle_retries_when_generated_case_already_passes(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x + 1\n")
    already_passing = {
        "target_file": "src/module.py",
        "target_function": "add_one",
        "cases": [{"args": [2], "expect": 3}],
    }
    genuinely_red = {
        "target_file": "src/module.py",
        "target_function": "add_one",
        "cases": [{"args": [2], "expect": 4}],
    }
    opener = _opener_yielding([already_passing, already_passing, genuinely_red, genuinely_red])

    path, reason = author_oracle(
        "fake-model",
        "Add one",
        "Fix add_one",
        sources,
        [],
        tmp_path / "oracle.py",
        tmp_path,
        attempts=2,
        opener=opener,
    )

    assert path.is_file()
    assert "confirmed red" in reason


def test_author_oracle_rejects_a_case_that_crashes_instead_of_asserting(tmp_path):
    sources = _write_module(tmp_path, "def divide(a, b):\n    return a / b\n")
    payload = {"target_file": "src/module.py", "target_function": "divide", "cases": [{"args": [1], "expect": 1}]}
    opener = _opener_yielding([payload, payload])

    with pytest.raises(OracleSpecError, match="crashed instead of failing its own assertion"):
        author_oracle(
            "fake-model",
            "Divide",
            "Fix divide",
            sources,
            [],
            tmp_path / "oracle.py",
            tmp_path,
            attempts=1,
            opener=opener,
        )


def test_author_oracle_rejects_a_function_absent_from_target_files(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x\n")
    payload = {"target_file": "src/module.py", "target_function": "os.system", "cases": [{"args": [2], "expect": 3}]}
    opener = _opener_yielding([payload, payload])

    with pytest.raises(OracleSpecError, match="not a valid identifier"):
        author_oracle(
            "fake-model",
            "Add one",
            "Fix add_one",
            sources,
            [],
            tmp_path / "oracle.py",
            tmp_path,
            attempts=1,
            opener=opener,
        )


def test_author_oracle_rejects_a_file_outside_the_approved_targets(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x\n")
    payload = {
        "target_file": "src/other.py",
        "target_function": "add_one",
        "cases": [{"args": [2], "expect": 3}],
    }
    opener = _opener_yielding([payload, payload])

    with pytest.raises(OracleSpecError, match="not an approved target file"):
        author_oracle(
            "fake-model",
            "Add one",
            "Fix add_one",
            sources,
            [],
            tmp_path / "oracle.py",
            tmp_path,
            attempts=1,
            opener=opener,
        )


def test_author_oracle_handles_tuple_shaped_cases(tmp_path):
    sources = _write_module(
        tmp_path,
        "def thirds(values):\n"
        "    return (values[0], values[1], values[2])\n",
    )
    payload = {
        "target_file": "src/module.py",
        "target_function": "thirds",
        "cases": [{"args": [[1.0, 2.0, 3.0]], "expect": [9.0, 2.0, 3.0]}],
    }
    opener = _opener_yielding([payload, payload])

    path, reason = author_oracle(
        "fake-model", "Thirds", "Fix thirds", sources, [], tmp_path / "oracle.py", tmp_path, opener=opener
    )

    rendered = path.read_text(encoding="utf-8")
    assert "(1.0, 2.0, 3.0)" in rendered
    assert "confirmed red" in reason


def test_author_oracle_for_new_file_only_needs_no_model_call(tmp_path):
    calls = []

    def opener(request, timeout):
        calls.append(request)
        raise AssertionError("should never call the model when there is nothing existing to reference")

    path, reason = author_oracle(
        "fake-model", "New module", "Create it", {}, ["src/new_module.py"], tmp_path / "oracle.py", tmp_path, opener=opener
    )

    assert not calls
    assert path.is_file()
    assert "file-creation checks only for 1 new file" in reason
    assert "confirmed red" in reason
    rendered = path.read_text(encoding="utf-8")
    assert "importlib.import_module" in rendered


def test_author_oracle_combines_existing_and_new_file_checks(tmp_path):
    sources = _write_module(tmp_path, "def add_one(x):\n    return x\n")
    payload = {"target_file": "src/module.py", "target_function": "add_one", "cases": [{"args": [2], "expect": 3}]}
    opener = _opener_yielding([payload, payload])

    path, reason = author_oracle(
        "fake-model",
        "Add one and a new file",
        "Fix add_one, create src/new_module.py",
        sources,
        ["src/new_module.py"],
        tmp_path / "oracle.py",
        tmp_path,
        opener=opener,
    )

    assert path.is_file()
    assert "add_one" in reason
    assert "plus 1 new file check(s)" in reason
    rendered = path.read_text(encoding="utf-8")
    assert "CASES = " in rendered
    assert "importlib.import_module" in rendered
