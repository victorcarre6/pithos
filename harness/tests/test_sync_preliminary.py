import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "sync_preliminary.py"
SPEC = importlib.util.spec_from_file_location("pithos_sync_preliminary", SCRIPT_PATH)
sync_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_module)


def test_sync_copies_declared_sources_and_hashes_without_caches(tmp_path, monkeypatch):
    harness = tmp_path / "harness"
    preliminary = tmp_path / "preliminary"
    source = harness / "src" / "fixture"
    source.mkdir(parents=True)
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "module.pyc").write_bytes(b"cache")
    test = harness / "tests" / "test_fixture.py"
    test.parent.mkdir()
    test.write_text("def test_value(): pass\n", encoding="utf-8")
    monkeypatch.setattr(
        sync_module,
        "PROJECTS",
        {"01-fixture": {"src": ["src/fixture"], "tests": ["tests/test_fixture.py"]}},
    )

    sync_module.sync(harness, preliminary)
    implementation = preliminary / "01-fixture" / "implementation"
    manifest = json.loads((implementation / "SNAPSHOT.json").read_text(encoding="utf-8"))

    assert (implementation / "src" / "fixture" / "module.py").is_file()
    assert not (implementation / "src" / "fixture" / "__pycache__").exists()
    assert {item["path"] for item in manifest["files"]} == {
        "src/fixture/module.py",
        "tests/test_fixture.py",
    }
    assert sync_module.verify(harness, preliminary) == []

    (implementation / "src" / "fixture" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
    assert sync_module.verify(harness, preliminary) == [
        {"project": "01-fixture", "source": "src/fixture"}
    ]
