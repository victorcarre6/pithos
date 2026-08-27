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
    assert result.history[0]["at"].endswith("+00:00")
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


def test_author_oracle_phase_hands_off_to_preflight_on_success(tmp_path):
    store = StateStore(tmp_path / "mission.json")

    def oracle_author(state):
        return True, "oracle authored"

    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "generated oracle"),
        lambda state: None,
        oracle_author=oracle_author,
    )
    state = MissionState("mission-oracle", "visualizer", phase="author_oracle")

    result = orchestrator.run(state, lambda current: current.failure_summary)

    assert result.phase == "done"
    assert result.status == "completed"
    assert result.history[1]["phase"] == "author_oracle"
    assert result.history[1]["success"] is True


def test_author_oracle_phase_fails_the_mission_when_no_red_oracle_is_found(tmp_path):
    store = StateStore(tmp_path / "mission.json")

    def oracle_author(state):
        return False, "no attempt produced a usable oracle"

    orchestrator = Orchestrator(store, None, None, None, oracle_author=oracle_author)
    state = MissionState("mission-oracle-2", "visualizer", phase="author_oracle")

    result = orchestrator.run(state, lambda current: current.failure_summary)

    assert result.phase == "failed"
    assert result.status == "failed"
    assert result.failure_summary == "no attempt produced a usable oracle"


def test_author_oracle_phase_without_an_oracle_author_fails_clearly(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    orchestrator = Orchestrator(store, None, None, None)
    state = MissionState("mission-oracle-3", "visualizer", phase="author_oracle")

    result = orchestrator.run(state, lambda current: current.failure_summary)

    assert result.phase == "failed"
    assert "requires an oracle_author" in result.failure_summary


def test_test_success_routes_through_propose_next_rush_when_configured(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []
    proposed = []

    def next_rush_author(state):
        proposed.append(state.mission_id)

        return True, "proposed next micro-rush 'next-id': Next thing"

    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "python acceptance.py"),
        lambda state: finalized.append(state.mission_id),
        next_rush_author=next_rush_author,
    )
    state = MissionState("mission-propose-1", "visualizer")

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert proposed == ["mission-propose-1"]
    assert finalized == ["mission-propose-1"]
    phases = [entry["phase"] for entry in result.history]
    assert "propose_next_rush" in phases
    assert phases.index("propose_next_rush") < phases.index("finalize")


def test_test_success_skips_propose_next_rush_when_not_configured(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []
    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "python acceptance.py"),
        lambda state: finalized.append(state.mission_id),
    )
    state = MissionState("mission-propose-2", "visualizer")

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert finalized == ["mission-propose-2"]
    assert "propose_next_rush" not in [entry["phase"] for entry in result.history]


def test_a_failed_proposal_still_lets_the_mission_finalize(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []

    def failing_next_rush_author(state):
        return False, "propose_next_rush failed: model unreachable"

    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "python acceptance.py"),
        lambda state: finalized.append(state.mission_id),
        next_rush_author=failing_next_rush_author,
    )
    state = MissionState("mission-propose-3", "visualizer")

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert finalized == ["mission-propose-3"]
    propose_entry = next(entry for entry in result.history if entry.get("phase") == "propose_next_rush" and "success" in entry)
    assert propose_entry["success"] is False


def test_review_success_also_routes_through_propose_next_rush(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []

    def phase_runner(phase, context):
        return PhaseResult(True, f"{phase} complete", [])

    def next_rush_author(state):
        return True, "proposed next micro-rush 'next-id': Next thing"

    orchestrator = Orchestrator(
        store,
        phase_runner,
        None,
        lambda state: finalized.append(state.mission_id),
        next_rush_author=next_rush_author,
    )
    state = MissionState("mission-propose-4", "visualizer", phase="review")

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert finalized == ["mission-propose-4"]
    phases = [entry["phase"] for entry in result.history]
    assert "propose_next_rush" in phases


def _todo(*titles):
    return [
        {"title": title, "description": "...", "target_files": [f"{title}.py"], "status": "pending"}
        for title in titles
    ]


def test_plan_todo_phase_calls_the_planner_then_moves_to_author_oracle(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    calls = []

    def todo_planner(state):
        calls.append(state.mission_id)
        state.todo = _todo("Only item")

        return True, "planned 1 item(s): Only item"

    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "generated oracle"),
        lambda state: None,
        oracle_author=lambda state: (True, "oracle authored"),
        todo_planner=todo_planner,
    )
    state = MissionState("mission-plan-1", "visualizer", phase="plan_todo")

    result = orchestrator.run(state, lambda current: "unused")

    assert calls == ["mission-plan-1"]
    assert result.status == "completed"
    assert [item["status"] for item in result.todo] == ["done"]


def test_plan_todo_phase_without_a_planner_behaves_like_a_single_implicit_item(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "generated oracle"),
        lambda state: None,
        oracle_author=lambda state: (True, "oracle authored"),
    )
    state = MissionState("mission-plan-2", "visualizer", phase="plan_todo")

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert result.todo == []


def test_multi_item_todo_all_succeed_finalizes_once(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []

    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "generated oracle"),
        lambda state: finalized.append(state.mission_id),
        oracle_author=lambda state: (True, f"oracle for item {state.todo_index}"),
    )
    state = MissionState("mission-todo-1", "visualizer", phase="plan_todo", todo=_todo("A", "B"))

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert result.phase == "done"
    assert [item["status"] for item in result.todo] == ["done", "done"]
    assert finalized == ["mission-todo-1"]


def test_multi_item_todo_skips_a_failed_item_but_still_finalizes(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []
    oracle_calls = []

    def oracle_author(state):
        oracle_calls.append(state.todo_index)
        if state.todo_index == 1:
            return False, "no case survived cross-generation agreement"

        return True, "oracle authored"

    orchestrator = Orchestrator(
        store,
        None,
        lambda changed_files: ValidationResult(True, "generated oracle"),
        lambda state: finalized.append(state.mission_id),
        oracle_author=oracle_author,
    )
    state = MissionState("mission-todo-2", "visualizer", phase="plan_todo", todo=_todo("A", "B", "C"))

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "completed"
    assert oracle_calls == [0, 1, 2]
    assert [item["status"] for item in result.todo] == ["done", "skipped", "done"]
    assert finalized == ["mission-todo-2"]


def test_multi_item_todo_fails_the_mission_when_every_item_fails(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    finalized = []

    orchestrator = Orchestrator(
        store,
        None,
        None,
        lambda state: finalized.append(state.mission_id),
        oracle_author=lambda state: (False, "no attempt produced a usable oracle"),
    )
    state = MissionState("mission-todo-3", "visualizer", phase="plan_todo", todo=_todo("A", "B"))

    result = orchestrator.run(state, lambda current: "unused")

    assert result.status == "failed"
    assert result.phase == "failed"
    assert [item["status"] for item in result.todo] == ["skipped", "skipped"]
    assert finalized == []


def test_a_failed_item_resets_repair_attempts_and_failure_summary_for_the_next_item(tmp_path):
    store = StateStore(tmp_path / "mission.json")
    validations = iter(
        [
            ValidationResult(False, "acceptance.py", stderr="FAILED forever"),
            ValidationResult(False, "acceptance.py", stderr="FAILED forever"),
            ValidationResult(False, "acceptance.py", stderr="FAILED forever"),
            ValidationResult(False, "acceptance.py", stderr="FAILED forever"),
            ValidationResult(True, "acceptance.py"),
        ]
    )

    def phase_runner(phase, context):
        return PhaseResult(True, f"{phase} complete", [])

    orchestrator = Orchestrator(
        store,
        phase_runner,
        lambda changed_files: next(validations),
        lambda state: None,
        oracle_author=lambda state: (True, "oracle authored"),
    )
    state = MissionState("mission-todo-4", "visualizer", phase="plan_todo", todo=_todo("A", "B"), max_repairs=2)

    result = orchestrator.run(state, lambda current: current.failure_summary)

    assert result.status == "completed"
    assert [item["status"] for item in result.todo] == ["skipped", "done"]
    assert result.repair_attempts == 0
    assert result.failure_summary == ""


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
        history=[
            {
                "phase": "preflight",
                "event": "started",
                "at": "2026-08-24T14:00:00+00:00",
            }
        ],
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
    assert 'started_at: "2026-08-24T14:00:00+00:00"' in report_path.read_text()
    assert validate_report(report_path)["run_id"] == state.mission_id
    assert (tmp_path / "logs" / "latest.md").exists()


def test_command_validator_requires_regression_suite_after_green_oracle(tmp_path):
    validator = CommandValidator(
        tmp_path,
        ["python", "-c", "print('oracle pass')"],
        regression_command=["python", "-c", "raise SystemExit('regression failed')"],
    )

    validation = validator([])

    assert validation.passed is False
    assert "oracle pass" in validation.stdout
    assert "regression failed" in validation.stderr
    assert "&&" in validation.command


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


def test_context_includes_the_rush_level_task_when_no_plan_exists(tmp_path):
    (tmp_path / "PROJECT.md").write_text("# Contract\n")
    project = {"title": "Borner les niveaux", "description": "Clamper smooth_levels dans [0, 1]."}

    context = ContextFactory(tmp_path, project=project)(MissionState("mission-6", "visualizer"))

    assert "## Current task" in context
    assert "Borner les niveaux" in context
    assert "Clamper smooth_levels dans [0, 1]." in context


def test_context_includes_the_active_todo_items_task_not_the_rushs(tmp_path):
    (tmp_path / "PROJECT.md").write_text("# Contract\n")
    project = {"title": "Rush title", "description": "Rush description"}
    state = MissionState(
        "mission-7",
        "visualizer",
        todo=[
            {"title": "Item A", "description": "First step", "target_files": [], "status": "done"},
            {"title": "Item B", "description": "Second step", "target_files": [], "status": "pending"},
        ],
        todo_index=1,
    )

    context = ContextFactory(tmp_path, project=project)(state)

    assert "Item B" in context
    assert "Second step" in context
    assert "Rush title" not in context


def test_context_omits_the_current_task_section_without_a_project(tmp_path):
    (tmp_path / "PROJECT.md").write_text("# Contract\n")

    context = ContextFactory(tmp_path)(MissionState("mission-8", "visualizer"))

    assert "## Current task" not in context


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


def test_finalizer_auto_merges_a_reused_pull_request_too(tmp_path):
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
        "run-20260824T150300Z-a1b2c3",
        "visualizer",
        phase="finalize",
        evidence=[{"command": "python acceptance.py", "passed": True}],
    )
    finalizer = LocalFinalizer(
        workspace,
        tmp_path / "missions" / state.mission_id,
        tmp_path / "logs",
        git_send,
        auto_merge=True,
    )

    finalizer(state)

    assert [request["operation"] for request in calls] == ["switch", "pr_view", "commit", "push", "pr_merge"]
    assert state.artifacts["merged"] is True


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


def test_finalizer_auto_merges_after_pr_create_when_enabled(tmp_path):
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
        "run-20260824T150000Z-a1b2c3",
        "visualizer",
        phase="finalize",
        evidence=[{"command": "python acceptance.py", "passed": True}],
    )
    finalizer = LocalFinalizer(
        workspace,
        tmp_path / "missions" / state.mission_id,
        tmp_path / "logs",
        git_send,
        auto_merge=True,
    )

    finalizer(state)

    assert [request["operation"] for request in calls] == [
        "switch",
        "pr_view",
        "commit",
        "push",
        "pr_create",
        "pr_merge",
    ]
    assert state.artifacts["merged"] is True
    assert "merge_failed" not in state.artifacts


def test_finalizer_never_calls_pr_merge_when_auto_merge_is_disabled(tmp_path):
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
        "run-20260824T150100Z-a1b2c3",
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

    assert "pr_merge" not in [request["operation"] for request in calls]
    assert "merged" not in state.artifacts


def test_a_failed_auto_merge_does_not_undo_an_already_validated_mission(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    calls = []

    def git_send(request):
        calls.append(request)
        if request["operation"] == "pr_view":
            raise RuntimeError("no pull request")
        if request["operation"] == "pr_merge":
            raise RuntimeError("branch protection: required review missing")
        stdout = "https://github.com/example/pithos/pull/1\n" if request["operation"] == "pr_create" else "ok\n"

        return {"ok": True, "stdout": stdout}

    state = MissionState(
        "run-20260824T150200Z-a1b2c3",
        "visualizer",
        phase="finalize",
        evidence=[{"command": "python acceptance.py", "passed": True}],
    )
    finalizer = LocalFinalizer(
        workspace,
        tmp_path / "missions" / state.mission_id,
        tmp_path / "logs",
        git_send,
        auto_merge=True,
    )

    finalizer(state)

    assert state.artifacts["pull_request"] == "https://github.com/example/pithos/pull/1"
    assert "branch protection" in state.artifacts["merge_failed"]
    assert "merged" not in state.artifacts


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
