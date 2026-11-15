# Comparaison ciblée avec des questionnaires et travaux existants

Recherche effectuée le 15 novembre 2026, sur des sources primaires : outils pédagogiques d'organismes canadiens et publications scientifiques originales. Le but est de remplacer une formulation ou un mécanisme seulement s'il apporte quelque chose à la banque actuelle de 42 critères et 34 questions. Aucun questionnaire supplémentaire n'est ajouté par ce document.

## Ce que les sources apportent réellement

L'AMF sépare les retraits proches de l'horizon du capital restant, distingue capacité et attitude, et définit la réserve par son accessibilité sans emprunt. Ces distinctions sont pertinentes pour les référents d'A2, A5, A9 et A10. Elles ne justifient pas d'ajouter toute sa liste d'événements de vie. [Questionnaire public de l'AMF, questions 2, 3 et 7](https://lautorite.qc.ca/_assets/9b006b219bc6994ce462346574e951ec/ProfilInvestisseur/ressources/index.html).

L'OSC Investor Office décrit la réserve à partir des dépenses essentielles et de l'accès rapide à l'argent. Cela soutient un vocabulaire concret pour A5, plutôt qu'une nouvelle question de risque. [Preparing for financial emergencies](https://www.getsmarteraboutmoney.ca/learning-path/saving-money/preparing-for-financial-emergencies/).

Le questionnaire du CIRO comporte une perte exprimée à la fois en dollars et en pourcentage, puis une réaction à un marché en baisse. Ses modalités de calcul distinguent capacité et tolérance. Notre base possède déjà ces deux dimensions et plusieurs mises en situation : en recopier les questions allongerait le parcours. Le CIRO présente explicitement son outil comme un point de départ pédagogique. [Questionnaire public](https://www.ciro.ca/office-investor/understanding-risk/investor-questionnaire), [méthode de calcul](https://www.ciro.ca/questionnaire-scoring).

Ces organismes sont des sources pertinentes de contenu. Leur publication ne démontre pas que notre adaptation orale française est psychométriquement validée, ni qu'elle réduit les erreurs de notre modèle.

## Trois remplacements au maximum, sans nouveau critère

| Sujet | Base actuelle | Changement proposé | Gain attendu et limite | Décision |
|---|---|---|---|---|
| A5 : réserve | La banque précise déjà « sans toucher à ce placement ». Le pilote oral emploie l'argent mis de côté pour les imprévus. | Une seule question : « En dehors de ce placement et sans emprunter, combien de mois de dépenses essentielles votre argent disponible pourrait-il couvrir ? » | Rend explicites la somme disponible, l'absence d'emprunt et les dépenses. La définition est appuyée par l'AMF et l'OSC ; son bénéfice dans notre interface reste à mesurer. Une réponse claire « six mois » suffit. | Intégrer comme remplacement de formulation si le parseur reconnaît ce libellé ; aucun ajout. |
| A3/A2/A9 : même somme et plusieurs objectifs | Le projet et l'horizon sont déjà demandés ensemble ; les retraits proches sont un critère distinct. Une réponse mêlant réserve et retraite peut néanmoins être mal attribuée. | Préambule court : « Parlons de cette somme précise à investir. À quoi servira-t-elle, et quand aurez-vous besoin d'en récupérer la majeure partie ? » Si la personne nomme deux sommes différentes, clarifier uniquement laquelle fait l'objet du profil. | Évite de traiter « réserve disponible maintenant » et « retraite dans quinze ans » comme deux horizons contradictoires du même capital. L'AMF fournit une distinction de retraits et d'horizon utile ; la branche conversationnelle est notre adaptation. | Intégrer le référent ; clarification conditionnelle seulement quand plusieurs sommes sont réellement évoquées. |
| B1/B1R : perte en argent et en pourcentage | B1R présente déjà 10 000 $ devenant 8 000 $. B1 recueille un pourcentage de rupture, puis le replay mesure un comportement. | Conserver B1R. Pour B1, garder un unique fait mais autoriser les deux unités : « Pour dix mille dollars investis, quelle baisse vous ferait vendre ? Vous pouvez répondre en dollars ou en pourcentage. » | Facilite une réponse concrète sans poser deux fois la question. Le CIRO utilise les deux unités sur un montant constant. Le bénéfice oral et l'équivalence des réponses exigent un test ; le code doit contrôler 2 000 $ / 10 000 $ = 20 %, et ne jamais confondre somme restante et perte. | À intégrer seulement avec conversion déterministe et tests d'unités. Sinon conserver B1 actuel : pas de nouvelle question. |

Les formulations du tableau sont des propositions originales, inspirées des dimensions observées. Elles ne reproduisent pas un barème propriétaire et ne reprennent pas automatiquement les points ou seuils des organismes.

Les deux premières améliorations sont surtout sémantiques. La troisième ne doit pas être adoptée si elle introduit une nouvelle ambiguïté de conversion. Aucune ne résout, à elle seule, le défaut technique qui redemandait un sujet pendant sa vérification : il faut garder le verrou de l'orchestrateur et la mémoire des réponses.

## Ce que la recherche académique permet, et ne permet pas, d'affirmer

Grable et Lytton ont développé un instrument de tolérance au risque en 13 items. Une étude ultérieure apporte des éléments de validité concurrente et de construit, tout en appelant à des travaux longitudinaux pour la validité prédictive. [Article original de 1999](https://ojs01.galib.uga.edu/fsr/article/view/3890), [étude de validité de 2003](https://ojs01.galib.uga.edu/fsr/article/view/4768).

La rétrospective de 2015 analyse 160 279 observations recueillies entre 2007 et 2013 et rapporte un alpha de Cronbach de 0,77, avec des associations entre score et détention d'actifs. Cela concerne l'instrument étudié, la population et les conditions de cette recherche. Ce nombre n'est pas un taux de bonnes classifications, et ne mesure pas la fiabilité de notre dialogue. [Publication de 2015, Financial Services Review](https://fsrtest.galib.uga.edu/fsr/article/view/3240?articlesBySameAuthorPage=3).

La traduction, la réduction à quelques items, la reformulation orale et un nouveau calcul changent l'instrument. Nous ne pouvons donc pas transférer cette validité à notre version simplement en empruntant des formulations. C'est une limite méthodologique de notre adaptation, et non un résultat mesuré sur le prototype.

## Éléments à écarter pour cette version

- **Ajouter l'échelle de 13 items entière : écarté.** Elle allongerait le parcours et ferait doublon avec les attitudes et simulations déjà présentes. Elle ne couvre pas à elle seule la capacité, les liquidités et toutes les contraintes de notre profil.
- **Remplacer le quiz par une auto-évaluation des connaissances : écarté.** Les questionnaires publics en proposent, mais notre quiz apporte déjà une observation distincte du ressenti déclaré. Aucun gain démontré ne justifie le remplacement.
- **Ajouter l'âge, les revenus nominaux et le patrimoine comme un nouveau barème : écarté.** La base recueille déjà situation, part d'épargne, réserve, dettes et stabilité. Copier des seuils externes ne démontre pas une meilleure mesure dans ce projet.
- **Ajouter toutes les situations de vie de l'AMF : écarté.** La question ouverte et les critères actuels couvrent déjà une partie du contexte. Une longue liste supplémentaire irait contre la demande de rapidité.
- **Confirmer systématiquement chaque réponse claire : écarté.** Les sources consultées n'apportent pas de preuve que ce mécanisme améliore notre parcours. Un bref écho des faits retenus et la possibilité de les corriger évitent d'exiger une deuxième réponse identique.

## Vérification avant de retenir une nouvelle formulation

Comparer l'ancienne et la nouvelle question sur les mêmes cas annotés : phrases numériques courtes, nombres en lettres, bornes exactes, montants, réserve distincte du placement, objectifs multiples, hésitations et erreurs de transcription. Le critère principal est la bonne valeur obtenue du premier coup avec une réponse claire ; les répétitions injustifiées et les erreurs acceptées sont mesurées séparément.

Une formulation est conservée si elle réduit l'ambiguïté ou l'effort sans augmenter les fausses validations ni supprimer une contrainte. Les taux, dénominateurs et limites d'échantillonnage figurent dans [le protocole de fiabilité](fiabilite_questions.md). Aucune supériorité statistique de ces trois propositions n'est annoncée avant cet essai.

## Choix appliqués dans ce correctif

Les deux premières formulations sont intégrées : référent de la somme précis dans l’ouverture et réserve hors placement, sans emprunt, en dépenses essentielles. La conversion libre dollars/pourcentage de B1 est différée ; le scénario B1R conserve déjà ses deux unités. Aucune question supplémentaire n’est ajoutée. R6, R8 et R9 deviennent des observations sans relance, car les dimensions comparées ne prouvent pas une contradiction.
