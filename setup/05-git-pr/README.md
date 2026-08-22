# Git/GitHub broker

Le broker tourne sur l'hôte et expose uniquement une socket Unix mode `0600`. Le container Pi monte la socket,
pas le home de l'utilisateur, le fichier de configuration `gh` ou un token.

```bash
pithos-git-broker \
  --repository ~/code/pithos/experiments/audio-visualizer \
  --remote https://github.com/OWNER/REPOSITORY \
  --socket ~/logs/pithos/runtime/git-broker.sock
```

## Requête

Une connexion transporte une ligne JSON :

```json
{
  "run_id": "run-20260822T220000Z-a1b2c3",
  "operation": "status",
  "arguments": {}
}
```

Opérations disponibles : `status`, `switch`, `commit`, `push`, `pr_create`, `pr_view`, `pr_merge`.

## Policy

- dépôt local et remote `origin` strictement égaux à la configuration ;
- branches limitées à `agent/rush-<slug>` ;
- aucun force-push ou changement de branche principale ;
- aucune création ou suppression de dépôt ;
- fusion limitée à une PR ouverte de la branche active vers la branche principale configurée ;
- journalisation du résultat sans commande, body de PR, stdout ou credential.

Le broker hérite de l'authentification `gh` de son processus hôte. Le runner Pi devra supprimer credentials et
home utilisateur de son propre container. Le test GitHub réel est volontairement différé après cette première
passe ; les tests utilisent un double de commande contrôlé et la socket réelle.

