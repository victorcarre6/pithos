"""Hash and copy harness trees without following external symlinks."""

import hashlib
import shutil
from pathlib import Path


EXCLUDED_PARTS = {".git", "node_modules", "__pycache__", ".pithos-staging"}


def iter_files(root: Path):
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            continue
        if path.is_file():
            yield path, relative


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def snapshot_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        raise FileExistsError(f"snapshot already exists: {destination}")
    destination.mkdir(parents=True)
    for path, relative in iter_files(source):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def tree_hashes(root: Path) -> dict[str, str]:
    return {str(relative): sha256_file(path) for path, relative in iter_files(root)}

