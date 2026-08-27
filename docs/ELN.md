# Cahier de laboratoire

## 23:08 — Socle 00 à 06

- Contrats JSON/Markdown versionnés et validés.
- Baseline Ollama mesurée ; `qwen3.8:27b` reste le modèle imposé malgré un débit inférieur à 1 token/s et
  des timeouts sur les probes structurés/tool calls.
- Capability probe, continuité atomique, runner borné, broker Git et promotion du harness implémentés.
- Les validations nécessitant une session Pi fonctionnelle restent explicitement ouvertes.

## 23:08 — Event store 07

- SQLite est une projection reconstructible ; les JSONL restent la preuve primaire.
- Curseur byte/ligne par source, ingestion idempotente, quarantaine et refus des troncatures.
- Migrations v1/v2 et projections métier ajoutées ; contenu brut intégral conservé.
- **56 tests passent** sur l'ensemble du dépôt.

## 23:08 — Dashboard 08

- API FastAPI strictement read-only avec pagination bornée et health service/données séparé.
- Interface React/Vite dérivée des design tokens et cartes d'Argos/Aede.
- SQLite et artefacts montés `:ro` dans la composition Docker ; publication LAN différée.

## 23:08 — Telegram 09

- Broker socket `0600`, destinataire fixe, cinq types sortants et rate limiting.
- Offset et `request_id` persistants pour rendre updates et envois idempotents après redémarrage.
- `/pause` et `/stop` sont observés par le monitor du run ; aucune reprise Telegram n'est exposée.
- Le loop guard tente le message exact avant l'interruption et reste fail-safe si Telegram est indisponible.

## 23:08 — Live logs 10

- Format mono-ligne horodaté, verrou `flock`, flush et `fsync` à chaque événement.
- Rotation par renommage vers une archive illimitée, sans dépendance à SQLite ou au dashboard.
- Test réel : un processus `tail -F` a reçu les lignes avant et après remplacement du fichier canonique.
- **72 tests passent** sur l'ensemble du dépôt.

## 23:08 — Audit transversal et runtime isolé

- Le runner utilise désormais Docker par défaut avec filesystem racine read-only, workspace ciblé,
  configuration Pi réinjectée et egress HTTP(S) via une allowlist Squid journalisée.
- Les événements JSON de Pi sont conservés puis projetés en métriques de modèle, tools, commandes, tests,
  fichiers, dépendances et réseau ; le chemin complet runner → JSONL → SQLite → API est testé.
- Les mutations Git, Telegram et du harness passent par des brokers Unix dédiés ; la ground truth n'est
  jamais montée en écriture dans le conteneur agent.
- Le dashboard expose les métriques, domaines et artefacts paginés. La visibilité d'un SQLite en WAL sur
  montage read-only est couverte par un test d'intégration.
- Les requêtes Telegram sont rejouables après erreur, les updates sont traitées au plus une fois et
  `/answer` alimente le contexte du réveil suivant.
- **87 tests passent**, le frontend TypeScript compile et les deux compositions Docker sont valides.
- La construction réelle des images reste non testée : le daemon Docker local est arrêté.

## 23:08 — Probes Pi réels de clôture

- Ollama `0.32.13` répond localement et expose les trois modèles attendus.
- Le timeout HTTP interne Pi de cinq minutes a été identifié puis porté à une heure dans les configurations
  host et Docker ; les retries agent sont désactivés pour préserver la limite globale d'un run.
- Après correction, `qwen3.8:27b` n'a produit que quatre fragments de thinking en dix minutes et aucune
  réponse finale. Les tool probes restent donc injustifiables dans cette configuration.
- Pi RPC charge réellement les trois extensions Pithos et découvre le skill de continuité dans un nouveau
  processus, sans dépendre de l'inference.
- **89 tests passent** après ajout des invariants de configuration Pi host/Docker.

## 23:08 — Bootstrap hôte

- `scripts/bootstrap.py` vérifie les commandes, fichiers contrôlés et configurations Pi avant toute écriture.
- Il crée uniquement les répertoires persistants manquants et préserve le contenu de `live.log` lors des
  réexécutions.
- Le bootstrap réel puis son mode `--check` retournent `ready=true` sur cette machine.
- **92 tests passent** après ajout des contrôles d'idempotence et de refus avant écriture.

## 23:08 — Réorganisation et benchmark modèle

- Le dépôt est séparé en `preliminary_work/`, `harness/` et `experiments/` sans submodule.
- Les douze projets sont numérotés `00` à `11`; le probe initial est fusionné dans `01-model-benchmark`.
- Les douze implémentations sont dupliquées avec manifests SHA-256 ; l'activation longue du projet 11 reste
  en attente de la sélection modèle.
- Le benchmark contrôle seulement la résidence des modèles déjà installés et exécute trois tentatives.
- Moteur headless, streaming TTFT, ressources, gates, suites Ollama/Pi/agentic/endurance, SQLite, export Git,
  TUI Textual et dashboard localhost sont implémentés.
- L'installateur du harness et le générateur de dépôts expérimentaux sont ajoutés et testés.
- Le lanceur d'expérience assemble proxy et brokers disponibles puis exécute un run unique ; le cleanup final
  du benchmark décharge toujours le modèle ciblé.
- **106 tests passent** après migration complète.

## 24:09 — Reprise du benchmark modèle

- Première vague fixée aux cinq tags Ollama déjà installés : `qwen2.5-coder:7b`,
  `maternion/ling-3.0-tiny:8b`, `qwen3.8:27b-mlx`, `qwen3.8:27b` et `qwen3.6:35b`.
- Qualification prévue par gabarit croissant : suites `smoke` et `protocol` comparables sur les cinq candidats,
  puis suites Pi et longues sur les candidats viables.
- Aucun résultat n'est inféré depuis la taille ou le nom du tag ; le benchmark archive les métadonnées Ollama
  exactes et conserve les échecs comme résultats.

## 24:09 — Première vague réelle

- `qwen2.5-coder:7b` : smoke 3/6 à 21,39 tok/s médian ; protocol 3/6 à 19,30 tok/s ; Pi 2/18.
  JSON structuré réussi 3/3, mais tool call natif 0/3 et tools Pi 0/15, sérialisés en texte.
- `maternion/ling-3.0-tiny:8b` : 0/6 ; Ollama refuse l'architecture `bailingmoe3` avant chargement.
- `qwen3.8:27b-mlx` : 0/6 ; chargement refusé, 16,9 GiB requis pour 11,3 GiB disponibles.
- `qwen3.8:27b` : tentative cold interrompue après 905 échantillons et plus de 15 minutes sans réponse finale ;
  pic mémoire 12 564 611 072 octets, swap 10 534 387 712 octets.
- `qwen3.6:35b` : tentative cold interrompue après 311 échantillons et plus de 5 minutes sans réponse ; pic
  mémoire 13 369 262 080 octets, swap 14 834 008 064 octets.
- Deux défauts du harness corrigés : corps des erreurs HTTP Ollama désormais conservé ; timeout streaming
  appliqué à la durée wall-clock et override inscrite dans le manifeste.
- Aucun candidat ne franchit la gate tools Pithos ; suites agentic/context/endurance non lancées.

## 24:09 — Ling débloqué par Ollama 0.32.15

- Ollama 0.32.13 embarquait llama.cpp `b10380`, antérieur au support `BailingMoE3` ajouté le 17/08/2026.
  Ollama 0.32.15 embarque `b10488`, qui contient ce support ; aucun poids ni Modelfile n'a été modifié.
- Ling smoke : 6/6, 52,57 tok/s médian ; protocol : 6/6, 53,17 tok/s médian, dont tools natifs 3/3.
- Ling Pi : 18/18 ; les effets réels de `bash`, `edit`, `read`, `test` et `write` sont vérifiés.
- Ling agentic : 4/6 ; rapport de continuité 3/3, multi-tool strict 1/3. Les deux échecs créent le bon fichier
  mais omettent ou désordonnent la vérification demandée.
- La speed gate a été corrigée : une suite coûteuse lancée isolément n'est plus skipped faute de mesure de
  vitesse dans la même campagne. L'absence de métrique n'est plus assimilée à une vitesse insuffisante.
- Ling devient baseline provisoire ; `context`, `endurance` et reprise inter-session restent à qualifier.

## 24:08 — Qualification longue de Ling

- Les prompts synthétiques ont été corrigés pour viser réellement les paliers annoncés : le filler précédent
  produisait environ trois tokens Ling par répétition. Les scénarios context sont versionnés en v2.
- Contexte : 4k, 8k et 16k passent chacun 3/3. Les prompts mesurés contiennent respectivement 4 045, 8 045
  et 16 045 tokens.
- Le premier essai 32k n'a produit aucun token après plus de 15 minutes. Il a été interrompu sans OOM ; il
  restait environ 4,7 Go disponibles et le swap n'augmentait pas. Ce palier est impraticable sur cette cible.
- Endurance : 1/3. Les trois processus et protocoles réussissent ; les deux échecs exécutent les tests mais
  omettent `report.md`, tandis que le troisième run termine les 12 tool calls et le rapport attendu.
- Décision : Ling devient la baseline pour la suite, avec contexte opérationnel borné à 16k, validation du
  rapport comme condition d'achèvement et reprise explicite des travaux incomplets.

## 24:08 — Capability probe et continuité réels avec Ling

- Le chemin CLI documenté `--all` échouait dans `argparse` sur la valeur par défaut du positional ; le défaut
  est corrigé et couvert par régression.
- Les huit capacités existantes passent en conditions réelles : text, read, write, edit, bash, test,
  multi-tool et rapport.
- Les deux scénarios manquants au contrat ont été ajoutés. Ling crée un skill puis le réutilise cognitivement
  dans un nouveau processus ; il crée aussi une extension TypeScript, qui est chargée et appelée après restart.
- Résultat capability final : 10/10, avec vérification externe et cycles tool équilibrés.
- Le probe de continuité lance deux workspaces et deux sessions Pi distincts. La première session crée et
  publie un rapport valide avec 2 tool calls ; seule une copie de `latest.md` atteint la seconde session.
- La seconde session exécute un read tool et restitue exactement `PITHOS_CONTINUITY_FACT_42`. La reprise
  inter-session est donc établie sans `pi --continue` ni lecture du JSONL précédent.

## 24:08 — Préparation du dry-run visualiseur

- La fiche `~/code/tempo/PROJECT.md` est adaptée dans `experiments/visualizer-dry-run/` avec un premier
  micro-rush borné : agrégation FFT déterministe en trois bandes, sans dépendance ni matériel audio.
- Les expériences appartiennent désormais au dépôt Pithos existant ; le générateur ne crée plus de `.git`
  imbriqué et refuse un remote distinct.
- Le broker Git accepte un workspace situé dans un dépôt parent et limite status/staging au sous-dossier
  expérimental. Ce garde-fou évite d'embarquer les changements préliminaires adjacents.
- Le runtime du premier dry-run est configuré sur l'hôte, car le daemon Docker local est arrêté.
- Blocages externes avant lancement : authentification `gh` invalide et credentials Telegram non injectés
  dans l'environnement sécurisé du processus.

## 24:12 — Dry-run supervisé Ling

- GitHub est authentifié et le probe Telegram réel confirme le bot `@pithos_workbot`. Le token est resté dans
  l'environnement des processus et n'a pas été écrit dans le workspace.
- Le launcher démarrait Docker même avec `runtime: host` ; la condition est corrigée et couverte par test.
- Run `run-20260824T100042Z-f2df8f` : échec à 4k, la compaction Pi dépasse la fenêtre Ollama effective.
- Un alias local Ling fixe `num_ctx=16384`; le modèle reste identique. Le runner accepte désormais le modèle
  déclaré par l'expérience.
- Run `run-20260824T101245Z-4c16f9` : Ling écrit du code et lance 14 tests, dont 1 échoue, puis s'arrête sans
  rapport après 14 471 tokens. Il tente aussi une installation NumPy contraire au projet.
- Run `run-20260824T101858Z-63523f` : après clarification du contrat, Ling relance les tests et édite le code,
  mais conserve une forme de retour incorrecte puis reste dans une génération prolongée. Interruption humaine
  après plus de sept minutes ; le document `run.json` reste `running`, révélant un défaut de finalisation sur
  `KeyboardInterrupt`.
- Aucun commit, push ni PR n'est créé. Le dry-run invalide donc Ling comme baseline d'autonomie longue en
  l'état, malgré ses bons capability probes atomiques.

## 24:30 — Notifications Telegram de cycle de vie

- Le runner envoie désormais un message statique au démarrage et à la fin de chaque run lorsque le broker
  Telegram est configuré ; ces messages ne dépendent pas du LLM.
- Une fin `completed` utilise `INFO`. Les statuts `failed`, `paused`, `timed_out` et autres fins non réussies
  utilisent `WARNING` et incluent la raison d'arrêt disponible.
- Les identifiants de requête sont déterministes par run (`started` / `finished`) pour conserver
  l'idempotence du broker. Une panne Telegram reste best-effort et ne change jamais le résultat du run.

## 24:31 — Orchestration spécialisée pour Ling

- Villani Code est étudié depuis son dépôt source. Les mécanismes retenus sont l'état de mission explicite,
  la gouvernance du contexte, les checkpoints, la validation externe et les raisons d'arrêt structurées.
- Le chantier `12-weak-model-orchestration` formalise `implement → test → repair → review → finalize`, avec
  trois réparations maximales et une session Pi neuve pour chaque phase cognitive.
- Le contexte est assemblé par priorité sous un budget de 40 000 caractères. Un contrat obligatoire hors
  budget est refusé avant inference et les erreurs de validation sont compactées à six lignes significatives.
- La machine à états persiste atomiquement chaque transition. Un prototype Pi exécute une phase courte sans
  imposer rapport, Git ou notification au modèle.
- `KeyboardInterrupt` arrête désormais le processus enfant puis finalise `run.json` avec le statut
  `interrupted`, une raison et la notification Telegram correspondante.
- État restant : raccorder le validateur externe, le finalizer rapport/Git et la limite totale de tools, puis
  rejouer le visualiseur deux fois avec Ling.

## 24:14 — Dry-run multi-session Ling validé

- Les runs exploratoires ont révélé quatre défauts du harnais : trois repairs configurés n'en lançaient que
  deux, l'alias Ollama 16k ne correspondait pas à l'ID Pi, une phase coupée laissait une génération Ollama
  orpheline, et le contrat produit complet diluait la tâche atomique.
- Le contrôleur accorde désormais trois sessions de repair réelles. Pi utilise l'alias
  `pithos/ling-3.0-tiny:8b-16k`, avec 1 024 tokens par génération, 8 tool calls et 300 secondes par phase.
- Le contexte préfère un brief `.pithos-task.md`, projette uniquement les fichiers explicitement ciblés et
  rejette les écritures hors cible lors de la recopie.
- Mission `run-20260824T140052Z-54896f` : Ling modifie `src/audio_visualizer.py` en un tool call et 5 660
  tokens cumulés ; l'oracle externe passe, sans repair. La review ouverte suivante atteint inutilement sa
  borne de 300 secondes, ce qui motive sa suppression du chemin nominal.
- Mission `run-20260824T140842Z-1cf808` : aucun fichier modifié sur le workspace déjà conforme ; après la
  borne de phase, l'oracle passe et la mission est finalisée. Deux missions consécutives sont donc completed.
- Le code produit par Ling repasse directement `visualizer_acceptance.py`. Prochaine optimisation : exécuter
  cet oracle en preflight pour éviter toute inference lorsque le workspace est déjà vert.

## 24:50 — Finalisation déterministe et tentative Git réelle

- Le preflight exécute désormais l'oracle avant inference. La mission `run-20260824T144651Z-85912b` termine
  sans appel Ling, publie un rapport conforme et archive la continuité du run.
- L'oracle combine la vérification constitutionnelle du source et le test exécutable du projet. Deux missions
  Ling ciblées sur l'ancien test ont échoué : créations hors cible puis 0 tool call en 300 secondes. Le
  harnais a matérialisé son acceptance test et les artefacts Pytest contradictoires ont été retirés.
- Le launcher canonique démarre les brokers puis appelle le contrôleur multi-session. Telegram début/fin est
  best-effort ; Git reste strictement ordonné `switch → commit → push → pr_create` après oracle vert.
- Mission `run-20260824T144826Z-f00869` : branche `agent/rush-visualizer-dry-run` et commit local `8394e9a`
  créés. Le push HTTPS échoue avec `could not read Username`; l'état devient `failed`, aucune PR n'est créée et
  la continuité globale n'est pas remplacée par ce run incomplet.
- `gh auth status` signale un token invalide et les variables Telegram sont absentes du processus. Le code est
  validé par 131 tests ; push/PR et notification réelle attendent uniquement le rétablissement des credentials.

## 24:54 — Push et PR GitHub réels

- Le statut `gh` hors sandbox confirme que le token est valide. Le push échouait parce que `~/.gitconfig` est
  un lien symbolique cassé vers un ancien dépôt de dotfiles, donc aucun credential helper n'était disponible.
- Le helper `gh auth git-credential` est configuré uniquement dans `.git/config`, sans modifier la
  configuration globale ni exposer le token.
- Mission `run-20260824T145348Z-c947ce` : preflight PASS, branche existante reprise, commit `875789f`, push
  réussi et PR GitHub `#1` créée vers `main` depuis `agent/rush-visualizer-dry-run`.
- Les événements `git.switch`, `git.commit`, `git.push` et `git.pr_create` sont tous `ok: true`. La PR est
  vérifiée distante à l'état `OPEN` : https://github.com/victorcarre6/pithos/pull/1.
- Le rapport du run est conforme puis publié dans la continuité globale. Telegram réel reste non mesuré car
  ses variables ne sont pas présentes dans l'environnement du launcher.

## 24:10 — Notifications Telegram réelles et chantier 12 clos

- Le launcher charge uniquement `TELEGRAM_BOT_TOKEN` et `TELEGRAM_USER_ID` depuis le `.env` de l'expérience,
  sans écraser les valeurs hôte. Le fichier est en mode `0600` et explicitement ignoré par Git.
- Mission `run-20260824T150624Z-fbeb4f` : preflight PASS sans inference, rapport valide, commit `359abc3`
  poussé et PR GitHub `#1` réutilisée par `pr_view` plutôt que recréée.
- Les requêtes Telegram statiques `orchestrated-started` et `orchestrated-finished` sont toutes deux enregistrées
  `result: sent`; les deux événements associés sont `telegram.sent` de niveau `INFO`.
- Le `.env` est absent de `git ls-files`. La suite complète passe avec 132 tests et les snapshots sont alignés.

## 24:08 — PR du harnais ouverte

- La PR expérimentale `#1` est fusionnée dans `main` au commit `33b1fe7`.
- Le socle préliminaire complet est figé dans `f4aea96` sur `agent/rush-harness-orchestration`, après
  validation des 132 tests, du build Vite, des deux configurations Compose, des snapshots et du diff Git.
- La PR GitHub `#2` propose ce lot vers `main` : https://github.com/victorcarre6/pithos/pull/2.
- Aucun credential Telegram n'est tracké ; le `.env` de l'expérience reste ignoré.
- Prochaine gate : daemon Docker actif, build de l'image runtime puis smoke isolé avec proxy et brokers.

## 24:08 — Runtime Docker et observabilité réels

- Docker Desktop `28.5.1` est actif. L'image arm64 `pithos-agent:local` est construite et Pi/Ling répond
  exactement `DOCKER_OK` depuis un container read-only sur le réseau interne.
- Squid autorise Ollama `0.32.15` avec un statut `200`, refuse `example.com` avec `403` et attribue la requête
  Pi au run `docker-pi-smoke`. L'auth Basic utilise un mot de passe fixe non secret uniquement pour forcer
  l'émission du `run_id` dans le log.
- Docker Desktop macOS refuse le bind mount des sockets Unix hôte, fichier seul comme répertoire parent. Le
  chemin orchestré est conservé : phases Ling sans broker dans Docker, finalizer brokerisé sur l'hôte.
- L'orchestrateur émet désormais `run.started` et `run.finished`; le collecteur parcourt `runs/` et `missions/`,
  et le live writer réplique les deux familles dans `live.log`.
- L'ingestion réelle projette **166 988 événements sans quarantaine**. Les images dashboard sont construites
  et l'API locale sert la mission `run-20260824T160502Z-e0f030`, son statut `completed`, sa durée de 6 ms,
  ses métriques nulles attendues sans inference et son rapport.
- Le run historique `run-20260824T101858Z-63523f`, interrompu avant le correctif KeyboardInterrupt, reste
  honnêtement `running` dans sa source append-only ; aucune projection n'est maquillée.

## 24:08 — Activation périodique préparée

- La PR `#2` est fusionnée dans `main` au commit `de34573`; le raccordement `launchd` est isolé sur
  `agent/launchd-autonomy`.
- Le launcher prend désormais un verrou couvrant Docker, brokers et mission. Un second réveil retourne un
  skip contrôlé ; un verrou de PID mort reste récupérable par le contrat existant.
- `micro_rush_id` pilote branche, rapport et idempotence. Une nouvelle branche est créée depuis
  `origin/main`; une PR `MERGED` ou `CLOSED` est refusée avant commit et push.
- Un marqueur sous `~/logs/pithos/runtime/` empêche de répéter un rush réussi jusqu'au changement de son ID.
- Le validateur remplace l'alias `python` par l'interpréteur courant du harnais ; la future exécution
  `launchd` ne dépend donc pas d'un shim `pyenv` interactif.
- L'installateur produit deux plist privés sans secret : runner toutes les trois heures et collecteur SQLite
  `RunAtLoad`/`KeepAlive`. Les plist rendus passent `plutil -lint`.
- Le prochain rush `band-smoothing` cible seulement `src/audio_visualizer.py` en Docker. L'ancien oracle reste
  vert et le nouvel oracle échoue avant inference sur l'absence attendue de `smooth_levels`.
- La suite complète passe avec **142 tests**. L'installation réelle attend le merge de cette branche afin que
  les futures branches créées depuis `origin/main` contiennent le scheduler validé.

## 24:08 — Premier wake autonome réel

- La PR `#3` est fusionnée dans `main` au commit `33ad4b6`. Les plist privés `0600` sont installés dans
  `~/Library/LaunchAgents` : collecteur `RunAtLoad`/`KeepAlive` actif et runner toutes les **10 800 s**.
- Mission `run-20260824T165029Z-dac825` : implement timeout à 300 s sans tool call, première réparation avec
  3 tools rejetée pour régression de `split_bands`, seconde réparation avec 3 tools acceptée par l'oracle.
- Le rush termine `completed` après **2 réparations**. Les oracles smoothing et historique passent ; Telegram
  enregistre les notifications début/fin et Git ouvre https://github.com/victorcarre6/pithos/pull/4 au commit
  `e4cd83d` sur `agent/rush-band-smoothing`.
- Le collecteur projette le run en SQLite : **533 278 ms**, **29 313 tokens d'entrée**, **8 230 de sortie**,
  **6 tool calls**, **3 tool failures**, **2 982 événements** associés et **0 quarantaine** globale.
- Un second `launchctl kickstart` termine avec exit 0 et `micro-rush already completed`, sans nouvelle mission.
- Défaut observé : le rapport prenait `updated_at` comme début. Le contrôleur horodate désormais chaque entrée
  `started`; le test du rapport verrouille cette valeur pour les futurs runs. Le rapport historique reste une
  preuve non réécrite de ce défaut.

## 24:08 — Récap Telegram humanisé

- `title` et `description` deviennent obligatoires dans `.pithos.json`. Les messages statiques affichent le
  but, puis statut, durée, réparations et PR depuis les faits du harnais.
- Deux essais Ling libres sont rejetés : le premier interpelle un personnage non destinataire ; le second
  adopte le bon ton mais invente un abandon malgré `validation: PASS`. Ces sorties ne sont pas envoyées.
- Le protocole final contraint Ling à choisir ouverture, réaction et chute dans trois enums JSON. Objectif,
  fichiers, réparations, tool calls, durée, validation et PR sont insérés ensuite par du code déterministe.
- Smoke réel avec `pithos/ling-3.0-tiny:8b-16k` : structured output valide en environ 2 s, texte inférieur à
  800 caractères, bégaiement et `Oh, punaise`, faits conformes au run `run-20260824T165029Z-dac825`.
- Le message est envoyé réellement par `@pithos_workbot` avec la requête idempotente
  `run-20260824T165029Z-dac825-morty-recap-smoke-v1`. Le token reste chargé depuis le `.env` ignoré.

## 24:20 — PR `#4` à `#6` fusionnées, campagne en pause

- Les PR `#4` (band-smoothing, commit `e4cd83d`), `#5` (horodatage `started` du rapport, commit `618d0ab`) et
  `#6` (récap Telegram humain, commit `6cf43c0`) sont fusionnées dans `main`, respectivement aux commits de
  merge `b69cded`, `02ff9d3` et `34a8ae8`.
- Le marqueur local `visualizer-dry-run-completed.json` conserve `band-smoothing` comme rush terminé ; les deux
  LaunchAgents restent actifs et chaque réveil se termine en skip idempotent tant que `micro_rush_id` n'a pas
  changé dans `experiments/visualizer-dry-run/.pithos.json`.
- **146 tests passent** sur l'ensemble du dépôt. Aucun nouveau rush n'a encore été défini : la campagne attend
  une décision explicite sur la tâche suivante avant le prochain réveil utile.

## 24:35 — Oracle auto-généré par le modèle

- Nouvelle phase `author_oracle`, placée avant `preflight` dans la machine à états (`controller.py`), activée
  uniquement quand `.pithos.json` omet `validation_command`. Le contrat manuel reste prioritaire et inchangé
  pour toute expérience qui le fournit déjà.
- Le modèle ne choisit jamais de code : seulement une fonction déjà présente dans `target_files` et 1 à 4 cas
  d'entrée/sortie numériques. Le harnais (`oracle.py`) rend le script exécuté, exige l'accord de deux
  générations indépendantes à températures différentes, vérifie la fonction par regex dans la source approuvée,
  puis exige que l'oracle rendu échoue sur le code actuel avant de l'accepter (jusqu'à 3 tentatives).
- L'oracle rendu est archivé hors Git dans `~/logs/pithos/missions/<mission_id>/oracle.py`, jamais dans le
  workspace projeté au modèle ni dans le diff Git du rush.
- **Preuve réelle Ling** : demander un oracle pour « normaliser `split_bands` pour que la somme des trois
  bandes vaille 1.0 » a produit un cas confirmé rouge sur le code réel de `visualizer-dry-run`, mais avec une
  valeur `expect` incorrecte au regard du comportement attendu — une erreur arithmétique reproduite de façon
  cohérente sur les deux générations. Le double-vote filtre le bruit aléatoire, pas une incompréhension
  systématique du contrat.
- **158 tests passent** (146 + 12 nouveaux : `test_oracle.py`, phase `author_oracle` du contrôleur, lancement
  sans `validation_command`). Voir [`RUN_GUIDE.md`](../RUN_GUIDE.md) pour le protocole de relance à jour et les
  limites connues.

## 24:55 — PR `#7` ratée, échec rapide et rushes auto-proposés (seed)

- **Diagnostic PR `#7`** : `experiment_id` avait été édité à la main en `"audio_processing"` (underscore
  invalide). Le lanceur ne validait alors ce champ nulle part ; l'échec n'est apparu qu'à `finalize`, après
  une session Docker/Pi complète et l'ouverture d'une PR sans changement réel (`target_files` pointait vers un
  fichier inexistant, `validation_command` recyclait l'oracle `band-smoothing` sans rapport — validation vide).
  La PR a été fermée manuellement par l'opérateur.
- **Correctif** : `launcher.py` valide désormais `experiment_id` et `micro_rush_id` contre
  `^[a-z0-9][a-z0-9-]{0,63}$` (le même motif que `contracts/v1/*.schema.json`) avant toute création de
  mission — un identifiant invalide échoue immédiatement, sans Docker, sans PR.
- **Rushes auto-proposés** : à la demande explicite de l'opérateur, `.pithos.json` peut désormais porter un
  champ `seed` (objectif long terme, jamais réécrit par le modèle). Quand il est présent, une nouvelle phase
  `propose_next_rush` (avant `finalize`) fait proposer par le modèle, en un appel borné à schéma JSON, le
  prochain micro-rush : identifiant, titre, description, jusqu'à 3 `target_files`. Le harnais valide tout
  (format d'identifiant, différent du rush courant, longueur bornée, chemins qui ne sortent pas du workspace)
  avant de réécrire `.pithos.json` avec ces seuls champs modifiés. Best-effort : un échec de proposition ne
  fait jamais échouer la mission qui vient de réussir.
- Le nouveau `.pithos.json` voyage dans le **même commit/PR** que le travail validé — le broker Git n'expose de
  toute façon aucune opération d'écriture directe sur `main` (`BRANCH_PATTERN` n'autorise que `agent/rush-*`).
  Fusionner la PR reste donc le seul point d'activation, cohérent avec la relecture déjà exigée pour l'oracle
  généré.
- **`oracle.py` étendu aux fichiers inexistants** : un `target_files` peut maintenant désigner un fichier qui
  n'existe pas encore (un rush auto-proposé peut légitimement en demander un). Pour ces fichiers, l'oracle ne
  vérifie plus qu'un cas numérique (impossible sans fonction existante) mais que le fichier existe et
  s'importe sans erreur après implémentation — mécaniquement rouge avant, vert après, une garantie
  volontairement plus faible que le contrat numérique, documentée comme telle.
- **Preuves réelles sur `pithos/ling-3.0-tiny:8b-16k`** : `NextRushAuthor` a proposé, à partir du seed
  « Construire un visualiseur audio destiné au VJing » et du rush `band-smoothing` juste terminé, le rush
  `band-peak-normalization` ciblant un fichier existant et deux nouveaux fichiers ; `OracleAuthor` a ensuite
  authoré avec succès un oracle mixte (cas numériques sur `split_bands` + vérifications d'import) sur ces
  mêmes cibles, confirmé rouge.
- **175 tests passent** (158 + 17 nouveaux : `test_next_rush.py`, extension `test_oracle.py` (fichiers
  neufs/mixtes), phase `propose_next_rush` du contrôleur, validation d'identifiants au lancement). Voir
  [`RUN_GUIDE.md`](../RUN_GUIDE.md) § *Rushes auto-proposés*.

## 25:05 — Auto-merge : la boucle se ferme vraiment

- Question posée directement par l'opérateur : « tout est vraiment autonome en vase clos ? ». Réponse honnête
  à ce moment-là : non — `pr_merge` existait déjà côté broker Git mais n'était appelé nulle part ; chaque
  mission ouvrait une PR et s'arrêtait là. Pire : sans merge entre deux réveils, le rush suivant risquait
  d'échouer à `finalize` (conflit Git, la nouvelle branche partant toujours d'`origin/main`, qui n'aurait pas
  le travail du rush précédent) — après avoir déjà consommé une session Docker/Pi complète.
- Sur confirmation explicite de l'opérateur (le compromis — la revue humaine passe d'avant-merge à
  après-merge — avait été posé clairement avant), `LocalFinalizer` (`campaign.py`) gagne un paramètre
  `auto_merge` : après création/réutilisation de la PR, il appelle `pr_merge` (déjà garde-fouté côté broker :
  tête/base conformes à la politique, PR encore `OPEN`). Best-effort — un échec de merge (protection de
  branche, panne GitHub) n'invalide jamais une mission déjà validée ; la cause atterrit dans
  `state.json` → `artifacts.merge_failed`, la PR reste ouverte comme avant.
- Même signal d'activation que `propose_next_rush` : `auto_merge` suit exactement la présence de `seed` dans
  `.pithos.json` (`launcher.py`). Sans `seed`, aucun merge automatique n'a jamais lieu — comportement
  strictement inchangé pour toute expérience qui n'a pas explicitement demandé l'autonomie complète.
- **179 tests passent** (175 + 4 nouveaux : séquence git avec/sans auto-merge, merge sur PR réutilisée, échec
  de merge best-effort, gating par `seed` au lancement). `RUN_GUIDE.md` documente le nouveau compromis de
  revue (avant vs après merge) et corrige l'ancienne affirmation « fusionner la PR active la proposition » —
  ce n'est plus vrai avec `seed` : l'activation est maintenant automatique.

## 25:08 — Diagnostic `level-clamping` et décomposition en micro-passes (`plan_todo`)

- **Diagnostic du run `run-20260825T023932Z-c637a7`** (`level-clamping`, auto-proposé après `band-smoothing`) :
  échec en `author_oracle`, 3 tentatives, toujours *"no case survived cross-generation agreement"*. Hypothèse
  initiale erronée (fonction inexistante ciblée) écartée par le message d'erreur lui-même : `_validate_spec`
  et `_require_same_target` réussissent nécessairement avant qu'`_agreeing_cases` ne puisse être vide, donc les
  deux générations s'accordaient bien sur la même fonction existante — c'est l'arithmétique des cas numériques
  qui a divergé, de façon reproductible sur 3 tentatives. Confirme, sur un second cas réel, la limite déjà
  documentée dans `RUN_GUIDE.md` (« l'arithmétique du modèle n'est pas fiable »).
- **Garde-fou immédiat, sans lien direct avec ce diagnostic** : `next_rush.py` (`propose_next_rush`) reçoit
  désormais `existing_functions` (fonctions déjà `def`-inies dans les fichiers modifiés) dans ses faits, avec
  consigne explicite de préférer modifier une fonction existante plutôt que d'en supposer une nouvelle — la
  fonction `existing_functions()` (ex-`_existing_functions`, renommée publique) est réutilisée telle quelle par
  `plan_todo.py` ci-dessous.
- **Hypothèse de l'opérateur, implémentée** : un petit modèle travaille mieux en plusieurs passes courtes à
  contexte frais qu'en une session longue. Nouvelle phase `plan_todo` (avant `author_oracle`, seulement quand
  l'oracle est auto-généré) : le modèle scinde le rush en 1 à 4 étapes atomiques bornées par schéma JSON
  (`plan_todo.py`), chacune retraversant ensuite le cycle complet `author_oracle → preflight → implement →
  test → repair` **seule, à contexte frais** (`MissionState.todo`/`todo_index`, `state.current_item` dans
  `state.py`, `_advance_todo` dans `controller.py`). Décomposition par défaut best-effort : tout échec de
  planification laisse `state.todo` vide et la mission se comporte exactement comme avant cette version (une
  étape implicite). Une étape qui échoue est marquée `skipped`, pas fatale — la mission échoue seulement si
  aucune étape n'a réussi.
- **Choix délibéré, discuté avec l'opérateur avant implémentation** : une seule PR et un seul récap Telegram
  pour toute la mission, quel que soit le nombre d'étapes — multiplier les PR par étape aurait démultiplié le
  risque de collision d'auto-merge déjà documenté (`Rushes auto-proposés`), sans bénéfice avéré. Seule la façon
  dont le *travail* est scindé change, pas la façon dont il est mergé/rapporté. `oracle-NN.py` remplace
  `oracle.py` seulement pour ce cas (numéroté par étape), afin de garder chaque contrat relisible séparément
  (étape 6 de `RUN_GUIDE.md`).
- **195 tests passent** (179 + 16 nouveaux : `test_plan_todo.py`, boucle multi-étapes du contrôleur — succès
  complet, échec partiel, échec total, réinitialisation des réparations entre étapes —, ciblage de l'étape
  active par `OracleAuthor`/`ContextFactory`, faits `existing_functions` de `next_rush.py`).
  `RUN_GUIDE.md` documente la décomposition sous « Décomposition en micro-passes (`plan_todo`) ».

## 25:09 — Premier run réel avec `plan_todo`, deux causes racines trouvées et corrigées

- **Run `run-20260825T091327Z-e39243`** (`level-clamping`, réveil autonome, première mission réelle sous
  `plan_todo`) : `plan_todo` a correctement jugé la tâche minimale (1 étape) ; `author_oracle` a réussi (2 cas
  d'accord inter-générations, confirmé rouge sur `smooth_levels`) ; mission `failed` après 3 réparations
  épuisées, `implement` et les 3 `repair` tournant chacun ~300-390 s avec **0 tool call, 0 token** avant timeout.
- **Cause racine n°1** : l'oracle généré appelait `smooth_levels(0.0, 0.0, 0.0)` (trois scalaires) alors que la
  vraie signature attend `(previous: tuple, current: tuple, alpha: float)` — rouge confirmé, mais par un
  `TypeError: 'float' object is not subscriptable` (mauvaise arité), pas par le mécanisme d'assertion prévu.
  `_run_script`/le red-check ne vérifiaient que le code de retour, jamais la nature de l'échec.
- **Cause racine n°2**, trouvée en lisant le flux brut du stream Pi (`stdout.jsonl`, 12 419 `thinking_delta`
  consécutifs, jamais un seul tool call) : `.pithos-task.md` — lu en priorité par `ContextFactory`, jamais mis
  à jour par `propose_next_rush` ni par rien d'autre — décrivait encore la tâche `band-smoothing` (« ajoute
  `smooth_levels` »), une fonction déjà mergée. Le modèle recevait donc une consigne contradictoire (ajouter
  ce qui existe déjà) en même temps qu'un crash sans rapport, et restait bloqué en réflexion sans jamais agir.
- **Correctifs :**
  1. `oracle.py` : `_is_assertion_failure(stderr)` — un rouge confirmé n'est accepté que si la dernière
     exception de la trace est bien notre propre `AssertionError` ; tout autre type (`TypeError`,
     `AttributeError`...) est traité comme un cas mal formé et retente (même quota `attempts`). Repro directe
     sur `smooth_levels` avec le payload fautif observé en prod : correctement rejeté.
  2. `campaign.py`/`launcher.py` : `ContextFactory` reçoit maintenant `project` et injecte une section
     `## Current task` (titre + description de l'étape active — `state.todo` si présent, sinon le rush) entre
     `Contract` et `Validation failure`. `.pithos-task.md` réécrit en brief vraiment durable (les deux
     fonctions déjà présentes et leur contrat), qui renvoie explicitement vers `## Current task` plutôt que de
     décrire une tâche figée.
- **199 tests passent** (195 + 4 nouveaux : rejet d'un cas qui crashe au lieu d'assert, section `Current task`
  avec/sans plan, absence de la section sans `project`).

## 25:10 — Troisième échec de `level-clamping` : cause différente, échappatoire manuelle activée

- **Run `run-20260825T100711Z-884d3b`** : le correctif n°1 ci-dessus fonctionne comme prévu — `author_oracle`
  échoue **vite et proprement** (~20 s, `failed` avant `preflight`) au lieu de laisser 4 sessions Pi tourner à
  vide pendant 26 min. Mais la cause de fond ressort : `attempt 1`/`attempt 2` → *"two independent generations
  disagreed on the target function"*, `attempt 3` → *"no case survived cross-generation agreement"*. C'est la
  même limite déjà documentée (arithmétique/contrat non fiable pour un petit modèle) que celle du tout premier
  échec (`run-20260825T023932Z-c637a7`), reconfirmée sur ce même rush après deux correctifs orthogonaux.
- **Diagnostic** : `level-clamping` demande d'ajouter une fonction qui **n'existe pas encore** pour un
  comportement (clamp) qui n'a par ailleurs aucun cas numérique canonique évident à partir de `smooth_levels`
  seul (qui ne clampe rien lui-même) — un contrat plus difficile à inventer correctement pour un modèle 8B que
  « vérifie la valeur de retour d'une fonction déjà là ». Trois tentatives réelles échouées sur exactement ce
  rush, deux d'entre elles pour des raisons différentes : ce n'est plus du bruit aléatoire.
- **Décision** : plutôt que de complexifier encore l'auto-génération d'oracle, activer l'échappatoire manuelle
  que `RUN_GUIDE.md` documente déjà pour ce cas précis. Nouvelle fixture `harness/fixtures/
  visualizer_level_clamping_acceptance.py` (même convention que `visualizer_smoothing_acceptance.py` :
  import qui échoue tant que `clamp_levels` n'existe pas → rouge mécanique, cas numériques couvrant valeurs
  déjà dans `[0, 1]` et hors bornes des deux côtés). Vérifiée rouge avant (`ImportError`) et verte après
  (implémentation de référence testée manuellement, retirée ensuite). `.pithos.json` reprend
  `validation_command` ; `auto_oracle` redevient `False` pour ce rush, donc `plan_todo` ne s'exécute pas non
  plus (cohérent : sa condition d'activation a toujours été liée à l'oracle auto-généré). La `description` est
  réécrite pour nommer explicitement `clamp_levels(levels)` et sa signature exacte, réutilisée telle quelle
  par la nouvelle section `## Current task`.
- **199 tests inchangés** (pas de changement de code, seulement fixture + config). À observer : si
  l'implémentation elle-même échoue maintenant malgré un contrat fiable, ce serait un signal différent —
  faiblesse d'exécution de Ling plutôt que faiblesse de génération de contrat.

## 25:11 — `level-clamping` réussit vraiment (PR #8), deux défauts trouvés dans ce qu'il a déclenché

- **`run-20260825T113201Z-123463`** : succès **réel**, pas un raccourci — vérifié en relisant le diff produit
  (`clamp_levels` correctement implémenté, style cohérent avec le reste du fichier, testé manuellement) et en
  ré-exécutant la fixture après coup. `preflight` rouge (import échoue), **1 seul tool call** en `implement`
  (5564 tokens), vert, PR `#8` créée et auto-mergée. Rapide (~35 s) parce que la tâche était enfin petite et
  précisément spécifiée grâce à `validation_command` + la section `## Current task` — pas un signe de travail
  bâclé.
- **Défaut n°1, dans la proposition auto-générée qui a suivi (`level-clamping-2`)** : `target_files` listait
  deux fichiers neufs sans rapport avec la description (`docs/audio_visualizer_api.md`,
  `tests/audio_visualizer_test.py` — nom qui ne correspond même pas à la convention réelle du projet,
  `tests/test_audio_visualizer.py`). `next_rush.py` ne validait que la sécurité des chemins, jamais leur
  pertinence ni leur type. Un `.md` en `target_files` avec oracle auto-généré est mécaniquement cassé : le
  repli « nouveau fichier » d'`oracle.py` fait `importlib.import_module` dessus sans condition, donc
  échouerait toujours, pour une raison qui ne dit rien du contenu attendu. **Corrigé** :
  `_validate_relative_path` exige maintenant une extension `.py` ; prompt de `_request_next_rush` mis à jour
  en conséquence. `.pithos.json` corrigé à la main pour ce cycle (`target_files` réduit à
  `src/audio_visualizer.py`, seul fichier que la description mentionne réellement).
- **Défaut n°2, retrouvé en préparant le relance** : après le merge auto de la PR `#8`, le checkout local est
  resté sur la branche `agent/rush-level-clamping` (supprimée côté remote par `--delete-branch`, mais
  toujours là en local, working directory pas rebasculé sur `main`) — exactement le risque déjà documenté en
  `RUN_GUIDE.md` (« vérifie quand même avec `git branch --show-current` »), maintenant observé une seconde
  fois (la première avec `agent/rush-setup`). **Corrigé à la racine plutôt que par vigilance manuelle** :
  `GitBroker._pr_merge` (`pithos_git_broker/broker.py`) enchaîne désormais `git switch main` + `git pull
  origin main` juste après un merge réussi, en best-effort (un échec de ce rattrapage ne doit jamais
  transformer un merge réussi en `merge_failed` signalé).
- **204 tests passent** (199 + 5 nouveaux : rejet d'un `target_files` non-`.py` dans `next_rush.py`,
  bascule + pull post-merge dans le broker Git, non-régression si ce rattrapage échoue).

## 25:12 — Réveils toutes les 15 min, verrou anti-chevauchement vérifié, `level-clamping-2` remplacé

- **Intervalle de réveil réduit à 900 s (15 min)**, à la demande explicite de l'opérateur, via l'installeur
  existant (`install_launchd.py --interval-seconds 900`, plancher 300 s) plutôt qu'en éditant le plist à la
  main. Confirmé côté `plutil`/`launchctl print`.
- **Le garde-fou « skip si en cours » existait déjà** (`pithos_runner.lock.RunLock`, verrou-répertoire
  atomique + PID vivant, acquis avant tout effet de bord dans `run_experiment.py`) — aucun code à écrire.
  Vérifié pour de vrai avec un PID réellement vivant (`sleep 300 &`) : skip propre, aucun conteneur Docker ni
  broker démarré. Un premier essai de vérification, avec un PID déjà mort (sous-processus `python3 -c`
  éphémère), a fait passer le verrou pour périmé au lieu de le trouver tenu — a déclenché une mission réelle
  par effet de bord (voir plus bas), pas un problème du mécanisme lui-même, juste un test mal conçu.
- **Effet de bord** : mission réelle sur `level-clamping-2` (le rush auto-proposé après `level-clamping`, qui
  demandait NaN/Inf handling) — échec, même fragilité déjà documentée sur ce type de tâche (les deux items de
  `plan_todo` ratent la génération d'oracle). En creusant, `clamp_levels` gère déjà `+Inf`/`-Inf` correctement
  par construction (`min`/`max` les clampent mécaniquement) et `NaN` retombe déterministiquement sur `1.0` —
  le rush était en grande partie redondant, pas seulement fragile.
- **Décision de l'opérateur** : remplacer plutôt que retenter ou fermer avec un oracle manuel qui ne ferait
  que verrouiller un comportement déjà là. Nouveau micro-rush `frame-pipeline` : assembler
  `process_frame(previous, magnitudes, alpha)` = `split_bands` → `smooth_levels` → `clamp_levels`, la
  composition qui manquait encore pour boucler la pile pure existante. Oracle manuel écrit directement
  (`harness/fixtures/visualizer_frame_pipeline_acceptance.py`, même convention), vérifié rouge avant
  (`ImportError`) et vert après (implémentation de référence jetable, 3 cas dont un calcul à la main).
- **204 tests inchangés** (fixture + config uniquement, pas de code touché).

## 25:13 — Boucle de 6h+ sur un fichier détruit : cause racine (`git switch` sur `origin/main` périmé) + garde-fou

- **Symptôme observé** : `dev.pithos.runner.visualizer-dry-run` tournait toutes les 15-20 min depuis
  `run-20260825T131106Z-db8c72` (13:11) jusqu'à `run-20260825T172751Z-9da0bd` (17:27, encore actif à
  l'inspection), échouant systématiquement en `author_oracle` sur `clamp_levels`/`split_bands`/`process_frame`
  « non défini » — alors que les trois existaient déjà dans le code avant `db8c72`.
- **Cause racine n°1 (déclencheur)** : `run-20260825T121729Z-d9a543` (le rush `frame-pipeline`, 12:19) a
  réellement réussi — `implement` a produit un `process_frame` correct, `test` est passé — mais `finalize` a
  échoué au `git switch -c agent/rush-frame-pipeline origin/main` : commit `17181d3` (config `frame-pipeline`)
  n'avait jamais été poussé (l'opérateur garde la main sur le push final, par consigne explicite), donc
  `origin/main` avait encore l'ancien `.pithos.json` — le switch refusait d'écraser le `.pithos.json` local
  déjà réécrit par `propose_next_rush`. Le travail réel restait non commité sur `main`, sans branche de
  protection. **`GitBroker._switch`** (`pithos_git_broker/broker.py`) basait toute nouvelle branche de rush
  sur `origin/<main>` au lieu du `main` local — un choix qui suppose `origin` toujours à jour, hypothèse
  fausse dès que l'opérateur retient un push. **Corrigé** : `git switch -c <branch> main` (HEAD local), plus
  de `git fetch origin main` préalable.
- **Cause racine n°2 (destruction)** : au réveil suivant (`run-20260825T131106Z-db8c72`, 13:11),
  `auto_oracle` a repris la main (le `propose_next_rush` raté avait déjà retiré `validation_command`) sur un
  `process_frame` non commité. Un `repair` (5 tool calls, weak model sans outil `read` — seulement
  `edit`/`write`) a fini par écraser tout `src/audio_visualizer.py` par un unique appel d'outil mal formé
  écrit comme contenu de fichier : `{"action": "check_file", "path": "/workspace/src/audio_visualizer.py"}`.
  Ce blob est du Python syntaxiquement valide (une expression littérale) donc rien ne l'a jamais rejeté :
  chaque réveil suivant repartait sur un fichier vide de toute fonction, en boucle infinie sans plus jamais le
  modifier (`changed_files: []` sur tous les runs de 14:10 à 17:27).
- **Corrigé à la racine** : `PiPhaseRunner.__call__` (`pi_phase.py`) refuse maintenant d'appliquer un
  changement `.py` à l'espace de travail hôte si (a) il ne compile pas, ou (b) le fichier avait des `def` au
  niveau module avant et n'en a plus aucune après — exactement la signature de cette destruction. Détection
  avant `_apply_projection`, jamais après.
- **Récupération** : le vrai `process_frame` (celui qui avait fait passer le test à 12:19) a survécu dans
  l'instantané de session `phases/01-implement/workspace/` du run `d9a543` — restauré tel quel sur
  `src/audio_visualizer.py`, revérifié rouge-avant/vert-après avec la fixture. `.pithos.json` remis à l'état
  du commit `17181d3` (annule la mutation de `propose_next_rush`, cohérent avec le code maintenant réel).
  `dev.pithos.runner.visualizer-dry-run` stoppé (`launchctl bootout`) le temps de la réparation.
- **3 scripts ajoutés à la racine** (`stop_launchd.sh`, `resume_launchd.sh`, `force_launchd.sh`) pour piloter
  ce LaunchAgent sans retaper les commandes `launchctl` à la main la prochaine fois qu'une boucle doit être
  coupée en urgence.
- **209 tests** (204 + 5 nouveaux : `_valid_python_changes` — accepte, rejette le blob, rejette une erreur de
  syntaxe, ignore le non-`.py`, laisse passer un fichier neuf sans `def` préalable ; `_switch` sur `main`
  local dans `test_git_broker.py`).

## 26:01 — `frame-pipeline-v2` en boucle stérile pendant ~1h20, garde-fou anti-boucle ajouté

- **Constat en reprenant le repo** : `dev.pithos.runner.visualizer-dry-run` n'était plus chargé
  (`launchctl list` ne le montre pas), `run-20260825T204222Z-1c13d7` restait figé en `status: running`
  (dernier événement à 20:45, aucun `finished_at`), et le verrou `visualizer-dry-run.lock` pointait sur le
  PID `94040`, mort. Rien de cassé structurellement : `RunLock._recover_stale_lock` traite déjà ce cas au
  prochain `acquire` (PID mort → verrou nettoyé automatiquement), donc aucune intervention manuelle requise
  sur le verrou lui-même.
- **Cause racine** : `.pithos.json` avait été auto-réécrit par `propose_next_rush` en `frame-pipeline-v2`,
  qui redemande mot pour mot la construction de `process_frame(previous, magnitudes, alpha)` — déjà
  implémenté et mergé (PR `#9`, cf. `25:13`). `existing_functions` listait bien `process_frame` dans les
  faits transmis au modèle, mais rien ne bloque une proposition qui redécrit une fonction déjà correcte :
  5 missions consécutives (`19:24` à `20:22`) ont échoué en `author_oracle` (« no case survived
  cross-generation agreement » — cohérent, il n'y a pas de vrai changement de comportement à spécifier), puis
  la 6ᵉ (`1c13d7`, `20:42`) a produit un cas d'oracle faux (`process_frame(*((0,0,0),(1,0,0),0.5))` attendu
  `(0,0,0)`, alors que la sémantique existante de `smooth_levels` donne `(0.5,0,0)` — implémentation
  correcte, oracle généré faux) avant d'être interrompue en plein `implement`.
- **Le vrai bug** : rien ne plafonne les tentatives d'un `micro_rush_id` qui échoue en boucle d'un réveil à
  l'autre — `run_experiment.py` ne sautait que sur un `micro_rush_id` déjà *complété* (`*-completed.json`),
  jamais sur un `micro_rush_id` qui échoue systématiquement. Sans intervention manuelle, le LaunchAgent
  aurait retenté `frame-pipeline-v2` toutes les 15 min indéfiniment.
- **Corrigé à la racine** : nouveau fichier d'état `{experiment_id}-failures.json` (même mécanique atomique
  que `*-completed.json`) dans `run_experiment.py` — un `micro_rush_id` qui échoue (`status != "completed"`)
  incrémente son compteur ; à `MAX_CONSECUTIVE_FAILURES` (3, aligné sur le `max_repairs` déjà utilisé pour
  `author_oracle`) consécutifs, les réveils suivants sont auto-skip jusqu'à ce qu'un humain change
  `micro_rush_id` ou qu'une mission réussisse (le compteur est alors effacé).
- **Prochain micro-rush choisi** (`.pithos.json` mis à jour, `micro_rush_id: compute-magnitudes`) :
  `compute_magnitudes(samples)`, transformée de Fourier discrète pure (bibliothèque standard uniquement) du
  signal brut vers les magnitudes consommées par `split_bands` — le seul candidat qui reste dans le moule
  « fonction pure sans dépendance » avant de buter sur les arbitrages humains différés de `PROJECT.md`
  (capture audio réelle, fenêtre, thèmes). Documenté dans `PROJECT.md` (nouvelle section « Troisième
  micro-rush ») avec les mêmes critères d'acceptation hand-verifiable que les rushes précédents.
- **211 tests** (209 + 2 nouveaux dans `test_run_experiment.py` : plafond de tentatives atteint → skip ;
  un succès efface un historique d'échecs antérieur).

## 26:19 — DFT fusionnée, oracles et propositions resserrés

- Trois missions `compute-magnitudes` ont été conservées en échec. La première a généré un oracle visant
  `split_bands`; la troisième a imposé deux résultats DFT faux, dont `compute_magnitudes([]) == [0.0]`.
  Le plafond de trois échecs a ensuite arrêté correctement les réveils.
- La DFT produite par Ling a été conservée puis simplifiée sans modifier les quatre primitives existantes.
  Un oracle manuel couvre la liste vide, le silence et un signal DC constant, puis relance le test projet.
- Mission réelle `run-20260826T171933Z-d0ccab` : preflight PASS, aucune inference, aucune réparation, rapport
  publié, PR `#10` créée puis fusionnée automatiquement dans `main`.
- La proposition suivante a redemandé exactement `compute_magnitudes` sous l'identifiant
  `compute-magnitudes-v3`. Le harnais exige désormais un `target_function` existant pour tout module déjà
  présent, contraint l'oracle à cette fonction et rejette une description identique au rush courant.
- `.pithos.json` est replacé sur le rush complété `compute-magnitudes-v2` avec son oracle manuel : un lancement
  accidentel reste donc un skip idempotent. Le LaunchAgent de l'expérience n'est pas rechargé avant le choix
  du prochain axe produit.
- Validation globale : **214 tests**, build Vite, TypeScript des extensions, deux configurations Compose,
  oracle DFT et contrôle `git diff --check` passent.

## 26:20 — Autonomie réaffirmée et visualiseur utilisable

- L'utilisateur confirme qu'il ne doit jamais choisir le prochain axe ni intervenir dans le code. Cette règle
  est ajoutée au projet canonique et au contrat de l'expérience.
- Décision autonome : Web Audio + Canvas 2D, servi uniquement sur `127.0.0.1`, sans dépendance npm ni service
  externe. Ce choix couvre en un incrément capture locale, FFT temps réel, plein écran et thèmes.
- Le prototype fournit une entrée par défaut, un sélecteur de périphérique, trois palettes et un lanceur macOS
  double-cliquable. Le pipeline numérique est séparé du DOM et couvert par Node.
- Preuves : 3 tests Node, 2 tests Python, tests historiques, oracle DFT, smoke HTTP localhost, syntaxe JS/shell.
  La capture Firefox headless est bloquée par l'instance Firefox utilisateur déjà ouverte ; elle n'a pas été
  interrompue. L'autorisation microphone reste nécessaire au premier usage, comme l'impose macOS/navigateur.

## 27:09 — Handoff autonome persistant

- **Rupture constatée** : après une proposition `propose_next_rush` invalide, la mission réussie était
  finalisée avec l'ancien `.pithos.json`; son marqueur de complétion transformait ensuite tous les réveils en
  `micro-rush already completed`. Le runner ne possédait aucun chemin pour reprendre seulement la décision.
- **Correction** : lorsqu'un marqueur correspond encore au rush configuré et qu'un `seed` est présent, le
  runner appelle désormais `NextRushAuthor`, recharge la configuration écrite atomiquement puis lance le rush
  choisi dans le même réveil. Il ne relance jamais le rush déjà validé.
- **Échecs persistants** : le plafond de trois missions ne demande plus d'intervention humaine en mode
  autonome; il déclenche le même handoff. Le mode sans `seed` conserve l'arrêt prudent existant.
- **Résilience** : trois générations bornées absorbent une sortie Ollama invalide. Si elles échouent toutes,
  le LaunchAgent reprendra la planification au réveil suivant. Les sources produit Python, leurs fonctions,
  les cibles courantes et la roadmap bornée alimentent la proposition même quand le dernier diff est vide.
- **Preuve ciblée** : 25 tests couvrent notamment succès complété → nouveau rush lancé, échec de handoff →
  nouvelle tentative au réveil suivant, plafond d'échec → replanification et contexte produit hors diff.
