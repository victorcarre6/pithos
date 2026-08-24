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
- [DONE] Campagne — PR `#4` (band-smoothing), `#5` (horodatage `started`) et `#6` (récap Telegram humain)
  fusionnées dans `main`.
- [TODO] Campagne — choisir le prochain micro-rush pour `visualizer-dry-run` et changer `micro_rush_id` dans
  `.pithos.json` pour le libérer ; sans ce changement, chaque réveil du runner reste un skip idempotent.
