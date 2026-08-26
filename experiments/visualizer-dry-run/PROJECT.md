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

## Deuxième micro-rush autonome — lissage temporel

Ajouter une fonction pure `smooth_levels(previous, current, alpha)` qui interpole indépendamment les trois
niveaux scalaires. Les entrées sont déjà valides et `alpha` est compris entre `0.0` et `1.0`. Le micro-rush
préserve `split_bands`, n'ajoute aucune dépendance et ne modifie que `src/audio_visualizer.py`.

Critères d'acceptation :

- `alpha=0.0` restitue exactement les niveaux précédents ;
- `alpha=1.0` restitue exactement les niveaux courants ;
- une valeur intermédiaire applique l'interpolation aux trois bandes ;
- les tests du premier micro-rush restent verts.

## Troisième micro-rush — magnitudes depuis le signal brut

Ajouter une fonction pure `compute_magnitudes(samples)` qui calcule la transformée de Fourier discrète
d'un signal réel (`samples: list[float]`) et retourne la liste des magnitudes (module de chaque
coefficient complexe), une valeur par échantillon d'entrée. Aucune dépendance externe (bibliothèque
standard uniquement). Ne modifie ni `split_bands`, ni `smooth_levels`, ni `clamp_levels`, ni
`process_frame`.

Critères d'acceptation :

- une liste vide retourne une liste vide ;
- un signal constant (DC) concentre la magnitude sur le premier coefficient ;
- un signal nul retourne des magnitudes nulles ;
- les tests des micro-rushes précédents restent verts.

## Commandes de vérification

La commande exacte dépend du langage choisi et doit être ajoutée ici ou dans `README.md`. Elle ne doit ni
télécharger de dépendance ni nécessiter une interface audio réelle.

## Arbitrages humains différés

- [DONE] Source audio : entrée locale par défaut via Web Audio, sélectionnable sans configuration de build.
  Une interface loopback macOS apparaît comme une entrée ordinaire lorsqu'elle est installée.
- [DONE] Fenêtre : application web locale Canvas 2D, plein écran via l'API navigateur. La transparence native
  hors fenêtre n'est pas disponible dans ce runtime et reste hors du chemin minimal.
- [DONE] Direction visuelle : trois thèmes cyberpunk intégrés, sélectionnables à chaud.

## Politique d'autonomie

Les choix produit et techniques ordinaires appartiennent à l'agent. L'utilisateur ne doit ni sélectionner le
prochain chantier de développement, ni écrire ou corriger du code. Un blocage n'est remonté que s'il dépend
d'un credential, d'un matériel ou d'une autorisation sans substitut local sûr.
