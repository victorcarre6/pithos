# Instructions — model benchmark

- Mesure avant de comparer ; ne transforme jamais une absence de métrique en zéro.
- Ne pull, ne supprime, ne renomme et ne recrée aucun modèle Ollama.
- Le chargement et le déchargement runtime des modèles installés sont autorisés.
- Conserve chaque tentative, y compris timeout, réponse vide, protocole invalide et crash.
- Trois runs sont la norme ; ne sélectionne pas la meilleure tentative en masquant les autres.
- Le seuil de `0,05 token/s` ne bloque que les suites longues, jamais les tests courts.
- Distingue Ollama natif, protocole structuré, intégration Pi et réussite agentique.
- Versionne prompts, schémas et résultats avec un identifiant de scénario et une version.
- Ne publie aucun score composite avant d'avoir exposé les métriques qui le composent.
- Toute nouvelle métrique doit indiquer unité, source et méthode de collecte.
