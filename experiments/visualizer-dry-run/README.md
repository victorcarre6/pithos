# Pithos experiment

Le premier micro-rush implémente l'agrégation déterministe d'un spectre FFT en trois niveaux scalaires.

## Vérification

```bash
python tests/test_audio_visualizer.py
python ../../harness/fixtures/visualizer_acceptance.py
```

## Run supervisé

```bash
harness/.venv/bin/python harness/scripts/run_experiment.py experiments/visualizer-dry-run
```

Telegram is activated automatically only when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_USER_ID` are present in the
host environment. Git operations are activated only when `origin` exists. Neither credential enters this
workspace.
