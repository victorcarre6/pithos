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

Le rapport ne dépend d'aucune session Pi. Un nouveau processus reçoit uniquement `latest.md` et les
instructions actives. La session JSONL précédente reste archivée pour l'observabilité, mais elle n'est pas une
source de reprise.

