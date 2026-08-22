# Évolution et archivage du harness

## But

Autoriser l'agent expérimental à créer et activer ses instructions, skills, scripts, extensions, tools et
sous-agents, tout en conservant une source de vérité externe et un historique complet des mutations.

## Livrables

- Séparation `ground_truth`, état actif et snapshots.
- Manifest des artefacts actifs avec hash et provenance.
- Snapshot `before/after`, rationale et validations dans `journals/harness/<run_id>/`.
- Activation immédiate des skills/prompts quand Pi le permet.
- Activation des extensions dans un nouveau processus contrôlé.
- Restauration explicite depuis `ground_truth` ou un snapshot.
- Diff d'audit entre constitution et état actif.

## Contraintes

- `ground_truth/` est hors workspace expérimental et monté read-only.
- Pi reçoit uniquement les instructions actives, jamais la constitution concaténée.
- Une mutation n'efface aucun snapshot précédent.
- Une extension invalide ne remplace pas silencieusement la dernière version fonctionnelle.
- Chaque activation est un événement observable.

## Critères de succès

- [ ] Un skill créé est archivé et actif après redémarrage ; sa réutilisation cognitive par Pi reste à tester.
- [ ] Une extension créée est validée et chargée dans un nouveau processus Node ; le chargement Pi reste à tester.
- [x] Une extension invalide laisse l'état actif précédent utilisable.
- [x] La constitution reste inchangée et permet une restauration.
- [x] Chaque fichier actif est attribuable à un run et à un snapshot.

## Validation réalisée

- Snapshots `before/after`, manifest SHA-256, rationale et journal de validations.
- Promotion d'un skill conforme au standard Agent Skills et redécouverte par une nouvelle instance du manager.
- Parsing TypeScript sans exécution via l'API compiler, puis import de l'extension promue dans un nouveau
  processus Node.
- Rejet d'une extension invalide sans altération de la version active.
- Diff et restauration explicite depuis une constitution dont le hash reste inchangé.

Les deux validations Pi réelles demeurent ouvertes à cause des timeouts de la baseline, sans bloquer le
mécanisme externe de snapshot et promotion.

## Dépendances

- `00-contracts`.
- `02-capability-probe`.
- `04-runner`.
