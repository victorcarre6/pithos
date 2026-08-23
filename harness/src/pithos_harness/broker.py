"""Constrain agent-requested harness promotions to staged resources."""

import re
from pathlib import Path

from .manager import HarnessError, HarnessManager


RUN_ID_PATTERN = re.compile(r"^run-[0-9]{8}T[0-9]{6}Z-[a-z0-9]{6}$")
TARGET_ROOTS = {
    "skill": (".pi", "skills"),
    "extension": (".pi", "extensions"),
    "prompt": (".pi", "prompts"),
}


class HarnessBroker:
    """Expose validation and promotion without exposing ground truth writes."""

    def __init__(self, manager: HarnessManager) -> None:
        self.manager = manager

    def handle(self, request: dict) -> dict:
        run_id = str(request.get("run_id", ""))
        kind = str(request.get("kind", ""))
        staged = Path(str(request.get("staged", "")))
        target = Path(str(request.get("target", "")))
        if not RUN_ID_PATTERN.fullmatch(run_id):
            raise HarnessError("run_id is invalid")
        if staged.is_absolute() or ".." in staged.parts or staged.parts[:1] != (".pithos-staging",):
            raise HarnessError("staged resource must remain under .pithos-staging")
        if target.is_absolute() or ".." in target.parts:
            raise HarnessError("target must remain relative")
        if kind == "instructions":
            if target not in {Path("AGENTS.md"), Path("SYSTEM.md")}:
                raise HarnessError("instructions target is not allowed")
        elif kind not in TARGET_ROOTS or target.parts[:2] != TARGET_ROOTS[kind]:
            raise HarnessError("target does not match the resource kind")

        source_path = self.manager.active_root / staged
        promoted = self.manager.promote(run_id, source_path, target, kind)

        return {"ok": True, "target": str(promoted.relative_to(self.manager.active_root))}
