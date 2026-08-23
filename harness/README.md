# Pithos Harness

Distribution consolidée du runner autonome, de ses brokers, de l'observabilité et du benchmark modèle.

## Installation locale

```bash
./install.sh --check
./install.sh --install-system --experiment first-experiment
./install.sh --experiment first-experiment
```

`--install-system` est l'option explicite pour un Mac neuf : Homebrew, Python 3.12, Node, Ollama, Docker
Desktop et Pi 0.84.2. Les poids Ollama restent toujours installés manuellement. Sans cette option, aucun
logiciel système n'est installé.

## Développement

```bash
python -m pip install -e '.[dev]'
pytest -q
npm --prefix dashboard/web run build
```

## Benchmark

```bash
pithos-benchmark list
pithos-benchmark qwen3.8:27b --suite smoke
pithos-benchmark dashboard
```

Le dashboard benchmark écoute seulement sur `127.0.0.1:4311`. Les campagnes brutes vivent sous
`~/logs/pithos/benchmarks/` et sont exportées dans le projet préliminaire lorsqu'il est présent.
