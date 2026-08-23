# Instructions — capability probe

Construis un probe déterministe et jetable ; ne construis pas encore le runner de production.

- Vérifie chaque effet par inspection externe au modèle.
- Utilise uniquement des fichiers et commandes sans risque dans la fixture.
- Ne transforme jamais un exit code nul en succès de tâche implicite.
- Conserve stdout, stderr, événements et session brute par scénario.
- Fais échouer clairement les sorties de tool calls sérialisées comme simple texte.
- Ne contourne pas une incapacité du modèle par une action cachée du harness.
- Documente la commande exacte pour reproduire chaque cas.
