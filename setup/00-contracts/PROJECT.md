# Contrats de données et d'exécution

## But

Définir les formats stables partagés par le runner, les collecteurs, le dashboard et les agents. Ce projet ne
développe aucun service : il produit des schémas, exemples et validateurs minimaux.

## Livrables

- Schéma d'un run, d'un micro-rush et de leurs statuts.
- Format JSONL versionné des événements.
- Format Markdown du rapport global `Context / Work / Next items`.
- Convention des `run_id`, timestamps, branches et chemins d'artefacts.
- Règles d'évolution compatibles des schémas.
- Fixtures valides et invalides, plus une commande de validation locale.

## Contraintes

- Les événements restent append-only.
- Les timestamps utilisent ISO 8601 avec timezone.
- Un événement porte au minimum `schema_version`, `run_id`, `timestamp`, `type` et `payload`.
- Le format reste lisible sans SQLite ni dashboard.
- Aucun secret ou exemple d'identifiant réel.

## Critères de succès

- [ ] Chaque consommateur prévu peut être décrit sans champ implicite.
- [ ] Les fixtures valides passent le validateur et les fixtures invalides échouent.
- [ ] Le rapport permet une reprise sans lire toute la session précédente.
- [ ] Les statuts distinguent succès processus, protocole, tâche et rapport.
- [ ] Les contrats précisent les champs obligatoires, optionnels et leur compatibilité.

## Dépendances

Aucune. Ce projet bloque tous les suivants.
