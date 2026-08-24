# Résultats — qwen3.8:27b

## Première vague du 24/08/2026

| Modèle | Gate atteinte | Résultat déterminant |
|---|---|---|
| `qwen2.5-coder:7b` | `pi` complète | Smoke 3/6 à 21,39 tok/s ; protocol 3/6 à 19,30 tok/s ; Pi 2/18. Tools réels : 0/15. |
| `maternion/ling-3.0-tiny:8b` | `endurance` complète | Après Ollama 0.32.15 : smoke 6/6 à 52,57 tok/s ; protocol 6/6 à 53,17 tok/s ; Pi 18/18 ; agentic 4/6 ; contexte 3/3 jusqu'à 16k ; endurance 1/3. |
| `qwen3.8:27b-mlx` | `smoke` complète | 0/6 ; 16,9 GiB requis, 11,3 GiB disponibles. |
| `qwen3.8:27b` | tentative cold | Plus de 15 minutes sans réponse finale ; pic swap 10 534 387 712 octets. |
| `qwen3.6:35b` | tentative cold | Plus de 5 minutes sans réponse ; pic swap 14 834 008 064 octets. |

Les deux tentatives interrompues conservent `environment.json`, `events.jsonl`, le stream partiel et les
ressources sous `~/logs/pithos/benchmarks/`. Elles n'ont ni manifeste final ni export Git et ne sont pas
présentées comme des campagnes complètes.

Ling échouait initialement avant chargement avec Ollama 0.32.13. Ce résultat reste conservé, mais il est rendu
obsolète pour la sélection par la mise à jour Ollama 0.32.15, dont la dépendance llama.cpp prend en charge
`BailingMoE3`. Aucun poids ni Modelfile n'a été modifié. Ling devient la baseline retenue ; ses deux échecs
agentic concernent l'ordonnancement multi-tool strict, pas le protocole ni la création du fichier demandé.

La qualification longue retient Ling comme baseline avec une limite opérationnelle à 16k tokens. Les paliers
4k, 8k et 16k passent chacun 3/3 avec respectivement 4 045, 8 045 et 16 045 tokens réellement mesurés. Le
premier essai 32k a été interrompu après plus de 15 minutes sans premier token, sans OOM ni croissance du
swap. L'endurance passe 1/3 : les deux échecs exécutent les tests mais omettent le rapport final ; le troisième
run réalise les 12 tool calls et produit le rapport valide. La suite doit donc traiter l'absence de rapport
comme un travail incomplet à reprendre, et non comme un run réussi.

---

## Configuration observée

- Date : 2026-08-22.
- Ollama : `0.32.13`.
- Modèle : `qwen3.8:27b`, famille `qwen35`, 27,3B.
- Quantification : `Q4_K_M`.
- Taille chargée rapportée : 18 207 064 715 octets.
- Part VRAM rapportée : 8 564 947 024 octets.
- Répartition `ollama ps` observée : 53 % CPU / 47 % GPU.
- Contexte chargé : 4096 tokens.
- Résultat brut : `~/logs/pithos/model-probes/qwen3.8-27b.json`.

## Scénarios

| Scénario | Protocole | Temps client | Débit Ollama | Résultat |
|---|---:|---:|---:|---|
| Texte exact | réussi | 134,954 s | 0,088 token/s | `PITHOS_TEXT_OK` |
| Developer role | réussi | 198,541 s | 0,068 token/s | `PITHOS_DEVELOPER_OK` |
| Structured output | non établi | > 300 s | non disponible | timeout |
| Tool call natif | non établi | > 300 s | non disponible | timeout |

## Conclusion factuelle

Le modèle se charge et respecte les deux instructions textuelles. La configuration observée ne satisfait pas
le seuil demandé de 1 token/s : le meilleur débit mesuré est 0,088 token/s. Structured output et tool calling
n'ont pas produit de réponse dans leur limite individuelle de cinq minutes.

La baseline n'est pas remplacée automatiquement. Le runtime et sa configuration restent administrés par
l'utilisateur. Les projets d'infrastructure peuvent continuer, mais le capability probe Pi ne pourra pas être
déclaré compatible tant que le tool calling réel n'aura pas terminé avec succès dans une durée exploitable.

## Limites de la mesure

- Le contexte maximal stable n'a pas été recherché : le runtime charge actuellement 4096 tokens.
- Les métriques mémoire proviennent d'Ollama et de l'observation processus, pas d'un benchmark énergétique.
- Les timeouts prouvent l'absence de réponse sous cinq minutes, pas une incompatibilité définitive du protocole.
- Aucun paramètre persistant, Modelfile ou poids n'a été modifié.
