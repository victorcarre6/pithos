# Probe du modèle local

## But

Mesurer la baseline d'inférence choisie par l'utilisateur sur le Mac mini M2 16 Go, sans modifier ni choisir
à sa place la configuration du serveur. Le candidat principal est `unsloth/Qwen3.8-27B-GGUF`.

## Livrables

- Protocole reproductible de mesure mémoire, swap, débit, latence et stabilité.
- Recherche du contexte maximal stable par paliers.
- Tests du developer role, du structured output et des tool calls.
- Rapport factuel par quantification/configuration fournie.
- Étude séparée de Qwen3.6-35B-A3B et Colibri, sans en faire automatiquement la baseline.

## Contraintes

- Le modèle et sa configuration restent contrôlés par l'utilisateur.
- Ne télécharge, ne remplace et ne supprime aucun poids sans autorisation explicite.
- Le seuil de débit minimal demandé est 1 token/s.
- Ne déduis pas la compatibilité mémoire de la seule taille des poids.
- Consigne les paramètres exacts et les valeurs réellement mesurées.

## Critères de succès

- [x] Le débit et la mémoire sont mesurés sur plusieurs prompts représentatifs.
- [ ] Le contexte maximal stable est borné par une mesure réussie et une limite observée.
- [ ] Les tool calls valides et invalides sont caractérisés — le cas valide expire actuellement après 300 s.
- [x] Les boucles, fins de génération et erreurs de parsing sont rapportées.
- [x] Une configuration baseline est documentée sans la modifier automatiquement.

## Dépendances

- `00-contracts` pour les résultats structurés.
