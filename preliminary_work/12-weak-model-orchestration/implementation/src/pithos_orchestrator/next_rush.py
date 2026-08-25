"""Author one harness-rendered proposal for the next bounded micro-rush.

The model never contributes executable code or touches infrastructure fields.
It only selects a handful of bounded strings -- a micro-rush id, a title, a
description, and a short list of relative file paths -- inside a
JSON-schema-constrained Ollama call. The harness validates every field,
copies the current .pithos.json verbatim for everything else (seed,
experiment_id, runtime, model, pi_config, ground_truth), and writes the
result back into the workspace so it rides along in the same commit/PR the
mission already produces. A human still has to merge that PR before the
proposal takes any effect.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
import re


MAX_TARGET_FILES = 3
MAX_TITLE_CHARS = 160
MAX_DESCRIPTION_CHARS = 500
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9_.\-/]{1,120}$")
_DEF = re.compile(r"(?m)^\s*def\s+([A-Za-z_][A-Za-z0-9_]{0,63})\s*\(")


class NextRushSpecError(ValueError):
    """The model's proposed next micro-rush could not be trusted."""


class NextRushAuthor:
    """Bind next-rush proposal authoring to one mission's project config."""

    def __init__(self, model, project, workspace, opener=None, timeout=45):
        self.model = model
        self.project = project
        self.workspace = Path(workspace)
        self.opener = opener
        self.timeout = timeout

    def __call__(self, state):
        seed = str(self.project.get("seed", "")).strip()
        if not seed:
            return False, "propose_next_rush skipped: no seed configured"

        facts = {
            "seed": seed,
            "current_micro_rush_id": self.project.get("micro_rush_id", ""),
            "current_title": str(self.project.get("title", "")).strip(),
            "current_description": str(self.project.get("description", "")).strip(),
            "changed_files": list(state.changed_files),
            "existing_functions": existing_functions(self.workspace, state.changed_files),
        }

        try:
            raw = _request_next_rush(self.model, facts, self.timeout, self.opener)
            proposal = _validate_proposal(raw, facts["current_micro_rush_id"], self.workspace)
        except NextRushSpecError as error:
            return False, f"propose_next_rush failed: {error}"

        updated = dict(self.project)
        updated["micro_rush_id"] = proposal["micro_rush_id"]
        updated["title"] = proposal["title"]
        updated["description"] = proposal["description"]
        updated["target_files"] = proposal["target_files"]
        updated.pop("validation_command", None)

        (self.workspace / ".pithos.json").write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")

        return True, f"proposed next micro-rush {proposal['micro_rush_id']!r}: {proposal['title']}"


def existing_functions(workspace, relative_paths):
    """List `def <name>(` matches found in the given workspace-relative files, sorted and de-duplicated.

    Shared with `plan_todo.py`: both bound a weak model's proposal to functions that already exist.
    """

    names = set()
    for relative in relative_paths:
        path = Path(workspace) / relative
        if not path.is_file():
            continue
        names.update(_DEF.findall(path.read_text(encoding="utf-8", errors="replace")))

    return sorted(names)


def _request_next_rush(model, facts, timeout, opener):
    prompt = (
        "Propose UN seul prochain micro-rush borné qui rapproche le projet de l'objectif ci-dessous, en "
        "t'appuyant sur ce qui vient d'être accompli. N'écris ni code ni instructions techniques : "
        "seulement un identifiant court, un titre, une description et une courte liste de chemins de "
        "fichiers relatifs à modifier ou créer. Réponds uniquement avec l'objet JSON demandé.\n\n"
        "`existing_functions` liste les fonctions déjà définies dans les fichiers qui viennent d'être "
        "modifiés : préfère un rush qui change le comportement d'une de ces fonctions existantes, plutôt "
        "qu'un rush qui n'a de sens qu'en ajoutant une fonction encore inexistante -- le contrat de test "
        "généré ensuite par le harnais ne peut viser qu'une fonction déjà présente dans le fichier cible. "
        "`target_files` doit lister uniquement des fichiers `.py` : le harnais ne sait générer un contrat "
        "que sur du code Python, jamais sur de la documentation ou de la configuration.\n\n"
        f"Faits : {json.dumps(facts, ensure_ascii=False, sort_keys=True)}"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": _spec_schema(),
        "options": {"num_predict": 300, "temperature": 0.4},
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
        raise NextRushSpecError("next-rush proposal request failed") from error

    try:
        return json.loads(str(body.get("response", "")))
    except json.JSONDecodeError as error:
        raise NextRushSpecError("next-rush proposal is not structured JSON") from error


def _spec_schema():
    return {
        "type": "object",
        "properties": {
            "micro_rush_id": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "target_files": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_TARGET_FILES,
                "items": {"type": "string"},
            },
        },
        "required": ["micro_rush_id", "title", "description", "target_files"],
    }


def _validate_proposal(raw, current_micro_rush_id, workspace):
    if not isinstance(raw, dict):
        raise NextRushSpecError("next-rush proposal must be a JSON object")

    micro_rush_id = raw.get("micro_rush_id")
    if not isinstance(micro_rush_id, str) or not _IDENTIFIER.fullmatch(micro_rush_id):
        raise NextRushSpecError("next-rush micro_rush_id is not a valid identifier")
    if micro_rush_id == current_micro_rush_id:
        raise NextRushSpecError("next-rush micro_rush_id must differ from the current one")

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > MAX_TITLE_CHARS:
        raise NextRushSpecError("next-rush title must be a short non-empty string")

    description = raw.get("description")
    if not isinstance(description, str) or not description.strip() or len(description) > MAX_DESCRIPTION_CHARS:
        raise NextRushSpecError("next-rush description must be a bounded non-empty string")

    target_files = raw.get("target_files")
    if not isinstance(target_files, list) or not (1 <= len(target_files) <= MAX_TARGET_FILES):
        raise NextRushSpecError("next-rush target_files must be a short non-empty list")

    return {
        "micro_rush_id": micro_rush_id,
        "title": title.strip(),
        "description": description.strip(),
        "target_files": [_validate_relative_path(path, workspace) for path in target_files],
    }


def _validate_relative_path(path, workspace):
    if not isinstance(path, str) or not _RELATIVE_PATH.fullmatch(path):
        raise NextRushSpecError(f"next-rush target file {path!r} is not a safe relative path")
    if path.startswith("/") or ".." in Path(path).parts:
        raise NextRushSpecError(f"next-rush target file {path!r} escapes the workspace")
    if not path.endswith(".py"):
        # the downstream pipeline is Python-only end to end: author_oracle looks for `def <name>(`
        # and its new-file fallback does importlib.import_module -- a doc or config path there is
        # either meaningless or mechanically broken, never a real check
        raise NextRushSpecError(f"next-rush target file {path!r} must be a Python file")

    workspace_root = workspace.resolve()
    resolved = (workspace_root / path).resolve()
    if resolved != workspace_root and workspace_root not in resolved.parents:
        raise NextRushSpecError(f"next-rush target file {path!r} escapes the workspace")

    return path
