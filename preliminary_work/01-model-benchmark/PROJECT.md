# Benchmark et sélection du modèle local

## But

Construire un benchmark reproductible et riche pour comparer environ dix modèles Ollama sur le Mac mini M2
16 Go, d'abord nativement puis à travers Pi. Le benchmark sélectionne une baseline praticable pour Pithos tout
en conservant assez de métriques et d'artefacts pour d'autres usages futurs.

Ce projet fusionne le probe historique de `qwen3.8:27b` et le benchmark multi-modèles. Les résultats initiaux
restent des preuves versionnées, pas une campagne comparable rétroactivement.

## Livrables

- Commande `pithos-benchmark <model_name>` avec TUI par défaut et mode headless.
- Trois tentatives par scénario, avec état cold initial puis runs chauds.
- Suites `smoke`, `protocol`, `pi`, `agentic`, `endurance` et stress `context` versionnées.
- Contrôle limité de la résidence Ollama : inventaire, chargement, `keep_alive` et déchargement.
- Mesures de latence, débit, tokens, mémoire, swap, CPU, stabilité, protocole et effets Pi.
- Gates permissives ; `0,05 token/s` est la limite basse avant les seules suites longues.
- Artefacts complets sous `~/logs/pithos/benchmarks/` et copie versionnable autonome sous `results/`.
- Projection SQLite reconstructible, TUI live et dashboard read-only sur `127.0.0.1:4311`.

## Contraintes

- Le benchmark ne pull, ne supprime et ne modifie aucun modèle ou Modelfile.
- L'utilisateur choisit et installe les modèles évalués.
- Une gate ne supprime jamais un résultat ; elle évite seulement une suite longue inexploitable.
- Requêtes, réponses, sessions, erreurs et résultats négatifs sont conservés.
- Toute métrique indisponible porte sa raison ; aucune valeur n'est estimée silencieusement.
- Le moteur headless ne dépend ni du TUI ni du dashboard, tous deux read-only vis-à-vis de l'exécution.

## Critères de succès

- [x] Le probe historique et toutes ses traces sont versionnés dans ce projet.
- [x] Un faux Ollama valide trois tentatives, erreurs, métriques, SQLite et export Git.
- [x] Le TUI consomme les événements du moteur et se teste sans écran.
- [x] Le dashboard consulte plusieurs campagnes et refuse les traversées de chemin.
- [ ] Une première campagne réelle complète les suites natives sur un modèle praticable.
- [ ] Au moins dix modèles installés par l'utilisateur sont comparés.
- [ ] La sélection finale repose sur les profils complets et les critères Pithos explicites.

## Dépendances

- `00-contracts` pour les conventions d'identité et d'événements.
- Ollama et les poids, administrés par l'utilisateur.
- Pi pour les suites `pi`, `agentic` et `endurance`.
