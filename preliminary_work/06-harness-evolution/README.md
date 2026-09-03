# Évolution du harness

## Cycle externe

```bash
pithos-harness \
  --active-root /workspace \
  --ground-truth-root ~/code/pithos/harness/ground_truth \
  --journals-root ~/code/pithos/journals/harness \
  --logs-root ~/logs/pithos \
  begin <run_id>

pithos-harness ... promote <run_id> skill /workspace/.pithos-staging/my-skill .pi/skills/my-skill
pithos-harness ... promote <run_id> extension /workspace/.pithos-staging/my.ts .pi/extensions/my.ts
pithos-harness ... finish <run_id> --rationale "..." --validation "..."
```

`begin` est appelé avant Pi et fige `before/`. `promote` valide la ressource staged, archive toute version
remplacée et promeut par renommage. `finish` fige `after/`, la justification, les validations et un manifest
SHA-256 attribuant chaque fichier actif au run.

En campagne, le runner appelle automatiquement `begin` et `finish`. Le broker permanent se lance avec :

```bash
pithos-harness \
  --active-root /path/to/experiment \
  --ground-truth-root ~/code/pithos/harness/ground_truth \
  --journals-root ~/code/pithos/journals/harness \
  --logs-root ~/logs/pithos \
  serve --socket ~/logs/pithos/runtime/harness-broker.sock
```

Le custom tool `pithos_promote` n'accepte que `.pithos-staging` comme source et les racines actives associées
au type de ressource. Après promotion, il programme `/pithos-reload` pour rendre la capacité utilisable.

## Activation

- Skills et prompts promus sont disponibles au prochain `/reload` ou processus Pi.
- Une extension est contrôlée par le parser TypeScript de Node avant promotion. Elle n'est chargée que dans un
  nouveau processus Pi, jamais injectée dans le processus qui l'a écrite.
- Une extension invalide produit `harness.rejected` et laisse la version active intacte.

## Ground truth

`ground_truth/` n'est jamais une destination d'écriture. `diff` compare ses hashes à l'état actif. `restore`
est une opération locale explicite sur un chemin précis ; aucun échec n'est restauré automatiquement.

Les tests chargent réellement une extension TypeScript promue dans un nouveau processus Node. Un probe RPC
charge aussi les extensions et découvre le skill dans un nouveau processus Pi. Le run de campagne
`run-20260903T152634Z-6ec0c3` prouve en plus sa réutilisation cognitive : création outillée, promotion
archivée, nouveau processus Pi, puis marqueur exact `PITHOS_CAMPAIGN_SKILL_REUSED`.
