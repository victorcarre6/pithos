# Pithos Model Benchmark

## Exécution

Depuis `harness/` après installation éditable :

```bash
python -m pip install -e '.[dev]'
pithos-benchmark list
pithos-benchmark qwen3.8:27b
```

Le TUI est activé par défaut. Le mode automatisable conserve les mêmes événements :

```bash
pithos-benchmark qwen3.8:27b --suite smoke --no-tui
```

Trois tentatives sont exécutées par défaut. Le seuil permissif de `0,05 token/s` ne coupe que les suites
agentiques longues.

La recherche de contexte est un stress test séparé afin de ne pas multiplier le coût de chaque campagne :

```bash
pithos-benchmark qwen3.8:27b --suite context
```

Elle essaie 4k, 8k, 16k puis 32k et arrête les paliers supérieurs si les trois tentatives d'un palier échouent.
Le `prompt_eval_count` Ollama reste la mesure réelle ; la taille synthétique n'est pas présentée comme un
token count exact.

## Dashboard

```bash
pithos-benchmark dashboard
```

Consultation : `http://127.0.0.1:4311`.

## Données

- Source exhaustive : `~/logs/pithos/benchmarks/<campaign_id>/`.
- Copie Git hors SQLite : `results/campaigns/<campaign_id>/`.
- Probes historiques : `results/legacy/`.

Le benchmark vérifie que le modèle est déjà installé, contrôle uniquement sa résidence mémoire avec
`keep_alive`, puis le décharge. Il ne pull, ne supprime et ne crée aucun modèle.
