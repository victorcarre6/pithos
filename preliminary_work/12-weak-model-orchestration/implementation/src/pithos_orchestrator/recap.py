"""Generate one bounded, factual Telegram recap with the local model."""

import json
import urllib.error
import urllib.request
from pathlib import Path


MAX_RECAP_CHARS = 800
OPENINGS = (
    "J-j-je vais pas mentir, euh...",
    "E-e-euh... genre, voilà le truc...",
    "H-h-hum... oh, mec, alors...",
)
ROUGH_REACTIONS = (
    "Oh, punaise... ça a un peu résisté.",
    "Oh, mince, évidemment, ça pouvait pas juste marcher du premier coup...",
    "Oh, mec... genre, il a fallu insister, parce que pourquoi faire simple...",
)
CALM_REACTIONS = (
    "Oh, punaise... pour une fois, ça s'est pas battu.",
    "Oh, mec... genre, c'est presque suspect que ça se soit bien passé.",
    "Oh, mince... hum, ça a marché sans drame, je crois...",
)
SUCCESS_CLOSINGS = (
    "Enfin... voilà, quoi.",
    "Bon, je souffle deux secondes...",
    "Oh, mec... on va dire que c'est une victoire.",
)
FAILURE_CLOSINGS = (
    "Enfin... voilà, c'est pas gagné.",
    "Bon, je vais respirer deux secondes...",
    "Oh, mec... on va clairement pas appeler ça une victoire.",
)


def generate_recap(model, facts, artifact_path, opener=None, timeout=45):
    """Generate and persist one short recap without exposing tools or files."""

    # le modèle choisit la voix, jamais les faits
    succeeded = facts.get("status") == "completed" and facts.get("validation") == "PASS"
    rough = not succeeded or facts.get("repairs") or facts.get("tool_failures")
    reactions = ROUGH_REACTIONS if rough else CALM_REACTIONS
    closings = SUCCESS_CLOSINGS if succeeded else FAILURE_CLOSINGS
    prompt = (
        "Choisis les trois fragments qui correspondent le mieux aux faits du run. Réponds uniquement avec "
        "l'objet JSON demandé. La voix est celle d'un jeune sidekick paniqué, hésitant, maladroit, parfois "
        "blasé ou brièvement sarcastique. Tu ne peux ni ajouter, ni reformuler les faits.\n\n"
        f"Faits : {json.dumps(facts, ensure_ascii=False, sort_keys=True)}"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "format": {
            "type": "object",
            "properties": {
                "opening": {"type": "string", "enum": list(OPENINGS)},
                "reaction": {"type": "string", "enum": list(reactions)},
                "closing": {"type": "string", "enum": list(closings)},
            },
            "required": ["opening", "reaction", "closing"],
        },
        "options": {
            "num_predict": 100,
            "temperature": 0.7,
        },
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # génération locale bornée
    open_request = opener or urllib.request.urlopen
    try:
        with open_request(request, timeout=timeout) as response:
            body = json.load(response)
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise RuntimeError("Telegram recap generation failed") from error

    # garde-fous de sortie
    try:
        generated = json.loads(str(body.get("response", "")))
    except json.JSONDecodeError as error:
        raise ValueError("Telegram recap is not structured JSON") from error
    opening = _selected(generated, "opening", OPENINGS)
    reaction = _selected(generated, "reaction", reactions)
    closing = _selected(generated, "closing", closings)
    factual_text = _factual_text(facts)
    text = f"{opening} {factual_text[0]}\n{reaction} {factual_text[1]}\n{closing} {factual_text[2]}"
    if len(text) > MAX_RECAP_CHARS:
        raise ValueError("Telegram recap is too long")

    artifact_path = Path(artifact_path)
    artifact_path.write_text(text + "\n", encoding="utf-8")

    return text


def _selected(generated, field, allowed):
    """Return one model-selected fragment only when it belongs to the allowlist."""

    value = str(generated.get(field, ""))
    if value not in allowed:
        raise ValueError(f"Telegram recap returned an invalid {field}")

    return value


def _factual_text(facts):
    """Build the three authoritative sentences inserted around generated voice fragments."""

    goal = str(facts.get("goal", "")).strip().rstrip(".")
    changed_files = [str(path) for path in facts.get("changed_files") or []]
    repairs = int(facts.get("repairs", 0))
    tool_calls = int(facts.get("tool_calls", 0))
    tool_failures = int(facts.get("tool_failures", 0))
    duration = int(facts.get("duration_seconds", 0))

    objective = f"Le but, c'était simple : {goal}."
    if changed_files:
        targets = ", ".join(changed_files)
        work = f"J'ai modifié {targets} en {repairs} réparation(s) et {tool_calls} appel(s) d'outil"
    else:
        work = f"Je n'ai modifié aucun fichier après {repairs} réparation(s) et {tool_calls} appel(s) d'outil"
    work = f"{work}, dont {tool_failures} en échec. Ça a pris {duration} s."

    validation = str(facts.get("validation", "FAIL"))
    conclusion = f"Au final, la validation externe est {validation}."
    todo = facts.get("todo") or []
    if todo:
        done = sum(1 for item in todo if item.get("status") == "done")
        conclusion = f"{conclusion} {done}/{len(todo)} étape(s) validée(s)."
    pull_request = facts.get("pull_request")
    if pull_request:
        conclusion = f"{conclusion} La PR est {pull_request}."
    elif facts.get("stop_reason"):
        conclusion = f"{conclusion} La mission s'arrête : {facts['stop_reason']}."

    return objective, work, conclusion
