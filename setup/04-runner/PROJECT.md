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

- [ ] Deux lancements concurrents n'exécutent qu'un seul Pi.
- [ ] Un verrou orphelin est diagnostiqué puis récupéré sans tuer un processus non lié.
- [ ] Le timeout interrompt proprement tout l'arbre de processus.
- [ ] L'état `paused` survit aux réveils périodiques.
- [ ] Une commande locale explicite permet la reprise.
- [ ] Tous les chemins et états du run sont rapportés.

## Dépendances

- `00-contracts`.
- `03-continuity`.
