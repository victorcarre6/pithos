from pithos_orchestrator.pi_phase import _valid_python_changes


def test_valid_python_changes_accepts_parseable_source(tmp_path):
    workspace = tmp_path / "workspace"
    projection = tmp_path / "projection"
    workspace.mkdir()
    projection.mkdir()
    (workspace / "audio_visualizer.py").write_text("def process_frame():\n    return 0\n")
    (projection / "audio_visualizer.py").write_text("def process_frame():\n    return 1\n")

    assert _valid_python_changes(workspace, projection, ["audio_visualizer.py"]) is True


def test_valid_python_changes_rejects_malformed_tool_call_dumped_as_content(tmp_path):
    workspace = tmp_path / "workspace"
    projection = tmp_path / "projection"
    workspace.mkdir()
    projection.mkdir()
    (workspace / "audio_visualizer.py").write_text("def split_bands(magnitudes):\n    return magnitudes\n")
    (projection / "audio_visualizer.py").write_text('{"action": "check_file", "path": "/workspace/x"}')

    assert _valid_python_changes(workspace, projection, ["audio_visualizer.py"]) is False


def test_valid_python_changes_rejects_syntax_errors(tmp_path):
    workspace = tmp_path / "workspace"
    projection = tmp_path / "projection"
    workspace.mkdir()
    projection.mkdir()
    (workspace / "audio_visualizer.py").write_text("def split_bands(magnitudes):\n    return magnitudes\n")
    (projection / "audio_visualizer.py").write_text("def split_bands(magnitudes:\n    return magnitudes\n")

    assert _valid_python_changes(workspace, projection, ["audio_visualizer.py"]) is False


def test_valid_python_changes_ignores_non_python_files(tmp_path):
    workspace = tmp_path / "workspace"
    projection = tmp_path / "projection"
    workspace.mkdir()
    projection.mkdir()
    (projection / "notes.md").write_text("not python at all {")

    assert _valid_python_changes(workspace, projection, ["notes.md"]) is True


def test_valid_python_changes_allows_a_brand_new_file_with_no_prior_defs(tmp_path):
    workspace = tmp_path / "workspace"
    projection = tmp_path / "projection"
    workspace.mkdir()
    projection.mkdir()
    (projection / "new_module.py").write_text('{"action": "check_file"}')

    assert _valid_python_changes(workspace, projection, ["new_module.py"]) is True
