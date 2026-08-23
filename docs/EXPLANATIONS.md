# Explications techniques

## Séparation preuve / projection

Chaque producteur écrit des événements JSONL append-only sans dépendre de SQLite. Le collecteur reprend à un
offset validé, conserve la ligne brute et construit des tables interrogeables. Cette séparation laisse le
runner progresser si l'observabilité est arrêtée et permet de reconstruire la base depuis les traces.

## Autorités séparées

Pi travaille dans le dépôt expérimental. Les credentials Git et Telegram restent dans des brokers hôte. Le
harness actif peut évoluer, tandis que `ground_truth` sert uniquement à l'audit et à la restauration.

## Continuité sans session persistante

Chaque réveil ouvre une session neuve. La continuité repose sur un rapport Markdown validé et publié
atomiquement, avec les sections `Context`, `Work` et `Next items`, et non sur la mémoire interne du modèle.

## Prototype autonome et distribution

Chaque dossier `preliminary_work/<id>/` conserve sa fiche, ses décisions, ses preuves et un snapshot hashé du
code/test qui lui appartient. `harness/` est la distribution consolidée réellement installée. La synchronisation
est explicitement unidirectionnelle avec `harness/scripts/sync_preliminary.py` : elle documente une extraction,
elle ne crée pas deux sources actives modifiables en parallèle.

## Benchmark modèle

Le benchmark sépare quatre niveaux : Ollama natif, conformité structured/tool, effets réels via Pi et tâche
agentique longue. Chaque scénario conserve trois tentatives. Le seuil permissif de `0,05 token/s` ne retire
aucune preuve et ne bloque que les suites coûteuses `agentic` et `endurance`.

Les événements et artefacts sous `~/logs/pithos/benchmarks` restent exhaustifs. Une copie textuelle complète,
hors SQLite reconstructible, est aussi placée dans `preliminary_work/01-model-benchmark/results/campaigns`.
