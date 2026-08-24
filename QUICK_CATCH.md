# Pithos — Quick catch

_État vérifié le 24/08/2026 à 22:13 CEST._

## Micro quick catch général

**But.** Construire puis observer une première campagne de développement autonome : Pi, un modèle Ollama
local et un harness isolé doivent produire un visualiseur audio/VJing tout en conservant la trajectoire
complète des runs.

**État.** Les **13 chantiers préliminaires (`00` à `12`)** ont une implémentation snapshotée. Le code actif
est consolidé dans `harness/`; `preliminary_work/` conserve les intentions, preuves et snapshots, pas une
seconde source à modifier. Les snapshots sont synchronisés avec le harness.

**Validation du socle.** **158 tests passent**. Le frontend React/Vite compile et les configurations Compose
du runtime et du dashboard sont valides. Les tests couvrent les contrats, probes déterministes, continuité,
runner, brokers Git/Telegram/harness, event store, dashboard, live log, bootstrap, oracle auto-généré et
intégrations.

**Baseline retenue.** Après mise à jour du serveur Ollama de `0.32.13` vers `0.32.15`,
`maternion/ling-3.0-tiny:8b` charge correctement : smoke **6/6** à 52,57 tok/s, protocol **6/6** à
53,17 tok/s, Pi **18/18**, agentic **4/6**, contexte **3/3 jusqu'à 16k** et endurance **1/3**. Le 32k
n'a produit aucun token en plus de 15 minutes. La faiblesse observée porte sur l'achèvement multi-tool :
les deux échecs d'endurance exécutent les tests mais omettent le rapport final.

**Prochain chemin critique.** Les PR `#1` à `#6` sont toutes fusionnées dans `main` et les deux LaunchAgents
restent actifs. Le rush `band-smoothing` est `completed` (commit `e4cd83d`, PR `#4`) et un marqueur local
empêche toute répétition. Les PR `#5` (horodatage `started` du rapport) et `#6` (récap Telegram humain) sont
également fusionnées. Il reste à choisir le prochain micro-rush pour `experiments/visualizer-dry-run/` et à
changer `micro_rush_id` dans `.pithos.json` pour le libérer ; jusque-là, chaque réveil du runner se termine en
skip idempotent. Le harnais peut désormais générer l'oracle du prochain rush lui-même (`.pithos.json` sans
`validation_command`) — voir [`RUN_GUIDE.md`](RUN_GUIDE.md). Aucun secret n'est tracké.

## Protocole de collecte — semaine autonome

Objectif : accumuler des trajectoires Ling comparables sans perdre les échecs intermédiaires. Pour chaque
nouveau rush, conserver **un objectif borné**, **un oracle externe rouge avant inference**, **un identifiant
unique**, **un titre** et **une description courte** human-readable dans `.pithos.json`.

1. Merger la PR du rush précédent avant de préparer le suivant, puis repartir de `origin/main`.
2. Changer `micro_rush_id` uniquement quand le nouveau contrat, les fichiers cibles et l'oracle sont prêts ;
   ne jamais supprimer manuellement le marqueur `~/logs/pithos/runtime/*-completed.json` pour forcer un run.
3. Laisser les LaunchAgents et Docker/Ollama actifs. Le runner se réveille toutes les **10 800 s** ; un rush
   terminé doit produire uniquement des skips jusqu'au changement explicite de son identifiant.
4. Ne supprimer ni JSONL, sessions Pi, rapports, streams, logs Squid, SQLite, échecs, timeouts ou tool failures.
   Le collecteur doit rester `RunAtLoad`/`KeepAlive` et la quarantaine doit rester visible, jamais maquillée.
5. N'accepter une PR autonome qu'après oracle vert, rapport conforme, notifications Telegram, commit, push et
   URL de PR observés. Une régression ou un timeout est une donnée à conserver, pas un résultat à corriger à la
   main dans la branche du modèle.
6. Contrôler chaque jour : état des deux LaunchAgents, espace disque, `pithos.db`, quarantaine, dernière mission,
   PR ouverte et présence des notifications Telegram début/fin/récap. Noter toute intervention humaine.

Contrat Telegram implémenté au commit `6cf43c0`, fusionné dans `main` via la PR `#6` (empilée sur `#5`) : les
messages statiques restent autoritaires et exposent le titre, la description, le statut, la durée, les
réparations et la PR. Après chaque mission complète, une session Ling
sans tool choisit des fragments de voix autour de phrases factuelles immuables et produit quelques lignes dans une
voix de sidekick paniqué : léger bégaiement, hésitations (`Euh`, `Hum`, `Genre`), expressions fréquentes
`Oh, punaise`, `Oh, mince` ou `Oh, mec`, langage parlé imparfait, phrases interrompues et brusques pointes de
colère ou de lassitude. Le prénom `Rick` n'est répété que si le message s'adresse réellement à Rick. Ce bonus
est borné à 45 s, 100 tokens et 800 caractères, journalisé et best-effort : aucune invention, aucun tool,
aucun effet sur le statut du run. Un smoke Ling local puis un envoi Telegram réel ont réussi.

## Carte du dépôt

| Chemin | Rôle |
|---|---|
| `PROJECT.md` | Périmètre et critères de succès canoniques du projet. |
| `docs/` | Roadmap, ELN, explications et ancien quick catch transversal. |
| `preliminary_work/00-*` à `12-*` | Sous-projets autonomes, décisions, preuves et snapshots SHA-256. |
| `harness/` | **Distribution active** : package Python, runtime, dashboard, scripts et templates. |
| `harness/ground_truth/` | Constitution read-only : `AGENTS.md`, skill de continuité et extensions brokerisées. |
| `experiments/` | Futurs dépôts Git indépendants générés pour les campagnes ; absent tant qu'aucune campagne n'est créée. |
| `journals/harness/` | Futurs snapshots de mutations du harness ; alimenté pendant les campagnes. |
| `~/logs/pithos/` | État mutable hors Git : runs, JSONL, SQLite, rapports, benchmark et `live.log`. |

> Les `__pycache__` présents dans certains snapshots préliminaires sont des artefacts figés. Ne pas les
> prendre pour une source active ni les éditer à la place de `harness/`.

---

## Scénarios préliminaires

### 00 — Contrats persistants — **DONE**

- **Implémenté :** schémas v1 `run`, `micro-rush`, `event`, métadonnées de rapport, fixtures et CLI de validation.
- **Garantie :** JSONL append-only, timestamps zonés et rapport `Context / Work / Next items` validable.
- **Suite :** faire évoluer les schémas uniquement de manière compatible avec les consommateurs existants.

### 01 — Benchmark et sélection du modèle — **DONE**

- **Implémenté :** moteur headless, trois tentatives, métriques ressources, SQLite, export Git, TUI Textual et
  dashboard localhost.
- **Scénarios :** 17 workloads répartis entre `smoke`, `protocol`, `pi`, `agentic`, `context` et `endurance`.
- **Acquis réel :** le probe historique de `qwen3.8:27b` est archivé ; son débit/timeout ne permet pas de le
  qualifier comme baseline praticable.
- **Première vague réelle :** les cinq candidats ont atteint la gate `smoke`. Ling devient la baseline
  retenue après mise à jour du runtime ; les deux grands modèles chargeables mais impraticables ont été
  interrompus après conservation des streams et métriques ressources.
- **Meilleur candidat court :** `qwen2.5-coder:7b`, **21,39 tok/s** en smoke et **19,30 tok/s** en protocol.
  Il échoue cependant les tools natifs 3/3 et les scénarios Pi outillés 15/15.
- **Ling :** tools Pi réels 15/15 dans la suite Pi ; agentic 4/6, contexte 3/3 à 4k, 8k et 16k ; premier
  essai 32k interrompu après plus de 15 minutes ; endurance 1/3.
- **Décision :** poursuivre avec Ling, contexte opérationnel borné à 16k et rapport validé comme condition
  d'achèvement. Une seconde vague reste possible sans bloquer la suite.

### 02 — Capability probe Pi + modèle — **DONE**

- **Implémenté :** dix capacités, fixtures isolées et classification séparée de `process_success`,
  `protocol_success`, `task_success` et `report_success`.
- **Garantie :** un tool call seulement imprimé est un échec ; les effets sont vérifiés hors réponse du modèle.
- **Preuve réelle Ling :** **10/10**, jusqu'aux multi-tools, rapport, skill réutilisé et extension chargée dans
  un nouveau processus.

### 03 — Continuité inter-session — **DONE**

- **Implémenté :** publication atomique de `latest.md`, archives immuables, métadonnées et refus des rapports
  invalides ou interrompus.
- **Preuve réelle Ling :** deux sessions et workspaces distincts ; la seconde reçoit uniquement `LATEST.md`,
  le lit avec un tool et restitue exactement le fait durable de la première.

### 04 — Runner autonome — **DONE (réel)**

- **Implémenté :** verrou anti-chevauchement, récupération de PID mort, heartbeat, timeout de 60 minutes,
  arrêt d'arbre de processus, loop guard et pause persistante.
- **Runtime :** Docker par défaut, filesystem racine read-only, workspace ciblé et egress via Squid allowlisté.
- **Preuve réelle :** image arm64 `pithos-agent:local` construite ; Pi/Ling répond `DOCKER_OK` dans un rootfs
  read-only via le réseau interne et Squid. Ollama répond `200`, un domaine arbitraire `403` et le log attribue
  la requête au run `docker-pi-smoke`.
- **Architecture macOS :** Docker Desktop ne monte pas les sockets Unix hôte. Le chemin orchestré ne les expose
  donc pas au modèle : le finalizer hôte appelle les brokers après oracle vert.

### 05 — Git et pull requests — **DONE (réel)**

- **Implémenté :** broker Unix `0600`, policy de dépôt/remote/branche et opérations `status`, `switch`, `commit`,
  `push`, `pr_create`, `pr_view`, `pr_merge`.
- **Garantie :** aucun credential dans le workspace, aucun force-push, fusion limitée à la PR autorisée.
- **Preuve réelle :** la mission `run-20260824T150624Z-fbeb4f` pousse puis réutilise la PR `#1`, fusionnée
  dans `main` le 24/08/2026.

### 06 — Évolution du harness — **PARTIAL**

- **Implémenté :** snapshots `before/after`, manifests SHA-256, promotion contrôlée, validation TypeScript,
  diff/restauration et brokers de mutation.
- **Acquis réel :** Pi RPC charge les trois extensions Pithos et découvre le skill de continuité sans inference.
- **À faire :** observer la création puis la **réutilisation cognitive** d'une capacité par Pi en campagne.

### 07 — Event store SQLite — **DONE**

- **Implémenté :** projection reconstructible depuis JSONL, migrations, curseurs byte/ligne, ingestion
  idempotente, quarantaine et refus des troncatures. Le collecteur couvre `runs/` et `missions/`.
- **Garantie :** Pi ne dépend pas de SQLite ; événements bruts, payloads et relations métier restent consultables.
- **Preuve réelle :** **166 988 événements**, **0 quarantaine**, dont les missions Ling et le trafic Squid.
- **Commande :** `pithos-events --logs-root ~/logs/pithos once`.

### 08 — Dashboard d'observabilité — **DONE (réel)**

- **Implémenté :** API FastAPI read-only, pagination, health service/données, frontend React/Vite et Compose.
- **Validation :** images API/web construites et services healthy ; SQLite et artefacts sont montés en lecture
  seule. La mission `run-20260824T160502Z-e0f030`, ses métriques, événements et rapport sont servis par l'API.
- **Accès :** `http://127.0.0.1:1208`. Toute publication LAN reste hors périmètre sans décision explicite.

### 09 — Telegram — **DONE (réel)**

- **Implémenté :** broker Unix `0600`, allowlist utilisateur, rate limiting, idempotence et commandes `/status`,
  `/latest`, `/pause`, `/stop`, `/answer` ; aucun `/resume` distant.
- **Garantie :** le loop guard tente `[WARNING] Boucle récursive infinie détectée.` puis interrompt même si
  Telegram est indisponible.
- **Preuve réelle :** le probe authentifié atteint `@pithos_workbot`; les credentials ne sont pas persistés.
- **Cycle de vie :** le runner envoie automatiquement début et fin de run ; une fin non réussie est signalée
  en `WARNING`. Ces notifications sont idempotentes et n'affectent jamais le statut du run.
- **Récap humain :** `title` et `description` sont obligatoires. Après la preuve terminale, Ling choisit trois
  fragments de voix sidekick dans des allowlists ; le harnais insère objectif, fichiers, réparations, tools,
  durée, validation et PR sans laisser le modèle les reformuler. Le texte est archivé hors Git avant envoi.

### 10 — Live logs — **DONE**

- **Implémenté :** `~/logs/pithos/live.log`, verrou `flock`, flush + `fsync`, rotation par renommage et archives
  illimitées, indépendamment de SQLite/dashboard.
- **Acquis réel :** `tail -F` a suivi les lignes avant et après rotation ; les événements des runners et des
  missions orchestrées alimentent le même fichier.
- **Commande :** `tail -F ~/logs/pithos/live.log` ; la commande SSH exacte attend l'hôte et l'utilisateur.

### 11 — Bootstrap de campagne — **DONE**

- **Implémenté :** bootstrap idempotent, installateur, templates d'expérience, création d'un dépôt Git isolé et
  lanceur d'un run supervisé avec les brokers disponibles.
- **Validation :** le générateur refuse d'écraser une cible et n'injecte aucun credential.
- **Dry-run préparé :** `experiments/visualizer-dry-run/` adapte la fiche `tempo` et borne le premier rush à
  une fonction pure d'agrégation FFT testée. Le dossier reste dans le dépôt Pithos, sans `.git` imbriqué.
- **Dry-run réel :** le contrôleur multi-session borne Ling, valide hors modèle, publie le rapport, notifie
  Telegram et finalise Git. La PR `#1` issue du dry-run a été fusionnée.
- **Activation réelle :** deux LaunchAgents utilisateur séparés exécutent le launcher toutes les trois heures
  et le collecteur SQLite en continu. Un verrou couvre toute la mission et un micro-rush réussi est ignoré aux
  réveils suivants jusqu'au changement de son identifiant. Les validations utilisent le Python exact du venv,
  sans dépendre d'un shim `pyenv` interactif.
- **Premier wake :** `run-20260824T165029Z-dac825` termine après un timeout, deux réparations et un oracle final
  vert : **533 278 ms**, **37 543 tokens**, **6 tool calls**, dont 3 en échec récupéré. Telegram envoie
  début/fin, Git pousse `agent/rush-band-smoothing` et ouvre la PR `#4`. Le wake suivant retourne
  `micro-rush already completed`, sans nouvelle mission.

---

## Commandes de reprise

```bash
cd ~/code/pithos/harness

# état déterministe du socle
python -m pip install -e '.[dev]'
pytest -q -p no:cacheprovider
python scripts/sync_preliminary.py --check
npm --prefix dashboard/web run build
docker compose -f runtime/docker-compose.yml config
docker compose -f dashboard/docker-compose.yml config

# prérequis et benchmark
./install.sh --check
pithos-benchmark list
pithos-benchmark <ollama_model_name> --suite smoke
pithos-benchmark <ollama_model_name> --suite protocol
pithos-benchmark <ollama_model_name> # campagne complète après qualification

# après sélection du modèle et validation des probes
./install.sh --experiment <experiment-id>
$EDITOR ../experiments/<experiment-id>/PROJECT.md
.venv/bin/python scripts/run_experiment.py ../experiments/<experiment-id>

# activation périodique après merge du code courant
.venv/bin/python scripts/install_launchd.py install ../experiments/visualizer-dry-run
```

## Gate avant autonomie périodique

- [x] Baseline locale sélectionnée sur résultats réels et limites documentées.
- [x] Tool calls Pi réellement exécutés dans la suite de qualification.
- [x] Reprise réussie entre deux sessions neuves via `latest.md`.
- [x] Runtime Docker construit et smoke testé avec egress attribué ; brokers exécutés côté hôte.
- [x] Telegram réel probé avec credentials hors workspace.
- [x] Branche, push et PR réels produits par un dry-run supervisé.
- [x] Événements JSONL, SQLite, dashboard, rapport et live log vérifiés sur une mission orchestrée.
- [x] Activation périodique `launchd` approuvée explicitement par l'utilisateur.
- [x] LaunchAgents installés et premier réveil autonome vérifié après merge du raccordement.

## Références canoniques

- Relancer un micro-rush : [`RUN_GUIDE.md`](RUN_GUIDE.md) — protocole à jour, oracle auto-généré et ses limites.
- Périmètre : [`PROJECT.md`](PROJECT.md)
- État détaillé : [`docs/ROADMAP.md`](docs/ROADMAP.md) et [`docs/ELN.md`](docs/ELN.md)
- Architecture et arbitrages : [`docs/EXPLANATIONS.md`](docs/EXPLANATIONS.md)
- Installation : [`harness/docs/SETUP.md`](harness/docs/SETUP.md)
- Détail d'un scénario : `preliminary_work/<id>/PROJECT.md`, puis son `README.md` quand présent.
