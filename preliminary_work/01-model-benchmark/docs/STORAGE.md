# Stockage

JSON et JSONL constituent la preuve primaire. SQLite est reconstruit depuis les `result.json` et n'est pas
copié dans Git. Tous les autres artefacts textuels sont exportés tels quels dans `results/campaigns/`.

```text
<campaign_id>/
├── environment.json
├── events.jsonl
├── manifest.json
├── summary.json
├── summary.md
└── attempts/<scenario_id>/attempt-<n>/
    ├── request.json
    ├── response.json
    ├── resources.jsonl
    ├── result.json
    ├── stdout.jsonl
    ├── stderr.log
    └── sessions/
```
