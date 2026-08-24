import json
import sys

import pytest

from pithos_orchestrator.context import ContextBudgetExceeded, ContextSection, build_context, compact_failure
from pithos_orchestrator.campaign import CommandValidator, ContextFactory, LocalFinalizer
from pithos_orchestrator.controller import Orchestrator, PhaseResult, ValidationResult
from pithos_orchestrator.pi_phase import PiPhaseRunner
from pithos_runner.events import EventWriter
from pithos_runner.runner import RunnerConfiguration
from pithos_orchestrator.state import MissionState, StateStore
from pithos_contracts import validate_report


def test_context_keeps_required_and_drops_optional_over_budget():
    sections = [
        ContextSection("contract", "required", required=True),
        ContextSection("target", "small"),
        ContextSection("noise", "x" * 100),
    ]

    context, included = build_context(sections, limit=60)

    assert included == ["contract", "target"]
    assert "required" in context
    assert "x" * 100 not in context


def test_context_refuses_mandatory_overflow():
    sections = [ContextSection("contract", "x" * 100, required=True)]

    with pytest.raises(ContextBudgetExceeded, match="mandatory context"):
        build_context(sections, limit=20)


def test_failure_compaction_keeps_only_actionable_lines():
    output = compact_failure("noise\nFAILED test_bass\nnoise", "AssertionError: 1 != 0\nmore")

    assert output == "FAILED test_bass\nAssertionError: 1 != 0"


def test_orchestrator_repairs_then_finalizes(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    phase_calls = []
    validations = iter(
        [
            ValidationResult(False, "pytest -q", stdout="FAILED test_bass"),
            ValidationResult(True, "pytest -q"),
        ]
    )
    finalized = []

    def phase_runner(phase, context):
        phase_calls.append((phase, context))

        return PhaseResult(True, f"{phase} complete", ["src/audio.py"])

    orchestrator = Orchestrator(
        store,
        phase_runner,
        lambda changed_files: next(validations),
        lambda state: finalized.append(state.mission_id),
    )
    state = MissionState("mission-1", "visualizer", phase="implement")

    result = orchestrator.run(state, lambda current: current.failure_summary or "implement")

    assert result.phase == "done"
    assert result.status == "completed"
    assert result.repair_attempts == 1
    assert [phase for phase, _ in phase_calls] == ["implement", "repair"]
    assert phase_calls[1][1] == "FAILED test_bass"
    assert finalized == ["mission-1"]
    assert json.loads(store.path.read_text())["phase"] == "done"


def test_orchestrator_stops_before_finalization_after_repair_budget(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []
    phases = []

    def run_phase(phase, context):
        phases.append(phase)

        return PhaseResult(True, "edited", ["src/audio.py"])

    orchestrator = Orchestrator(
        store,
        run_phase,
        lambda changed_files: ValidationResult(False, "pytest -q", stderr="FAILED forever"),
        lambda state: finalized.append(state.mission_id),
    )
    state = MissionState("mission-2", "visualizer", phase="implement", max_repairs=3)

    result = orchestrator.run(state, lambda current: current.failure_summary)

    assert result.phase == "failed"
    assert result.repair_attempts == 3
    assert phases == ["implement", "repair", "repair", "repair"]
    assert finalized == []


def test_interruption_is_persisted_and_resumable(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    orchestrator = Orchestrator(store, None, None, None)
    state = MissionState("mission-3", "visualizer", phase="repair", repair_attempts=1)

    orchestrator.interrupt(state, "KeyboardInterrupt")
    persisted = store.load()

    assert persisted.phase == "interrupted"
    assert persisted.status == "interrupted"
    assert persisted.repair_attempts == 1
    assert persisted.failure_summary == "KeyboardInterrupt"


def test_pi_phase_runs_fresh_session_without_report_requirement(tmp_path):
    executable = tmp_path / "fake-pi"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json\n"
        "from pathlib import Path\n"
        "Path('result.py').write_text('VALUE = 1\\n')\n"
        "print(json.dumps({'type': 'agent_start'}), flush=True)\n"
        "print(json.dumps({'type': 'agent_end', 'messages': []}), flush=True)\n"
    )
    executable.chmod(0o755)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    configuration = RunnerConfiguration(
        experiment_id="test",
        workspace=workspace,
        logs_root=tmp_path / "logs",
        pi_config_dir=tmp_path / "config",
        pi_executable=str(executable),
        runtime="host",
        provider="fake",
        model="fake",
    )
    events = EventWriter(tmp_path / "events.jsonl", "run-20260824T120000Z-a1b2c3")
    runner = PiPhaseRunner(configuration, tmp_path / "mission", events)

    result = runner("implement", "## Contract\n\nDo the work.\n\n## File: result.py\n\n")

    assert result.success is True
    assert "phase=implement status=completed" in result.summary
    assert result.changed_files == ["result.py"]
    assert (tmp_path / "mission" / "phases" / "01-implement" / "result.json").exists()
    assert not (workspace / ".pithos" / "report.md").exists()


def test_campaign_components_build_validate_and_finalize(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "PROJECT.md").write_text("# Contract\n")
    source = workspace / "src"
    source.mkdir()
    (source / "feature.py").write_text("VALUE = 1\n")
    state = MissionState(
        "run-20260824T140000Z-a1b2c3",
        "visualizer",
        phase="finalize",
        changed_files=["src/feature.py"],
    )

    context = ContextFactory(workspace)(state)
    validation = CommandValidator(workspace, ["python", "-c", "print('ok')"])(state.changed_files)
    mission_root = tmp_path / "missions" / state.mission_id
    finalizer = LocalFinalizer(workspace, mission_root, tmp_path / "logs")
    state.evidence.append({"command": validation.command, "passed": validation.passed})
    finalizer(state)

    assert "VALUE = 1" in context
    assert validation.passed is True
    assert validation.command.startswith(sys.executable)
    report_path = workspace / ".pithos" / "report.md"
    assert "PASS" in report_path.read_text()
    assert validate_report(report_path)["run_id"] == state.mission_id
    assert (tmp_path / "logs" / "latest.md").exists()


def test_context_prefers_phase_brief_over_full_project(tmp_path):
    (tmp_path / "PROJECT.md").write_text("# Full product backlog\n")
    (tmp_path / ".pithos-task.md").write_text("Change only src/feature.py.\n")

    context = ContextFactory(tmp_path)(MissionState("mission-5", "visualizer"))

    assert "Change only src/feature.py." in context
    assert "Full product backlog" not in context


def test_context_can_target_one_test_file_explicitly(tmp_path):
    (tmp_path / "PROJECT.md").write_text("# Contract\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_feature.py").write_text("EXPECTED = 3\n")
    source = tmp_path / "src"
    source.mkdir()
    (source / "feature.py").write_text("VALUE = 3\n")

    context = ContextFactory(tmp_path, target_paths=["tests/test_feature.py"])(
        MissionState("mission-target", "visualizer")
    )

    assert "## File: tests/test_feature.py" in context
    assert "EXPECTED = 3" in context
    assert "VALUE = 3" not in context


def test_preflight_finalizes_without_calling_model(tmp_path):
    store = StateStore(tmp_path / "state.json")
    phase_calls = []
    finalized = []
    orchestrator = Orchestrator(
        store,
        lambda phase, context: phase_calls.append(phase),
        lambda changed_files: ValidationResult(True, "python acceptance.py"),
        lambda state: finalized.append(state.mission_id),
    )
    state = MissionState("run-20260824T141000Z-a1b2c3", "visualizer")

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert phase_calls == []
    assert finalized == [state.mission_id]
    assert result.evidence == [{"command": "python acceptance.py", "passed": True}]


def test_preflight_failure_starts_implementation_without_using_repair_budget(tmp_path):
    store = StateStore(tmp_path / "state.json")
    phase_calls = []
    validations = iter(
        [
            ValidationResult(False, "python acceptance.py", stderr="AssertionError: missing"),
            ValidationResult(True, "python acceptance.py"),
        ]
    )

    def run_phase(phase, context):
        phase_calls.append((phase, context))

        return PhaseResult(True, "implemented", ["src/feature.py"])

    orchestrator = Orchestrator(store, run_phase, lambda changed: next(validations), lambda state: None)
    state = MissionState("run-20260824T141100Z-a1b2c3", "visualizer")

    result = orchestrator.run(state, lambda current: current.failure_summary)

    assert result.status == "completed"
    assert result.repair_attempts == 0
    assert phase_calls == [("implement", "AssertionError: missing")]


def test_finalizer_uses_allowlisted_git_sequence_after_report(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    calls = []

    def git_send(request):
        calls.append(request)
        if request["operation"] == "pr_view":
            raise RuntimeError("no pull request")
        stdout = "https://github.com/example/pithos/pull/1\n" if request["operation"] == "pr_create" else "ok\n"

        return {"ok": True, "stdout": stdout}

    state = MissionState(
        "run-20260824T141200Z-a1b2c3",
        "visualizer",
        phase="finalize",
        evidence=[{"command": "python acceptance.py", "passed": True}],
    )
    finalizer = LocalFinalizer(
        workspace,
        tmp_path / "missions" / state.mission_id,
        tmp_path / "logs",
        git_send,
    )

    finalizer(state)

    assert [request["operation"] for request in calls] == ["switch", "pr_view", "commit", "push", "pr_create"]
    assert state.artifacts["pull_request"] == "https://github.com/example/pithos/pull/1"
    assert validate_report(workspace / ".pithos" / "report.md")["branch"] == "agent/rush-visualizer"


def test_finalizer_reuses_existing_pull_request(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    calls = []

    def git_send(request):
        calls.append(request)
        if request["operation"] == "pr_view":
            return {
                "ok": True,
                "stdout": '{"url":"https://github.com/example/pithos/pull/1","state":"OPEN"}\n',
            }

        return {"ok": True, "stdout": "ok\n"}

    state = MissionState(
        "run-20260824T145500Z-a1b2c3",
        "visualizer",
        phase="finalize",
        evidence=[{"command": "python acceptance.py", "passed": True}],
    )
    finalizer = LocalFinalizer(
        workspace,
        tmp_path / "missions" / state.mission_id,
        tmp_path / "logs",
        git_send,
    )

    finalizer(state)

    operations = [request["operation"] for request in calls]
    assert operations == ["switch", "pr_view", "commit", "push"]
    assert state.artifacts["pull_request"] == "https://github.com/example/pithos/pull/1"


def test_finalizer_refuses_to_push_to_merged_pull_request(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    calls = []

    def git_send(request):
        calls.append(request)
        response = {
            "url": "https://github.com/example/pithos/pull/1",
            "state": "MERGED",
        }

        return {"ok": True, "stdout": json.dumps(response)}

    state = MissionState(
        "run-20260824T145600Z-a1b2c3",
        "visualizer",
        micro_rush_id="band-smoothing",
        phase="finalize",
        evidence=[{"command": "python acceptance.py", "passed": True}],
    )
    finalizer = LocalFinalizer(
        workspace,
        tmp_path / "missions" / state.mission_id,
        tmp_path / "logs",
        git_send,
    )

    with pytest.raises(RuntimeError, match="already MERGED"):
        finalizer(state)

    assert [request["operation"] for request in calls] == ["switch", "pr_view"]


def test_finalization_failure_is_persisted(tmp_path):
    store = StateStore(tmp_path / "state.json")

    def fail(state):
        raise RuntimeError("push refused")

    orchestrator = Orchestrator(
        store,
        None,
        lambda changed: ValidationResult(True, "python acceptance.py"),
        fail,
    )
    state = MissionState("run-20260824T141300Z-a1b2c3", "visualizer")

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "failed"
    assert result.phase == "failed"
    assert result.failure_summary == "finalization failed: push refused"
    assert store.load().status == "failed"


def test_git_failure_does_not_publish_continuity(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    def git_send(request):
        raise RuntimeError("push refused")

    state = MissionState(
        "run-20260824T141400Z-a1b2c3",
        "visualizer",
        phase="finalize",
        evidence=[{"command": "python acceptance.py", "passed": True}],
    )
    finalizer = LocalFinalizer(
        workspace,
        tmp_path / "missions" / state.mission_id,
        tmp_path / "logs",
        git_send,
    )

    with pytest.raises(RuntimeError, match="push refused"):
        finalizer(state)

    assert (workspace / ".pithos" / "report.md").exists()
    assert not (tmp_path / "logs" / "latest.md").exists()
