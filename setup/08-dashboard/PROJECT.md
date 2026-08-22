# Dashboard d'observabilité

## But

Construire un dashboard dockerisé permanent qui consulte SQLite et les artefacts de runs sans modifier la
campagne. L'utilisateur fournira un template Node.js, TypeScript et Python avant l'implémentation.

## Vues minimales

- Runs actifs, terminés, interrompus et bloqués.
- Timeline des messages, tool calls, commandes et erreurs.
- Durée, tokens, débit et taux d'échec.
- Fichiers modifiés, tests et événements Git/PR.
- Skills, tools et extensions créés ou utilisés.
- Dépendances, accès réseau et messages Telegram.
- Progression des `next_items` et accès aux rapports/logs bruts.

## Livrables

- Service backend read-only.
- Interface web suivant le template fourni.
- Image et composition Docker.
- Healthcheck et configuration d'exploitation permanente.
- Pagination/streaming pour les payloads volumineux.
- Documentation de déploiement LAN différée jusqu'aux directives utilisateur.

## Contraintes

- Attendre le template utilisateur avant de choisir l'architecture applicative.
- Monter SQLite et les logs en lecture seule.
- Ne pas exposer le service au-delà de la configuration explicitement fournie.
- Le dashboard ne commande ni Pi, ni Git, ni Telegram.
- L'absence du dashboard n'affecte pas les runs.

## Critères de succès

- [ ] Les vues minimales utilisent des données réellement ingérées.
- [ ] Un gros run reste consultable sans charger tous ses payloads en mémoire.
- [ ] Le container redémarre sans migration destructive.
- [ ] Aucun endpoint de lecture ne modifie SQLite ou les artefacts.
- [ ] Le healthcheck distingue service disponible et données indisponibles.

## Dépendances

- Template utilisateur.
- `07-event-store` stabilisé.
