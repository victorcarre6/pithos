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

La première vague compare les cinq tags installés suivants :

```text
qwen2.5-coder:7b
maternion/ling-3.0-tiny:8b
qwen3.8:27b-mlx
qwen3.8:27b
qwen3.6:35b
```

Commencer par `--suite smoke`, puis `--suite protocol`, avant une campagne complète sur les candidats dont le
débit et la stabilité justifient les suites Pi et agentiques.

`maternion/ling-3.0-tiny:8b` nécessite Ollama **0.32.15 ou plus récent** pour le support de l'architecture
`BailingMoE3`.

Ce modèle est la baseline locale retenue. Le contexte opérationnel est borné à **16k tokens** : le palier
32k n'a produit aucun token en plus de 15 minutes sur le Mac mini M2 16 Go.

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
