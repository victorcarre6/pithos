import io
import json

import pytest

from pithos_orchestrator.oracle import OracleAuthor, OracleSpecError, author_oracle


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
        "fake-model", "Add one", "Fix add_one", sources, tmp_path / "oracle.py", tmp_path, opener=opener
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

    success, reason = author(state=None)

    assert success is True
    assert validator.command[0] != "python"
    assert validator.command[1].endswith("oracle.py")


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
            tmp_path / "oracle.py",
            tmp_path,
            attempts=1,
            opener=opener,
        )


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
        tmp_path / "oracle.py",
        tmp_path,
        attempts=2,
        opener=opener,
    )

    assert path.is_file()
    assert "confirmed red" in reason


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
        "fake-model", "Thirds", "Fix thirds", sources, tmp_path / "oracle.py", tmp_path, opener=opener
    )

    rendered = path.read_text(encoding="utf-8")
    assert "(1.0, 2.0, 3.0)" in rendered
    assert "confirmed red" in reason
