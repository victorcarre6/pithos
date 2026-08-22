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

