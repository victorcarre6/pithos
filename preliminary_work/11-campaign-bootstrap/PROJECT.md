# Bootstrap de la première campagne

## But

Assembler les composants validés et préparer, sans lancer une autonomie longue, le dépôt expérimental du
visualiseur audio/VJing.

## Livrables

- Vérification des prérequis et versions compatibles.
- Création locale de l'expérience sous `~/code/pithos/experiments/`, dans le dépôt privé Pithos existant.
- Injection initiale contrôlée des instructions et capacités actives.
- Fiche projet du visualiseur audio reprise depuis la référence `tempo`, puis rendue mesurable.
- Configuration des domaines documentaires autorisés et de leur journalisation.
- Dry-run complet supervisé d'un micro-rush.
- Checklist et commande explicite d'activation de `launchd`.

## Contraintes

- Ne supprime pas `~/code/tempo` ; l'utilisateur le fera après la session.
- Ne lance pas la campagne périodique sans validation explicite de la checklist.
- Les tests restent headless sur le Mac mini M2.
- La cible de performance reste un MacBook Intel 2018 sans GPU dédié.
- L'entrée audio cible est une interface audio ; les détails de driver sont différés.
- Le runtime/modèle reste administré hors du contrôle de Pi.

## Critères de succès

- [ ] Tous les probes et services obligatoires sont au vert.
- [ ] Un dry-run produit événements, rapport, logs, branche et PR attendus.
- [ ] Le timeout et le loop-guard ont été testés avant activation.
- [ ] La reprise depuis `latest.md` fonctionne dans une session neuve.
- [x] Le générateur crée un workspace d'expérience sans dépôt Git imbriqué ni remplacement d'une cible.
- [x] La ground truth active, les docs et la configuration non secrète sont injectées depuis des templates.
- [ ] L'activation périodique nécessite une commande humaine explicite.
- [x] Le dépôt expérimental ne contient aucun credential.

## Résultat du premier dry-run supervisé

- [x] GitHub et Telegram réels sont joignables depuis les brokers hôte.
- [x] Les échecs Ling à 4k puis 16k sont conservés dans les artefacts de run.
- [ ] Ling termine le micro-rush, publie un rapport valide et produit une PR.
- [ ] Le runner finalise proprement `run.json` lors d'une interruption opérateur.

## Dépendances

- `00-contracts` à `10-live-logs`, avec dashboard et Telegram disponibles selon leur configuration finale.
