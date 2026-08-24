# Benchmark et sélection du modèle local

## But

Construire un benchmark reproductible et riche pour comparer une première vague de cinq modèles Ollama sur le
Mac mini M2 16 Go, d'abord nativement puis à travers Pi. Le benchmark sélectionne une baseline praticable pour
Pithos tout en conservant assez de métriques et d'artefacts pour d'autres usages futurs.

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

## Première vague

Inventaire fourni le 24/08/2026 ; les tailles sont celles rapportées par `ollama list` :

| Ordre | Modèle | Taille | Rôle dans la comparaison |
|---:|---|---:|---|
| 1 | `qwen2.5-coder:7b` | 4,7 Go | Petit modèle spécialisé code ; valide aussi le protocole de campagne. |
| 2 | `maternion/ling-3.0-tiny:8b` | 5,3 Go | Second candidat compact, distinct du modèle spécialisé code. |
| 3 | `qwen3.8:27b-mlx` | 18 Go | Tag portant le suffixe MLX, à comparer au tag standard sans supposer son runtime. |
| 4 | `qwen3.8:27b` | 17 Go | Candidat dense historique et point de comparaison avec les probes archivés. |
| 5 | `qwen3.6:35b` | 23 Go | Candidat le plus lourd ; risque de pression mémoire à mesurer, pas à présumer. |

La validation commence par les deux petits modèles, puis couvre les trois modèles plus lourds : `smoke` puis
`protocol` sur les cinq candidats. Les suites `pi`, `agentic`, `context` et `endurance` ne sont lancées qu'après
examen des résultats courts et application
des gates documentées. Les deux tags `qwen3.8` restent des candidats distincts ; aucune équivalence de poids,
quantification ou runtime n'est supposée sans les métadonnées Ollama archivées par le benchmark.

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
- [x] Les cinq modèles atteignent la gate `smoke` ; les runs impraticables conservent leurs artefacts partiels.
- [x] Ling complète les suites Pi et agentiques après mise à jour vers Ollama 0.32.15.
- [x] Ling est qualifié jusqu'à 16k et ses limites 32k/endurance sont conservées comme résultats négatifs.
- [x] La sélection finale repose sur les profils mesurés et les limites Pithos explicites.

## Dépendances

- `00-contracts` pour les conventions d'identité et d'événements.
- Ollama et les poids, administrés par l'utilisateur.
- Pi pour les suites `pi`, `agentic` et `endurance`.
