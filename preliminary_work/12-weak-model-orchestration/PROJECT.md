# Orchestration des modèles faibles

## But

Transformer Ling, fiable sur des actions atomiques mais fragile sur les longues sessions, en agent autonome
par une machine à états déterministe pilotant plusieurs sessions Pi courtes.

## Principes retenus

- Ling comprend, modifie et répare le code ; le harness orchestre et vérifie.
- Chaque phase possède une session neuve, un contexte borné et une sortie attendue explicite.
- L'état durable et les preuves observées priment sur la mémoire conversationnelle.
- Git, rapport final et notifications de cycle de vie sont déclenchés par le harness après les gates.
- Les tentatives et échecs restent conservés ; aucun succès n'est déduit du discours du modèle.

## Machine à états

`implement → test → repair → test → finalize`

- `repair` est borné à trois tentatives.
- Un test réussi mène directement à la finalisation déterministe ; une review ouverte n'est pas une gate.
- Budget dépassé, interruption ou échec irrécupérable produisent un checkpoint terminal explicite.
- La reprise relit l'état durable et démarre une nouvelle session Pi, jamais `pi --continue`.

## Budget Ling initial

- contexte construit : 40 000 caractères au maximum, avec réserve pour les tools et la sortie ;
- 8 tool cycles au maximum par session ;
- 1 024 tokens au maximum par génération et 300 secondes par phase ;
- sorties de validation compactées à 6 lignes significatives ;
- seuls le contrat, le checkpoint, les fichiers ciblés, le diff et l'échec courant sont admissibles.

## Critères de succès

- [x] L'état de mission est écrit atomiquement avant et après chaque phase.
- [x] Une reprise recommence depuis la phase persistée sans historique Pi.
- [x] Un contexte hors budget est refusé avant inference.
- [x] Un test en échec produit un feedback compact puis une session `repair` neuve.
- [x] Trois réparations échouées arrêtent la mission sans finalisation.
- [x] Une interruption finalise l'état durable de mission.
- [x] Le rapport local n'arrive qu'après validation externe réussie.
- [x] Le dry-run visualiseur termine deux fois consécutivement avec Ling sans assistance.
- [x] Le rapport de continuité est validé et publié après les gates externes.
- [x] Git et Telegram sont raccordés au launcher par brokers hôte.
- [x] Un push et une PR GitHub sont observés via le broker hôte.
- [x] Les notifications Telegram sont observées sur une mission multi-session réelle.

## Référence

Villani Code sert de référence de conception pour la gouvernance du contexte, les checkpoints, les preuves,
la validation ciblée et les raisons d'arrêt structurées. Son code n'est pas copié : Pithos conserve une
surface plus petite, centrée sur Pi, Ollama et ses brokers existants.
