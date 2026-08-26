# Roadmap — Visualiseur audio VJing

- [DONE] Fonction pure `split_bands` retournant exactement trois niveaux scalaires.
- [DONE] Tests déterministes sans dépendance externe.
- [DONE] Rapport de continuité produit par le harnais après validation.
- [DONE] Lissage temporel pur des trois niveaux avec `smooth_levels` (PR `#4`).
- [DONE] Composition pure `process_frame` = `split_bands` → `smooth_levels` → `clamp_levels` (PR `#9`).
- [TODO] Capture d'une source audio locale.
- [TODO] FFT temps réel.
- [TODO] Fenêtre plein écran et thèmes cyberpunk.
