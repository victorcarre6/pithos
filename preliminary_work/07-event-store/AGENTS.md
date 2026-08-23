# Instructions — event store

SQLite est une projection reconstruisible ; JSONL reste la preuve primaire.

- N'ajoute pas de write path SQLite dans Pi ou son runner critique.
- Utilise transactions et contraintes d'unicité pour l'idempotence.
- Conserve le payload brut avec les colonnes indexées utiles.
- Versionne le schéma et teste une migration depuis la version précédente.
- Quarantaine les lignes invalides sans les réécrire.
- Teste interruption au milieu d'un fichier, reprise et duplication.
- Ne développe aucune UI dans ce chantier.
