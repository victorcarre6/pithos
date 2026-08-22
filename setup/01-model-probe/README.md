# Exécuter le model probe

Le probe utilise l'API native Ollama et ne modifie ni Modelfile, ni quantification, ni paramètres persistants.
Il teste texte exact, developer role, structured output et tool call natif. Les réponses brutes et timings sont
conservés dans un fichier JSON.

```bash
pithos-model-probe \
  --model qwen3.8:27b \
  --output ~/logs/pithos/model-probes/qwen3.8-27b.json
```

Le chargement initial du modèle fait partie du temps client mais reste séparé dans `load_duration_ns` lorsque
Ollama le rapporte. `decode_tokens_per_second` vient de `eval_count / eval_duration`.

Le résultat est publié atomiquement après chaque scénario. Une interruption conserve donc tous les scénarios
achevés. Le timeout par requête est de dix minutes par défaut et peut être réduit avec `--timeout-seconds`.

## Limite volontaire

La recherche du contexte maximal stable n'est pas automatisée lors du probe fonctionnel. Sur une machine de
16 Go, elle doit être lancée par paliers explicitement approuvés et surveillés, car le modèle dense occupe déjà
17 Go sur disque et Ollama peut utiliser le swap. Le probe conserve la valeur réellement chargée retournée par
`/api/ps`.

Qwen3.6-35B-A3B reste une étude distincte. Aucun probe ne remplace automatiquement la baseline ni ne modifie
le runtime administré par l'utilisateur.
