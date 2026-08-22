# Broker Telegram

## But

Fournir à l'agent expérimental une communication Telegram limitée et journalisée, sans exposer le token du bot
ni transformer Telegram en orchestrateur implicite.

## Messages sortants

- `INFO` : progression notable.
- `WARNING` : stagnation ou anomalie.
- `QUESTION` : choix réellement bloquant.
- `STOP_PROPOSAL` : proposition d'arrêt du projet.
- `EMERGENCY` : boucle ou corruption probable.

## Commandes entrantes initiales

- `/status`
- `/latest`
- `/pause`
- `/stop`
- `/answer <run_id> <message>`

La reprise après loop-guard reste une commande locale sur le poste ; Telegram ne fournit pas `/resume`.

## Livrables

- Service broker permanent.
- Tool Pi à surface minimale.
- Allowlist de chat/user.
- Journalisation des requêtes, résultats et messages.
- Rate limiting, idempotence et gestion des indisponibilités.
- Intégration du message exact de loop-guard.

## Contraintes

- Token et identifiants autorisés restent hors workspace et hors contexte Pi.
- Pi ne choisit ni destinataire arbitraire ni méthode Telegram.
- Une panne Telegram ne bloque pas l'écriture locale du rapport.
- Le message de boucle est `[WARNING] Boucle récursive infinie détectée.`.

## Critères de succès

- [ ] Un message autorisé est envoyé et journalisé sans exposer le token.
- [ ] Un destinataire ou une commande non autorisés sont refusés.
- [ ] Les updates dupliquées ne produisent pas plusieurs actions.
- [ ] `/pause` et `/stop` affectent le runner via une interface contrôlée.
- [ ] Le loop-guard notifie puis interrompt même si Telegram est indisponible.

## Dépendances

- `00-contracts`.
- `04-runner`.
- `07-event-store` pour la projection des événements.
