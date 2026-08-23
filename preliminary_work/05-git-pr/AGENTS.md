# Instructions — Git et PR

Implémente une capacité brokerisée minimale autour de Git et de l'API distante.

- Résous et vérifie le remote et le dépôt autorisé avant chaque mutation distante.
- Refuse force-push, reset destructif, modification de la branche protégée et création de dépôt.
- N'expose jamais les credentials au modèle, à l'environnement du shell agent ou aux logs.
- Sépare les opérations locales Git des opérations distantes brokerisées.
- Rends chaque opération idempotente quand l'API le permet.
- Teste les refus de policy autant que le chemin nominal.
- Ne fusionne rien pendant le développement hors dépôt de test explicitement autorisé.
