# Workflow Git et pull requests

## But

Permettre à l'agent expérimental de conserver un micro-rush sur une branche, puis de pousser, ouvrir et
éventuellement fusionner une pull request lorsqu'il le déclare terminé.

## Livrables

- Convention de branche `agent/<micro-rush-id>-<slug>`.
- Tools brokerisés pour status, commit, push, création, inspection et fusion de PR.
- Policy limitée au dépôt privé précréé par l'utilisateur.
- Journalisation structurée de toutes les opérations.
- Gestion d'un micro-rush incomplet sur plusieurs runs.
- Tests sur un dépôt distant de test privé ou un double local contrôlé.

## Contraintes

- L'agent ne crée pas de dépôt distant.
- Aucun token ou credential n'est accessible dans le workspace ou les sorties du tool.
- Aucun force-push, réécriture d'historique ou suppression de branche principale.
- Une PR correspond à un micro-rush terminé, pas à chaque réveil.
- L'échec est conservé pour analyse.

## Critères de succès

- [ ] Un micro-rush incomplet reprend sur la même branche.
- [ ] Un micro-rush terminé produit un commit traçable et une PR.
- [ ] La policy refuse un autre dépôt et une opération destructive.
- [ ] La fusion est possible uniquement pour une PR autorisée.
- [ ] Les credentials n'apparaissent dans aucun artefact de test.

## Dépendances

- `00-contracts`.
- `04-runner` pour l'identité du run.
