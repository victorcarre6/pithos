# Quick catch

## État

Les chantiers **00 à 08** sont implémentés. Les limites mesurées de la baseline empêchent encore de valider
les critères qui exigent des tool calls Pi réels. Le prochain chantier est le broker Telegram `09`.

## Commandes

```bash
pytest -q
pithos-events --logs-root ~/logs/pithos once
pithos-runner status --logs-root ~/logs/pithos
npm run validate:typescript
```

## Suite

1. Construire l'API SQLite read-only et l'interface issue d'Argos/Aede.
2. Construire le broker Telegram jusqu'au probe réel avec credentials injectés.
3. Produire `live.log`, puis auditer les contrats inter-composants.
