# Événements et stockage SQLite

## But

Ingérer les événements JSONL append-only dans une base SQLite consultable, sans rendre l'exécution de Pi
dépendante de la disponibilité de la base.

## Livrables

- Collecteur permanent et reprise après redémarrage.
- Schéma SQLite versionné et migrations.
- Ingestion idempotente avec curseur par fichier.
- Tables pour runs, tool calls, commandes, fichiers, tests, dépendances, réseau, harness, Git et Telegram.
- Conservation des prompts, réponses et payloads complets.
- Diagnostic des événements invalides sans arrêt global.
- Commandes de vérification et fixtures de charge.

## Contraintes

- JSONL reste la source primaire append-only.
- Pi n'écrit pas directement dans SQLite.
- Aucun événement brut n'est supprimé après ingestion.
- Aucun filtrage ou masquage du contenu n'est demandé ; les credentials ne doivent donc jamais atteindre la
  source d'événements.
- Un événement invalide est quarantiné avec sa position exacte.

## Critères de succès

- [DONE] Une réingestion ne duplique aucune donnée.
- [DONE] Une ligne invalide n'empêche pas l'ingestion des lignes suivantes.
- [DONE] Un redémarrage reprend au bon offset.
- [DONE] Les relations run/micro-rush/session/PR restent interrogeables.
- [DONE] Les migrations préservent les événements et payloads existants.

## Dépendances

- `00-contracts`.
- Producteurs d'événements de `04-runner`, `05-git-pr` et `06-harness-evolution`.
