# Setup minimal de Pithos

## Objectif

Préparer l'environnement pour qu'un agent d'infrastructure déjà qualifié réalise les micro-projets de setup.
Pi ne construit ni le dashboard, ni Telegram, ni son propre runner initial : ces composants doivent être
validés avant que Pi devienne le sujet de l'expérience autonome.

## État vérifié

- macOS sur Mac mini M2, 16 Go de mémoire unifiée ;
- Node.js `26.7.0` ;
- Pi `0.84.2` installé dans `~/.npm-global/bin/pi` ;
- Docker CLI disponible, mais daemon actuellement arrêté ;
- Ollama `0.32.13` actif avec les trois modèles locaux attendus ;
- extensions et skill Pithos dédiés sous `ground_truth/.pi/`, chargés par Pi RPC ;
- QEMU/Gondolin absent et non requis pour la baseline Docker.

## Arborescence à préparer

```text
~/code/pithos/
├── PROJECT.md
├── ground_truth/
├── setup/
├── experiments/
├── journals/harness/
└── draft/SETUP.md

~/logs/pithos/
├── live.log
├── latest.md
└── runs/
```

Ne pas recopier `~/code/tempo` dans Pithos. Ce dépôt sert uniquement de retour d'expérience et sera supprimé
par l'utilisateur.

## Bootstrap humain minimal

### 1. Préparer les emplacements

Créer l'arborescence ci-dessus. Le script de bootstrap à produire ensuite devra être idempotent et refuser
d'écraser une constitution ou un rapport existant.

À chaque run, `ground_truth/` est disponible comme référence externe en lecture seule. Pi reçoit uniquement
la dernière version active de ses instructions ; la constitution n'est pas ajoutée à son contexte.

### 2. Préparer le serveur d'inférence

La configuration du modèle reste sous contrôle humain et hors du workspace de l'agent.

Le premier micro-projet doit mesurer `unsloth/Qwen3.8-27B-GGUF` sur la machine :

- quantification et taille réellement chargées ;
- mémoire, swap et stabilité ;
- débit avec un seuil minimal de 1 token/s ;
- contexte maximal stable, déterminé par mesure ;
- support réel du developer role et des tool calls via l'API exposée à Pi.

`unsloth/Qwen3.6-35B-A3B-GGUF` et Colibri constituent une piste séparée. Colibri annonce environ 20 Go de
poids int4 et 24 Go de RAM en pleine résidence pour ce modèle ; ne pas supposer sa compatibilité avec 16 Go.

### 3. Créer le dépôt distant de l'expérience

L'utilisateur crée un dépôt GitHub privé vide pour chaque expérience. L'agent ne crée pas les dépôts, mais
peut ensuite créer des branches, pousser, ouvrir des pull requests et les fusionner.

Ne placer aucun token GitHub ou Telegram dans le dépôt, les rapports ou la configuration lisible par Pi. Les
opérations distantes devront passer par un tool ou un service local brokerisé.

### 4. Micro-projets d'infrastructure

Les projets `00` à `10` disposent chacun d'un `PROJECT.md` autonome et de leur implémentation. Leur état
canonique est suivi dans `docs/ROADMAP.md` et les observations dans `docs/ELN.md`.

La baseline modèle reste le seul prérequis non conforme : Pi ne termine pas une réponse textuelle en dix
minutes dans la configuration Ollama mesurée, même après correction de son timeout HTTP interne.

### 5. Lancer Pi en mode supervisé

Avant toute planification périodique, exécuter les probes dans des sessions neuves avec :

- approbation explicite des ressources locales du projet ;
- répertoire de configuration Pi dédié à Pithos ;
- répertoire de sessions dédié ;
- sortie JSON ou RPC pour observer les événements ;
- tools limités au scénario courant ;
- timeout externe d'une heure ;
- stdout et stderr redirigés vers le dossier du run.

Ne pas utiliser l'exit code seul comme critère de succès. Le prototype `tempo` a déjà retourné `0` après avoir
imprimé un appel `read` sous forme de JSON sans l'exécuter.

### 6. Valider le capability probe

Le probe doit réussir séparément :

1. réponse textuelle ;
2. lecture ;
3. écriture ;
4. édition ciblée ;
5. commande shell ;
6. test automatisé ;
7. chaîne multi-tools ;
8. rapport `Context / Work / Next items` ;
9. création puis réutilisation d'un skill après redémarrage ;
10. création puis chargement d'une extension dans un nouveau processus.

Classer chaque cas avec `process_success`, `protocol_success`, `task_success` et `report_success`.

### 7. Autoriser l'automatisation progressivement

Après validation des probes, faire réaliser successivement par l'agent d'infrastructure :

1. le contrat JSONL et le rapport de continuité ;
2. le runner avec verrou, heartbeat et timeout ;
3. la gestion des branches et pull requests ;
4. l'archivage des mutations du harness ;
5. le collecteur SQLite ;
6. le dashboard ;
7. le broker Telegram ;
8. le producteur de `~/logs/pithos/live.log` ;
9. le bootstrap de la campagne du visualiseur audio.

Chaque composant doit être testé manuellement avant de débloquer le suivant. Pi n'est lancé en autonomie
qu'après cette validation.

## Contrat de run minimal

Chaque run possède :

```text
~/logs/pithos/runs/<run_id>/
├── events.jsonl
├── report.md
├── stdout.jsonl
├── stderr.log
└── sessions/
```

Le runner publie atomiquement le rapport achevé vers `~/logs/pithos/latest.md` et écrit des lignes flushées
dans `~/logs/pithos/live.log`.

## Conditions avant le premier réveil automatique

- [ ] modèle chargé et débit mesuré ;
- [ ] tool calls exécutés correctement ;
- [ ] rapport de continuité validé ;
- [x] verrou et récupération d'un PID mort testés ;
- [x] timeout et arbre de processus testés avec une limite réduite déterministe ;
- [x] arrêt sur boucle testé ;
- [x] reprise automatique désactivée après loop-guard ;
- [x] credentials absents du workspace agent et des fixtures ;
- [ ] première pull request créée lors d'un run supervisé ;
- [x] `tail -F ~/logs/pithos/live.log` testé à travers une rotation.

## Sources techniques

- [Pi](https://pi.dev/)
- [Pi sur GitHub](https://github.com/earendil-works/pi)
- [Qwen3.8-27B GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
- [Qwen3.6-35B-A3B GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF)
- [Colibri](https://github.com/JustVugg/colibri)
