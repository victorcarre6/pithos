"""Build small, explicit contexts for one Ling phase."""

from dataclasses import dataclass


class ContextBudgetExceeded(ValueError):
    """Raised before inference when mandatory context cannot fit."""


@dataclass(frozen=True)
class ContextSection:
    """One named context fragment ordered by relevance."""

    name: str
    content: str
    required: bool = False


def build_context(sections, limit=40_000):
    """Render required sections then fit optional sections within a character budget."""

    required = [section for section in sections if section.required]
    optional = [section for section in sections if not section.required]
    selected = required.copy()

    required_text = _render(selected)
    if len(required_text) > limit:
        raise ContextBudgetExceeded(
            f"mandatory context uses {len(required_text)} characters, budget is {limit}"
        )

    for section in optional:
        candidate = _render([*selected, section])
        if len(candidate) <= limit:
            selected.append(section)

    rendered = _render(selected)
    included = [section.name for section in selected]

    return rendered, included


def compact_failure(stdout, stderr, line_limit=6):
    """Keep the first distinct failure-bearing validation lines."""

    lines = []
    for raw_line in f"{stdout}\n{stderr}".splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        signals = ("error", "failed", "failure", "traceback", "assert", "exit")
        if line and any(signal in lowered for signal in signals) and line not in lines:
            lines.append(line)
        if len(lines) == line_limit:
            break

    if not lines:
        fallback = next((line.strip() for line in stdout.splitlines() if line.strip()), "validation failed")
        lines.append(fallback)

    return "\n".join(lines)


def _render(sections):
    blocks = []
    for section in sections:
        blocks.append(f"## {section.name}\n\n{section.content.strip()}")

    return "\n\n".join(blocks) + "\n"
