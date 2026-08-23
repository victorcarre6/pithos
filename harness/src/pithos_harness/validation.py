"""Validate staged skills, prompts, instructions and TypeScript extensions."""

import re
import subprocess
from pathlib import Path

import yaml


SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ResourceValidationError(ValueError):
    """Reject a staged resource before it reaches the active harness."""


def validate_skill(path: Path) -> None:
    skill_path = path / "SKILL.md" if path.is_dir() else path
    if not skill_path.exists():
        raise ResourceValidationError("skill must contain SKILL.md")
    content = skill_path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        raise ResourceValidationError("skill frontmatter is absent")
    try:
        _, frontmatter, body = content.split("---", 2)
        metadata = yaml.safe_load(frontmatter)
    except (ValueError, yaml.YAMLError) as error:
        raise ResourceValidationError(f"invalid skill frontmatter: {error}") from error
    if not isinstance(metadata, dict):
        raise ResourceValidationError("skill frontmatter must be an object")
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if not isinstance(name, str) or not SKILL_NAME.fullmatch(name) or len(name) > 64:
        raise ResourceValidationError("skill name is invalid")
    if not isinstance(description, str) or not description.strip() or len(description) > 1024:
        raise ResourceValidationError("skill description is invalid")
    if not body.strip():
        raise ResourceValidationError("skill instructions are empty")


def validate_extension(path: Path) -> None:
    if path.suffix not in {".ts", ".js", ".mjs"}:
        raise ResourceValidationError("extension must be TypeScript or JavaScript")
    validator_script = Path(__file__).resolve().parents[2] / "scripts" / "validate-typescript.mjs"
    result = subprocess.run(
        ["node", str(validator_script), str(path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        error = result.stderr.strip() or result.stdout.strip()
        raise ResourceValidationError(f"extension syntax is invalid: {error}")


def validate_markdown(path: Path) -> None:
    if path.suffix != ".md" or not path.read_text(encoding="utf-8").strip():
        raise ResourceValidationError("Markdown resource must be non-empty")


def validate_resource(path: Path, kind: str) -> None:
    validators = {
        "skill": validate_skill,
        "extension": validate_extension,
        "prompt": validate_markdown,
        "instructions": validate_markdown,
    }
    if kind not in validators:
        raise ResourceValidationError(f"unsupported resource kind: {kind}")
    validators[kind](path)
