# Quick catch — Visualiseur audio VJing

_État vérifié le 26/08/2026 à 20:11 CEST._

## État

Le produit utilisable est dans `web/` : capture Web Audio, FFT temps réel, trois bandes lissées, Canvas 2D,
trois thèmes cyberpunk et plein écran. `start.command` le lance par double-clic sur un serveur localhost.

Le micro-rush `compute-magnitudes-v2` a passé son oracle externe en preflight sans inference ni réparation.
La PR `#10` est fusionnée. La configuration locale conserve cet identifiant complété afin que tout réveil
automatique soit ignoré ; Codex pilote directement les incréments suivants sans demander de choix opérateur.

## Vérification

```bash
python tests/validate_product.py
```

Le premier lancement interactif requiert uniquement l'autorisation audio imposée par le navigateur.
