# Résultats — qwen3.8:27b

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

