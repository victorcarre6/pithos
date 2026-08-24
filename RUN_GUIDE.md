# Guide de relance — lancer le prochain micro-rush

Ce guide reprend, étape par étape, ce qui reste **manuel côté humain** pour relancer un cycle d'autonomie sur
`experiments/visualizer-dry-run/` une fois le rush courant fusionné. Le harnais lui-même n'a besoin d'aucune
modification de code pour un nouveau micro-rush ordinaire.

Depuis cette version, **l'oracle n'est plus écrit à la main** : le harnais le fait générer par le modèle local
lui-même, sous contrainte, puis le vérifie avant de s'en servir. Voir [Oracle auto-généré](#oracle-auto-généré-comment-ça-marche)
plus bas pour le fonctionnement exact et ses limites.

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
  "runtime": "docker",
  "model": "pithos/ling-3.0-tiny:8b-16k",
  "target_files": ["src/audio_visualizer.py"],
  "pi_config": "/Users/victorcarre/code/pithos/harness/config/pi-docker",
  "ground_truth": "/Users/victorcarre/code/pithos/harness/ground_truth"
}
```

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

## 5. Déclencher (ou attendre) le prochain réveil

```bash
launchctl kickstart -k gui/$(id -u)/dev.pithos.runner.visualizer-dry-run   # forcer maintenant
# sinon le réveil normal arrive automatiquement toutes les 10 800 s
```

## 6. Relire l'oracle généré avant de faire confiance à un `completed`

L'oracle produit est archivé hors Git dans `~/logs/pithos/missions/<mission_id>/oracle.py`. Le lire fait partie
du contrôle qualité tant que cette capacité est jeune :

```bash
cat ~/logs/pithos/missions/<mission_id>/oracle.py
```

Un run `failed` avec `author_oracle failed: ...` dans `state.json` signifie que le harnais n'a pas réussi à
générer un contrat rouge et fiable — c'est une donnée à conserver, pas une panne à masquer. La cause la plus
fréquente attendue : la fonction ciblée n'a pas une signature purement numérique (voir limites ci-dessous).

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
