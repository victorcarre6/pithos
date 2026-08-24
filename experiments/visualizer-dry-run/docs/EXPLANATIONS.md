# Explications techniques

Le premier micro-rush isole l'agrégation FFT du matériel audio et de l'interface. Le spectre est découpé en
trois tranches contiguës ; la moyenne de chaque tranche produit un niveau scalaire déterministe.

Les tests du projet doublent l'oracle externe conservé par Pithos. Le modèle peut modifier l'implémentation,
mais il ne peut pas rendre une mission verte en affaiblissant uniquement ses propres tests.
