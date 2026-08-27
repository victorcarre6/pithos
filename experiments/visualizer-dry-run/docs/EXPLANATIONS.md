# Explications techniques

Le premier micro-rush isole l'agrégation FFT du matériel audio et de l'interface. Le spectre est découpé en
trois tranches contiguës ; la moyenne de chaque tranche produit un niveau scalaire déterministe.

Les tests du projet doublent l'oracle externe conservé par Pithos. Le modèle peut modifier l'implémentation,
mais il ne peut pas rendre une mission verte en affaiblissant uniquement ses propres tests.

`compute_magnitudes` utilise directement la définition de la DFT, en complexité quadratique. Ce choix reste
la référence déterministe sur de petits signaux. Le runtime temps réel ne l'appelle pas : Web Audio fournit
une FFT native bornée à 1 024 échantillons, puis `audio-core.mjs` normalise les octets, agrège les trois bandes
et applique le lissage pur déjà éprouvé par le prototype Python.

Le navigateur remplace une distribution desktop lourde. Il fournit capture audio, sélection de périphérique,
plein écran et Canvas 2D sur macOS Intel sans dépendance applicative. Le serveur Python ne publie que le dossier
`web/` et écoute explicitement sur `127.0.0.1`; le code client ne contient aucune URL externe. Une interface
loopback éventuellement présente est visible comme une entrée standard, sans couplage à un driver précis.

La campagne est pilotée par le `seed`, pas par un opérateur externe. Le marqueur de complétion empêche de
rejouer le même rush, puis déclenche un handoff local : Pithos propose une nouvelle identité et un contrat
borné, remplace atomiquement `.pithos.json` et enchaîne la mission. Si Ollama ou la validation de proposition
échoue, le rush terminé n'est jamais rejoué et le LaunchAgent reprend la planification au réveil suivant.

Le runtime actif est `host` : Pi utilise le profil local borné et Ollama via loopback. Docker reste une
capacité du harness mais n'appartient plus au chemin nominal de cette campagne après la saturation observée
de sa VM. Ce choix ne modifie ni les fichiers projetés à Pi ni les gates externes.

Chaque rush auto-généré conserve aussi `regression_command: ["python", "tests/validate_product.py"]`. Un
oracle nouveau ne peut donc valider un comportement qui casse le noyau Python, le lanceur localhost ou le
pipeline JavaScript déjà livré. Si aucune réparation ne satisfait les deux contrats, le launcher restaure les
fichiers cibles capturés avant mission.
