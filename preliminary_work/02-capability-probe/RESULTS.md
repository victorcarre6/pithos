# Résultats — Pi + qwen3.8:27b

## Test réel

Commande : scénario `text`, timeout 60 secondes, nouvelle session, JSON event stream.

Résultat :

```text
process_success=false
protocol_success=false
task_success=false
report_success=null
timed_out=true
```

Pi a écrit cinq événements partiels, puis le runner a interrompu le groupe de processus. Aucun `agent_end` ni
message assistant final n'a été produit. Les artefacts sont conservés sous
`~/logs/pithos/capability-probes/qwen3.8-27b/text/`.

Ce test prouve le fonctionnement du timeout et de la persistance, pas la capacité textuelle de la baseline.
Le model probe direct a déjà obtenu cette réponse en 134,954 secondes ; le timeout de 60 secondes est donc
volontairement inférieur à la latence connue.

## Tests déterministes du harness

Le faux processus Pi couvre :

- parsing du JSON event stream ;
- rejet d'une ligne invalide ;
- rejet d'un tool call sérialisé comme texte ;
- détection des tool events déséquilibrés ;
- vérification externe d'un fichier écrit ;
- interruption d'un groupe contenant un descendant.

## État

Le moteur du capability probe est validé. La compatibilité réelle Pi/Ollama reste non établie pour `read`,
`write`, `edit`, `bash`, tests, multi-tools et rapport, car le tool calling direct expire déjà après cinq
minutes avec la configuration actuelle. Skill et extension seront raccordés avec `06-harness-evolution`.

## Recontrôle du 23 août 2026

Un premier run de dix minutes a confirmé le timeout HTTP interne de Pi après 300 secondes, suivi d'un retry.
La configuration dédiée fixe maintenant `httpIdleTimeoutMs` et `retry.provider.timeoutMs` à une heure et
désactive les retries agent.

Un second run `text` de dix minutes n'a plus produit `Request timed out`, ce qui valide la correction. Il n'a
toutefois généré que quatre fragments de thinking avant le timeout externe, sans réponse finale. La baseline
reste donc incompatible avec une campagne autonome exploitable dans sa configuration Ollama actuelle.

Artefacts :

- `~/logs/pithos/capability-probes/qwen3.8-27b-recheck/text/` ;
- `~/logs/pithos/capability-probes/qwen3.8-27b-timeout-fixed/text/`.

## Qualification Ling du 24 août 2026

Commande complète avec `maternion/ling-3.0-tiny:8b`, Ollama 0.32.15 et timeout de 900 secondes par processus.

Les huit capacités mono-processus passent : texte, read, write, edit, bash, test, multi-tool et rapport. Deux
scénarios inter-processus ont été ajoutés et passent également :

- création d'un skill, redémarrage de Pi, découverte et réutilisation cognitive du marker ;
- création d'une extension TypeScript, redémarrage de Pi, chargement puis exécution de son tool.

Résultat final : **10/10**, avec succès processus, protocole et effet externe pour chaque scénario. Les traces,
sessions, stdout, stderr, workspaces et résultats structurés sont conservés sous
`~/logs/pithos/capability-probes/ling-3.0-tiny-8b/`.
