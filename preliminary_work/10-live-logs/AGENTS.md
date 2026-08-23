# Instructions — live logs

Construis un flux opérateur simple, durable et indépendant.

- Optimise d'abord pour `tail -F`, pas pour une UI riche.
- Utilise une écriture append-only avec flush explicite.
- Sérialise les écritures concurrentes ou prouve leur atomicité.
- Teste une rotation pendant qu'un lecteur suit le fichier.
- N'implémente pas la configuration SSH du poste distant sans directives utilisateur.
- Ne parse pas les logs pour piloter le runner.
- Ne supprime aucune archive dans la politique initiale.
