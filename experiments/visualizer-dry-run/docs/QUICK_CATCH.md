# Quick catch — Visualiseur audio VJing

_État vérifié le 24/08/2026 à 14:47 CEST._

## État

`src/audio_visualizer.py` expose `split_bands(magnitudes) -> tuple[float, float, float]`.
Le retour contient les moyennes scalaires des tranches bass, mid et treble.

## Vérification

```bash
python tests/test_audio_visualizer.py
python ../../harness/fixtures/visualizer_acceptance.py
```

Les deux commandes utilisent uniquement la bibliothèque standard.
