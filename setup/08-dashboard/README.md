# Dashboard Pithos

L'interface reprend les design tokens, cartes de métriques et listes de statut d'Argos/Aede. Son domaine est
strictement Pithos : runs, timeline et payloads paginés.

```bash
cd dashboard
PITHOS_LOGS_ROOT="$HOME/logs/pithos" docker compose up -d --build
```

Le port local par défaut est `1208`. Les chemins SQLite et logs sont montés en lecture seule. La publication
sur le LAN reste volontairement différée jusqu'aux directives d'exploitation.
