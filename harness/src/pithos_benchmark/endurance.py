"""Deterministic multi-step Pi task used as the long benchmark gate."""

import subprocess
from pathlib import Path

from pithos_capability_probe.scenarios import Scenario
from pithos_contracts import ValidationFailure, validate_report


def _prepare(workspace: Path):
    """Create a small broken project with tests and a report contract."""

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "PROJECT.md").write_text(
        "Implement add(a, b), run the tests, then write the supplied continuity report.\n",
        encoding="utf-8",
    )
    (workspace / "calculator.py").write_text(
        "def add(a, b):\n    raise NotImplementedError\n",
        encoding="utf-8",
    )
    (workspace / "test_calculator.py").write_text(
        (
            "import unittest\n\n"
            "from calculator import add\n\n\n"
            "class CalculatorTest(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(19, 23), 42)\n\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        ),
        encoding="utf-8",
    )


def _verify(workspace: Path, events: list[dict]):
    """Verify code, test execution, report contract and real tool trajectory."""

    test = subprocess.run(
        ["python", "-m", "unittest", "-v", "test_calculator.py"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    report = workspace / "report.md"
    try:
        validate_report(report)
        report_valid = True
    except (OSError, ValidationFailure):
        report_valid = False
    tools = {
        event.get("toolName")
        for event in events
        if event.get("type") == "tool_execution_end" and not event.get("isError", False)
    }
    passed = test.returncode == 0 and report_valid and {"read", "edit", "bash", "write"}.issubset(tools)

    return passed, f"tests={test.returncode == 0}, report={report_valid}, tools={sorted(tools)}"


ENDURANCE_SCENARIO = Scenario(
    name="benchmark_endurance",
    prompt=(
        "Read PROJECT.md and the source. Implement only the requested function with edit, run the real tests "
        "with bash, then use write to create report.md from REPORT_TEMPLATE.md without changing its metadata."
    ),
    prepare=_prepare,
    verify=_verify,
    report_expected=True,
)
