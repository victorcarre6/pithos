# Pithos Visualizer

Visualiseur audio cyberpunk local pour macOS. Il capture l'entrée audio par défaut, calcule le spectre avec
Web Audio et affiche trois bandes réactives dans un Canvas 2D.

## Lancer

Double-cliquer sur `start.command`, puis autoriser l'accès audio dans le navigateur. L'entrée par défaut est
utilisée automatiquement ; le menu permet de choisir une interface physique ou loopback déjà installée.

Le serveur écoute uniquement sur `127.0.0.1`. L'application n'utilise aucun service distant, compte,
télémétrie ou dépendance npm.

## Vérification

```bash
python tests/validate_product.py
```

## Run supervisé

```bash
harness/.venv/bin/python harness/scripts/run_experiment.py experiments/visualizer-dry-run
```

Telegram is activated automatically only when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_USER_ID` are present in the
host environment. Git operations are activated only when `origin` exists. Neither credential enters this
workspace.
