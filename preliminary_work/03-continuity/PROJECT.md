# Continuité entre sessions

## But

Permettre à une nouvelle session Pi de reprendre le travail à partir d'un rapport global unique, sans reprendre
la session LLM précédente.

## Livrables

- Génération et validation du rapport `Context / Work / Next items`.
- Métadonnées machine-readables du run.
- Publication atomique de `~/logs/pithos/latest.md`.
- Archivage immuable des rapports par `run_id`.
- Probe de reprise en deux sessions indépendantes.
- Gestion explicite d'un rapport absent, invalide ou interrompu.

## Contraintes

- Une seule version globale de `latest.md`.
- L'archive d'un run n'est jamais écrasée.
- `latest.md` ne pointe que vers un rapport validé et achevé.
- `next_items` peut être entièrement réécrit par l'agent expérimental.

## Critères de succès

- [ ] Une seconde session Pi reprend un fait créé par la première sans lire sa session JSONL.
- [x] Une écriture interrompue ou invalide ne corrompt pas le dernier rapport valide.
- [x] Les trois sections obligatoires sont contrôlées.
- [x] Le micro-rush, la branche et la prochaine action sont identifiables.
- [x] Les archives et le rapport global restent cohérents.

## Validation réalisée

Les tests couvrent publication, lecture indépendante, idempotence, collision d'archive, rapport invalide et
absence de `latest.md`. La validation Pi en deux sessions reste impossible avec la baseline actuelle dans une
durée exploitable ; elle demeure explicitement ouverte.

## Dépendances

- `00-contracts`.
- `02-capability-probe` validé.
