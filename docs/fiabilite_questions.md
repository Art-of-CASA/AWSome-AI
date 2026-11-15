# Fiabilité des questions : diagnostic et protocole de mesure

Ce document sépare les défauts observables dans le code, les garanties vérifiables par tests et les mesures à réaliser avec de vrais échanges. Il ne présente aucun score réel du modèle ou de reconnaissance vocale comme acquis.

## Pourquoi une réponse claire pouvait être redemandée

Dans l'orchestration auditée avant la refonte, `app.repondre` lançait le classement en arrière-plan, puis envoyait les critères encore présents dans `restants` à une réplique générée. Les critères en cours de vérification restaient dans cette liste. La question suivante pouvait donc viser l'horizon ou la réserve que la personne venait de renseigner. Une consigne de prompt « ne pas redemander » n'était pas un verrou de code.

Le contrôle des résultats ignorait aussi un instantané entier dès qu'une nouvelle réponse était arrivée. Si le classement durait plusieurs tours, une réponse sur les dettes pouvait empêcher temporairement d'intégrer l'horizon donné au tour précédent. Cela pouvait prolonger l'état « inconnu » alors que la donnée figurait déjà dans la conversation.

Enfin, une limite de relance propre à la conversation ne suffisait pas à empêcher la même question de revenir ensuite dans les compléments ou les précisions. Une réponse claire doit conserver sa valeur et sa provenance entre les phases, plutôt que devenir un sujet à reposer parce qu'un contrôle est lent.

Ces causes sont distinctes de la compréhension linguistique du critique. Ajouter des exemples au prompt aide le modèle, mais ne remplace pas un état structuré du sujet réellement demandé.

## Les deux exemples signalés

| Réponse et contexte | Information attendue | Traitement attendu |
|---|---|---|
| « Quinze ans » après une question univoque sur l'horizon | Horizon numérique 15 ans | Enregistrer une fois, appliquer une borne de classement explicite et passer à un autre sujet |
| « Six mois de dépenses » après « sans toucher au placement, combien de mois de dépenses sont disponibles ailleurs ? » | Réserve numérique de 6 mois, classe `3_6_mois` | Enregistrer une fois ; six ne signifie pas plus de six |
| « J'aurai besoin de ce placement dans six mois » | Horizon court | Ne pas en déduire six mois de réserve |
| « Mon placement couvre six mois » | Référent incertain | Une seule précision ciblée sur le sens des six mois |
| « Horizon de quinze ans et réserve de six mois hors placement » | Deux informations explicites | Extraire les deux, garder deux citations et éviter deux nouvelles questions |
| « Au moins quinze ans » | Borne inférieure de l'horizon | Conserver cette borne ; le passage en classe doit suivre une politique déclarée, sans présenter l'expression comme une réponse incompréhensible |

Les anciens libellés « 3 à 5 », « 5 à 10 » et « 10 à 15 » se touchent aux bornes. Le classement doit préciser les intervalles utilisés. Une ambiguïté créée par les classes de l'outil n'est pas une raison de faire répéter à la personne une valeur numérique déjà claire.

## Contrat d'orchestration à tester

Le code doit connaître le ou les identifiants de critères effectivement visés par chaque question. Pour chaque critère, il distingue au minimum : inconnu, question posée, réponse reçue, analyse en cours, valeur validée et ambiguïté à préciser.

- Un critère connu ou en cours de vérification ne redevient pas une question initiale.
- Une analyse en attente n'est pas une ambiguïté de la réponse utilisateur.
- Une valeur numérique directe, dans un contexte univoque, est enregistrée avec son nombre, sa citation et sa règle de classement.
- Le contrôle sémantique intervient pour les formulations ouvertes ou réellement ambiguës ; sa confiance déclarée ne mesure pas sa probabilité d'avoir raison.
- Une clarification vise seulement le point manquant, par exemple « ces six mois sont-ils disponibles en dehors du placement ? ».
- Une clarification n'est comptée que lorsqu'elle a réellement été présentée. Son budget est suivi entre les phases.
- Les corrections explicites restent possibles ; une tâche portant sur un ancien texte ne rétablit pas une valeur corrigée.
- Les besoins de liquidité, les contraintes et les exclusions restent requis même s'ils ne changent pas immédiatement le budget de perte.

Un écho court tel que « Je retiens quinze ans pour l'horizon et six mois de réserve » restitue la compréhension sans obliger à répondre une nouvelle fois. La personne doit pouvoir corriger cet écho. Une validation répétée systématique annulerait le gain recherché.

## Reconnaissance vocale et compréhension : deux mesures séparées

Le chemin de transcription audité ne conservait que le texte final de la première alternative. Une extraction numérique déterministe ne peut pas détecter à elle seule que la reconnaissance vocale a transcrit « cinquante » lorsque la personne a dit « quinze ».

Pour évaluer le parcours oral, conserver sur le jeu d'essai une transcription de référence humaine et comparer :

1. les faits présents dans la parole de référence ;
2. les faits encore présents dans la transcription automatique ;
3. les valeurs extraites de cette transcription ;
4. les questions réellement posées ensuite.

Cette séparation permet d'attribuer une erreur à la capture, à l'interprétation, aux bornes ou à l'orchestration. Une qualité de classement mesurée sur du texte parfait ne démontre pas la qualité de toute la chaîne vocale.

## Ce qui doit être mesuré

`mvp_profil/evaluation_questions.py` calcule les mesures à partir d'événements annotés indépendamment du modèle. Il n'ajoute pas d'étiquettes de vérité à des traces non relues.

| Mesure | Numérateur | Dénominateur |
|---|---|---|
| Réponse claire acceptée correctement du premier coup | Premières réponses claires correctement renseignées et utilisables | Premières réponses annotées claires avec une valeur attendue |
| Erreurs parmi les valeurs utilisables | Réponses utilisables différentes de l'étiquette attendue | Réponses utilisables et annotées |
| Abstention sur une réponse claire | Réponses claires laissées non utilisables | Réponses annotées claires avec une valeur attendue |
| Bon refus | Cas sans valeur exploitable correctement laissés non utilisables | Cas annotés sans valeur exploitable |
| Questions injustifiées | Questions annotées inutiles, dont répétitions de faits clairs | Questions dont la justification a été annotée |
| Clarifications injustifiées | Clarifications annotées inutiles | Clarifications dont la justification a été annotée |
| Complétion | Sessions terminées | Sessions closes, terminées ou abandonnées ; les sessions en cours sont affichées séparément |

Le rapport expose aussi les questions initiales et clarifications par critère, les dépassements du budget, les raisons d'une répétition, les effectifs non annotés et la durée médiane des sessions closes dont la durée est connue.

Une première réponse non annotée n'est pas réétiquetée comme une réussite au premier essai grâce à une répétition ultérieure annotée. Une question sans annotation n'est pas supposée justifiée.

Chaque proportion expose son numérateur, son dénominateur et un intervalle de Wilson bilatéral à 95 %. Si aucun cas n'est disponible, le taux et l'intervalle restent inconnus. L'intervalle n'est interprétable comme incertitude d'une population que sous des hypothèses d'échantillonnage appropriées. Les réponses d'une même conversation sont corrélées.

À titre de propriété mathématique de l'estimateur, zéro erreur sur cent observations indépendantes donne encore une borne supérieure Wilson d'environ 3,7 %. Cela ne signifie pas qu'une centaine de tests réussis garantit un système sans erreur. Rejouer cent fois une seule phrase ne crée pas cent situations d'investisseurs indépendantes.

## Jeu de validation à construire et à garder séparé du réglage

Le jeu doit contenir des conversations distinctes, annotées avant d'examiner les sorties :

- chiffres et nombres en lettres, dont toutes les bornes 3, 5, 6, 10 et 15 ;
- réponses brèves contextualisées et réponses portant sur deux critères explicites ;
- réserve en dehors du placement, capital retiré et revenu de dividendes clairement distingués ;
- hésitations, négations, corrections, plusieurs horizons ou plusieurs objectifs ;
- réponses réellement ambiguës et réponses hors sujet ;
- classement lent, réponses rapides, correction pendant une analyse et changement de phase ;
- audio avec pauses, accents et bruit, avec référence humaine indépendante.

Deux personnes peuvent annoter séparément un sous-ensemble et résoudre les désaccords avant le calcul final. Les paraphrases d'une même situation restent regroupées dans la même famille ; une partie de ces familles sert au réglage, une autre reste réservée à l'évaluation. Les résultats se présentent par strate, afin qu'un grand nombre de cas faciles ne masque pas les erreurs des cas limites.

Pour comparer deux versions, conserver les mêmes scénarios et l'ordre des réponses, puis comparer les erreurs et questions injustifiées de façon appariée. Pour un essai utilisateur, équilibrer l'ordre de présentation des versions. Les répétitions du modèle mesurent sa variabilité ; elles ne remplacent pas des conversations distinctes. Les intervalles sur une comparaison de parcours doivent tenir compte des groupes de réponses d'une même conversation.

## Optimiser les questions avec une contrainte de fiabilité

L'objectif opérationnel est de réduire le nombre de demandes et le temps total, sous contrainte de conserver une erreur acceptable et les informations impératives. Un tri par impact et effort reste une heuristique tant que les distributions de réponses, les coûts réels et les erreurs ne sont pas mesurés.

Une question est utile lorsqu'elle peut lever une incertitude qui change une décision, révèle une contrainte ou empêche une interprétation dangereuse. Elle n'est pas utile simplement parce que le critère n'a pas encore reçu le statut « validé » d'un contrôle lent.

Une réduction du nombre de questions n'est retenue comme progrès qu'avec un niveau comparable de bonnes valeurs recueillies, de respect des contraintes et de refus appropriés. L'outil ne gagne pas en efficacité en cachant des inconnues derrière des défauts prudents.

## État du déploiement observé par les fichiers

Lors du diagnostic, les documents locaux étaient contradictoires : le README principal annonçait une publication de l'évolution, tandis que le README du MVP la décrivait encore comme locale. L'archive `mvp_profil.zip` présente dans le dossier ne contenait pas `pilotage.py` et son `app.py` différait du fichier local.

Ces constats établissent une incohérence documentaire et une archive locale périmée. Ils ne permettent pas de conclure quelle version tourne réellement sur le serveur. Un identifiant de version ou une empreinte de paquet affichée par l'application permet de comparer sans ambiguïté le code testé, l'archive envoyée et le site utilisé.
