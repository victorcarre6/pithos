# Quick catch — Visualiseur audio VJing

_État vérifié le 03/09/2026 à 17:00 CEST._

## État

Le produit utilisable est dans `web/` : capture Web Audio, FFT temps réel, trois bandes lissées, Canvas 2D,
trois thèmes cyberpunk et plein écran. `start.command` le lance par double-clic sur un serveur localhost.

La PR `#10` est fusionnée et la roadmap produit ne contient plus aucun travail automatisable. Le run
`run-20260903T152634Z-6ec0c3` a créé, promu puis réutilisé le skill `pithos-campaign-proof` dans deux
sessions Pi neuves. Après passage de `tests/validate_product.py`, le run
`run-20260903T152705Z-c7f1da` a envoyé une proposition d'arrêt Telegram. Les réveils suivants sont des
no-op idempotents tant que le hash de la roadmap ne change pas. Le marqueur courant
`run-20260903T154816Z-8db897` porte le hash documentaire final; la notification correspondante a été
dédupliquée.

## Vérification

```bash
python tests/validate_product.py
```

Le premier lancement interactif requiert uniquement l'autorisation audio imposée par le navigateur. Ce
contrôle matériel reste différé, car aucun navigateur interactif n'était disponible lors de la validation.

Le runner de campagne utilise désormais le runtime **host** et le profil `harness/config/pi`; Docker Desktop
n'est pas requis. Le réveil nominal est toutes les trois heures et chaque phase reste bornée à cinq minutes.
