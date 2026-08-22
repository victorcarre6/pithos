# Instructions — runner

Le runner est une enveloppe déterministe ; ne lui délègue aucune décision cognitive.

- Utilise des chemins explicites et valide-les avant toute suppression ou signal.
- Identifie un processus par PID et marqueur propre au run avant de l'interrompre.
- N'utilise pas un simple fichier PID sans test de vivacité et d'identité.
- Fais propager les signaux à l'arbre de processus.
- Teste concurrence, crash, verrou orphelin, timeout et état paused.
- Garde `launchd` comme adaptateur mince autour du runner.
- Ne stocke aucun credential dans le plist ou les logs.
