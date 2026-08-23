# Event store SQLite

Le collecteur projette les flux `~/logs/pithos/runs/*/events.jsonl` dans SQLite. Les fichiers JSONL restent
la source de vérité : une indisponibilité du collecteur ne bloque jamais le runner.

```bash
pithos-events --logs-root ~/logs/pithos once
pithos-events --logs-root ~/logs/pithos --interval-seconds 5 watch
```

La base par défaut est `~/logs/pithos/pithos.db`. Elle utilise WAL, reprend chaque fichier à son dernier
offset validé et place les lignes invalides dans `quarantine`. Une troncature d'un flux déjà lu est refusée
car elle viole le contrat append-only.
