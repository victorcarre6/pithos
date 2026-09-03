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
et mission. Après succès, un marqueur hors Git associe le `micro_rush_id` au run terminé. Pour une campagne
sans `seed`, les réveils suivants restent des no-op. Avec un `seed`, le runner demande lui-même une nouvelle
proposition bornée, remplace atomiquement `.pithos.json`, recharge cette configuration puis lance le nouveau
rush dans le même réveil. Le même handoff remplace un rush autonome après trois missions en échec. Une panne
de planification ne rejoue jamais l'ancien rush : elle est retentée au réveil périodique suivant.

Le démarrage Compose est lui aussi borné à 120 secondes. Un daemon Docker suspendu ne peut donc plus conserver
le verrou du runner pendant des dizaines de minutes : le processus sort, le contexte libère le verrou et un
réveil ultérieur peut reprendre après restauration du runtime externe.

Après observation d'une VM Docker maintenue au-dessus de 200 % CPU malgré l'absence de mission, la campagne
visualiseur utilise le runtime `host` déjà supporté par le runner. Pi reste borné par phase et pointe vers
Ollama sur `127.0.0.1`; les workspaces projetés, oracles externes, limites de tools et brokers hôte restent
inchangés. Ce basculement retire Docker du chemin nominal de cette expérience sans supprimer ni affaiblir le
runtime Docker du harness.

Un oracle généré ne constitue pas seul une autorité suffisante : Ling a produit un cas exigeant
`compute_magnitudes([]) == [0.0]`, en contradiction avec le contrat déjà validé. La configuration autonome
peut donc déclarer une `regression_command`, conservée lors de chaque handoff. Le validator exécute d'abord
l'oracle actif; seulement s'il passe, il exécute la suite produit. Les deux doivent être vertes.

La mission est également transactionnelle sur ses `target_files`. Le launcher capture leur contenu avant la
machine à états et les restaure atomiquement si le statut terminal n'est pas `completed` ou si l'orchestration
lève une exception. Un fichier cible nouveau est supprimé lors du rollback; aucun fichier hors allowlist
n'est touché. Ainsi, une réparation guidée par un faux oracle peut échouer et rester observable sans laisser
le workspace produit régressé.

Le handoff ne dépend pas du dernier diff, qui peut être vide après un preflight déjà vert. Il transmet au
modèle les sources Python produit disponibles, leurs fonctions, les cibles courantes et la roadmap bornée.
Les champs d'infrastructure restent recopiés sans modification et seule une proposition validée peut changer
l'identité du rush. Une nouvelle branche part toujours de `main`, et une PR fermée n'est jamais réutilisée.

Les credentials Telegram peuvent être chargés depuis le `.env` ignoré de l'expérience. Le launcher ne lit
que les deux clés allowlistées et transmet cet environnement au broker hôte ; le modèle, le workspace projeté,
les événements et les commits ne reçoivent jamais la valeur du token.

Les notifications de cycle de vie utilisent le `title` et la `description` obligatoires du rush. Le message
de fin reste entièrement déterministe : statut, durée, réparations et PR viennent de l'état et des événements.
Après `run.finished`, un appel Ollama sans tool choisit seulement trois fragments de voix dans des enums JSON
contraints. Le harnais insère ensuite les phrases factuelles exactes, archive `telegram-recap.txt` hors Git et
envoie une requête idempotente `orchestrated-recap`. Timeout, JSON invalide ou broker indisponible sont
journalisés sans modifier le résultat de mission.

## Contrat explicite de la fonction ciblée

L'oracle numérique ne peut valider de manière forte que des fonctions déjà présentes. Les échecs
`compute-magnitudes` ont montré deux ambiguïtés distinctes : une tâche d'ajout dans un module existant peut
faire sélectionner une ancienne fonction sans rapport, et deux générations Ling peuvent s'accorder sur la
même arithmétique fausse.

Les rushes auto-proposés sur un module existant portent donc un `target_function` choisi dans les fonctions
réellement détectées. Cette valeur contraint le schéma de l'oracle suivant. Les créations de fichiers gardent
`target_function: null` et restent limitées au faible contrôle d'import déjà documenté. Une description
strictement identique au rush courant est aussi refusée avant d'écrire `.pithos.json`. Ces garde-fous règlent
la sélection et la répétition exacte ; ils ne transforment pas le modèle en oracle arithmétique. Pour une
fonction nouvelle dans un fichier existant, un `validation_command` déterministe reste requis.

## Runtime produit sans dépendance

Le prototype final utilise le navigateur comme runtime local : Web Audio remplace PortAudio/NumPy pour la
capture et la FFT, tandis que Canvas 2D suffit aux trois bandes réactives. Cela réduit la surface de packaging
sur le MacBook Intel cible et conserve le calcul applicatif pur dans `audio-core.mjs`. Un petit serveur Python
lié à `127.0.0.1` est nécessaire au secure context navigateur ; il ne constitue ni un service distant ni une
surface LAN. Aucun endpoint externe n'est présent dans le client.

## Terminaison d'une campagne autonome

La roadmap est l'autorité bornée de fin : elle doit contenir au moins un item et tous ses items doivent être
`[DONE]` ou `[x]`. Dans cet état, `NextRushAuthor` ne consulte pas le modèle et produit un `stop_proposal`
déterministe. Le launcher exécute encore la `regression_command`; une campagne ne peut donc pas se déclarer
terminée sur un produit régressé.

La proposition est un vrai run observable et un message Telegram best-effort. Son marqueur hors Git contient
le SHA-256 de la roadmap : les réveils répétés restent des no-op tant que le contrat ne change pas, sans rendre
un futur ajout de backlog invisible. Le signal est une proposition d'arrêt, pas une suppression silencieuse
du scheduler.

## Durcissement de l'oracle et de la projection

Les `args` produits par le modèle représentent toujours les arguments positionnels. L'AST du module cible
donne maintenant le minimum et le maximum acceptés; un cas d'arité impossible est rejeté avant import et
exécution. Cela intercepte notamment la confusion entre une fonction recevant une liste et plusieurs
arguments scalaires. Après le plafond d'échec d'un rush, sa fonction cible est aussi exclue de la proposition
suivante pour ne pas reformuler indéfiniment le même contrat.

Les fichiers JSONL restent la source de vérité. Au démarrage, le launcher finalise explicitement les anciens
checkpoints `running` dont le processus a disparu; SQLite peut alors refléter `interrupted` au lieu d'un état
actif fantôme. Le collecteur conserve son mode détaillé pour `once`, mais son LaunchAgent utilise `--quiet` :
l'absence de delta n'engendre plus une copie de l'inventaire des sources toutes les cinq secondes.

## Preuve de capacité en campagne

`prove_campaign_skill.py` sépare volontairement la preuve en deux processus Pi. Le premier ne reçoit que le
tool `write`, sans skills ni extensions, et matérialise un skill au contenu exact dans le staging. Le
`HarnessManager` enregistre le snapshot, valide et promeut l'artefact. Le second processus ne reçoit que le
tool `read`, charge les skills actifs et doit produire un marqueur textuel exact. Manifest, sessions, streams
Pi et validations restent liés au même run et au journal du harness.
