# Runner autonome

## But

Exécuter Pi à intervalle fixe dans une nouvelle session, sans chevauchement, avec une limite dure d'une heure et
un arrêt persistant après détection de boucle.

## Livrables

- Runner idempotent.
- Verrou avec PID, timestamps et récupération d'un verrou orphelin.
- Répertoire de run et capture stdout/stderr/session/événements.
- Heartbeat observable.
- Timeout dur de 60 minutes.
- État `paused` persistant après loop-guard.
- Commandes locales explicites de status, démarrage, pause et reprise.
- Configuration `launchd` à intervalle réglable, trois heures par défaut.

## Contraintes

- Une seule instance active.
- Chaque lancement crée une nouvelle session Pi.
- Aucun redémarrage automatique après un arrêt de boucle.
- La terminaison d'un enfant ne doit pas laisser un faux verrou actif.
- Le runner ne décide ni du micro-rush ni du contenu du projet.

## Critères de succès

- [x] Deux lancements concurrents n'exécutent qu'un seul Pi.
- [x] Un verrou orphelin est diagnostiqué puis récupéré sans tuer un processus non lié.
- [x] Le timeout interrompt proprement tout l'arbre de processus.
- [x] L'état `paused` survit aux réveils périodiques.
- [x] Une commande locale explicite permet la reprise.
- [x] Tous les chemins et états du run sont rapportés.

## Validation réalisée

- Processus factices : succès avec rapport, timeout avec descendant, boucle de tools et refus après pause.
- Verrou : propriétaire vivant refusé, PID mort récupéré sans signal.
- Heartbeat : événement append-only émis pendant une exécution longue.
- Contrats : `run.json` et `events.jsonl` validés dans le chemin nominal.
- Plist : `plutil -lint` réussi ; installation volontairement non effectuée.

## Dépendances

- `00-contracts`.
- `03-continuity`.
