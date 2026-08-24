# Quick catch — Visualiseur audio VJing

_État vérifié le 24/08/2026 à 18:20 CEST._

## État

`src/audio_visualizer.py` expose `split_bands(magnitudes) -> tuple[float, float, float]`.
Le retour contient les moyennes scalaires des tranches bass, mid et treble.

Le prochain micro-rush `band-smoothing` doit ajouter `smooth_levels(previous, current, alpha)` dans le même
module. Son oracle externe est volontairement rouge avant le premier réveil autonome.

## Vérification

```bash
python tests/test_audio_visualizer.py
python ../../harness/fixtures/visualizer_acceptance.py
python ../../harness/fixtures/visualizer_smoothing_acceptance.py
```

Les deux commandes utilisent uniquement la bibliothèque standard.
