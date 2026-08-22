# Cahier de laboratoire

## 23:08 — Socle 00 à 06

- Contrats JSON/Markdown versionnés et validés.
- Baseline Ollama mesurée ; `qwen3.8:27b` reste le modèle imposé malgré un débit inférieur à 1 token/s et
  des timeouts sur les probes structurés/tool calls.
- Capability probe, continuité atomique, runner borné, broker Git et promotion du harness implémentés.
- Les validations nécessitant une session Pi fonctionnelle restent explicitement ouvertes.

## 23:08 — Event store 07

- SQLite est une projection reconstructible ; les JSONL restent la preuve primaire.
- Curseur byte/ligne par source, ingestion idempotente, quarantaine et refus des troncatures.
- Migrations v1/v2 et projections métier ajoutées ; contenu brut intégral conservé.
- **56 tests passent** sur l'ensemble du dépôt.

## 23:08 — Dashboard 08

- API FastAPI strictement read-only avec pagination bornée et health service/données séparé.
- Interface React/Vite dérivée des design tokens et cartes d'Argos/Aede.
- SQLite et artefacts montés `:ro` dans la composition Docker ; publication LAN différée.

## 23:08 — Telegram 09

- Broker socket `0600`, destinataire fixe, cinq types sortants et rate limiting.
- Offset et `request_id` persistants pour rendre updates et envois idempotents après redémarrage.
- `/pause` et `/stop` sont observés par le monitor du run ; aucune reprise Telegram n'est exposée.
- Le loop guard tente le message exact avant l'interruption et reste fail-safe si Telegram est indisponible.

## 23:08 — Live logs 10

- Format mono-ligne horodaté, verrou `flock`, flush et `fsync` à chaque événement.
- Rotation par renommage vers une archive illimitée, sans dépendance à SQLite ou au dashboard.
- Test réel : un processus `tail -F` a reçu les lignes avant et après remplacement du fichier canonique.
- **72 tests passent** sur l'ensemble du dépôt.
