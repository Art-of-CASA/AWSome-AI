# AlphaForge AI — documentation technique

Datathon PolyFinances 2026, défi AlphaForge AI (Banque Nationale, AWS). Version du 15 novembre 2026.

**Simulation éducative.** Profils fictifs, données publiques, aucun ordre réel, aucun conseil financier personnalisé. Les mesures décrivent le passé sur une période dite ; elles ne prédisent pas les rendements futurs.

## 1. La question traitée

> Quels actifs et quel mini-portefeuille fictif sont cohérents avec la capacité, les préférences et le comportement observé d'une personne dans nos simulations, et pourquoi ?

L'angle propre au projet est l'écart entre le **déclaré** et le **vécu**. Le profil ne retient pas seulement ce que la personne dit accepter : il mesure aussi ce qu'elle fait dans trois mises en situation (replay de 2022, fourchettes de résultats, effet de mode). En cas d'écart, la valeur la plus prudente l'emporte.

Les résultats sont **traçables** : chaque conclusion renvoie à une donnée datée, à une réponse du profil ou à une hypothèse écrite. Nous ne disons pas « 100 % explicable » : la trace montre d'où vient un chiffre, elle ne prouve pas que la règle est la bonne.

## 2. Vue d'ensemble

```
 PROFIL (mvp_profil/)                       DONNÉES (data_extended/asset_criteria.csv)
 entretien vocal, questionnaire,            111 actifs × 109 colonnes, mots-clés kw_*
 3 mises en situation, critères dynamiques  prix quotidiens convertis en CAD
        │ profil + synthèse (budget de perte)        │
        ▼                                            ▼
 contraintes.py ───────────────▶ appariement.py ──────────────────▶ portefeuille.py      (mvp_profil/recommandation/)
 exclusions, plafonds, budget,      verdict, score 0-100,            poids, perte de stress,
 préférences, inconnus              poids maximal, preuves           tension en % et en $
        └──────────────────────── analyse.py (recherche, comparaison, « Et si… ? ») ───────────────────────┘
                                             │ outils (outils.py)
                      ┌──────────────────────┴───────────────────────┐
              Agent Conseiller                              Agent Explicateur
              (orchestration)                               (« pourquoi ? », refus)
                      └────────── vérificateur de fidélité, gouvernance, Guardrail ──────────┘
                                             │
                  étape 4 du site (mvp_profil/app.py, écrans dans ecrans.py) + journal des actions
```

Le site est une seule application Streamlit : la recommandation est la quatrième étape du parcours, ouverte depuis la synthèse du profil. Tout son code vit dans `mvp_profil/recommandation/`, parce que le paquet déployé ne contient que `mvp_profil/`. Les données qu'elle lit (univers, prix en CAD, positions des FNB, copies de `config/`) sont préparées dans `mvp_profil/recommandation/donnees/` par `python scripts/build_donnees_recommandation.py` ; un test échoue si elles ne suivent plus leurs sources.

Principe tenu partout : **le code décide ; les modèles classent, orchestrent et sélectionnent les explications.** Aucun modèle ne produit un verdict, un score, un poids ou un chiffre affiché. Depuis les correctifs de l'audit multi-agents, les phrases financières finales sont assemblées par le code ; le modèle ne peut sélectionner que des détails identifiés dans un catalogue fermé.

## 3. Méthodes et justification

### 3.1 Du profil aux contraintes (`contraintes.py`)

Le profil est lu tel quel ; rien n'y est écrit. La synthèse existante (`mvp_profil/synthese.py`) fournit le budget de perte, le plus prudent de trois composantes : capacité, tolérance déclarée, tolérance observée.

| Famille | Contenu | Critères |
|---|---|---|
| Exclusions dures | Classe refusée, thème refusé, controverse, fossile, activité, pays, accès, crypto à 0 %, spéculatif refusé, critère personnel « exclure » | D1, D6, E2, E1, E5, F2, G3, D2, D12, X* |
| Plafonds | Par titre, crypto, spéculatif, secteur, secteur de l'emploi, change, fonds exposés, complexité, critère personnel « plafonner » | D9, D2, D12, A12, D4, E1, F2, C1, X* |
| Budget de risque | Budget de perte, volatilité maximale, durée sous l'eau maximale, part de croissance indicative | Synthèse du profil |
| Préférences pondérées | Thèmes, régions, style, revenu, forme, exigence ESG, diversification, critère personnel « privilégier » | D5, D3, D7, A10, D11, E4, D10, X* |

Les refus E2 (controverses) et E5 (activités) s'appliquent aussi aux sous-jacents connus des FNB. Un fonds détenant une entreprise exclue est écarté avec la preuve de sa position et de son motif d'exclusion. La couverture partielle reste affichée : aucune garantie n'est donnée sur les positions inconnues. Les restrictions de classe ou d'accès aux marchés ne sont pas propagées aux titres des fonds.

La devise de cotation ne mesure pas le change économique : XEQT, coté CAD mais non couvert sur ses actifs étrangers, reste exposé. Sans ventilation complète, tout le poids d'un fonds exposé compte dans le plafond de change ; c'est une borne prudente, pas une estimation de sa fraction exacte en devises.

**États d'un critère.** Le profil utilise les statuts `validé`, `retenu`, `incertain`, `à préciser`, `analyse en cours`. La couche de recommandation les traduit ainsi :

| État | Signification | Traitement |
|---|---|---|
| `CONNU` | Réponse validée ou retenue | Appliquée. Une réponse « retenue » (confiance réduite) pèse moitié moins dans le score |
| `INCERTAIN` | Réponse non validée | Jamais utilisée pour filtrer |
| `INCONNU` | Question non posée, sans réponse ou à préciser | Risque : réglage prudent déjà déclaré dans le profil, signalé. Exclusions et préférences : aucun filtre, et c'est dit |
| `NON_APPLICABLE` | Valeur neutre (« indifférent ») ou colonne sans objet pour l'actif | Sans effet |
| `DONNÉE_MANQUANTE` | Cellule vide côté actif | Affichée, jamais remplacée. Sous 60 % de critères évalués : « données insuffisantes » |

Un critère inconnu n'est jamais comblé par une valeur inventée.

### 3.2 Appariement profil ↔ actif (`appariement.py`)

Les règles de `config/criteres_appariement.csv` sont des phrases. Leur traduction exécutable est déclarée dans `config/regles_appariement.json`, une entrée par ligne de la grille ; un test échoue si une ligne n'a pas d'entrée. Sept critères non posés par choix (A11, C3, D10, E3, F1, G4, G5) sont marqués « non codés » avec leur raison ; D10 s'applique par défaut.

Ordre des effets : **exclusion > budget de risque > plafond > préférence.**

1. **Exclusion.** Le verdict est « exclu ». Le score n'est pas calculé : une exclusion ne se compense jamais.
2. **Budget de risque.** Le risque ne se juge pas actif par actif : 92 actifs sur 111 dépassent 15 % de volatilité, et un profil prudent n'aurait presque rien. Pour un actif seul, le moteur calcule le **poids maximal compatible** : le plus petit de (0,8 × budget de perte ÷ perte maximale historique de l'actif) et des plafonds qui le concernent.
3. **Plafond.** Complexité, actif spéculatif ou très médiatisé face à un profil prudent, controverse moyenne, exposition au change.
4. **Préférence.** Satisfaite, neutre ou contraire.

**Score de 0 à 100** = 100 × Σ(poids × note) ÷ Σ(poids), sur les critères évalués. Poids de base : budget de risque 3, plafond 2, préférence 1. La grille ne contient aucune pondération : celle-ci est une hypothèse d'équipe.

**Pondération selon la personne**, calculée à partir de ses propres réponses : l'exigence ESG (E4) multiplie le poids des critères ESG (« préfère » × 1, « exige » × 2) ; le besoin de revenu (A10) multiplie celui du revenu ; une réponse « retenue » compte pour moitié.

**Une préférence ne compense jamais une tension.** Si un critère de risque ou de plafond est « en tension », le score est borné à 49 ; s'il est « à surveiller », à 69.

| Score | Verdict |
|---|---|
| 70 et plus | Compatible : l'écran dit pourquoi c'est adapté |
| 50 à 69 | À examiner : ce qui soutient, ce qui retient |
| Moins de 50 | Peu adapté : ce qui pose problème, sans jugement sur la personne |
| Exclusion dure | Exclu, quel que soit le reste |

### 3.3 Mini-portefeuille fictif (`portefeuille.py`)

Construction déterministe, sans bibliothèque d'optimisation, pour rester explicable.

1. Candidats : actifs compatibles dont le score atteint 80 (descente par paliers à 75 puis 70 s'il y en a trop peu, et l'écran le dit). Douze positions au plus.
2. Deux poches selon le rôle : amortisseur (liquidités, obligations) et croissance.
3. Sélection : jusqu'à trois fonds de cœur, un représentant par thème d'intérêt déclaré, puis les meilleurs scores, deux titres au plus par secteur.
4. Poids proportionnels au score (un fonds de cœur compte triple), rabotés par les plafonds ; l'excédent est redistribué.
5. La part de croissance part de la borne haute indicative du niveau de risque et descend par pas de 5 points jusqu'à respecter : perte de stress ≤ 0,8 × budget, volatilité ≤ plafond, durée sous l'eau ≤ limite. La contrainte qui a arrêté la descente est **nommée** à l'écran.
6. Si même la répartition la plus prudente dépasse une limite, le reste passe en fonds de liquidités, puis en **encaisse** (non investie, affichée et expliquée). Une part que les plafonds ne permettent pas de placer reste aussi en encaisse.
7. Un actif ajouté à la demande de la personne garde son poids ; le reste se réorganise autour de lui sous les mêmes plafonds.

**Vérification sur des profils aléatoires.** Les trois personas ne suffisent pas à éprouver un calcul. Un test tire 200 profils au hasard (réponses manquantes, incertaines, contradictoires) et exige, pour chaque portefeuille construit : aucun actif non compatible, aucun poids au-dessus du maximum, aucune limite dépassée, perte de stress sous le budget, encaisse expliquée. Ce test a révélé trois défauts de la première version, corrigés depuis : une part non investie sans explication, un budget de perte dépassé quand aucun actif défensif n'était accepté, et des refus sans diagnostic.

**Mesures**, sur les prix en CAD du 12 novembre 2021 au 12 novembre 2026, portefeuille rééquilibré chaque jour : volatilité annualisée, perte maximale, durée sous l'eau, rendement de 2022, pire mois, expositions effectives à travers les FNB.

**Perte de stress** = la pire de : perte maximale historique, perte de 2022, choc de taux de +2 points appliqué aux FNB obligataires par leur sensibilité mesurée. Un krach des actions de −45 % est affiché comme **scénario fictif**, hors de la tension.

**Tension** = perte de stress ÷ budget de perte. Moins de 0,8 : cohérent ; 0,8 à 1 : à surveiller ; plus de 1 : en tension. Elle est affichée en pourcentage et en dollars sur un montant fictif.

### 3.4 Demande d'un titre : verdict figé (`evaluer_demande`)

Cas de référence : Robert, tenté par un titre très médiatisé.

1. Le code réajuste le portefeuille autour du titre demandé et calcule le verdict : **le pire critère**, au niveau du portefeuille et du montant.
2. Le verdict reçoit un horodatage et une empreinte.
3. Le code détecte les incohérences entre la demande et le profil.
4. Seulement ensuite, la justification de la personne est lue et transmise à l'agent Explicateur.
5. Après la rédaction, le verdict est recalculé : il doit être identique.

Le texte de la justification n'est pas un paramètre du moteur : le verdict ne peut pas en dépendre. Un test le vérifie avec dix justifications, dont une tentative de détournement.

### 3.5 Parler au conseiller (`conversation.py`)

La personne écrit ou dit ce qu'elle aimerait ajouter. Le partage des rôles ne change pas.

| Étape | Qui | Ce qui se passe |
|---|---|---|
| Comprendre | Modèle (ou interprète à règles sans modèle) | Quel actif, quelle part, quelle envie ; choix de l'outil |
| Décider | Code | Ajout appliqué, part réduite proposée, ou refus |
| Proposer | Code | Alternatives compatibles : fonds qui détient le titre, même thème, même secteur |
| Revoir le profil | Code, après accord explicite | Les réponses déclarées à revoir sont nommées ; rien n'est appliqué sans « oui » |
| Expliquer | Code + sélection du modèle | Les verdicts et confirmations sont imposés par le code ; le modèle choisit seulement des détails autorisés, sans prose financière libre |

Trois garde-fous propres à la conversation :

- **Ce qui est mesuré ne se déclare pas.** Le replay, les fourchettes et le quiz ne peuvent pas être revus dans la conversation. Robert peut relever un plafond qu'il avait déclaré ; son budget de perte, tiré de son comportement observé, ne bouge pas.
- **Une promesse est vérifiée avant d'être faite.** Avant de dire « il faudrait revoir telle réponse », le code rejoue l'ajout sur le profil modifié.
- **Le profil d'origine est conservé.** Les réponses mises à jour sont gardées à part, affichées, et s'annulent d'un clic.

À l'oral, la demande passe par Amazon Transcribe et la réponse par Amazon Polly, comme pour l'entretien.

### 3.6 Recherche, comparaison, « Et si… ? » (`analyse.py`)

- **Recherche** par ticker ou par nom, sans accents ni casse. Un actif absent de l'univers reçoit la réponse « absent », jamais une évaluation.
- **Comparaison** critère par critère. L'**écart décisif** est le premier critère qui diffère, dans l'ordre exclusion, budget de risque, plafond, préférence.
- **« Et si… ? »** : une réponse est modifiée dans une copie du profil, tout est recalculé, et chaque changement nomme la règle en cause. Le profil enregistré n'est pas touché.
- **Sensibilité** : horizon d'un cran, seuils du score à ± 5, seuil de tension à 0,7 et 0,9, période sans 2022. Ce n'est ni un intervalle de confiance ni une prévision.

### 3.7 L'univers peut changer

Le moteur relit l'univers à chaque démarrage (`donnees/actifs.csv`, copie de `data_extended/asset_criteria.csv`). Aucun ticker ni nombre d'actifs n'est écrit dans le code. Pour ajouter un actif : l'ajouter aux données, relancer `python scripts/build_donnees_recommandation.py`, pousser. Un test ajoute un actif, en retire trois, insère une ligne incomplète et retire une colonne requise.

## 4. Démarche agentique

| Composant | Type | Pourquoi il existe | Outils |
|---|---|---|---|
| Entretien, classificateur, critique, découvreur, chercheur | Modèles (Haiku 5.5) | Établir le profil à partir de paroles, avec citation exacte | Partie profil |
| **Conseiller** | Modèle à outils (Sonnet 5.5) | Comprendre une demande en langage courant, choisir l'outil, résumer | Conversation : `ajouter_au_portefeuille`, `chercher_par_envie`, `retirer_du_portefeuille`, `proposer_mise_a_jour_du_profil`, `confirmer`, `refuser`, `annuler_les_mises_a_jour`, `voir_le_portefeuille`. Résumé : `lire_contraintes`, `construire_portefeuille`, `et_si`, `tester_sensibilite` |
| **Explicateur** | Modèle à outils (Sonnet 5.5) | Répondre à « pourquoi ? » à partir d'un verdict déjà figé, et refuser ce que les données ne soutiennent pas | `lire_contraintes`, `chercher_actif`, `comparer_actifs`, `evaluer_demande`, `lire_preuve` |
| Détecteur d'incohérence | Code | Relever une demande contraire au profil avant toute rédaction | — |
| Vérificateur de fidélité | Code | Empêcher un chiffre inventé d'atteindre l'écran | — |
| Mises en situation | Code | Mesurer le comportement ; ce n'est pas un agent | — |

Deux agents à modèle seulement pour la recommandation. Le détecteur et le vérificateur sont du code et présentés comme tels.

**Points de contrôle de la restitution**, dans l'ordre :

1. **Contrat fermé.** Le modèle renvoie uniquement des identifiants de détails présents dans le catalogue courant. Le code conserve tous les verdicts, limites, avertissements et confirmations, même si aucun détail facultatif n'est sélectionné. Tout champ libre, identifiant inconnu ou doublon invalide la sortie. Les actions conversationnelles sont restituées intégralement par le code.
2. **Fidélité et gouvernance.** Les nombres affichés sont comparés aux sorties d'outils ; des regex détectent des formulations interdites connues. Ces regex restent un filet partiel, pas un vérificateur sémantique général.
3. **Guardrail Bedrock**, s'il est activé.

Une sortie rejetée est redemandée une fois, puis le code utilise son gabarit à partir des seules sorties d'outils. La mention « simulation » est ajoutée par le code. La trace distingue rédaction par le code et sélection par le modèle ; aucune prose libre du modèle ne remplace les résultats financiers.

**Explications fidèles aux actions observables.** L'affichage courant est sobre : phrases en clair et sources (donnée, valeur, date, origine). Le réglage « Détails techniques » montre, pour qui veut vérifier, les outils appelés, leurs entrées et sorties, le contrôle de chaque texte et le journal des actions. Le raisonnement interne du modèle n'est ni affiché ni journalisé.

**Pourquoi pas des agents de A à Z ?** Nous l'avons essayé : Sonnet 5.5 a construit seul neuf portefeuilles (trois par persona) à partir du profil et de l'univers complet. Il respecte les contraintes écrites, mais dépasse dans trois cas sur neuf une règle qu'on ne lui avait pas rappelée, estime sa perte de stress à 5,5 points près, ne redonne pas les mêmes poids d'un essai à l'autre et met 14 à 29 secondes. Le compte rendu, régénérable, est dans `docs/experience_modele_seul.md`. D'où le partage retenu : les règles pour ce qui doit être exact, les agents pour comprendre, expliquer et refuser.

## 5. Exemple : d'une conclusion à la donnée

Robert (59 ans, risque faible à modéré, 3 à 5 ans) demande 20 % de NVIDIA dans son portefeuille fictif. Dans la conversation, l'outil refuse 20 %, propose 5 %, et n'ajoute rien avant son accord.

| Étape | Action observable | Résultat |
|---|---|---|
| 1 | `verdict_fige` | « En tension avec le profil », horodaté, empreinte calculée |
| 2 | `incoherence` | Demande contraire aux plafonds du profil |
| 3 | `justification_recue` | « Tout le monde en parle… » |
| 4 | `controle_texte` | Chiffres du texte retrouvés dans les sorties d'outils |
| 5 | `verdict_reverifie` | Inchangé |

| Conclusion affichée | Preuve | Origine |
|---|---|---|
| Part demandée de 20 % au-dessus du plafond par titre de 5 % | `profil:D9` | Réponse du profil (simulée pour le persona) |
| Placements spéculatifs : 20 % pour une limite de 5 % | `profil:D12`, `actif:NVDA:speculative` | Profil ; volatilité de 51,0 % (≥ 45 %) |
| À 20 %, perte de stress de 5,3 % à 18,4 %, budget de 15 % ; à 5 %, de 5,3 % à 8,4 % | `calcul:demande:perte_stress_apres` | Prix en CAD, 2021-11-15 au 2026-11-12 |
| Actif très médiatisé face à un profil de niveau 2 | `actif:NVDA:kw_attention`, `profil:D8` | Pages vues Wikipédia ; réponse du profil |
| Part maximale compatible : 5 % | `hypothese:tension`, `profil:D9` | Seuils écrits |

À 5 %, la même demande devient « à surveiller » : compatible avec les plafonds, sans acquiescement. Pour Amira (risque élevé, 15 ans ou plus), 5 % de NVIDIA est « cohérent », avec un maximum de 10 %. Pour Mateo, le titre est exclu : il refuse tout placement spéculatif. Le tableau complet est régénéré par `python scripts/tableau_personas.py` (`docs/resultats_personas.md`).

## 6. Données, sources et licences

| Famille | Source | Conditions |
|---|---|---|
| Prix, dividendes, fondamentaux, fiches de fonds, actualités | Yahoo Finance par yfinance | Conditions d'utilisation de Yahoo : usage personnel, redistribution limitée |
| Change | Banque du Canada (Valet) | Conditions de la Banque du Canada |
| Taux et macro | Banque du Canada, FRED et ALFRED | Conditions de chaque source |
| Attention médiatique | Wikimedia Pageviews | CC0 |
| Indice Jantzi Social | BlackRock Canada (positions de XEN) | Conditions de BlackRock |
| Controverses, exclusions, thèmes, accès | Recherche et saisie manuelles de l'équipe, sources citées | Liste non exhaustive |

**Point de licence à trancher par l'équipe.** Les conditions de Yahoo limitent la redistribution des données brutes. Le dépôt contient ces fichiers pour que le jury puisse reproduire les calculs ; l'alternative est de ne remettre que les scripts et les indicateurs dérivés.

Chaque colonne d'actif est reliée à son fichier, sa source, sa date et ses conditions dans `config/sources_colonnes.json` ; c'est ce que le registre de preuves affiche.

**Traitements.** Tout est converti en CAD. Corrections documentées dans les `README` de données : sous-unités (pence, cents sud-africains), deux jours à prix cent fois trop petits, faux fractionnements. Aucun remplissage de données manquantes au-delà de cinq jours ouvrables pour aligner les calendriers.

Les exercices rentables sont comptés à partir de `Net Income`, jamais du signe du ROE. Lorsque les capitaux propres sont non positifs ou inconnus, ROE et dette/capitaux propres deviennent non interprétables ; un ancien ratio valide n'est pas repris silencieusement à leur place. Les versions des dépendances testées sont fixées dans `mvp_profil/constraints.txt`.

**Cohérence temporelle.** La recommandation décrit l'univers à la date des données ; elle ne rejoue aucune décision passée, donc n'utilise aucune information « du futur ». Pour une simulation historique, la règle retenue par l'équipe est : publication = fin d'exercice + 90 jours.

## 7. Hypothèses

Tous les seuils sont des hypothèses d'équipe, écrites et ajustables. Aucun n'est une norme publiée.

| Fichier | Contenu |
|---|---|
| `config/hypotheses_recommandation.json` | Bandes du score, bornes, pondération, multiplicateurs, plafonds par défaut, règles du portefeuille, scénarios de stress |
| `mvp_profil/hypotheses_profil.json` | Capacité par horizon, perte maximale par niveau, réglages prudents |
| `config/seuils_criteres.json` | Seuils de calcul des mots-clés des actifs |

Hypothèses de calcul à connaître : rééquilibrage quotidien ; plafond de 40 % par secteur et de 25 % sur le secteur de l'emploi (exemple chiffré de la grille) ; plafond de 40 % par fonds ; plafond de 10 % pour un groupe « à limiter » sans chiffre.

## 8. Validations

| Suite | Ce qu'elle vérifie |
|---|---|
| `mvp_profil/test_reco_contrat.py` | Chaque ligne de la grille a une règle ; chaque libellé du profil a un pendant côté actif ; états explicites ; univers variable ; données embarquées à jour ; paquet complet |
| `mvp_profil/test_reco_moteur.py` | Exclusions non compensables, bornes du score, preuves ; portefeuilles des trois personas ; encaisse et ajouts ; **200 profils aléatoires** ; demande de titre ; recherche ; comparaison ; « Et si… ? » ; déterminisme |
| `mvp_profil/test_reco_conversation.py` | Part réduite proposée puis appliquée ; exclusions tenues ; alternatives toujours compatibles ; profil mis à jour seulement après accord ; réponses mesurées protégées ; modèle sans pouvoir de décision |
| `mvp_profil/test_reco_agents.py` | Fidélité des chiffres ; dix justifications sans effet sur le verdict ; ordre de la trace ; gabarits fidèles ; rejets et secours ; gouvernance |
| `mvp_profil/test_reco_interface.py` | Le site entier dans `app.py` : de la synthèse aux six écrans, pour les trois personas ; recherche ; demande ; sensibilité ; profil jamais modifié |
| 21 suites du profil et des données | Toujours vertes |

```bash
python scripts/lancer_tests.py
```

Le lanceur découvre aussi les cinq suites de recommandation ; l'intégration continue les exécute avant chaque déploiement.

**Vérifications historiques sur Amazon Bedrock le 15 novembre 2026, antérieures au nouveau contrat de restitution** : les notes précédentes documentent des appels d'outils, six messages types et des essais du Guardrail. Ces résultats et délais ne valident pas le nouveau contrat fermé. Celui-ci est vérifié localement avec des modèles simulés ; il reste à mesurer sur les vrais modèles et le serveur.

**Non vérifié** : le parcours complet avec le modèle réel depuis le serveur déployé (les agents n'ont tourné dans l'application qu'avec un modèle simulé) ; la fiabilité du classement des réponses libres (mesure prête, non lancée) ; l'exactitude des liens de controverses.

## 9. Intégration AWS

| Service | Rôle concret | Entrée → sortie | Alternative écartée | État |
|---|---|---|---|---|
| EC2 | Héberge l'application Streamlit | Requêtes → pages | Fargate : plus long à mettre en place | En service |
| CloudFront | HTTPS, exigé par le micro du navigateur | Navigateur → serveur | Certificat sur l'instance : domaine requis | En service |
| S3 | Paquet du site | Fichier → objet | Disque de l'instance : rien de reproductible | En service |
| IAM | Privilèges minimaux : un modèle, une table, un Guardrail | — | Rôle large | En service, étendu |
| Transcribe, Polly | Voix de l'entretien | Audio ↔ texte | — | En service |
| Bedrock, Haiku 5.5 | Entretien et classement | Paroles → critères | — | En service |
| Bedrock, Sonnet 5.5 | Conseiller et Explicateur à outils | Demande + sorties d'outils → texte | Haiku : moins sûr sur l'enchaînement d'outils | Droits accordés, vérifié |
| Bedrock Guardrails | Bloque conseil personnalisé et prédiction, masque des données personnelles | Texte → accepté ou bloqué | Consigne seule : non vérifiable | Créé, désactivé par défaut |
| DynamoDB | Journal des actions : verdicts figés, appels d'outils, contrôles | Action → ligne horodatée | Fichier local : perdu au redémarrage, ordre non prouvable | Créé, vérifié |
| Cognito | Accès du jury par identifiant et mot de passe | Identifiants → accès | Filtre par adresse IP : inutilisable pour un jury | Groupe créé, non branché au site |
| CloudFormation | Ajouts reproductibles et réversibles (`infra/alphaforge-recommandation.yaml`) | Gabarit → ressources | CDK : non initialisé dans le compte | Pile déployée |
| Systems Manager, GitHub Actions (OIDC) | Déploiement à chaque fusion dans `main`, avec vérification et retour arrière | Paquet vérifié → site en service | Déploiement manuel | En service |
| AWS Budgets | Suivi du coût | Seuil → suivi | — | Créé |

**Écartés, faute de rôle réel** : Step Functions (aucun enchaînement de fonctions), Knowledge Bases (les preuves sont des colonnes datées, pas des documents), AgentCore, API Gateway, Glue. **Lambda** : la permission est prouvée, mais les outils tournent dans le serveur ; les déplacer en Lambda n'aurait rien changé au résultat, seulement ajouté un point de panne.

## 10. Encadrement responsable

| Exigence | Mécanisme |
|---|---|
| Simulation uniquement | Aucune fonction d'exécution d'ordre n'existe ; mention sur chaque écran et à la fin de chaque réponse, ajoutée par le code |
| Aucun conseil personnalisé | Formulations « cohérent avec le profil saisi », « plafonné à » ; contrôle de gouvernance ; Guardrail |
| Aucune prédiction | Les rendements passés ne servent qu'à décrire, avec leur période ; refus vérifié en réel |
| Données manquantes visibles | État affiché, part des critères évalués sur chaque fiche |
| Faits, hypothèses, scénarios | Étiquette sur chaque mesure de stress et chaque preuve |
| Pas de données de clients | Trois personas fictifs de l'énoncé |
| Raisonnement interne non exposé | Seules les actions observables sont affichées et journalisées |

## 11. Limites

- **Une seule crise dans la fenêtre.** 2021-2026 contient surtout 2022 : la perte historique sous-estime le risque d'un portefeuille riche en actions. Le scénario fictif de krach le rappelle ; il n'entre pas dans la tension.
- **Mesure dans l'échantillon.** Les mots-clés des actifs et les mesures du portefeuille portent sur la même période.
- **Biais du survivant.** L'univers a été choisi en 2026.
- **Personas.** Leurs 42 réponses sont simulées à partir de l'énoncé : elles illustrent le fonctionnement, elles ne décrivent pas de vraies personnes. Pour un profil réel incomplet, une durée de récupération issue d'un réglage par défaut est signalée « à confirmer » et ne bloque pas la construction.
- **Pondération du score.** Hypothèse d'équipe, non calibrée sur des décisions réelles. Les scores se regroupent sur peu de valeurs.
- **Portefeuille.** Heuristique explicable, pas une optimisation. Les portefeuilles restent loin du budget de perte (tension de 0,4 à 0,6) : la part de croissance est bornée par la part d'actions indicative du profil. Dans notre expérience, le modèle seul utilisait mieux le budget d'Amira.
- **Conversation sans modèle.** L'interprète à règles comprend un nom d'actif, une part, une envie simple, oui et non ; il ne comprend pas une phrase complexe.
- **Mises à jour du profil.** Elles vivent dans les propositions : la synthèse et l'export du profil gardent les réponses d'origine.
- **FNB.** Seules les dix premières positions et la répartition sectorielle sont connues.
- **Exclusions et controverses.** Saisies à la main, non exhaustives : « aucune trouvée » ne veut pas dire « aucune ».
- **Régions.** L'Amérique latine et le Moyen-Orient n'existent pas dans le critère D3 du profil.
- **Vérificateur de fidélité.** Son contrôle numérique ne juge pas le sens des phrases. La restitution financière utilise donc des fragments rédigés par le code et des verdicts obligatoires ; la qualité des règles et données doit encore être validée.
- **Guardrail.** Il bloque aussi certains refus de prédiction et reste désactivé par défaut. Les regex du code ne lui sont pas équivalentes ; le contrat fermé empêche la substitution d'une prose financière libre.
- **Modèle des agents.** Les deux agents passent par Amazon Bedrock ; avec une clé Anthropic seule (réglage local du profil), les textes viennent des gabarits.
- **Résidence des données.** Région `us-east-1` et profil d'inférence américain.

## 12. Améliorations envisagées

Historique long et scénarios de stress calibrés ; positions complètes des FNB ; pondération validée avec des planificateurs financiers ; mesure de la fiabilité des agents sur un jeu annoté ; outils des agents en fonctions isolées et tracées ; résidence canadienne des données.
