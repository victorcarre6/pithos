"""State machine that surrounds short model sessions with external gates."""

from dataclasses import dataclass, field

from .context import compact_failure


@dataclass(frozen=True)
class PhaseResult:
    """Observed outcome of one fresh model session."""

    success: bool
    summary: str
    changed_files: list = field(default_factory=list)


@dataclass(frozen=True)
class ValidationResult:
    """Observed outcome of harness-owned validation."""

    passed: bool
    command: str
    stdout: str = ""
    stderr: str = ""


class Orchestrator:
    """Drive one mission through bounded fresh-session phases."""

    def __init__(self, store, phase_runner, validator, finalizer):
        self.store = store
        self.phase_runner = phase_runner
        self.validator = validator
        self.finalizer = finalizer

    def run(self, state, context_for, max_steps=20):
        """Continue from persisted state until terminal or step budget exhaustion."""

        self.store.save(state)
        for _ in range(max_steps):
            if state.phase in {"done", "failed", "interrupted"}:
                return state

            state.history.append({"phase": state.phase, "event": "started"})
            self.store.save(state)
            self._step(state, context_for)
            self.store.save(state)

        state.phase = "failed"
        state.status = "failed"
        state.failure_summary = "orchestrator step budget exceeded"
        self.store.save(state)

        return state

    def interrupt(self, state, reason="operator interrupt"):
        """Persist an explicit terminal checkpoint for an interrupted mission."""

        state.phase = "interrupted"
        state.status = "interrupted"
        state.failure_summary = reason
        state.history.append({"phase": "interrupted", "event": reason})
        self.store.save(state)

        return state

    def _step(self, state, context_for):
        if state.phase == "preflight":
            self._run_validation(state)
            return
        if state.phase in {"implement", "repair", "review"}:
            self._run_model_phase(state, context_for)
            return
        if state.phase == "test":
            self._run_validation(state)
            return
        if state.phase == "finalize":
            try:
                self.finalizer(state)
            except (OSError, RuntimeError, ValueError) as error:
                state.phase = "failed"
                state.status = "failed"
                state.failure_summary = f"finalization failed: {error}"
                state.history.append({"phase": "finalize", "event": state.failure_summary, "success": False})
                return
            state.phase = "done"
            state.status = "completed"
            state.history.append({"phase": "finalize", "event": "completed"})
            return

        raise ValueError(f"unsupported active phase: {state.phase}")

    def _run_model_phase(self, state, context_for):
        phase = state.phase
        context = context_for(state)
        result = self.phase_runner(phase, context)
        state.changed_files = sorted(set([*state.changed_files, *result.changed_files]))
        state.history.append({"phase": phase, "event": result.summary, "success": result.success})

        if not result.success:
            state.phase = "failed"
            state.status = "failed"
            state.failure_summary = result.summary
            return
        if phase == "review":
            state.phase = "finalize"
            return

        state.phase = "test"

    def _run_validation(self, state):
        phase = state.phase
        result = self.validator(state.changed_files)
        evidence = {
            "command": result.command,
            "passed": result.passed,
        }
        state.evidence.append(evidence)
        state.history.append({"phase": "test", "event": result.command, "success": result.passed})

        if result.passed:
            state.failure_summary = ""
            state.phase = "finalize"
            return

        if phase == "preflight":
            state.failure_summary = compact_failure(result.stdout, result.stderr)
            state.phase = "implement"
            return

        state.failure_summary = compact_failure(result.stdout, result.stderr)
        if state.repair_attempts >= state.max_repairs:
            state.phase = "failed"
            state.status = "failed"
            return

        state.repair_attempts += 1
        state.phase = "repair"
