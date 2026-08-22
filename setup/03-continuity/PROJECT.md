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

- [ ] La seconde session reprend un fait créé par la première sans lire sa session JSONL.
- [ ] Une écriture interrompue ne corrompt pas le dernier rapport valide.
- [ ] Les trois sections obligatoires sont contrôlées.
- [ ] Le micro-rush, la branche et la prochaine action sont identifiables.
- [ ] Les archives et le rapport global restent cohérents.

## Dépendances

- `00-contracts`.
- `02-capability-probe` validé.
