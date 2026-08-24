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
