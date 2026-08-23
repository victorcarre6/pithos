# Métriques

## Ollama natif

- durée client et durée totale serveur ;
- chargement, prompt evaluation et génération ;
- tokens prompt et réponse ;
- prompt/decode tokens par seconde ;
- `done_reason`, erreur et timeout ;
- métadonnées exactes du modèle installé et résident.

## Ressources hôte

- CPU global ;
- mémoire utilisée et disponible ;
- swap ;
- snapshots `/api/ps` chaque seconde.

macOS ne fournit pas de compteur GPU par processus stable et non privilégié. Cette métrique est marquée
`available=false` plutôt qu'estimée à partir d'un autre signal.

## Fonctionnelles

- conformité exacte texte, JSON et tool call ;
- processus, protocole, tâche et rapport pour Pi ;
- résultats des trois tentatives ;
- erreurs et effets externes complets.
