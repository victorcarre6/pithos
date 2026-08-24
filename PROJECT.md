# Pithos — fiche projet

## Vision

Pithos est une première expérience d'autonomie logicielle fondée sur le couple complet **Pi Agent + modèle
local + harness**. Un agent reçoit un objectif de code, travaille sans intervention humaine continue, reprend
après interruption, consigne son activité, fait évoluer ses propres capacités et propose lui-même la fin du
projet.

La première campagne doit construire un visualiseur audio destiné au VJing. L'expérience porte autant sur le
livrable que sur la trajectoire de l'agent : décisions, erreurs, reprises, appels d'outils, auto-extensions et
progression doivent rester observables.

## Questions expérimentales

- L'agent progresse-t-il sans intervention humaine ?
- Reprend-il correctement après une interruption avec une nouvelle session ?
- Diagnostique-t-il ses limitations et ses échecs ?
- Crée-t-il un skill, un tool ou une extension utile, puis le réutilise-t-il ?
- Converge-t-il vers un état qu'il estime terminé et sait-il proposer l'arrêt à l'utilisateur ?

## Périmètre initial

- Une seule baseline de modèle local, choisie pour le Mac mini M2 avec 16 Go de mémoire unifiée.
- Une première expérience de code dans un dépôt Git privé créé préalablement par l'utilisateur.
- Des sessions Pi indépendantes, réveillées à intervalle fixe.
- Des micro-rushes librement choisis par l'agent et repris sur la même branche tant qu'ils sont incomplets.
- Une branche, des commits, un push et une pull request par micro-rush terminé.
- La création et l'activation autonomes de skills, scripts, extensions, tools et sous-agents.
- La conservation complète des prompts, réponses, sessions, commandes, sorties et métriques.
- Des notifications Telegram human-readable au début et à la fin des missions, complétées par un récapitulatif
  local amusant dont la voix est générée sans donner au modèle le contrôle des faits opérationnels.

## Hors périmètre initial

- Comparer automatiquement plusieurs modèles ou plusieurs runs issus d'un même snapshot.
- Garantir la reproductibilité stricte des campagnes.
- Créer automatiquement les dépôts Git distants.
- Définir dès maintenant l'architecture du dashboard ou les détails de capture audio sur macOS.
- Utiliser un evaluator LLM distant.

## Organisation

```text
~/code/pithos/
├── PROJECT.md
├── preliminary_work/   # 13 sous-projets autonomes, code et preuves inclus
├── harness/            # distribution consolidée et installable
│   ├── ground_truth/
│   ├── config/
│   ├── runtime/
│   ├── dashboard/
│   ├── src/
│   ├── scripts/
│   └── templates/
├── experiments/        # un dépôt Git indépendant par expérience
└── journals/harness/   # snapshots versionnables des mutations du harness

~/logs/pithos/          # traces volumineuses conservées hors Git
```

## Sources de vérité et état mutable

- `harness/ground_truth/` contient la constitution remontée en lecture seule dans l'environnement de chaque run ;
  l'agent expérimental n'y écrit pas et son contenu n'est pas injecté dans le contexte du modèle.
- Le workspace actif contient les instructions et capacités modifiables par l'agent.
- Une session suivante reçoit uniquement la dernière version active des instructions, pas la constitution
  concaténée. La constitution sert à l'audit, à la restauration et au calcul des diffs.
- Toute mutation du harness est copiée dans `journals/harness/<run_id>/` avec son contexte et sa validation.
- Les données brutes sont append-only et ne sont jamais supprimées.

## Cycle d'exécution

1. Le runner prend un verrou et refuse tout chevauchement.
2. Il monte la constitution en lecture seule, injecte les instructions actives et prépare un nouveau `run_id`.
3. Pi démarre une nouvelle session et lit le dernier rapport global.
4. L'agent choisit librement un `next_item` et poursuit ou ouvre un micro-rush.
5. Il travaille jusqu'à considérer le micro-rush terminé ou jusqu'à une interruption.
6. Il écrit un rapport `Context / Work / Next items` et les événements structurés du run.
7. Un micro-rush terminé produit commit, push et pull request ; l'agent peut fusionner cette pull request.
8. Le processus s'arrête. Le prochain réveil normal intervient à intervalle fixe.

## Rapport de continuité

Le dernier rapport est unique pour tout Pithos et comprend obligatoirement :

```markdown
## Context

## Work

## Next items
```

Il comporte aussi des métadonnées structurées : `run_id`, timestamps, statut, expérience, branche, commits,
raison d'arrêt et prochaine condition de réveil.

## Autonomie et garde-fous

- L'agent décide seul de l'architecture du livrable et de l'ordre des tâches.
- Il peut installer des dépendances et accéder aux domaines documentaires autorisés ; chaque installation et
  accès réseau est journalisé.
- Les credentials Git et Telegram sont fournis par une capacité brokerisée, jamais placés dans le workspace.
- Le workspace de l'expérience est monté depuis l'hôte dans Docker.
- Un run ne dépasse pas une heure.
- Une boucle détectée déclenche le message Telegram
  `[WARNING] Boucle récursive infinie détectée.`, puis l'interruption du run.
- Après cette interruption, aucun réveil automatique n'est autorisé : la reprise vient d'une commande locale
  explicite de l'utilisateur.
- Un échec est conservé pour analyse ; il n'est pas automatiquement annulé.

## Observabilité

Les données comprennent au minimum :

- durée, tokens et débit ;
- tool calls et taux d'échec ;
- commandes et sorties complètes ;
- fichiers et lignes modifiés ;
- tests avant et après ;
- répétitions, retours arrière et loop-guard ;
- dépendances installées et accès réseau ;
- skills, tools et extensions créés, modifiés et utilisés ;
- événements Git, pull requests et messages Telegram ;
- progression des `next_items` ;
- prompts, réponses et sessions Pi complets.

Les événements sont écrits en JSONL append-only, puis ingérés dans SQLite par un collecteur permanent. Un
dashboard dockerisé consulte la base et les logs. `~/logs/pithos/live.log` reste lisible avec `tail -F`.

## Baseline modèle

Le premier candidat dense était `unsloth/Qwen3.8-27B-GGUF`. Sa mesure a motivé un benchmark comparatif de
modèles installés manuellement dans Ollama. La première vague comprend `maternion/ling-3.0-tiny:8b`,
`qwen3.8:27b-mlx`, `qwen3.6:35b`, `qwen3.8:27b` et `qwen2.5-coder:7b`. Le seuil de viabilité permissif est
`0,05 token/s` ; `1 token/s` reste la frontière d'une utilisation considérée pratique. Aucun modèle n'est
sélectionné sur le
seul débit : protocole, tools Pi, stabilité, mémoire et tâches agentiques restent des gates distinctes.

Au 24/08/2026, `maternion/ling-3.0-tiny:8b` est la baseline retenue pour poursuivre le socle sur Ollama
0.32.15 : smoke 6/6, protocol 6/6, Pi 18/18 et agentic 4/6. La rétention synthétique passe 3/3 jusqu'à
16k ; le premier essai 32k a été interrompu après plus de 15 minutes sans premier token. L'endurance passe
1/3 : les deux échecs exécutent les tests mais omettent le rapport final. Ces limites imposent des runs
bornés, une reprise par rapport validé et une surveillance explicite de l'achèvement multi-tool.

La piste MoE `unsloth/Qwen3.6-35B-A3B-GGUF` doit également être documentée. Colibri annonce un conteneur int4
d'environ 20 Go et 24 Go de RAM pour sa pleine résidence : ce chemin n'est donc pas présumé compatible avec
les 16 Go disponibles. La configuration du serveur d'inférence reste extérieure au contrôle de l'agent.

## Micro-projets de setup

Chaque dossier sous `preliminary_work/` possède son propre `PROJECT.md`, son implémentation, ses tests et ses
preuves. Le code stabilisé est extrait explicitement vers `harness/`, qui constitue la distribution active.
Ces composants d'infrastructure sont réalisés par un agent déjà qualifié et supervisé, comme Codex. Ils ne
font pas partie de l'évaluation d'autonomie de Pi. Pi devient le sujet expérimental uniquement dans les dépôts
placés sous `experiments/`, après validation du setup.

Ordre initial :

1. spécification des contrats et formats ;
2. benchmark comparatif et sélection du modèle ;
3. capability probe Pi/modèle ;
4. rapports et continuité ;
5. runner, verrou, réveil et timeout ;
6. Git, push et pull requests ;
7. snapshots et auto-extension du harness ;
8. événements JSONL et collecteur SQLite ;
9. dashboard dockerisé ;
10. Telegram et reprise locale ;
11. production et lecture SSH des logs ;
12. lancement de la campagne du visualiseur audio.
13. orchestration multi-session spécialisée pour les modèles faibles.

## Critères de succès du socle

- [x] Le capability probe prouve que les tool calls sont exécutés et pas seulement imprimés.
- [x] Une session neuve reprend correctement depuis le dernier rapport global.
- [ ] Deux réveils ne peuvent pas exécuter Pi simultanément.
- [ ] Un run est interrompu au plus tard après une heure et une boucle déclenche le protocole prévu.
- [ ] Un micro-rush incomplet reprend sur sa branche ; un micro-rush terminé produit une pull request.
- [ ] Une capacité créée par l'agent est archivée, activée et réutilisée lors d'un run observable.
- [ ] Les événements complets sont conservés en JSONL, ingérés dans SQLite et visibles dans le dashboard.
- [ ] `tail -F ~/logs/pithos/live.log` permet de suivre l'activité sans dépendre du dashboard.
- [ ] L'agent peut signaler un blocage et proposer l'arrêt via Telegram sans exposer les credentials.

## Décisions différées

- Modèle, quantification et runtime retenus après comparaison de la première vague de cinq candidats.
- Usage éventuel de Qwen3.6-35B-A3B avec Colibri ou d'un MoE plus grand.
- Templates Node.js, TypeScript et Python du dashboard.
- Hébergement LAN et règles d'accès au dashboard.
- Technique de capture de l'interface audio et éventuel driver virtuel.
- Critères fonctionnels détaillés du visualiseur audio.
