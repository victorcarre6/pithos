# Contrats persistants Pithos — version 1.0

## Identifiants

- Run : `run-YYYYMMDDTHHMMSSZ-xxxxxx`, suffixe alphanumérique aléatoire.
- Événement : `evt-YYYYMMDDTHHMMSS.ffffffZ-xxxxxx`.
- Micro-rush : `rush-<slug>`.
- Branche : `agent/<micro-rush-id>`.

Les timestamps sont en ISO 8601 avec timezone. Les identifiants utilisent UTC afin que leur ordre lexical
reste proche de l'ordre temporel ; le champ `timestamp` reste la référence.

## Flux d'événements

Un fichier `events.jsonl` contient un objet `event` par ligne. Il est append-only. Le couple
`(run_id, event_id)` identifie une ligne lors de l'ingestion SQLite. `sequence`, lorsqu'il est présent, est
monotone dans un run et aide à détecter une perte ; il ne remplace pas `event_id`.

Les types suivent `<domaine>.<action>`, par exemple :

- `run.started`, `run.finished`, `run.heartbeat` ;
- `model.request`, `model.response` ;
- `tool.called`, `tool.completed`, `tool.failed` ;
- `file.changed`, `test.completed`, `dependency.installed`, `network.requested` ;
- `harness.changed`, `git.committed`, `telegram.sent`.

Le schéma laisse `payload` ouvert pour permettre de nouveaux événements sans modifier l'enveloppe. Les
consommateurs inconnus conservent le payload brut et ignorent les champs qu'ils ne comprennent pas.

## Statuts

### Run

- `starting` : artefacts réservés, processus Pi pas encore actif ;
- `running` : processus actif ;
- `completed` : run terminé normalement ;
- `failed` : erreur non assimilée à un timeout ou un loop-guard ;
- `interrupted` : interruption explicite ;
- `timed_out` : limite d'une heure atteinte ;
- `paused` : loop-guard déclenché, réveil automatique interdit.

Les quatre dimensions de succès restent indépendantes et peuvent être `null` tant qu'elles ne sont pas
évaluées : processus, protocole tool-calling, tâche et rapport.

### Micro-rush

`planned → active → completed` est le chemin nominal. `blocked` et `abandoned` conservent les essais et ne
suppriment ni branche ni artefacts.

## Rapport de continuité

Le rapport commence par un frontmatter YAML conforme à `report-metadata.schema.json`, puis contient exactement
une fois et dans cet ordre :

```markdown
## Context

## Work

## Next items
```

`latest.md` n'est publié qu'après validation. L'archive du run reste la source durable ; `latest.md` est la
copie atomique du dernier rapport valide.

## Compatibilité

- Un ajout optionnel dans un `payload` existant est compatible avec `1.0`.
- Un nouveau type d'événement est compatible : les consommateurs doivent pouvoir l'ignorer.
- Ajouter un champ obligatoire, retirer ou renommer un champ, modifier son type ou sa sémantique exige une
  nouvelle version majeure du contrat.
- Une correction qui resserre un invariant déjà documenté exige au minimum une nouvelle version mineure et
  une migration des fixtures.
- Les producteurs écrivent une seule version. Les consommateurs peuvent en accepter plusieurs explicitement.

## Validation

```bash
pithos-contracts json run contracts/fixtures/valid/run.json
pithos-contracts events contracts/fixtures/valid/events.jsonl
pithos-contracts report contracts/fixtures/valid/report.md
pytest
```

