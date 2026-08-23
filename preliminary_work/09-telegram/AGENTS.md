# Instructions — Telegram

Le broker détient le secret ; le modèle ne reçoit qu'une capacité étroite.

- Ne place jamais token, chat id ou login dans le dépôt, les fixtures ou les logs.
- Valide côté broker les types de messages, commandes et destinataires.
- Refuse toute méthode Telegram générique fournie directement par le modèle.
- Rends les commandes entrantes idempotentes et attribuables à un update Telegram.
- Ne crée pas de commande distante de reprise après loop-guard.
- Journalise les métadonnées utiles sans inclure les headers d'authentification.
- Teste l'indisponibilité réseau et les réponses Telegram en erreur.
