# Explications techniques

## Séparation preuve / projection

Chaque producteur écrit des événements JSONL append-only sans dépendre de SQLite. Le collecteur reprend à un
offset validé, conserve la ligne brute et construit des tables interrogeables. Cette séparation laisse le
runner progresser si l'observabilité est arrêtée et permet de reconstruire la base depuis les traces.

## Autorités séparées

Pi travaille dans le dépôt expérimental. Les credentials Git et Telegram restent dans des brokers hôte. Le
harness actif peut évoluer, tandis que `ground_truth` sert uniquement à l'audit et à la restauration.

Sur Docker Desktop macOS, les sockets Unix de l'hôte ne sont pas bind-mountables dans la VM Linux. Le chemin
orchestré n'en dépend pas : les phases Ling s'exécutent sans broker dans le container, puis le finalizer hôte
appelle les brokers après validation externe. Le modèle ne reçoit donc ni socket ni credential.

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

## Orchestration d'un modèle faible

Le dry-run Ling montre qu'une longue session mélangeant exploration, code, tests, Git et rapport dépasse ses
capacités d'auto-orchestration, alors que ses actions atomiques restent fiables. Pithos déplace donc la boucle
de contrôle dans le harness : sessions Pi neuves par phase, état persistant, contexte sélectionné, validation
externe et finalisation conditionnelle.

Cette architecture reprend des principes observés dans [Villani Code](https://github.com/mmprotest/villani-code),
notamment mission state, context governance, checkpoints, evidence et validation loop. Pithos n'en reprend pas
la surface générale : il conserve une machine à états minimale dédiée à Pi, Ling et aux brokers existants.

Le test visualiseur montre que la sélection du contexte est le levier principal. Le `PROJECT.md` complet
amenait Ling à suivre des exigences secondaires et à recréer une arborescence inutile. Un brief de phase
autoritaire (`.pithos-task.md`), un seul fichier projeté et un oracle hors modèle ont permis une correction en
un tool call. Une review générative après oracle vert a été retirée du chemin nominal : elle consommait la
borne de phase sans produire de preuve supplémentaire.

Le launcher exécute aussi un preflight : un workspace déjà conforme atteint directement la finalisation sans
charger le modèle. Le rapport est écrit dans le workspace avant le commit, mais sa publication comme
continuité globale intervient seulement après les opérations Git réussies. Un push refusé laisse ainsi un
checkpoint terminal et les événements Git, sans annoncer un run incomplet comme nouvelle vérité durable.

Chaque mission émet désormais son propre cycle `run.started` / `run.finished`. Le collecteur ingère à la fois
`runs/*/events.jsonl` et `missions/*/events.jsonl`, et `EventWriter` réplique les deux familles dans
`live.log`. SQLite et le dashboard restent des projections read-only et reconstructibles.

La planification macOS sépare deux LaunchAgents utilisateur : le collecteur SQLite reste vivant, tandis que
le launcher d'expérience se réveille toutes les trois heures. Un verrou par expérience couvre proxy, brokers
et mission. Après succès, un marqueur hors Git associe le `micro_rush_id` au run terminé ; les réveils suivants
sont des no-op jusqu'à la publication d'un nouvel identifiant. Une nouvelle branche part toujours de
`origin/main`, et une PR fermée n'est jamais réutilisée.

Les credentials Telegram peuvent être chargés depuis le `.env` ignoré de l'expérience. Le launcher ne lit
que les deux clés allowlistées et transmet cet environnement au broker hôte ; le modèle, le workspace projeté,
les événements et les commits ne reçoivent jamais la valeur du token.
