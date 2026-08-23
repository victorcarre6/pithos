# Exécuter le capability probe

Le probe crée un workspace et un répertoire de sessions séparés par scénario. Il capture le flux JSON de Pi,
équilibre les événements `tool_execution_start/end`, puis vérifie l'effet réel sur le filesystem.

```bash
pithos-capability-probe \
  --all \
  --config-dir harness/config/pi \
  --output-dir ~/logs/pithos/capability-probes/qwen3.8-27b
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

Le model probe du 22 août 2026 mesure 0,068–0,088 token/s et des timeouts de cinq minutes sur structured output
et tool call natif. Le capability probe réel complet n'est donc pas lancé automatiquement : sa limite d'une
heure risquerait de ne couvrir qu'un ou deux scénarios. Le moteur et ses vérifications externes sont testés avec
un faux Pi déterministe ; la compatibilité réelle reste à établir.

La configuration Pi dédiée porte `httpIdleTimeoutMs` et `retry.provider.timeoutMs` à une heure. Le défaut Pi
de cinq minutes interrompait les générations locales lentes avant le timeout externe. Les retries agent sont
désactivés : le runner demeure l'unique limite dure et ne cumule pas plusieurs appels d'une heure.

## Scénarios différés

La création/réutilisation d'un skill et la création/activation d'une extension nécessitent deux processus Pi.
Ils seront ajoutés avec `06-harness-evolution`, qui définit snapshot, validation et promotion de ces artefacts.
