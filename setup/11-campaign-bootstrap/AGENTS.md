# Instructions — campaign bootstrap

Ce chantier assemble des composants validés ; il ne les réécrit pas et ne démarre pas silencieusement la
campagne longue.

- Vérifie chaque dépendance par sa commande documentée.
- Arrête le bootstrap au premier invariant critique non satisfait.
- Ne supprime, ne migre et ne copie pas automatiquement `~/code/tempo`.
- Ne crée pas le dépôt distant ; utilise uniquement celui fourni par l'utilisateur.
- Exécute un seul dry-run supervisé et conserve tous ses artefacts.
- Laisse `launchd` désactivé jusqu'à une confirmation humaine explicite.
- Documente les limites encore ouvertes sur la capture audio sans les résoudre spéculativement.
