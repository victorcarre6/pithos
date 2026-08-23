# Architecture

```text
scenario YAML
    ↓
BenchmarkEngine ──→ OllamaClient / capability probe Pi
    │
    ├── events.jsonl ──→ TUI
    ├── raw artifacts
    ├── benchmark.db ──→ dashboard
    └── export complet ──→ results/campaigns
```

Le moteur est indépendant des présentations. Le TUI l'exécute dans un worker et reçoit les événements déjà
persistés. Le dashboard ne consulte que les campagnes terminées.

La duplication suit un sens unique : le prototype autonome est stabilisé ici puis extrait explicitement vers
`harness/src/pithos_benchmark`.
