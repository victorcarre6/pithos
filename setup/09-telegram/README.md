# Telegram broker

Le service hôte est prêt jusqu'à l'injection des deux secrets :

```bash
export TELEGRAM_BOT_TOKEN='...'
export TELEGRAM_USER_ID='...'
pithos-telegram probe
pithos-telegram serve --socket /private/tmp/pithos-telegram.sock
```

Pi reçoit uniquement le socket mode `0600`. Une requête sortante contient `request_id`, `run_id`, `kind` et
`text`; le destinataire n'est jamais choisi par Pi. Les commandes entrantes sont `/status`, `/latest`,
`/pause`, `/stop` et `/answer <run_id> <message>`. Il n'existe volontairement aucune commande `/resume`.
