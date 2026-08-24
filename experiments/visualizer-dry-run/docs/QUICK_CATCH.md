# Quick catch — Visualiseur audio VJing

_État vérifié le 24/08/2026 à 19:03 CEST._

## État

`src/audio_visualizer.py` expose `split_bands(magnitudes) -> tuple[float, float, float]`.
Le retour contient les moyennes scalaires des tranches bass, mid et treble.

Le micro-rush `band-smoothing` a ajouté `smooth_levels(previous, current, alpha)` après un timeout et deux
réparations bornées. L'oracle externe final passe et la PR `#4` est ouverte. Le marqueur hors Git empêche tout
nouveau run de ce rush jusqu'au changement de son identifiant.

## Vérification

```bash
python tests/test_audio_visualizer.py
python ../../harness/fixtures/visualizer_acceptance.py
python ../../harness/fixtures/visualizer_smoothing_acceptance.py
```

Les deux commandes utilisent uniquement la bibliothèque standard.
