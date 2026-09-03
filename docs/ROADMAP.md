# Roadmap

- [DONE] 00 — contrats persistants.
- [DONE] 01a — qualifier la première vague de cinq modèles Ollama et conserver les résultats négatifs.
- [DONE] 01b — qualifier Ling sur smoke, protocol, Pi et agentic après mise à jour Ollama 0.32.15.
- [DONE] 01c — retenir Ling après context/endurance, avec contexte opérationnel 16k et garde-fous multi-tool.
- [DONE] 02 — valider les dix capacités Pi réelles avec Ling, dont skill et extension après redémarrage.
- [DONE] 03 — continuité atomique et reprise réelle entre deux sessions Pi indépendantes.
- [DONE] 04 — runner Docker, verrou, timeout, arrêt forcé et loop guard.
- [DONE] 05 — broker Git local, authentification GitHub réelle et push/PR produits par le dry-run agent.
- [DONE] 06 — snapshots, broker de promotion et extensions Pi rechargeables.
- [DONE] 07 — stockage SQLite reconstructible et ingestion egress Squid.
- [DONE] 08 — dashboard dockerisé, construit et vérifié sur la projection réelle des missions.
- [DONE] 09 — broker Telegram, probe réel et notifications statiques début/fin de run.
- [DONE] 09b — messages human-readable et récap sidekick généré localement autour de faits immuables.
- [DONE] 10 — live log compatible `tail -F`.
- [DONE] 11 — finaliser correctement les interruptions et requalifier Ling sur un dry-run borné.
- [DONE] 12 — orchestration Ling, preflight, rapport, Telegram, push et PR validés en conditions réelles.
- [DONE] Activation — LaunchAgents installés, premier wake Ling terminé et second wake ignoré idempotemment.
- [DONE] Campagne — PR `#4` (band-smoothing), `#5` (horodatage `started`), `#6` (récap Telegram humain),
  `#8` (level-clamping) et `#9` (frame-pipeline) fusionnées dans `main`.
- [DONE] Garde-fou anti-boucle — un micro-rush qui échoue au même `micro_rush_id` sur
  `MAX_CONSECUTIVE_FAILURES` réveils consécutifs est désormais auto-skip jusqu'à intervention humaine
  (`run_experiment.py`), au lieu de retenter indéfiniment ; déclenché en pratique par la proposition
  redondante `frame-pipeline-v2` (redemandait `process_frame`, déjà mergé en `#9`).
- [DONE] Campagne — `compute_magnitudes` (DFT pure) validé sans inference par un oracle manuel, puis fusionné
  dans `main` via la PR `#10`.
- [DONE] Garde-fou de proposition — une tâche sur un module existant doit déclarer une fonction cible réelle,
  l'oracle est contraint à cette fonction et une description identique au rush courant est rejetée.
- [DONE] Produit — prototype web local avec capture audio sélectionnable, FFT temps réel, Canvas plein écran,
  trois thèmes cyberpunk et lanceur macOS sans dépendance npm.
- [DONE] Boucle fermée — un rush autonome terminé ou plafonné déclenche lui-même une proposition bornée du
  suivant ; une génération invalide est retentée sans demander à l'utilisateur de choisir ou d'éditer le code.
- [DONE] Runtime borné — le démarrage Compose ne peut plus retenir indéfiniment le verrou de campagne lorsque
  Docker Desktop ne répond pas.
- [DONE] Reprise CPU-safe — campagne active sur le runtime host existant, sans VM Docker, avec réveil nominal
  rétabli à 10 800 secondes.
- [DONE] Réinstallation idempotente — un LaunchAgent désactivé est réactivé avant son `bootstrap`.
- [DONE] Validation transactionnelle — un oracle auto-généré vert doit aussi préserver la suite produit, et
  toute mission non terminée restaure atomiquement ses seuls fichiers cibles.
- [DONE] Oracle signature-aware — le nombre d'arguments positionnels est validé avant d'exécuter un cas
  généré, et une fonction ayant déjà échoué en boucle est exclue de la proposition suivante.
- [DONE] Projection assainie — les runs laissés `running` par une interruption sont réconciliés en
  `interrupted`; le collecteur LaunchAgent n'écrit plus un inventaire complet toutes les cinq secondes.
- [DONE] Capacité en campagne — le run `run-20260903T152634Z-6ec0c3` crée, archive, active puis réutilise
  le skill `pithos-campaign-proof` dans deux sessions Pi neuves.
- [DONE] Terminaison autonome — une roadmap entièrement terminée produit une proposition d'arrêt Telegram
  idempotente, liée au hash de la roadmap (`run-20260903T152705Z-c7f1da`).
- [TODO] Campagne — observer une session audio interactive réelle lorsque l'autorisation navigateur et un
  périphérique sont disponibles ; aucune décision ni modification de code utilisateur n'est requise.
