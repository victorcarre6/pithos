# Visualiseur audio VJing — dry-run

## Vision

Construire un visualiseur audio local et léger pour le VJing. Il doit transformer le son joué sur le Mac en
visualisations cyberpunk réactives aux bandes de fréquences, sans service réseau ni GPU dédié.

## Utilisateur

Un DJ utilise l'application sur macOS, notamment sur un MacBook Intel 2018, pendant un mix. L'interface doit
rester minimale et ne pas perturber le logiciel audio.

## Périmètre produit

- Capture d'une source audio sélectionnée localement.
- Analyse fréquentielle temps réel.
- Visualisation plein écran avec fond transparent lorsque la plateforme le permet.
- Plusieurs thèmes cyberpunk sélectionnables.
- JavaScript ou Python, avec priorité au chemin le plus léger et testable.

## Hors périmètre initial

- Compte utilisateur, cloud, télémétrie ou accès réseau applicatif.
- Génération vidéo par modèle IA.
- Accélération nécessitant un GPU dédié.
- Support d'autres systèmes que macOS avant validation du prototype.

## Premier micro-rush supervisé

Implémenter uniquement le noyau déterministe qui transforme un tableau de magnitudes FFT déjà normalisées
entre 0 et 1 en trois niveaux scalaires `bass`, `mid` et `treble`, eux aussi compris entre 0 et 1.

Le tableau est découpé par position en trois tranches contiguës aussi équilibrées que possible, dans l'ordre
bass, mid, treble. Chaque niveau est la moyenne arithmétique de sa tranche. Le choix du langage et la forme
exacte du retour restent à l'agent, mais le retour contient exactement ces trois scalaires.

Le micro-rush doit :

1. choisir JavaScript ou Python sans ajouter de dépendance ;
2. exposer une fonction pure et documenter brièvement son contrat ;
3. couvrir silence, valeurs maximales et activation isolée de chaque bande par des tests déterministes ;
4. exécuter les tests réels ;
5. mettre à jour `docs/ELN.md`, `docs/ROADMAP.md` et `docs/QUICK_CATCH.md` ;
6. écrire le rapport de continuité valide dans `.pithos/report.md`.

## Contraintes

- Tout reste dans `experiments/visualizer-dry-run/`.
- Aucune dépendance ni accès réseau pour ce micro-rush.
- Une intention par ligne et aucune abstraction spéculative.
- Les valeurs invalides sont traitées seulement si les tests en définissent le contrat.
- Les credentials, sockets et logs hôte ne sont jamais copiés dans le workspace.

## Critères d'acceptation du micro-rush

- [ ] Une fonction pure produit exactement trois bandes normalisées.
- [ ] Les tests déterministes passent avec une commande documentée.
- [ ] Aucun fichier hors de l'expérience n'est modifié par Pi.
- [ ] Les documents de suivi reflètent les changements réellement vérifiés.
- [ ] `.pithos/report.md` est conforme au contrat Pithos.

## Commandes de vérification

La commande exacte dépend du langage choisi et doit être ajoutée ici ou dans `README.md`. Elle ne doit ni
télécharger de dépendance ni nécessiter une interface audio réelle.

## Arbitrages humains différés

- Source audio macOS exacte : loopback virtuel, interface physique ou capture applicative.
- Technologie de fenêtre transparente et mode plein écran.
- Direction visuelle finale des thèmes.
