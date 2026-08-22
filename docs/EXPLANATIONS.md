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
