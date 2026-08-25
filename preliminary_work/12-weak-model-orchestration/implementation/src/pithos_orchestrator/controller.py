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

    def __init__(
        self, store, phase_runner, validator, finalizer, oracle_author=None, next_rush_author=None, todo_planner=None
    ):
        self.store = store
        self.phase_runner = phase_runner
        self.validator = validator
        self.finalizer = finalizer
        self.oracle_author = oracle_author
        self.next_rush_author = next_rush_author
        self.todo_planner = todo_planner

    def run(self, state, context_for, max_steps=20):
        """Continue from persisted state until terminal or step budget exhaustion."""

        self.store.save(state)
        for _ in range(max_steps):
            if state.phase in {"done", "failed", "interrupted"}:
                return state

            state.history.append(
                {
                    "phase": state.phase,
                    "event": "started",
                    "at": state.updated_at,
                }
            )
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
        if state.phase == "plan_todo":
            self._run_plan_todo(state)
            return
        if state.phase == "author_oracle":
            self._run_oracle_authoring(state)
            return
        if state.phase == "preflight":
            self._run_validation(state)
            return
        if state.phase in {"implement", "repair", "review"}:
            self._run_model_phase(state, context_for)
            return
        if state.phase == "test":
            self._run_validation(state)
            return
        if state.phase == "propose_next_rush":
            self._run_propose_next_rush(state)
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

    def _run_plan_todo(self, state):
        if self.todo_planner is None:
            state.phase = "author_oracle"
            return

        try:
            success, reason = self.todo_planner(state)
        except (OSError, RuntimeError, ValueError) as error:
            success, reason = False, f"plan_todo crashed: {error}; proceeding with a single implicit item"

        state.history.append({"phase": "plan_todo", "event": reason, "success": success})
        state.phase = "author_oracle"

    def _run_oracle_authoring(self, state):
        if self.oracle_author is None:
            state.phase = "failed"
            state.status = "failed"
            state.failure_summary = "author_oracle phase requires an oracle_author"
            return

        try:
            success, reason = self.oracle_author(state)
        except (OSError, RuntimeError, ValueError) as error:
            success, reason = False, f"oracle authoring crashed: {error}"

        state.history.append({"phase": "author_oracle", "event": reason, "success": success})
        if not success:
            state.failure_summary = reason
            self._advance_todo(state, item_success=False)
            return

        state.phase = "preflight"

    def _run_propose_next_rush(self, state):
        try:
            success, reason = self.next_rush_author(state)
        except (OSError, RuntimeError, ValueError) as error:
            success, reason = False, f"propose_next_rush crashed: {error}"

        state.history.append({"phase": "propose_next_rush", "event": reason, "success": success})
        # best-effort: a bad or missing proposal must not undo work that already passed validation
        state.phase = "finalize"

    def _next_phase_after_success(self):
        return "propose_next_rush" if self.next_rush_author is not None else "finalize"

    def _advance_todo(self, state, item_success):
        """Record the active item's outcome, then move to the next item or to the mission tail.

        Without a plan (`state.todo` empty), this reduces exactly to the pre-todo behaviour: succeed
        into the mission tail, or fail the whole mission. With a plan, one item failing only skips that
        item -- best-effort, the same philosophy already used for a failed `propose_next_rush` or a
        failed auto-merge: partial success must not throw away work that already passed validation.
        """

        if state.todo:
            state.todo[state.todo_index]["status"] = "done" if item_success else "skipped"

        has_more = bool(state.todo) and state.todo_index + 1 < len(state.todo)
        if has_more:
            state.todo_index += 1
            state.repair_attempts = 0
            state.failure_summary = ""
            state.phase = "author_oracle"
            return

        any_succeeded = any(item["status"] == "done" for item in state.todo) if state.todo else item_success
        if not any_succeeded:
            state.phase = "failed"
            state.status = "failed"
            return

        state.failure_summary = ""
        state.phase = self._next_phase_after_success()

    def _run_model_phase(self, state, context_for):
        phase = state.phase
        context = context_for(state)
        result = self.phase_runner(phase, context)
        state.changed_files = sorted(set([*state.changed_files, *result.changed_files]))
        state.history.append({"phase": phase, "event": result.summary, "success": result.success})

        if not result.success:
            state.failure_summary = result.summary
            self._advance_todo(state, item_success=False)
            return
        if phase == "review":
            self._advance_todo(state, item_success=True)
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
            self._advance_todo(state, item_success=True)
            return

        if phase == "preflight":
            state.failure_summary = compact_failure(result.stdout, result.stderr)
            state.phase = "implement"
            return

        state.failure_summary = compact_failure(result.stdout, result.stderr)
        if state.repair_attempts >= state.max_repairs:
            self._advance_todo(state, item_success=False)
            return

        state.repair_attempts += 1
        state.phase = "repair"
