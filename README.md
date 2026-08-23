# Pithos

Pithos prépare puis observe des campagnes de développement autonomes exécutées par Pi avec un modèle Ollama
local. Le dépôt sépare les preuves de construction, le produit installable et les expériences autonomes.

```text
preliminary_work/  12 sous-projets, prototypes, tests et résultats
harness/           runtime consolidé, ground truth et installation
experiments/       dépôts Git indépendants créés pour Pi
```

## Benchmark d'un modèle

```bash
cd harness
python -m pip install -e '.[dev]'
pithos-benchmark list
pithos-benchmark <ollama_model_name>
```

Les poids doivent déjà être installés par l'utilisateur. Le benchmark ne pull et ne supprime aucun modèle.

## Installer le harness

```bash
./harness/install.sh --check
./harness/install.sh --experiment my-first-experiment
```

Compléter ensuite `experiments/my-first-experiment/PROJECT.md` avant le premier run supervisé.

```bash
harness/.venv/bin/python harness/scripts/run_experiment.py experiments/my-first-experiment
```

Voir [`PROJECT.md`](PROJECT.md) pour le protocole global et
[`preliminary_work/01-model-benchmark/README.md`](preliminary_work/01-model-benchmark/README.md) pour les suites
de sélection du modèle.
