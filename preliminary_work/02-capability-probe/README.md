# Exécuter le capability probe

Le probe crée un workspace et un répertoire de sessions séparés par scénario. Il capture le flux JSON de Pi,
équilibre les événements `tool_execution_start/end`, puis vérifie l'effet réel sur le filesystem.

```bash
pithos-capability-probe \
  --all \
  --config-dir harness/config/pi \
  --model maternion/ling-3.0-tiny:8b \
  --output-dir ~/logs/pithos/capability-probes/ling-3.0-tiny-8b
```

Pour limiter un premier essai :

```bash
pithos-capability-probe \
  text read \
  --timeout-seconds 600 \
  --config-dir harness/config/pi \
  --output-dir ~/logs/pithos/capability-probes/qwen3.8-27b
```

Chaque `result.json` expose séparément :

- `process_success` : Pi termine avec un code nul ;
- `protocol_success` : JSONL valide, cycle agent complet et tool calls équilibrés ;
- `task_success` : effet attendu observé hors de la réponse du modèle ;
- `report_success` : rapport conforme, pour le scénario concerné.

Un contenu assistant ressemblant à `{"name": ..., "arguments": ...}` sans événement tool est explicitement
un échec protocolaire.

## État de la baseline

La baseline Ling passe les dix scénarios réels, y compris les deux redémarrages nécessaires au skill et à
l'extension. L'ancienne baseline qwen3.8 reste documentée dans `RESULTS.md` comme résultat négatif historique.

La configuration Pi dédiée porte `httpIdleTimeoutMs` et `retry.provider.timeoutMs` à une heure. Le défaut Pi
de cinq minutes interrompait les générations locales lentes avant le timeout externe. Les retries agent sont
désactivés : le runner demeure l'unique limite dure et ne cumule pas plusieurs appels d'une heure.

Les scénarios `skill_reuse` et `extension_reuse` conservent séparément les stdout, stderr et sessions initiales
et de follow-up. Le second processus partage uniquement le workspace contenant la capacité créée.
