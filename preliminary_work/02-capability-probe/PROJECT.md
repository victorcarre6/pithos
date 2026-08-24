# Capability probe Pi + modèle

## But

Prouver que le couple Pi + modèle exécute réellement les capacités nécessaires avant toute autonomie.

## Scénarios

1. Réponse textuelle.
2. Lecture d'un fichier.
3. Écriture d'un fichier.
4. Édition ciblée.
5. Commande shell.
6. Exécution d'un test.
7. Chaîne multi-tools.
8. Rapport `Context / Work / Next items`.
9. Création puis réutilisation d'un skill après redémarrage.
10. Création puis chargement d'une extension dans un nouveau processus.

## Livrables

- Fixture isolée et réinitialisable.
- Runner de probe non interactif.
- Résultat structuré par scénario.
- Capture des événements et de la session Pi.
- Rapport des incompatibilités observées.

## Critères de succès

- [x] Chaque scénario distingue `process_success`, `protocol_success`, `task_success` et `report_success`.
- [x] Un tool call imprimé mais non exécuté échoue explicitement.
- [x] Les effets attendus sont vérifiés hors de la réponse du modèle.
- [x] Deux exécutions simultanées ne partagent pas leurs fixtures.
- [x] Le probe peut être relancé sans nettoyage manuel dangereux.
- [x] Les dix capacités passent réellement avec Ling, dont skill et extension dans un nouveau processus.

La conformité de ces invariants est couverte par tests déterministes et par un probe réel complet avec
`maternion/ling-3.0-tiny:8b` ; voir `RESULTS.md`.

## Dépendances

- `00-contracts`.
- Baseline sélectionnée par `01-model-benchmark`.
