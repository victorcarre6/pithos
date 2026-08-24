# Quick catch (archivé)

> Instantané figé du socle avant la campagne du visualiseur audio (chantiers `00` à `08`, PR GitHub `#1`
> seule). Pour l'état courant du projet, voir [`../QUICK_CATCH.md`](../QUICK_CATCH.md) à la racine du dépôt.

## État

Les projets préliminaires **00 à 12** et leur intégration transversale sont implémentés. Ling est la baseline
locale ; le contrôleur multi-session a terminé deux missions visualiseur consécutives sous oracle externe.
La suite compte **132 tests**. Le runtime agent est Docker par défaut ; son build réel attend un daemon Docker
actif. Rapport, Telegram, push et réutilisation de la PR GitHub `#1` sont validés en conditions réelles.

## Commandes

```bash
cd harness
pytest -q -p no:cacheprovider
python scripts/bootstrap.py --check
pithos-benchmark list
pithos-benchmark <model_name>
pithos-events --logs-root ~/logs/pithos once
pithos-runner status --logs-root ~/logs/pithos
npm --prefix dashboard/web run build
docker compose -f runtime/docker-compose.yml config
docker compose -f dashboard/docker-compose.yml config
```

## Suite

1. Examiner puis fusionner explicitement la PR GitHub `#1`.
2. Démarrer Docker, construire le runtime et lancer un smoke test agent + proxy.
3. Démarrer Docker, construire le runtime et lancer un smoke test agent + proxy.
