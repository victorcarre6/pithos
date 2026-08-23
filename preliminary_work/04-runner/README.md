# Runner Pithos

## Commandes locales

```bash
pithos-runner status
pithos-runner pause --reason "maintenance locale"
pithos-runner resume

pithos-runner run \
  --experiment-id audio-visualizer \
  --workspace ~/code/pithos/experiments/audio-visualizer \
  --pi-config-dir ~/code/pithos/harness/config/pi
```

Ajoute `--git-socket` et `--telegram-socket` lorsque les brokers tournent. Le runner traduit ces chemins en
`PITHOS_GIT_SOCKET` et `PITHOS_TELEGRAM_SOCKET` pour les extensions, sans transmettre leurs credentials.

Le runner refuse `run` lorsque `~/logs/pithos/runtime/state.json` porte `paused=true`. Seule la commande locale
`resume` efface cet état. Un réveil `launchd` suivant ne peut donc pas reprendre après un loop-guard.

## Arrêts

- **Timeout** : 3600 secondes par défaut ; `SIGTERM` au groupe Pi, puis `SIGKILL` après cinq secondes.
- **Loop-guard** : cinq tool calls consécutifs ayant le même nom et les mêmes arguments ; message
  `[WARNING] Boucle récursive infinie détectée.`, arrêt du groupe et état `paused` persistant.
- **Rapport absent/invalide** : run `failed`, même si Pi retourne zéro.

Chaque run écrit immédiatement sous `~/logs/pithos/runs/<run_id>/` :

```text
events.jsonl
run.json
sessions/
stderr.log
stdout.jsonl
```

Le rapport valide est archivé par le composant de continuité et publié dans le `latest.md` global.

## launchd

Le plist de référence exécute uniquement le runner. Il doit recevoir des chemins absolus lors du bootstrap.
Son installation et son activation restent manuelles jusqu'à validation de la campagne.
