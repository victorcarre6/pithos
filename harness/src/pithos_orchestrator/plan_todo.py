"""Author one harness-rendered decomposition of a micro-rush into small, independently-testable items.

The model never contributes executable code or touches infrastructure fields. It only proposes, per item,
a title, a description, and a short list of relative file paths taken from the rush's own approved
`target_files`. The harness validates every field before trusting it. Decomposition is a pure convenience
for a weak model working better in short, fresh-context passes -- it must never be a hard requirement, so
any failure (unreachable model, invalid JSON, an item that fails validation) simply leaves `state.todo`
empty, and the mission proceeds exactly as it would with no plan at all: one implicit item covering the
whole rush.
"""

import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from .next_rush import existing_functions


MAX_ITEMS = 4
MAX_TITLE_CHARS = 160
MAX_DESCRIPTION_CHARS = 500
_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9_.\-/]{1,120}$")


class TodoPlanError(ValueError):
    """The model's proposed decomposition could not be trusted."""


class TodoPlanner:
    """Bind todo-list authoring to one mission's project config."""

    def __init__(self, model, project, workspace, opener=None, timeout=45):
        self.model = model
        self.project = project
        self.workspace = Path(workspace)
        self.opener = opener
        self.timeout = timeout

    def __call__(self, state):
        target_files = self.project.get("target_files") or []
        facts = {
            "title": str(self.project.get("title", "")).strip(),
            "description": str(self.project.get("description", "")).strip(),
            "target_files": target_files,
            "existing_functions": existing_functions(self.workspace, target_files),
        }

        try:
            raw = _request_plan(self.model, facts, self.timeout, self.opener)
            items = _validate_plan(raw, target_files)
        except TodoPlanError as error:
            return False, f"plan_todo failed: {error}; proceeding with a single implicit item"

        state.todo = items
        state.todo_index = 0

        return True, f"planned {len(items)} item(s): " + "; ".join(item["title"] for item in items)


def _request_plan(model, facts, timeout, opener):
    prompt = (
        "Scinde la tâche suivante en 1 à "
        f"{MAX_ITEMS} sous-étapes indépendantes, ordonnées, et aussi simples que possible. Chaque étape doit "
        "modifier le comportement d'UNE seule fonction déjà listée dans `existing_functions` -- jamais une "
        "fonction absente, jamais un nouveau fichier. Si la tâche est déjà minimale, réponds avec une seule "
        "étape identique à la tâche. N'écris ni code ni instructions techniques : seulement, pour chaque "
        "étape, un titre, une description et une courte liste de chemins pris dans `target_files`. Réponds "
        "uniquement avec l'objet JSON demandé.\n\n"
        f"Faits : {json.dumps(facts, ensure_ascii=False, sort_keys=True)}"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": _plan_schema(),
        "options": {"num_predict": 400, "temperature": 0.3},
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    open_request = opener or urllib.request.urlopen
    try:
        with open_request(request, timeout=timeout) as response:
            body = json.load(response)
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise TodoPlanError("plan request failed") from error

    try:
        return json.loads(str(body.get("response", "")))
    except json.JSONDecodeError as error:
        raise TodoPlanError("plan is not structured JSON") from error


def _plan_schema():
    return {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_ITEMS,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "target_files": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    },
                    "required": ["title", "description", "target_files"],
                },
            },
        },
        "required": ["items"],
    }


def _validate_plan(raw, allowed_target_files):
    if not isinstance(raw, dict):
        raise TodoPlanError("plan must be a JSON object")

    items = raw.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= MAX_ITEMS):
        raise TodoPlanError(f"plan must contain between 1 and {MAX_ITEMS} items")

    allowed = set(allowed_target_files)

    return [_validate_item(item, allowed) for item in items]


def _validate_item(raw, allowed_target_files):
    if not isinstance(raw, dict):
        raise TodoPlanError("plan item must be a JSON object")

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE_CHARS:
        raise TodoPlanError("plan item title must be a short non-empty string")

    description = raw.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > MAX_DESCRIPTION_CHARS:
        raise TodoPlanError("plan item description must be a bounded non-empty string")

    target_files = raw.get("target_files")
    if not isinstance(target_files, list) or not target_files:
        raise TodoPlanError("plan item target_files must be a short non-empty list")
    for path in target_files:
        if not isinstance(path, str) or not _RELATIVE_PATH.fullmatch(path) or path not in allowed_target_files:
            raise TodoPlanError(f"plan item target file {path!r} is not one of the rush's approved target files")

    return {
        "title": title.strip(),
        "description": description.strip(),
        "target_files": target_files,
        "status": "pending",
    }
