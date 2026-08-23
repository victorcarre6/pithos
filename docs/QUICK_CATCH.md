# Quick catch

## État

Les chantiers **00 à 10** et leur intégration transversale sont implémentés. La suite compte **89 tests**.
Le runtime agent est Docker par défaut ; son build réel attend un daemon Docker actif. Le probe Telegram
attend uniquement `TELEGRAM_BOT_TOKEN` et `TELEGRAM_USER_ID`. Les validations réelles Pi/Ollama restent
ouvertes à cause du débit et des timeouts observés sur `qwen3.8:27b`.

## Commandes

```bash
pytest -q -p no:cacheprovider
pithos-events --logs-root ~/logs/pithos once
pithos-runner status --logs-root ~/logs/pithos
npm --prefix dashboard/web run build
docker compose -f runtime/docker-compose.yml config
docker compose -f dashboard/docker-compose.yml config
```

## Suite

1. Démarrer Docker, construire le runtime et lancer un smoke test agent + proxy.
2. Injecter les deux credentials Telegram et exécuter le probe réel.
3. Reprendre les probes Pi/Ollama, puis lancer le bootstrap de campagne `11`.
