# Instructions — évolution du harness

Ce chantier donne de l'autonomie sans confondre état actif et source de vérité.

- Ne rends jamais `ground_truth/` writable par l'agent expérimental.
- Snapshotte avant toute activation, pas après coup seulement.
- Calcule les hashes sur le contenu réellement activé.
- Valide syntaxe et chargement dans un processus isolé avant promotion d'une extension.
- N'autorise pas une extension à modifier le runner externe ou le broker de credentials.
- Fournis une restauration explicite et testée ; ne restaure jamais automatiquement un échec à analyser.
- Journalise les raisons données par l'agent sans les traiter comme preuve de validité.
