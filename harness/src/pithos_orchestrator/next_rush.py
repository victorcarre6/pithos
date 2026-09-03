"""Author one harness-rendered proposal for the next bounded micro-rush.

The model never contributes executable code or touches infrastructure fields.
It only selects a handful of bounded strings -- a micro-rush id, a title, a
description, and a short list of relative file paths -- inside a
JSON-schema-constrained Ollama call. The harness validates every field,
copies the current .pithos.json verbatim for everything else (seed,
experiment_id, runtime, model, pi_config, ground_truth), and writes the
result back into the workspace so it rides along in the same commit/PR the
mission already produces. The runner can also invoke the same author after a
completed or repeatedly failed rush, so a transient proposal failure never
stalls an autonomous campaign permanently.
"""

import json
import urllib.error
import urllib.request
from pathlib import Path
import re


MAX_TARGET_FILES = 3
MAX_TITLE_CHARS = 160
MAX_DESCRIPTION_CHARS = 500
MAX_CONTEXT_FILES = 12
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9_.\-/]{1,120}$")
_DEF = re.compile(r"(?m)^\s*def\s+([A-Za-z_][A-Za-z0-9_]{0,63})\s*\(")
_ROADMAP_ITEM = re.compile(r"(?m)^\s*-\s+\[(DONE|TODO|x|X| )\]\s+")


class NextRushSpecError(ValueError):
    """The model's proposed next micro-rush could not be trusted."""


class NextRushAuthor:
    """Bind next-rush proposal authoring to one mission's project config."""

    def __init__(self, model, project, workspace, opener=None, timeout=45, attempts=3):
        self.model = model
        self.project = project
        self.workspace = Path(workspace)
        self.opener = opener
        self.timeout = timeout
        self.attempts = attempts

    def __call__(self, state):
        seed = str(self.project.get("seed", "")).strip()
        if not seed:
            return False, "propose_next_rush skipped: no seed configured"

        # contexte produit borné, y compris lorsque le dernier diff est vide
        roadmap_path = self.workspace / "docs" / "ROADMAP.md"
        roadmap_content = ""
        if roadmap_path.is_file():
            roadmap_content = roadmap_path.read_text(encoding="utf-8", errors="replace")
        if roadmap_complete(self.workspace, content=roadmap_content):
            reason = "all declared roadmap items are done"
            state.artifacts["stop_proposal"] = reason

            return True, f"project completion proposed: {reason}"

        roadmap = roadmap_content[:4000]
        context_files = candidate_files(self.workspace)
        target_files = list(self.project.get("target_files") or [])
        relevant_files = list(dict.fromkeys([*state.changed_files, *target_files, *context_files]))
        forbidden_functions = list(state.artifacts.get("avoid_target_functions") or [])
        facts = {
            "seed": seed,
            "current_micro_rush_id": self.project.get("micro_rush_id", ""),
            "current_title": str(self.project.get("title", "")).strip(),
            "current_description": str(self.project.get("description", "")).strip(),
            "changed_files": list(state.changed_files),
            "candidate_files": context_files,
            "existing_functions": existing_functions(self.workspace, relevant_files),
            "forbidden_target_functions": forbidden_functions,
            "roadmap": roadmap,
        }

        # plusieurs générations bornées absorbent les sorties faibles ou momentanément invalides
        errors = []
        proposal = None
        for attempt in range(1, self.attempts + 1):
            try:
                raw = _request_next_rush(self.model, facts, self.timeout, self.opener)
                proposal = _validate_proposal(
                    raw,
                    facts["current_micro_rush_id"],
                    self.workspace,
                    current_description=facts["current_description"],
                    forbidden_target_functions=forbidden_functions,
                )
                break
            except NextRushSpecError as error:
                errors.append(f"attempt {attempt}: {error}")

        if proposal is None:
            detail = "; ".join(errors)

            return False, f"propose_next_rush failed: {detail}"

        updated = dict(self.project)
        updated["micro_rush_id"] = proposal["micro_rush_id"]
        updated["title"] = proposal["title"]
        updated["description"] = proposal["description"]
        updated["target_files"] = proposal["target_files"]
        if proposal["target_function"]:
            updated["target_function"] = proposal["target_function"]
        else:
            updated.pop("target_function", None)
        updated.pop("validation_command", None)

        configuration_path = self.workspace / ".pithos.json"
        temporary = configuration_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
        temporary.replace(configuration_path)

        return True, f"proposed next micro-rush {proposal['micro_rush_id']!r}: {proposal['title']}"


def candidate_files(workspace):
    """Return a bounded list of Python product sources available to the next-rush author."""

    workspace = Path(workspace)
    paths = [path.relative_to(workspace).as_posix() for path in workspace.glob("*.py")]
    source_root = workspace / "src"
    if source_root.is_dir():
        for path in source_root.rglob("*.py"):
            relative = path.relative_to(workspace).as_posix()
            paths.append(relative)

    return sorted(paths)[:MAX_CONTEXT_FILES]


def _read_bounded(path, limit=4000):
    """Read a small project-status document when present."""

    if not path.is_file():
        return ""

    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def roadmap_complete(workspace, content=None):
    """Return whether one declared roadmap has items and every item is done."""

    if content is None:
        path = Path(workspace) / "docs" / "ROADMAP.md"
        content = ""
        if path.is_file():
            content = path.read_text(encoding="utf-8", errors="replace")
    statuses = _ROADMAP_ITEM.findall(content)

    return bool(statuses) and all(status.casefold() in {"done", "x"} for status in statuses)


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
        "fichiers relatifs à modifier ou créer. Pour un fichier existant, `target_function` doit être le nom "
        "exact d'une fonction de `existing_functions`. Pour un fichier entièrement nouveau, utilise `null`. "
        "Réponds uniquement avec l'objet JSON demandé.\n\n"
        "`candidate_files` et `existing_functions` décrivent le code produit réellement disponible, et "
        "`roadmap` son état déclaré. Ne répète pas un item marqué DONE. Préfère un rush qui change le "
        "comportement d'une fonction existante, plutôt "
        "qu'un rush qui n'a de sens qu'en ajoutant une fonction encore inexistante -- le contrat de test "
        "généré ensuite par le harnais ne peut viser qu'une fonction déjà présente dans le fichier cible. "
        "`target_files` doit lister uniquement des fichiers `.py` : le harnais ne sait générer un contrat "
        "que sur du code Python, jamais sur de la documentation ou de la configuration. Une fonction dans "
        "`forbidden_target_functions` vient d'échouer de façon répétée et ne peut pas être proposée à nouveau.\n\n"
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
            "target_function": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "target_files": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_TARGET_FILES,
                "items": {"type": "string"},
            },
        },
        "required": ["micro_rush_id", "title", "description", "target_function", "target_files"],
    }


def _validate_proposal(
    raw,
    current_micro_rush_id,
    workspace,
    current_description="",
    forbidden_target_functions=None,
):
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
    if description.strip().casefold() == current_description.strip().casefold():
        raise NextRushSpecError("next-rush description must differ from the current one")

    target_files = raw.get("target_files")
    if not isinstance(target_files, list) or not (1 <= len(target_files) <= MAX_TARGET_FILES):
        raise NextRushSpecError("next-rush target_files must be a short non-empty list")

    validated_files = [_validate_relative_path(path, workspace) for path in target_files]
    functions = existing_functions(workspace, validated_files)
    target_function = raw.get("target_function")
    if functions and target_function not in functions:
        raise NextRushSpecError("next-rush target_function is not defined in the target files")
    if not functions and target_function is not None:
        raise NextRushSpecError("next-rush target_function must be null for new target files")
    if target_function in set(forbidden_target_functions or []):
        raise NextRushSpecError("next-rush target_function just failed repeatedly")

    return {
        "micro_rush_id": micro_rush_id,
        "title": title.strip(),
        "description": description.strip(),
        "target_function": target_function,
        "target_files": validated_files,
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
