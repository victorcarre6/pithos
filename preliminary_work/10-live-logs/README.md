# Live log

Chaque événement Pithos est reflété immédiatement dans `~/logs/pithos/live.log` :

```text
2026-08-23T12:00:00.000+00:00 [INFO] [run-…] [runner] run.started
```

Lecture locale :

```bash
tail -F ~/logs/pithos/live.log
```

Les writers se synchronisent avec `runtime/live.lock`. À la limite de taille, le fichier courant est renommé
dans `archive/live/`, puis un nouveau `live.log` est créé. Aucune archive n'est supprimée. La commande SSH
exacte sera ajoutée lorsque l'hôte et l'utilisateur de lecture seront définis.
