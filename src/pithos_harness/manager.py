"""Coordinate immutable snapshots and explicit harness promotions."""

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pithos_runner.events import EventWriter

from .files import sha256_file, snapshot_tree, tree_hashes
from .validation import ResourceValidationError, validate_resource


class HarnessError(RuntimeError):
    """Reject an unsafe harness lifecycle transition."""


class HarnessManager:
    """Manage one active harness against external ground truth and journals."""

    def __init__(
        self,
        active_root: Path,
        ground_truth_root: Path,
        journals_root: Path,
        logs_root: Path | None = None,
    ) -> None:

        self.active_root = active_root.resolve()
        self.ground_truth_root = ground_truth_root.resolve()
        self.journals_root = journals_root.resolve()
        self.logs_root = logs_root.resolve() if logs_root else None

    def begin(self, run_id: str) -> Path:
        journal = self._journal(run_id)
        journal.mkdir(parents=True, exist_ok=True)
        snapshot_tree(self.active_root, journal / "before")
        (journal / "rationale.md").write_text("# Rationale\n\nPending agent rationale.\n", encoding="utf-8")
        (journal / "validation.md").write_text("# Validation\n\nPending validation.\n", encoding="utf-8")
        self._event(run_id, "harness.snapshot_before", {"journal": str(journal)})

        return journal

    def promote(self, run_id: str, staged: Path, relative_target: Path, kind: str) -> Path:
        journal = self._journal(run_id)
        if not (journal / "before").exists():
            raise HarnessError("begin must create the before snapshot before promotion")
        if relative_target.is_absolute() or ".." in relative_target.parts:
            raise HarnessError("target must remain relative to the active harness")
        if not staged.exists():
            raise HarnessError(f"staged resource is absent: {staged}")

        try:
            validate_resource(staged, kind)
        except ResourceValidationError as error:
            self._record_validation(journal, relative_target, kind, False, str(error))
            self._event(run_id, "harness.rejected", {"target": str(relative_target), "kind": kind})
            raise

        target = self.active_root / relative_target
        temporary = target.parent / f".{target.name}.{os.getpid()}.pending"
        if temporary.exists():
            if temporary.is_dir():
                shutil.rmtree(temporary)
            else:
                temporary.unlink()
        temporary.parent.mkdir(parents=True, exist_ok=True)
        if staged.is_dir():
            shutil.copytree(staged, temporary)
        else:
            shutil.copy2(staged, temporary)
        if target.exists():
            backup = journal / "replaced" / relative_target
            backup.parent.mkdir(parents=True, exist_ok=True)
            if target.is_dir():
                shutil.copytree(target, backup)
                shutil.rmtree(target)
            else:
                shutil.copy2(target, backup)
                target.unlink()
        temporary.replace(target)
        self._record_validation(journal, relative_target, kind, True, "validated and promoted")
        self._event(run_id, "harness.promoted", {"target": str(relative_target), "kind": kind})

        return target

    def finish(self, run_id: str, rationale: str, validation: str) -> dict:
        journal = self._journal(run_id)
        snapshot_tree(self.active_root, journal / "after")
        (journal / "rationale.md").write_text(f"# Rationale\n\n{rationale.strip()}\n", encoding="utf-8")
        validation_path = journal / "validation.md"
        with validation_path.open("a", encoding="utf-8") as validation_file:
            validation_file.write(f"\n## Run conclusion\n\n{validation.strip()}\n")
        manifest = self.manifest(run_id)
        (journal / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        self._event(
            run_id,
            "harness.snapshot_after",
            {"artifact_count": len(manifest["artifacts"])},
        )

        return manifest

    def manifest(self, run_id: str) -> dict:
        artifacts = []
        for path, digest in tree_hashes(self.active_root).items():
            artifacts.append(
                {
                    "path": path,
                    "sha256": digest,
                    "source_run_id": run_id,
                }
            )

        return {
            "schema_version": "1.0",
            "run_id": run_id,
            "generated_at": datetime.now(UTC).isoformat(),
            "artifacts": artifacts,
        }

    def diff_ground_truth(self) -> dict:
        ground_truth = tree_hashes(self.ground_truth_root)
        active = tree_hashes(self.active_root)
        paths = sorted(set(ground_truth) | set(active))

        return {
            path: {
                "ground_truth": ground_truth.get(path),
                "active": active.get(path),
                "status": "same" if ground_truth.get(path) == active.get(path) else "changed",
            }
            for path in paths
        }

    def restore(self, relative_path: Path) -> Path:
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise HarnessError("restore path must remain relative")
        source = self.ground_truth_root / relative_path
        if not source.exists():
            raise HarnessError(f"ground truth resource is absent: {source}")
        target = self.active_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)

        return target

    def _journal(self, run_id: str) -> Path:
        if not run_id.startswith("run-"):
            raise HarnessError("run_id is invalid")

        return self.journals_root / run_id

    def _record_validation(self, journal: Path, target: Path, kind: str, passed: bool, detail: str) -> None:
        with (journal / "validation.md").open("a", encoding="utf-8") as validation_file:
            validation_file.write(
                f"\n## {target}\n\n- Kind: `{kind}`\n- Passed: `{str(passed).lower()}`\n- Detail: {detail}\n"
            )

    def _event(self, run_id: str, event_type: str, payload: dict) -> None:
        if not self.logs_root:
            return
        events_path = self.logs_root / "runs" / run_id / "events.jsonl"
        EventWriter(events_path, run_id, source="harness").append(event_type, payload)
