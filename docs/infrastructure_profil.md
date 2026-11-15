# Infrastructure du profil : ordre des questions, contrôles et restitution

Ce document décrit le fonctionnement implémenté, avec le correctif des répétitions publié le 15 novembre 2026 (version `profil-afe8ed38fc7d`). L'identifiant de contenu visible dans l'interface distingue le code testé de la version du serveur. L'objectif est de recueillir les informations utiles avec moins de répétitions, en gardant une preuve de ce qui est déclaré, confirmé, mesuré ou encore inconnu. Les suggestions personnalisées et le moteur d'appariement restent une étape distincte.

L'ordre est une **heuristique déterministe**, pas un optimum démontré du nombre de questions ou de la durée. Les coefficients d'utilité et les coûts sont des hypothèses explicites. Aucune mesure avec de vrais utilisateurs ou avec le modèle Bedrock n'établit encore le gain de temps ou la qualité des nouvelles formulations.

## 1. Responsabilités des composants

| Composant | Responsabilité | Limite de son rôle |
|---|---|---|
| `criteres.py` | Définit les critères, les valeurs autorisées, les questions et les choix du questionnaire. | Une liste fermée ne prouve pas à elle seule la justesse d'une interprétation. |
| `pilotage.py` | Classe les questions restantes par prérequis de sécurité, impact calculé et utilité relative. | Réordonne sans inventer de réponse ni supprimer une information nécessaire. |
| `entretien.py` | Formule une question courte à partir des priorités et de la conversation. | Ne valide pas le profil par le simple fait de reformuler une réponse. |
| `agents.py` | Classe les réponses libres puis fait vérifier la proposition par le critique. | Une objection explicite ne peut pas devenir un accord par le mécanisme de repli. |
| `app.py` | Orchestre les étapes, les tâches en arrière-plan, les versions, les précisions et les confirmations. | Les résultats périmés ne remplacent pas une réponse plus récente. |
| `profil.py` | Applique les déductions déterministes, les contrôles de cohérence et le recoupement avec le replay. | Un correctif demande une réponse lorsqu'aucune valeur n'a été choisie. |
| `simulations.py` | Conserve les observations des trois mises en situation. | Une mesure simulée reste distincte d'une déclaration et ne prouve pas le comportement réel. |
| `criteres_dynamiques.py` | Traduit les précisions personnelles en règles, notes ou contraintes à confirmer. | Une intention de limiter sans chiffre ne devient pas une exclusion. |
| `chercheur.py` | Documente les liens entre un concept et les actifs, avec preuves et couverture. | Ne pas trouver un lien ne prouve pas son absence. |
| `synthese.py` | Calcule la synthèse, les réponses décisives et la sensibilité locale. | Les hypothèses de risque ne sont pas une calibration validée ni une prévision. |

Le pilote de questions déterministe et l'analyse ont deux rôles séparés : l'utilisateur peut continuer pendant la vérification, mais le panneau du profil ne marque une valeur comme validée qu'après les contrôles.

## 2. Ordre concret du parcours

Le questionnaire classique ouvre les pages dans cet ordre :

1. Votre projet : objectif, horizon, retraits et besoin de revenu.
2. Votre situation : réserve, dettes, part d'épargne engagée et autres éléments de capacité.
3. Vous et le risque : réaction à une baisse, point de rupture, variation acceptée et récupération.
4. Vos connaissances : quiz et expérience des produits encore inconnue.
5. Vos valeurs et votre compte : exclusions, exigences ESG, accès aux marchés et contexte du compte.
6. Vos préférences : contraintes restantes sur les placements, puis régions, style et thèmes.
7. Les trois mises en situation, puis les précisions et contrôles de cohérence.
8. Une dernière question ouverte pour les particularités personnelles.
9. La synthèse, ses réponses décisives, sa robustesse et les confirmations encore nécessaires.

Les pages déjà ouvertes ne sont pas déplacées. Les questions restantes de la page sont priorisées et celles dont la valeur est déjà utilisable sont retirées. Après une conversation, une page de compléments reprend uniquement les critères de contexte qui restent inconnus ; les autres pages sont réordonnées avec les mêmes prérequis.

Le dialogue oral couvre les critères de contexte, pas l'intégralité du questionnaire. Il reçoit la priorité de `pilotage.py`, utilise ce qui a déjà été dit et laisse les QCM, quiz et simulations compléter le parcours. La conversation est bornée à dix tours ; passer aux questions suivantes conserve les informations acquises et fait reprendre ce qui manque.

### Exemples de questions utiles

Les formulations ci-dessous illustrent les consignes et les questions de référence. Le pilote choisit la formulation et sa cible ; les questions déjà répondues ne reviennent pas pendant la vérification. Toutes les réponses ouvertes passent par le micro.

| Moment | Question ou format | Informations visées | Contrôle d'intégrité |
|---|---|---|---|
| Ouverture | « À quoi servira cet argent et dans combien d'années devrez-vous en récupérer la majeure partie ? » | A3, A2 | Un objectif et sa date peuvent être recueillis ensemble ; une date incertaine reste à préciser. |
| Disponibilité du capital | « Prévoyez-vous de retirer une partie du capital avant cette échéance ? » | A9 | Ne pas confondre retrait du capital et perception des revenus du placement. |
| Revenu du placement | « Avez-vous besoin des intérêts ou dividendes pour payer vos dépenses courantes ? » | A10 | L'absence de retrait ne signifie pas absence de besoin de revenu. |
| Réserve | « Sans toucher à ce placement, combien de mois de dépenses pourriez-vous couvrir ? » | A5 | Le référent est la réserve disponible hors placement. |
| Dette | « Avez-vous actuellement une dette à taux élevé, par exemple un solde de carte de crédit ? » | A7 | Un « non » à cette question précise peut être suffisant ; l'absence de mention n'est pas un non. |
| Part de l'épargne | « Quelle part de votre épargne totale ce placement entier représente-t-il ? » | A4 | Ne pas demander la part correspondant à la perte de la moitié du placement : ce serait une autre quantité. |
| Situation | Réponse libre sur la stabilité des revenus, le secteur, les personnes financièrement à charge et les dettes. | A6, A12, A8, A7 encore inconnus | Extraire chaque information donnée ; ne pas remplir les autres champs avec un simple oui/non. |
| Risque concret | « Vos 10 000 dollars deviennent 8 000 dollars en trois mois. Que faites-vous ? » puis curseur de rupture. | B1R, B1 | Garder la réaction et le point déclaré distincts, puis clarifier une éventuelle contradiction. |
| Connaissances | Trois questions à bonnes réponses. | C1 | Le quiz reste mesuré ; une aisance à l'oral ou un métier ne le remplace pas. |
| Contraintes | Choix explicites sur les activités refusées, les controverses et les marchés accessibles. | D6, E1, E2, E4, E5, F2, G3 | Une exclusion reste utile même si elle ne change pas le budget de perte. |
| Préférences | « Quels thèmes vous intéressent et lesquels refusez-vous ? » | D5, D6 encore inconnus | Une préférence positive et un refus doivent rester distingués. |
| Particularité personnelle | « Y a-t-il quelque chose de particulier que nous n'avons pas abordé ? » | Critères X1, X2… | Citation, cible et effet contrôlés ; les pourcentages manquants sont demandés explicitement. |

Un regroupement est utile quand la réponse permet de distinguer les sujets : objectif avec horizon, expérience avec produits détenus, thèmes souhaités avec thèmes refusés. Deux questions indépendantes appelant chacune oui/non sont posées séparément. « Avez-vous une réserve et des dettes ? — Oui » ne justifie aucune attribution automatique aux deux champs.

## 3. Comment le code choisit la priorité

`pilotage.py` attribue une bande à chaque critère :

| Bande | Priorité | Exemples |
|---|---|---|
| 0 | Projet et horizon | A3, A2 |
| 1 | Disponibilité de l'argent, réserve et dettes | A9, A10, A5, A7 |
| 2 | Capacité, risque et connaissances | A4, A6, A8, B1, B1R, B3, B5, B7, C1 |
| 3 | Contraintes, plafonds et accès | Classes acceptées, crypto, concentration, exclusions, ESG, G3 |
| 4 | Contexte complémentaire | Étape de vie, secteur, produits détenus, montant, compte, consultation |
| 5 | Préférences | Régions, thèmes d'intérêt, style, médiatisation, fonds ou titres |

Une grande variation potentielle du score ne permet pas à une préférence de passer devant une information de sécurité. Une information inconnue est prioritaire par rapport à une information déjà connue lorsqu'elles sont présentes dans la même liste de candidats.

Pour les critères intervenant dans le calcul, le code essaie les valeurs autorisées, une à une, en conservant les autres réponses. Il mesure :

- l'amplitude possible du budget de perte ;
- l'amplitude des composantes de capacité et de tolérance, même lorsqu'une autre composante masque leur effet sur le minimum final ;
- les changements de limites : volatilité, durée sous l'eau, concentration, marchés accessibles ou besoins de liquidité à préciser.

À l'intérieur d'une bande, une question groupée est classée par l'utilité relative suivante :

```text
utilité = somme sur les critères encore inconnus de
          (1 + amplitude du budget / 5
             + amplitude des composantes / 10
             + indicateur de changement des limites)
          / effort relatif de la question
```

Les efforts relatifs sont 1 pour un QCM ou un curseur, 1,3 pour un choix multiple, 2 pour une réponse libre et le nombre de questions pour un quiz. Ce sont des unités de classement, pas des secondes mesurées. Le tri des critères seuls utilise les mêmes impacts et un ordre de départage fixe.

Cette méthode ne calcule ni une entropie ni une probabilité de réponse. Elle préserve les exclusions et les besoins de liquidité même lorsqu'ils ne changent pas le niveau numérique. Elle ne sait pas encore déterminer expérimentalement le meilleur compromis entre durée, fatigue et quantité d'information.

## 4. Extraire une fois, vérifier, puis éviter les répétitions

À chaque réponse libre, le classificateur reçoit les critères demandés et d'autres critères déclaratifs encore inconnus. Une information donnée spontanément peut donc renseigner un autre bloc. Seule une proposition validée est conservée pour ces critères facultatifs ; le simple fait d'en parler ne clôt pas la question.

Le classificateur et le critique reçoivent le sens des codes et les libellés des choix issus du questionnaire. Le critique doit lire la citation avec sa question et les échanges utiles. Il accepte une réponse courte claire et ne cherche une autre lecture que si elle est plausible et changerait la valeur. Il garde les contrôles de négation, de fourchette, de citation et de correction récente.

Les sources restent distinguées : QCM, curseur, quiz, conversation, déduction, replay ou confirmation. Être parent ne permet pas de compter automatiquement les personnes actuellement à charge. Le métier ne permet pas à lui seul de conclure que les revenus sont stables.

Une précision libre est bornée à une reformulation. Le parcours conserve son seuil de validation pendant la clarification ; un manque précis doit la justifier. Un désaccord interne seul ne demande pas à l'utilisateur de répéter. Un résultat refusé par le critique reste non utilisable ; un accord avec confiance réduite peut être signalé comme « retenu ». Une information inconnue n'est pas transformée en consentement ou en exclusion.

## 5. Analyse en arrière-plan et corrections

L'orchestration de la conversation est dans `app.py` :

1. Chaque échange reçoit un numéro correspondant à la longueur de l'historique.
2. Les critères déjà en cours de vérification ne sont pas relancés pour le même instantané.
3. Si des réponses arrivent pendant une vérification, elles sont regroupées pour une analyse du dernier historique disponible.
4. La fraîcheur est vérifiée par critère. Un nouveau sujet ne périme pas un résultat utile antérieur ; seule une nouvelle réponse ou correction sur ce critère bloque l'ancien résultat.
5. Une correction explicite, comme « je me corrige » ou « finalement », déclenche une relecture des informations déjà connues. La nouvelle valeur doit être étayée par les mots récents ; une ancienne citation ne suffit pas.
6. Une correction ambiguë appelle une précision. La confiance élevée d'une ancienne interprétation ne doit pas empêcher une correction plus récente.
7. Avant de quitter la conversation, le code termine les vérifications et leur rattrapage ; les critères encore inconnus passent dans les compléments.

Le panneau de progression distingue une analyse en cours d'une valeur validée. Le regroupement asynchrone vise à éviter les analyses redondantes ; son gain de latence et de coût doit encore être mesuré sur des parcours réels.

## 6. Contraintes personnelles : intention, cible et applicabilité

« Limiter les banques » conserve l'effet `plafonner`, avec un pourcentage inconnu. Le critère est affiché à préciser et ne filtre rien automatiquement. L'interface propose un pourcentage et une confirmation explicite de la règle et de sa cible. Ne rien confirmer laisse le critère non applicable. Un plafond explicite de zéro reste un plafond de zéro ; aucune conversion implicite en exclusion n'est nécessaire.

Trois éléments restent séparés :

- l'intention de la personne et sa citation ;
- la traduction de cette intention en règle ;
- les données permettant d'identifier les actifs concernés.

Confirmer une règle n'établit pas un fait d'exposition. Une recherche en attente ou en échec ne devient pas applicable parce que l'intention a été confirmée. `est_applicable` vérifie le statut, la cible, le pourcentage lorsqu'il est requis et la présence d'actifs identifiés pour un mot-clé dynamique.

Le chercheur conserve un état pour chacun des actifs : `oui`, `partiel`, `non_concerne` ou `inconnu`. Chaque verdict affirmatif ou négatif exige une preuve réellement renvoyée par un outil, un ticker connu, l'accord du critique et une confiance suffisante des deux agents. Un manque de résultat, une preuve insuffisante, un désaccord ou des preuves contradictoires laissent l'actif inconnu.

Les principales positions d'un FNB donnent une exposition minimale connue. Elles ne permettent pas d'affirmer que le reste du fonds est exempt du concept. La couverture, les actifs inconnus et les preuves sont visibles et exportés. Le cache distingue les concepts complets et les versions des données, des consignes et du modèle ; sa durée de validité de sept jours reste une hypothèse de fraîcheur.

## 7. Réponses décisives et robustesse

La synthèse garde le minimum entre capacité financière, tolérance déclarée et tolérance observée. Les nouveaux éléments expliquent ce calcul sans confier la justification à une génération libre.

**Réponses décisives.** Le code remplace une réponse connue par les autres valeurs autorisées et relève les dimensions réellement modifiées. Il cite la réponse originale, sa source et son statut. Les mesures du replay sont conservées ; le déclaré d'avant replay et le point observé restent distincts. Une exclusion est expliquée comme contrainte pour la comparaison future, sans prétendre qu'elle a modifié le budget.

**Robustesse locale.** Sur des échelles ordonnées, le code déplace une réponse d'un cran, une à la fois. Il affiche la plage des budgets recalculés, les niveaux possibles et les variantes qui modifient une limite. Il ne crée aucun ordre artificiel entre des métiers ou des objectifs et ne modifie pas le comportement observé pour fabriquer une variation.

Un profil incomplet ou un besoin de liquidité non chiffré reste provisoire. La plage de robustesse ne constitue ni un intervalle de confiance, ni une prévision de perte, ni une validation indépendante des hypothèses de l'équipe. Elle ne couvre pas les interactions entre plusieurs changements simultanés.

Les retraits réguliers ou le revenu indispensable signalent les montants, dates et fréquences encore nécessaires. Le code n'invente pas un nouveau plafond financier à partir d'un besoin non chiffré.

## 8. Validation et prochaines mesures

Les tests hors ligne vérifient le tri déterministe, la conservation des questions, les contraintes avant les préférences, les citations, le refus d'un désaccord comme repli, les plafonds à confirmer, les états du chercheur et les effets de sensibilité. Les tests avec réponses simulées contrôlent les règles d'orchestration et le format des appels ; ils ne démontrent pas que le vrai modèle interprète correctement toutes les formulations.

L'évaluation Bedrock doit notamment mesurer la justesse des valeurs, la stabilité des sorties, les faux accords, la prise en compte des corrections, les négations et les erreurs de transcription. L'évaluation utilisateur doit mesurer la durée, les relances, la compréhension du résumé, les corrections apportées et le taux de complétion. Aucun de ces résultats n'est supposé acquis par le seul passage des tests simulés.

Pour comparer l'ancien et le nouveau parcours, conserver les mêmes cas annotés et relever : informations utiles confirmées par minute, erreurs acceptées, questions répétées, coût par profil et temps d'attente. Une réduction de durée n'est retenue comme progrès que si la justesse et le respect des contraintes sont maintenus.
