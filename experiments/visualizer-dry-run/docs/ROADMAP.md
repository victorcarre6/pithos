# Roadmap — Visualiseur audio VJing

- [DONE] Fonction pure `split_bands` retournant exactement trois niveaux scalaires.
- [DONE] Tests déterministes sans dépendance externe.
- [DONE] Rapport de continuité produit par le harnais après validation.
- [DONE] Lissage temporel pur des trois niveaux avec `smooth_levels` (PR `#4`).
- [DONE] Composition pure `process_frame` = `split_bands` → `smooth_levels` → `clamp_levels` (PR `#9`).
- [DONE] Magnitudes DFT pures depuis un signal réel avec `compute_magnitudes` (PR `#10`).
- [DONE] Capture d'une source audio locale via Web Audio, avec entrée par défaut et changement à chaud.
- [DONE] FFT temps réel via `AnalyserNode`, normalisation et lissage testés hors navigateur.
- [DONE] Canvas plein écran et trois thèmes cyberpunk (`neon`, `acid`, `ember`).
- [DONE] Lanceur macOS par double-clic, serveur borné à `127.0.0.1` et smoke HTTP réel.
