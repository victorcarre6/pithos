"""Fixtures, prompts and external verifiers for Pi capability scenarios."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pithos_contracts import ValidationFailure, validate_report


Verifier = Callable[[Path, list[dict]], tuple[bool, str]]


@dataclass(frozen=True)
class Scenario:
    """Describe one isolated capability and its observable success condition."""

    name: str
    prompt: str
    prepare: Callable[[Path], None]
    verify: Verifier
    report_expected: bool = False
    follow_up_prompt: str | None = None


def _empty_prepare(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)


def _prepare_read(workspace: Path) -> None:
    _empty_prepare(workspace)
    (workspace / "input.txt").write_text("PITHOS_READ_SECRET_42\n", encoding="utf-8")


def _prepare_edit(workspace: Path) -> None:
    _empty_prepare(workspace)
    (workspace / "target.txt").write_text("state=before\n", encoding="utf-8")


def _prepare_test(workspace: Path) -> None:
    _empty_prepare(workspace)
    (workspace / "test_probe.py").write_text(
        (
            "import unittest\n\n"
            "class ProbeTest(unittest.TestCase):\n"
            "    def test_probe(self):\n"
            "        self.assertEqual(6 * 7, 42)\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        encoding="utf-8",
    )


def _tool_names(events: list[dict]) -> list[str]:
    return [
        event.get("toolName", "")
        for event in events
        if event.get("type") == "tool_execution_end" and not event.get("isError", False)
    ]


def _assistant_text(events: list[dict]) -> str:
    texts = []
    for event in events:
        if event.get("type") != "message_end":
            continue
        message = event.get("message", {})
        if message.get("role") != "assistant":
            continue
        for content in message.get("content", []):
            if content.get("type") == "text":
                texts.append(content.get("text", ""))

    return "\n".join(texts)


def _verify_text(workspace: Path, events: list[dict]) -> tuple[bool, str]:
    content = _assistant_text(events).strip()

    return content == "PITHOS_TEXT_OK", f"assistant={content!r}"


def _verify_read(workspace: Path, events: list[dict]) -> tuple[bool, str]:
    tool_names = _tool_names(events)
    content = _assistant_text(events)
    passed = "read" in tool_names and "PITHOS_READ_SECRET_42" in content

    return passed, f"tools={tool_names}, secret_returned={'PITHOS_READ_SECRET_42' in content}"


def _verify_file(path: str, expected: str, tool: str) -> Verifier:
    def verify(workspace: Path, events: list[dict]) -> tuple[bool, str]:
        target = workspace / path
        actual = target.read_text(encoding="utf-8") if target.exists() else None
        tool_names = _tool_names(events)
        passed = actual == expected and tool in tool_names

        return passed, f"tools={tool_names}, content={actual!r}"

    return verify


def _verify_test(workspace: Path, events: list[dict]) -> tuple[bool, str]:
    tool_names = _tool_names(events)
    outputs = [
        event.get("result", {})
        for event in events
        if event.get("type") == "tool_execution_end" and event.get("toolName") == "bash"
    ]
    serialized_outputs = repr(outputs)
    passed = "bash" in tool_names and "OK" in serialized_outputs

    return passed, f"tools={tool_names}, unittest_ok={'OK' in serialized_outputs}"


def _verify_multi_tool(workspace: Path, events: list[dict]) -> tuple[bool, str]:
    target = workspace / "derived.txt"
    actual = target.read_text(encoding="utf-8") if target.exists() else None
    tool_names = set(_tool_names(events))
    passed = {"read", "write", "bash"}.issubset(tool_names) and actual == "PITHOS_MULTI_42\n"

    return passed, f"tools={sorted(tool_names)}, content={actual!r}"


def _verify_report(workspace: Path, events: list[dict]) -> tuple[bool, str]:
    report_path = workspace / "report.md"
    if not report_path.exists():
        return False, "report.md is absent"

    try:
        validate_report(report_path)
    except ValidationFailure as error:
        return False, str(error)

    return "write" in _tool_names(events), "report contract is valid"


def _verify_skill_reuse(workspace: Path, events: list[dict]) -> tuple[bool, str]:
    skill_path = workspace / ".pi" / "skills" / "probe-skill" / "SKILL.md"
    content = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
    assistant = _assistant_text(events).strip()
    passed = "name: probe-skill" in content and assistant == "PITHOS_SKILL_REUSED"

    return passed, f"skill_exists={skill_path.exists()}, assistant={assistant!r}"


def _verify_extension_reuse(workspace: Path, events: list[dict]) -> tuple[bool, str]:
    extension_path = workspace / ".pi" / "extensions" / "probe-extension.ts"
    tool_names = _tool_names(events)
    passed = extension_path.exists() and "probe_marker" in tool_names

    return passed, f"extension_exists={extension_path.exists()}, tools={tool_names}"


SCENARIOS = {
    "text": Scenario(
        name="text",
        prompt="Reply with exactly PITHOS_TEXT_OK. Do not use tools.",
        prepare=_empty_prepare,
        verify=_verify_text,
    ),
    "read": Scenario(
        name="read",
        prompt="Use the read tool on input.txt, then reply with its exact content.",
        prepare=_prepare_read,
        verify=_verify_read,
    ),
    "write": Scenario(
        name="write",
        prompt="Use the write tool to create created.txt containing exactly PITHOS_WRITE_OK followed by a newline.",
        prepare=_empty_prepare,
        verify=_verify_file("created.txt", "PITHOS_WRITE_OK\n", "write"),
    ),
    "edit": Scenario(
        name="edit",
        prompt="Use the edit tool to replace state=before with state=after in target.txt.",
        prepare=_prepare_edit,
        verify=_verify_file("target.txt", "state=after\n", "edit"),
    ),
    "bash": Scenario(
        name="bash",
        prompt="Use bash to run: printf 'PITHOS_BASH_OK\\n' > bash.txt",
        prepare=_empty_prepare,
        verify=_verify_file("bash.txt", "PITHOS_BASH_OK\n", "bash"),
    ),
    "test": Scenario(
        name="test",
        prompt="Use bash to run python -m unittest -v test_probe.py. Report the real result.",
        prepare=_prepare_test,
        verify=_verify_test,
    ),
    "multi_tool": Scenario(
        name="multi_tool",
        prompt=(
            "Read input.txt. Use write to create derived.txt containing exactly PITHOS_MULTI_42 and a newline. "
            "Then use bash to verify it with: grep -Fx PITHOS_MULTI_42 derived.txt"
        ),
        prepare=_prepare_read,
        verify=_verify_multi_tool,
    ),
    "report": Scenario(
        name="report",
        prompt=(
            "Use write to create report.md. Copy the YAML metadata and the three sections from "
            "REPORT_TEMPLATE.md, replacing no values."
        ),
        prepare=_empty_prepare,
        verify=_verify_report,
        report_expected=True,
    ),
    "skill_reuse": Scenario(
        name="skill_reuse",
        prompt=(
            "Use write to create .pi/skills/probe-skill/SKILL.md with exactly this content:\n"
            "---\nname: probe-skill\ndescription: Return the deterministic capability marker.\n---\n\n"
            "# Probe skill\n\nWhen asked for the skill marker, reply exactly PITHOS_SKILL_REUSED.\n"
        ),
        prepare=_empty_prepare,
        verify=_verify_skill_reuse,
        follow_up_prompt="Use the probe-skill skill to provide its marker.",
    ),
    "extension_reuse": Scenario(
        name="extension_reuse",
        prompt=(
            "Use write to create .pi/extensions/probe-extension.ts with exactly this content:\n"
            "import { Type } from \"@earendil-works/pi-ai\";\n\n"
            "export default function probe(pi) {\n"
            "  pi.registerTool({\n"
            "    name: \"probe_marker\",\n"
            "    label: \"Probe Marker\",\n"
            "    description: \"Return the deterministic extension marker.\",\n"
            "    parameters: Type.Object({}),\n"
            "    async execute() {\n"
            "      return { content: [{ type: \"text\", text: \"PITHOS_EXTENSION_REUSED\" }], details: {} };\n"
            "    },\n"
            "  });\n"
            "}\n"
        ),
        prepare=_empty_prepare,
        verify=_verify_extension_reuse,
        follow_up_prompt="Use the probe_marker tool exactly once, then report its result.",
    ),
}


def prepare_report_template(workspace: Path) -> None:
    """Add a valid deterministic report template after the base scenario setup."""

    template = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid" / "report.md"
    (workspace / "REPORT_TEMPLATE.md").write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
