# Instructions — model probe

Ce chantier mesure ; il ne sélectionne ni n'administre le modèle à la place de l'utilisateur.

- Inspecte d'abord le runtime et la configuration exposée, hors secrets.
- Demande avant tout téléchargement volumineux ou changement du serveur d'inférence.
- N'invente aucune métrique et conserve les sorties brutes.
- Isole warm-up, prefill, decode et pression mémoire quand les données le permettent.
- Teste les tool calls avec des outils factices sans effet de bord.
- Arrête un essai qui provoque une pression mémoire dangereuse ou une instabilité système.
- Sépare résultats mesurés, informations des auteurs et hypothèses.
