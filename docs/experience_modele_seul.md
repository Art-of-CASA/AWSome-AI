# Expérience : un portefeuille construit par un modèle seul, sans moteur

Produit par `python scripts/experience_modele_seul.py`. Simulation éducative ; aucun conseil financier.

**Question.** Faut-il confier la construction du portefeuille à des agents de A à Z, ou garder des règles écrites ?

**Protocole.** Claude Sonnet 5.5 sur Amazon Bedrock, le 15 novembre 2026. Pour chaque persona : le profil en clair, la synthèse calculée (budget de perte, part d'actions indicative) et l'univers complet (111 actifs, 16 colonnes). Consigne : 5 à 12 positions, poids totalisant 100, toutes les contraintes respectées. Trois essais par persona, sans outil. Les neuf réponses sont jugées par les contrôles du moteur (`portefeuille.controles`), les mêmes que pour nos propres portefeuilles.

## Résultats

| Persona | Essai | Somme | Actifs exclus retenus | Contraintes en conflit | Perte de stress estimée par le modèle | Perte de stress mesurée | Écart |
|---|---|---|---|---|---|---|---|
| Amira | 1 | 100 | aucun | Exposition effective au secteur de l'emploi (Information Technology, Communication Services) | 38,5 % | 30,9 % | 7,6 % |
| Amira | 2 | 100 | aucun | Exposition effective au secteur de l'emploi (Information Technology, Communication Services) | 37,9 % | 30,5 % | 7,4 % |
| Amira | 3 | 100 | aucun | Exposition effective au secteur de l'emploi (Information Technology, Communication Services) | 37,0 % | 30,0 % | 7,0 % |
| Mateo | 1 | 100 | aucun | aucune | 15,5 % | 11,5 % | 4,0 % |
| Mateo | 2 | 100 | aucun | aucune | 15,5 % | 11,2 % | 4,3 % |
| Mateo | 3 | 100 | aucun | aucune | 16,0 % | 11,7 % | 4,3 % |
| Robert | 1 | 100 | aucun | aucune | 11,9 % | 6,7 % | 5,2 % |
| Robert | 2 | 100 | aucun | aucune | 11,7 % | 7,2 % | 4,5 % |
| Robert | 3 | 100 | aucun | aucune | 12,0 % | 6,8 % | 5,2 % |

## Stabilité d'un essai à l'autre

| Persona | Actifs communs aux trois essais | Actifs cités au moins une fois | Écart moyen de poids entre essais |
|---|---|---|---|
| Amira | 11 | 12 | 1,2 point |
| Mateo | 7 | 15 | 3,2 point |
| Robert | 10 | 13 | 1,4 point |

## Coût et délai

| | Modèle seul | Moteur à règles |
|---|---|---|
| Délai par portefeuille | 14 à 29 s | moins de 0,1 s |
| Jetons par portefeuille | environ 9272 en entrée, 1814 en sortie | aucun |
| Même entrée, même sortie | non | oui (testé) |
| Chaque poids relié à une règle et à une preuve | non : une phrase de justification par ligne | oui |

## Comparaison avec le moteur

| Persona | Budget de perte | Moteur : perte de stress | Modèle seul : perte de stress mesurée (3 essais) |
|---|---|---|---|
| Amira | 45 % | 22,5 % | 30,9 %, 30,5 %, 30,0 % |
| Mateo | 22 % | 12,8 % | 11,5 %, 11,2 %, 11,7 % |
| Robert | 15 % | 6,0 % | 6,7 %, 7,2 %, 6,8 % |

## Lecture

**Ce que le modèle fait bien.**
- Sur ces neuf essais, il respecte les contraintes écrites en toutes lettres : 0 portefeuille sur 9 retient un actif exclu ou dépasse un plafond par titre. Les poids totalisent 100 à chaque fois, aucun ticker n'est inventé.
- Ses portefeuilles sont diversifiés et sensés (or pour Robert, semi-conducteurs pour Amira). Pour Amira, il utilise mieux le budget de perte que notre moteur, qui reste très en dessous.

**Ce qu'il fait moins bien.**
- **Il ne voit pas les règles qu'on ne lui écrit pas.** 3 portefeuilles sur 9 dépassent le plafond d'exposition au secteur de l'emploi (25 %, fonds compris) : le profil disait « secteur d'emploi : technologie », pas la règle. Le moteur l'applique toujours ; le modèle seulement si on pense à la lui rappeler.
- **Il estime son risque, il ne le calcule pas.** L'écart moyen entre la perte de stress qu'il annonce et celle que nous mesurons sur les prix est de 5,5 %, toujours dans le même sens (il surestime).
- **Il ne se répète pas.** Pour la même personne, les poids changent d'un essai à l'autre, et pour Mateo moins de la moitié des actifs cités reviennent dans les trois essais. Deux utilisateurs identiques recevraient deux portefeuilles différents.
- **Il est lent et ne laisse pas de trace vérifiable.** Quinze à trente secondes par portefeuille, contre moins d'un dixième de seconde, et une phrase de justification par ligne au lieu d'une preuve par contrainte.
- **Rien n'est garanti.** Neuf essais sur trois personas ne font pas une statistique : ils montrent que c'est souvent juste, pas que c'est toujours juste. Or une exclusion (armement, tabac) doit tenir à chaque fois.

## Décision

Nous gardons les règles pour tout ce qui doit être exact et identique d'une fois à l'autre : exclusions, plafonds, poids, perte de stress, verdicts. Les agents font ce que les règles font mal : comprendre une demande en langage courant, choisir les outils, expliquer, proposer une alternative, refuser. Dans « Parler au conseiller », le modèle ne modifie le portefeuille qu'à travers des outils dont le code vérifie chaque effet.

## Améliorations tirées de l'expérience

1. **Modèle qui propose, moteur qui valide.** Laisser le modèle suggérer plusieurs portefeuilles candidats ; le moteur écarte ceux qui violent une contrainte, mesure les autres et garde le meilleur. On gagne son sens de la composition sans perdre la garantie.
2. **Mieux utiliser le budget des profils dynamiques.** Le modèle donne plus de poids aux thèmes d'intérêt (semi-conducteurs, IA) ; notre moteur pourrait incliner davantage les poids vers les préférences quand la tension est très basse.
3. **Rendre les règles implicites visibles.** Le plafond du secteur de l'emploi surprend : il mérite d'être dit à la personne dès la synthèse du profil, pas seulement dans les contrôles du portefeuille.
4. **Mesurer avant d'élargir.** Refaire cette expérience sur quelques dizaines de profils annotés avant de confier davantage au modèle.
