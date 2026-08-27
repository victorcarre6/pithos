# Quick catch — Visualiseur audio VJing

_État vérifié le 27/08/2026 à 09:00 CEST._

## État

Le produit utilisable est dans `web/` : capture Web Audio, FFT temps réel, trois bandes lissées, Canvas 2D,
trois thèmes cyberpunk et plein écran. `start.command` le lance par double-clic sur un serveur localhost.

Le micro-rush `compute-magnitudes-v2` a passé son oracle externe en preflight sans inference ni réparation.
La PR `#10` est fusionnée. Quand le runner retrouve cet identifiant complété, **Pithos propose lui-même le
suivant, recharge `.pithos.json` et le lance dans le même réveil**. Une proposition invalide est retentée trois
fois, puis lors d'un réveil ultérieur ; un rush plafonné après trois échecs est lui aussi remplacé par le
système. Aucun choix de chantier ni changement de code n'est attendu de l'utilisateur.

## Vérification

```bash
python tests/validate_product.py
```

Le premier lancement interactif requiert uniquement l'autorisation audio imposée par le navigateur.
