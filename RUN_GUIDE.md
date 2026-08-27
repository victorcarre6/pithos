# Guide d'exploitation — campagne autonome

Avec un `seed` non vide, **aucune relance ni sélection de micro-rush n'est manuelle**. Le LaunchAgent réveille
`experiments/visualizer-dry-run/`, Pithos choisit le prochain contrat borné, le valide, l'exécute et fusionne
la PR. Les étapes manuelles ci-dessous ne décrivent que le mode supervisé sans `seed` et le diagnostic.

Depuis cette version, **l'oracle n'est plus écrit à la main** : le harnais le fait générer par le modèle local
lui-même, sous contrainte, puis le vérifie avant de s'en servir. Voir [Oracle auto-généré](#oracle-auto-généré-comment-ça-marche)
plus bas pour le fonctionnement exact et ses limites.

Et depuis cette version-ci, **le prochain micro-rush lui-même peut être proposé par le harnais, et sa PR
fusionnée automatiquement** dès qu'un `seed` (objectif long terme) est présent dans `.pithos.json`. Voir
[Rushes auto-proposés](#rushes-auto-proposés-seed) plus bas — si tu préfères continuer à choisir chaque
micro-rush toi-même et garder la main sur chaque merge, ignore simplement cette section et suis les étapes 1
à 7 comme avant : sans `seed`, rien ne change, y compris le merge qui reste entièrement manuel.

Et depuis cette version-ci également, **chaque mission commence par se scinder elle-même en micro-passes**
avant de toucher au code, quand l'oracle est auto-généré. Voir [Décomposition en micro-passes](#décomposition-en-micro-passes-plan_todo)
plus bas — l'idée, l'implémentation et pourquoi une seule PR/un seul récap Telegram couvrent toujours toute
la mission, même scindée en plusieurs étapes internes.

## 1. Définir le prochain micro-rush

Choisir un objectif **borné** pour `experiments/visualizer-dry-run/` : idéalement un seul fichier cible, une
tâche que Ling peut couvrir en quelques tool calls (le pattern qui a marché pour `band-smoothing`).

Le `title` et la `description` ne servent plus seulement à Telegram : ils sont maintenant aussi le **brief
envoyé au modèle pour générer l'oracle**. Une description précise, qui nomme le comportement numérique attendu
(valeurs, bornes, invariants), donne un contrat de test bien meilleur qu'une description vague.

## 2. Mettre à jour `.pithos.json`

Dans `experiments/visualizer-dry-run/.pithos.json`, changer ensemble :

- `micro_rush_id` (nouvel identifiant unique) ;
- `title` / `description` (courts, précis, human-readable — ils nourrissent Telegram **et** l'oracle) ;
- `target_files` (fichier(s) que le contexte doit projeter, et dans lesquels l'oracle doit chercher sa
  fonction cible).

`experiment_id` et `micro_rush_id` doivent tous les deux respecter `^[a-z0-9][a-z0-9-]{0,63}$` (minuscules,
chiffres, tirets — jamais d'underscore). Le lanceur refuse maintenant de démarrer une mission dont l'un des
deux ne respecte pas ce format, avant même d'ouvrir Docker — une faute de frappe ici coûtait auparavant une
session Pi entière et une PR vide (`PR #7`) avant d'échouer à `finalize`.

**Ne plus renseigner `validation_command`** pour laisser le harnais générer l'oracle automatiquement. Si ce
champ est absent, la mission démarre par une phase `author_oracle` avant `preflight`. Le garder (comme pour
`band-smoothing`) reste possible et prioritaire — c'est l'échappatoire manuelle pour un contrat trop complexe
pour l'auto-génération (voir limites plus bas).

```json
{
  "schema_version": 1,
  "experiment_id": "visualizer-dry-run",
  "title": "...",
  "description": "...",
  "micro_rush_id": "...",
  "seed": "Construire un visualiseur audio destiné au VJing.",
  "runtime": "docker",
  "model": "pithos/ling-3.0-tiny:8b-16k",
  "target_files": ["src/audio_visualizer.py"],
  "pi_config": "/Users/victorcarre/code/pithos/harness/config/pi-docker",
  "ground_truth": "/Users/victorcarre/code/pithos/harness/ground_truth"
}
```

`seed` est optionnel : sans lui, tout se comporte exactement comme avant (tu choisis chaque prochain
micro-rush toi-même, étape par étape). Avec lui, voir [Rushes auto-proposés](#rushes-auto-proposés-seed).

## 3. Committer et pousser directement sur `main`

```bash
git add experiments/visualizer-dry-run/.pithos.json
git commit -m "..."
git push origin main
```

C'est important : le broker Git crée toujours la branche du rush depuis `origin/main` (`git switch -c <branch>
origin/main`). Si le nouveau `.pithos.json` n'est pas poussé, la prochaine branche partira encore de l'ancienne
config.

## 4. Ne rien toucher côté marqueurs/LaunchAgents

- Ne pas supprimer `~/logs/pithos/runtime/visualizer-dry-run-completed.json` à la main — un nouveau
  `micro_rush_id` suffit à le rendre obsolète automatiquement.
- Docker, Ollama et les deux LaunchAgents restent actifs tels quels.
- Après avoir mergé une PR de rush (`agent/rush-*`) toi-même (pas de `seed`, donc pas d'auto-merge), repasser
  sur `main` en local (`git switch main && git pull`) avant le prochain réveil : `finalize` laisse le dépôt
  sur la branche du rush, et le prochain réveil lit `.pithos.json` sur la branche actuellement extraite, pas
  forcément sur `main`. Avec `seed` (auto-merge activé), `gh pr merge --delete-branch` s'exécute depuis la
  branche du rush et bascule normalement le dépôt local sur `main` tout seul — vérifie quand même avec
  `git branch --show-current` de temps en temps plutôt que de tenir ça pour acquis.

## 5. Déclencher (ou attendre) le prochain réveil

```bash
launchctl kickstart -k gui/$(id -u)/dev.pithos.runner.visualizer-dry-run   # forcer maintenant
# sinon le réveil normal arrive automatiquement toutes les 10 800 s
```

## 6. Relire l'oracle généré avant de faire confiance à un `completed`

L'oracle produit est archivé hors Git dans `~/logs/pithos/missions/<mission_id>/`. Si la mission n'a pas été
scindée en micro-passes (pas de plan, ou `plan_todo` retombé sur l'implicite), c'est un fichier unique
`oracle.py`. Si elle l'a été, chaque étape a le sien, numéroté dans l'ordre : `oracle-01.py`, `oracle-02.py`,
etc. — le lire fait partie du contrôle qualité tant que cette capacité est jeune :

```bash
cat ~/logs/pithos/missions/<mission_id>/oracle*.py
```

`state.json` porte aussi `todo`, la liste des étapes retenues avec leur `status` (`done`/`skipped`) — utile
pour voir d'un coup d'œil laquelle a réellement fait avancer le rush et laquelle a été sautée.

Un run `failed` avec `author_oracle failed: ...` dans `state.json` signifie que le harnais n'a pas réussi à
générer un contrat rouge et fiable **pour aucune étape** — c'est une donnée à conserver, pas une panne à
masquer. La cause la plus fréquente attendue : la fonction ciblée n'a pas une signature purement numérique
(voir limites ci-dessous), ou le petit modèle se trompe simplement dans son arithmétique de façon reproductible
sur les deux générations (le double-vote ne protège que du bruit aléatoire, pas d'une erreur systématique).

Avec `seed` (auto-merge, voir plus bas), cette relecture arrive nécessairement **après coup** : le code est
déjà sur `main` au moment où tu la fais. C'est un vrai changement de posture par rapport au workflow manuel —
tu deviens auditeur plutôt que portier. `git revert` sur `main` reste la voie de repli normale si une
relecture après-coup découvre un problème.

## 7. Suivre le protocole quotidien déjà documenté

Le check-list reste dans `QUICK_CATCH.md` § *Protocole de collecte* : état des deux LaunchAgents, espace
disque, `pithos.db`, quarantaine, dernière mission, PR ouverte, notifications Telegram début/fin/récap.

---

## Oracle auto-généré — comment ça marche

Le modèle **n'écrit jamais le code de l'oracle**. Il choisit seulement, parmi les fichiers déjà approuvés par
l'humain (`target_files`) :

- une fonction déjà définie dans un de ces fichiers ;
- 1 à 4 cas d'entrée/sortie **numériques** (nombres ou petites listes de nombres).

Le harnais rend ensuite lui-même le script Python exécuté (`~/logs/pithos/missions/<mission_id>/oracle.py`),
avec les garde-fous suivants :

1. **Deux générations indépendantes** (températures différentes) doivent tomber d'accord sur la fonction ciblée
   et sur chaque cas conservé ; tout cas où elles divergent est écarté.
2. Le nom de fonction est vérifié par regex (`def <nom>(`) dans le fichier cible déclaré — impossible de faire
   exécuter autre chose qu'une fonction déjà présente dans les fichiers approuvés.
3. L'oracle rendu doit **échouer** sur le code actuel (non corrigé) avant d'être accepté ; un oracle qui passe
   déjà ne prouve rien et déclenche une nouvelle tentative (3 tentatives maximum).
4. Aucun code du modèle n'est jamais exécuté : seuls une chaîne (nom de fonction) et des littéraux numériques
   traversent la frontière modèle → exécution.

### Limites connues

- **Uniquement des contrats numériques.** Une fonction qui lève une exception, retourne une chaîne, un objet
  ou dépend d'un état externe n'est pas couverte ; renseigner `validation_command` à la main dans ce cas.
- **L'arithmétique du modèle n'est pas fiable.** Testé en conditions réelles sur `pithos/ling-3.0-tiny:8b-16k` :
  demander un oracle pour « normaliser `split_bands` pour que la somme des trois bandes vaille 1.0 » a produit
  un cas confirmé rouge, mais dont la valeur `expect` ne correspondait ni au comportement actuel ni à une
  normalisation correcte — un calcul simplement faux, reproduit de façon cohérente sur les deux générations. Le
  double-vote réduit le bruit aléatoire, il ne corrige pas une incompréhension systématique. D'où l'étape 6 :
  relire l'oracle généré avant de faire confiance à un run `completed` sur une tâche encore peu familière.
- **Un fichier cible qui n'existe pas encore n'a droit qu'à une vérification faible.** Si `target_files`
  contient un chemin absent du dépôt, l'oracle ne peut référencer aucune fonction existante ; il se contente
  de vérifier, après implémentation, que le fichier existe et s'importe sans erreur (`importlib.import_module`).
  C'est mécaniquement rouge avant (le fichier n'existe pas) et vert dès qu'un fichier syntaxiquement valide
  apparaît au bon endroit — ça ne dit rien sur la justesse du contenu. Un mélange fichiers existants/nouveaux
  combine les deux styles de vérification dans le même script.

## Décomposition en micro-passes (`plan_todo`)

Hypothèse de départ, posée par l'opérateur : un petit modèle local travaille mieux sur plusieurs passes
courtes, à contexte frais, que sur une seule session longue couvrant tout un micro-rush. Depuis cette
version, quand l'oracle est auto-généré (`validation_command` absent), chaque mission commence par une
nouvelle phase `plan_todo`, insérée avant `author_oracle`, qui tente de scinder la description du rush en
2 à 4 étapes atomiques avant de faire quoi que ce soit d'autre.

**Comment ça marche :**

1. Le modèle reçoit le titre, la description, les `target_files` du rush, et `existing_functions` : la liste
   des fonctions déjà définies dans ces fichiers (le même garde-fou que pour `propose_next_rush`). Il choisit,
   par étape, un titre, une description et une courte liste de chemins **pris dans `target_files`** — jamais
   un nouveau fichier, jamais une fonction qui n'existe pas encore. Si la tâche est déjà minimale, une seule
   étape identique à la tâche est une réponse valide.
2. Le harnais valide chaque étape avant de lui faire confiance : nombre borné (1 à 4), titre/description non
   vides et bornés, et chaque chemin de fichier appartient strictement à la liste déjà approuvée par l'humain
   dans `.pithos.json` — aucun chemin inventé n'est jamais accepté, quelle que soit sa forme.
3. **La décomposition est un confort, jamais une exigence.** Tout échec (modèle injoignable, JSON invalide,
   étape qui ne passe pas la validation) laisse simplement la mission repartir exactement comme avant cette
   version : une seule étape implicite couvrant tout le rush. Rien ne bloque, rien n'échoue à cause d'un plan
   raté — c'est journalisé dans `state.json` (`plan_todo failed: ...; proceeding with a single implicit item`)
   et la mission continue.
4. Chaque étape retenue traverse ensuite **l'intégralité du cycle existant** pour elle seule, à contexte
   frais : sa propre génération d'oracle (son propre fichier `oracle-NN.py`, voir étape 6 plus haut), son
   propre `preflight`/`implement`/`test`/`repair`. Une étape qui échoue (oracle non rouge-fiable, réparations
   épuisées) est marquée `skipped` dans `state.json` → `todo` et la mission passe à l'étape suivante — même
   philosophie *best-effort* qu'un `propose_next_rush` raté ou un auto-merge en échec : un incident partiel ne
   doit jamais jeter un travail déjà validé.
5. **Une seule PR, un seul récap Telegram pour toute la mission**, quel que soit le nombre d'étapes — c'est un
   choix délibéré, pas un oubli. Multiplier les PR par étape aurait démultiplié le risque de collision
   d'auto-merge déjà documenté plus bas (`Rushes auto-proposés`), sans bénéfice avéré : seule la façon dont le
   *travail* est scindé en interne change, pas la façon dont il est mergé ou rapporté. `finalize` s'exécute une
   fois, après la dernière étape, avec les fichiers changés de toutes les étapes réussies accumulés ; le récap
   Telegram ajoute une ligne factuelle `N/M étapes validées`.
6. La mission échoue globalement **seulement si aucune étape n'a réussi** — dès qu'une seule passe la
   validation, il y a quelque chose à finaliser.

Sans oracle auto-généré (`validation_command` renseigné à la main), cette phase n'existe pas : un contrat
écrit par un humain couvre le rush entier par construction, le scinder dans son dos casserait ce contrat.

### Limites connues

- **La décomposition ne corrige pas une erreur d'arithmétique systématique du modèle** (voir limite
  ci-dessus) — elle réduit seulement la surface de chaque contrat individuel, ce qui peut aider sans le
  garantir.
- **Chaque étape relance une session Pi/Docker fraîche**, avec son coût de démarrage propre (observé autour de
  quelques minutes selon la charge de la machine). Pour un rush déjà minimal, la décomposition n'apporte rien
  et coûte ce démarrage en plus — c'est pourquoi une seule étape identique au rush reste une réponse valide de
  `plan_todo`, pas un échec déguisé.
- **`plan_todo` est lui-même une proposition non vérifiée sémantiquement** : le harnais valide la forme
  (nombre, longueur, chemins autorisés), jamais que le découpage a du sens. Une mauvaise décomposition ne fait
  pas échouer la mission (repli sur l'étape unique en cas d'erreur dure), mais peut produire des étapes
  arbitrairement mal coupées sans le signaler autrement que dans `state.json` → `history`.

## Rushes auto-proposés (seed)

Avec un champ `seed` non vide dans `.pithos.json`, le harnais propose lui-même le prochain micro-rush à la
fin de chaque mission réussie, au lieu d'attendre que tu édites `.pithos.json` à la main (étapes 1-2
ci-dessus). C'est une nouvelle phase `propose_next_rush`, insérée juste avant `finalize`.

**Comment ça marche :**

1. Le modèle reçoit uniquement des faits assemblés par le harnais : le `seed`, le titre/description du rush
   qui vient de réussir, et les fichiers modifiés. Il choisit seulement un identifiant, un titre, une
   description et jusqu'à 3 chemins de fichiers relatifs — jamais de code.
2. Le harnais valide tout avant de faire confiance à quoi que ce soit : format de l'identifiant, qu'il diffère
   du micro-rush courant (sinon la prochaine relance se skiperait silencieusement pour toujours), longueur du
   titre/de la description, et que chaque chemin reste bien à l'intérieur du workspace (pas de `..`, pas de
   chemin absolu).
3. Si tout passe, le harnais réécrit `.pithos.json` avec le nouvel identifiant/titre/description/
   `target_files`, en recopiant `seed`, `experiment_id`, `runtime`, `model`, `pi_config`, `ground_truth`
   **tels quels** (jamais touchés par le modèle) et en supprimant `validation_command` (un rush auto-proposé
   repasse toujours par `author_oracle` au cycle suivant).
4. Ce nouveau `.pithos.json` est ensuite inclus dans le **même commit et la même PR** que le travail qui vient
   d'être validé.
5. Si la proposition de fin de mission échoue, le travail validé est quand même finalisé. Au réveil suivant,
   le runner reconnaît le rush complété et reprend uniquement le handoff : trois générations bornées sont
   tentées, sans rejouer le code déjà validé. Une proposition valide est chargée puis exécutée immédiatement ;
   sinon le prochain réveil retente automatiquement.
6. Après trois missions en échec sur le même identifiant, une campagne avec `seed` abandonne ce contrat et
   passe par le même handoff autonome. Sans `seed`, le comportement prudent historique reste un arrêt.

Sans `seed`, cette phase n'existe pas — comportement strictement identique à avant.

### Auto-merge

Avec ce même `seed`, la PR ouverte à `finalize` est **fusionnée automatiquement**, tout de suite après sa
création (ou réutilisation) — `gh pr merge --merge --delete-branch`, exactement la même commande que tu
lancerais toi-même. Concrètement, **la revue humaine passe d'avant-merge à après-merge** : rien n'attend ta
validation pour atteindre `main`, et la proposition du prochain micro-rush qui voyage dans cette même PR
(section précédente) s'active donc elle aussi sans étape de merge manuelle. C'est ce qui ferme réellement la
boucle : sans ça, un `seed` proposait le prochain rush mais chaque cycle restait bloqué en attendant un merge
humain, et deux réveils rapprochés sans merge entre les deux pouvaient même faire échouer le second à
`finalize` (conflit Git : la nouvelle branche du rush suivant part toujours d'`origin/main`, qui n'aurait pas
encore le travail du rush précédent).

Garde-fous, hérités tels quels de l'opération `pr_merge` du broker Git (`harness/src/pithos_git_broker/broker.py`),
inchangés par cette fonctionnalité :

- ne fusionne que la PR dont la branche tête/base correspond exactement à la politique du dépôt (`agent/rush-*`
  vers `main`) ;
- ne fusionne que si la PR est encore `OPEN` ;
- déclenché seulement **après** que la mission a déjà passé la validation externe (oracle rouge-avant/vert-après)
  — l'auto-merge n'ajoute aucun nouveau critère de confiance, il active juste automatiquement celui qui existe
  déjà.

Le merge est **best-effort** : s'il échoue (protection de branche, panne GitHub, etc.), la mission reste
`completed` — le travail déjà validé est en sécurité, commité et poussé — et la cause atterrit dans
`state.json` → `artifacts.merge_failed`. Rien n'est perdu, la PR attend juste un merge manuel comme avant.

Sans `seed`, aucun merge automatique n'a jamais lieu — comportement strictement identique à avant.
