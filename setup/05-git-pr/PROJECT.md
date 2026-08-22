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

- [x] Un micro-rush incomplet reprend sur la même branche.
- [x] Un micro-rush terminé produit un commit traçable et une PR via le double contrôlé.
- [x] La policy refuse un autre dépôt et une opération destructive.
- [x] La fusion est possible uniquement pour une PR autorisée.
- [x] Les credentials n'apparaissent dans aucun artefact de test.

## Validation réalisée

- Socket Unix réelle mode `0600`.
- Double contrôlé couvrant branche existante, commit, push, création, inspection et fusion de PR.
- Refus d'une opération inconnue, de `main`, d'un autre remote et d'une PR head/base incorrecte.
- Vérification qu'aucune commande n'utilise `--force` ou un token et que les événements ne conservent que
  statut et code de sortie.

Le test GitHub réel reste volontairement différé après la première passe autonome, conformément à la décision
utilisateur. La surface broker et sa policy sont prêtes pour cette validation.

## Dépendances

- `00-contracts`.
- `04-runner` pour l'identité du run.
