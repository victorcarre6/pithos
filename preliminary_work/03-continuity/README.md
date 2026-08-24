# Continuité entre runs

Publier un rapport validé :

```bash
pithos-continuity publish --logs-root ~/logs/pithos /path/to/report.md
```

Lire le rapport injecté à une nouvelle session :

```bash
pithos-continuity latest --logs-root ~/logs/pithos
```

La publication suit cet ordre : validation complète, archive immuable du run, puis remplacement atomique de
`latest.md`. Un rapport invalide ou une collision d'archive laisse le dernier rapport valide inchangé.

Le rapport ne dépend d'aucune session Pi. Un nouveau processus reçoit uniquement `latest.md`, les instructions
actives et les artefacts explicitement autorisés. La session JSONL précédente reste archivée pour
l'observabilité, mais elle n'est pas une source de reprise.

Probe réel en deux sessions indépendantes :

```bash
pithos-continuity \
  --logs-root ~/logs/pithos/continuity-probes/ling-3.0-tiny-8b/state \
  probe \
  --model maternion/ling-3.0-tiny:8b \
  --config-dir harness/config/pi \
  --output-dir ~/logs/pithos/continuity-probes/ling-3.0-tiny-8b/run
```
