# Logs live et lecture SSH

## But

Produire un flux global lisible avec `tail -F` depuis un écran dédié via SSH, indépendamment de SQLite et du
dashboard.

## Livrables

- Producteur append-only de `~/logs/pithos/live.log`.
- Format de ligne horodaté avec `run_id`, niveau, composant et message.
- Flush immédiat des événements importants.
- Rotation compatible avec `tail -F` et conservation illimitée des archives.
- Commandes documentées de lecture locale et SSH.
- Tests de concurrence, rotation et redémarrage.

## Contraintes

- Le flux reste utile en texte brut.
- Aucun ANSI ou rendu interactif requis.
- Les logs ne sont pas la source de reprise ; `latest.md` remplit ce rôle.
- Aucun filtrage de contenu n'est demandé : les producteurs doivent empêcher les credentials d'entrer dans les
  événements en amont.
- La configuration SSH elle-même reste hors périmètre tant que l'utilisateur ne l'a pas fournie.

## Critères de succès

- [DONE] `tail -F ~/logs/pithos/live.log` suit plusieurs runs sans doublons manifestes.
- [DONE] Chaque ligne permet d'identifier l'heure, le run et la gravité.
- [DONE] La rotation ne coupe pas durablement un lecteur existant.
- [DONE] Un redémarrage reprend l'écriture sans écraser l'historique.
- [DONE] Une panne SQLite ou dashboard n'interrompt pas le flux.

## Dépendances

- `00-contracts`.
- `04-runner` et autres producteurs d'événements.
