import json
import subprocess
from pathlib import Path

import pytest

from pithos_harness import HarnessManager
from pithos_harness.broker import HarnessBroker
from pithos_harness.manager import HarnessError
from pithos_harness.files import sha256_file
from pithos_harness.validation import ResourceValidationError, validate_skill


RUN_ID = "run-20260823T010000Z-a1b2c3"


def _manager(tmp_path):
    active = tmp_path / "active"
    ground_truth = tmp_path / "ground-truth"
    journals = tmp_path / "journals"
    logs = tmp_path / "logs"
    active.mkdir()
    ground_truth.mkdir()
    (active / "AGENTS.md").write_text("active instructions\n")
    (ground_truth / "AGENTS.md").write_text("constitution\n")

    return HarnessManager(active, ground_truth, journals, logs), active, ground_truth, journals, logs


def _valid_skill(path: Path):
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(
        """---
name: probe-skill
description: Writes a deterministic marker during the harness probe.
---

# Probe skill

Write the requested marker and verify its contents.
"""
    )


def test_skill_is_snapshotted_promoted_and_visible_after_restart(tmp_path):
    manager, active, _, journals, _ = _manager(tmp_path)
    staged = tmp_path / "staged-skill"
    _valid_skill(staged)

    manager.begin(RUN_ID)
    target = manager.promote(RUN_ID, staged, Path(".pi/skills/probe-skill"), "skill")
    manifest = manager.finish(RUN_ID, "Needed deterministic writing.", "Skill contract validated.")

    restarted_manager = HarnessManager(active, tmp_path / "ground-truth", journals)
    validate_skill(target)
    assert restarted_manager.manifest(RUN_ID)["artifacts"]
    assert (journals / RUN_ID / "before" / "AGENTS.md").exists()
    assert (journals / RUN_ID / "after" / ".pi" / "skills" / "probe-skill" / "SKILL.md").exists()
    assert any(item["path"].endswith("SKILL.md") for item in manifest["artifacts"])


def test_extension_is_loaded_by_a_new_node_process(tmp_path):
    manager, active, _, _, _ = _manager(tmp_path)
    staged = tmp_path / "probe.ts"
    staged.write_text("export default function probe(value: unknown) { return value; }\n")
    manager.begin(RUN_ID)

    target = manager.promote(RUN_ID, staged, Path(".pi/extensions/probe.ts"), "extension")

    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--input-type=module",
            "-e",
            f"import('{target.as_uri()}').then(m => process.stdout.write(typeof m.default))",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == "function"
    assert target.exists()


def test_invalid_extension_preserves_active_version(tmp_path):
    manager, active, _, journals, _ = _manager(tmp_path)
    target = active / ".pi" / "extensions" / "probe.ts"
    target.parent.mkdir(parents=True)
    target.write_text("export default function probe() { return 'stable'; }\n")
    staged = tmp_path / "probe.ts"
    staged.write_text("export default function broken( {\n")
    manager.begin(RUN_ID)

    with pytest.raises(ResourceValidationError, match="syntax"):
        manager.promote(RUN_ID, staged, Path(".pi/extensions/probe.ts"), "extension")

    assert "stable" in target.read_text()
    validation = (journals / RUN_ID / "validation.md").read_text()
    assert "Passed: `false`" in validation


def test_ground_truth_is_unchanged_and_can_restore(tmp_path):
    manager, active, ground_truth, _, _ = _manager(tmp_path)
    original_hash = sha256_file(ground_truth / "AGENTS.md")
    (active / "AGENTS.md").write_text("mutated instructions\n")

    diff = manager.diff_ground_truth()
    restored = manager.restore(Path("AGENTS.md"))

    assert diff["AGENTS.md"]["status"] == "changed"
    assert restored.read_text() == "constitution\n"
    assert sha256_file(ground_truth / "AGENTS.md") == original_hash


def test_manifest_attributes_every_active_file_to_run(tmp_path):
    manager, _, _, journals, logs = _manager(tmp_path)
    manager.begin(RUN_ID)

    manifest = manager.finish(RUN_ID, "Reason.", "Validated.")

    assert {item["source_run_id"] for item in manifest["artifacts"]} == {RUN_ID}
    persisted = json.loads((journals / RUN_ID / "manifest.json").read_text())
    assert persisted["artifacts"] == manifest["artifacts"]
    events = [
        json.loads(line)
        for line in (logs / "runs" / RUN_ID / "events.jsonl").read_text().splitlines()
    ]
    assert [event["type"] for event in events] == [
        "harness.snapshot_before",
        "harness.snapshot_after",
    ]


def test_broker_promotes_only_staged_resource_to_matching_harness_root(tmp_path):
    manager, active, _, _, _ = _manager(tmp_path)
    staged = active / ".pithos-staging" / "probe-skill"
    _valid_skill(staged)
    manager.begin(RUN_ID)
    broker = HarnessBroker(manager)

    response = broker.handle(
        {
            "run_id": RUN_ID,
            "kind": "skill",
            "staged": ".pithos-staging/probe-skill",
            "target": ".pi/skills/probe-skill",
        }
    )

    assert response == {"ok": True, "target": ".pi/skills/probe-skill"}
    assert (active / ".pi" / "skills" / "probe-skill" / "SKILL.md").exists()
    with pytest.raises(HarnessError, match="staged"):
        broker.handle(
            {
                "run_id": RUN_ID,
                "kind": "skill",
                "staged": "outside/skill",
                "target": ".pi/skills/other",
            }
        )
