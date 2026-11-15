# Grille de critères : profil de l'investisseur ↔ actifs

Version du 15 novembre 2026. Simulation éducative : cette grille sert à expliquer une compatibilité, pas à donner un conseil financier.

Ce document est **généré à partir des fichiers du dépôt** : les tableaux de critères viennent de [criteres_appariement.csv](../config/criteres_appariement.csv), les chiffres de [asset_criteria.csv](../data_extended/asset_criteria.csv).

## Principe

Chaque critère existe des deux côtés :

- **Côté profil** : une question, dont la réponse est rangée dans une liste fermée de valeurs ([criteres.py](../mvp_profil/criteres.py), source de vérité).
- **Côté actif** : une valeur calculée par du code à partir de données datées, pour chacun des 66 actifs.
- **Entre les deux** : une règle écrite à l'avance, et une table de correspondance de vocabulaire ([correspondances.json](../config/correspondances.json)).

Deux niveaux de vérification, à ne pas confondre :

| Niveau | Ce qu'on y vérifie | Critères |
|---|---|---|
| **Portefeuille** | Le risque : perte de stress, volatilité, durée sous l'eau, concentration | A2, A5, A9, B1, B5, B7, D2, D9, D12 |
| **Actif** | Les exclusions, l'accès, la complexité, les préférences | D1, D6, E1, E2, E5, F2, G3, C1, D5, D7 |

Juger le risque actif par actif ne fonctionne pas : 59 actifs sur 66 ont une volatilité de 15 % ou plus. Un profil prudent n'aurait alors presque rien, alors qu'un portefeuille 30 % ZST, 40 % XBB, 30 % XEQT a une volatilité de 5,3 % et une perte maximale de 11,2 % sur 2021-2026.

Types de règle :

| Type | Effet |
|---|---|
| `exclusion` | L'actif est retiré |
| `plafond` | Poids ou niveau maximal |
| `seuil` | Comparaison chiffrée : cohérent, à surveiller, en tension |
| `preference` | Trie les suggestions ; n'améliore jamais la compatibilité |
| `calcul_capacite` | Entre dans la synthèse du profil |
| `information` | Affiché, sans effet sur le verdict |
| `controle` | Vérification de gouvernance |

## Du profil au budget de perte

La synthèse ([synthese.py](../mvp_profil/synthese.py)) résume le profil en un **budget de perte du portefeuille**, le plus prudent de trois composantes :

| Composante | Critères | Calcul |
|---|---|---|
| Capacité | A2, A4, A5, A6, A7, A8 | L'horizon fixe un plafond de 1 à 5 ; un cran en moins par fragilité ; dettes à taux élevé : plafond 1 |
| Tolérance déclarée | B1, B1R, B3 | Point de rupture déclaré, en % ; une classe de moins sans expérience d'une baisse |
| Tolérance observée | B2, B6 | Perte réelle au moment de « Tout vendre » au replay ; portefeuille choisi dans les fourchettes |

Le niveau de 1 à 5 est une étiquette lisible ; le moteur utilise le budget. Toutes les tables sont des **hypothèses** de l'équipe, dans [hypotheses_profil.json](../mvp_profil/hypotheses_profil.json).

| Persona (énoncé) | Niveau | Budget de perte | Limité par |
|---|---|---|---|
| Robert, 3 à 5 ans, risque faible à modéré | 2 sur 5 | 15 % | capacité, tolérance observée |
| Mateo, 8 à 12 ans, risque modéré | 3 sur 5 | 22 % | capacité, tolérance observée |
| Amira, 15 ans ou plus, risque élevé | 5 sur 5 | 45 % | capacité, tolérance observée |

Ces résultats dépendent des valeurs « hypothèse de test » des personas ([personas/](../mvp_profil/personas/)) et se reproduisent avec `python mvp_profil/test_synthese.py`.

## Les critères


### Situation et capacité

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| A1 | Âge et étape de vie | posé | etudes, debut_carriere, milieu_carriere, pre_retraite, retraite | (aucun : entre dans la capacité) | Sert à vérifier la cohérence de l'horizon et la capacité à reconstituer des pertes | `calcul_capacite` |
| A2 | Horizon de placement | posé | moins_3_ans, 3_5_ans, 5_10_ans, 10_15_ans, plus_15_ans | horizon_min_years, recovery_days, kw_recuperation | Vérifié sur le PORTEFEUILLE (pas actif par actif) : l'horizon fixe le plafond de capacité (hypotheses_profil.json), donc le budget de perte ; horizon_min_years reste une information par actif | `seuil` |
| A3 | Objectif principal | posé | coussin_securite, projet_date, retraite, revenu, croissance, transmission | role, kw_cycle | coussin_securite : rôle liquidites seulement ; projet_date : liquidites et obligations_amortisseur près de l'échéance ; revenu : préférence satellite_revenu ; croissance : tous les rôles dans les plafonds | `plafond` |
| A4 | Part de l'épargne totale | posé | faible_moins_25, moyenne_25_60, forte_plus_60 | stress_loss | Avec l'horizon : table de capacité qui fixe la perte maximale supportable | `calcul_capacite` |
| A5 | Fonds d'urgence | posé | aucun, moins_3_mois, 3_6_mois, plus_6_mois | (contrôle) | Moins de 3 mois : un cran de capacité en moins ; aucun : alerte et niveau plafonné à 2 (niveau du portefeuille) | `calcul_capacite` |
| A6 | Stabilité des revenus | posé | stables, variables, incertains, retraite | (aucun : capacité) | Revenus incertains : perte supportable réduite d'un cran | `calcul_capacite` |
| A7 | Dettes à taux élevé | posé | oui, non | (contrôle) | Oui : alerte « rembourser avant d'investir » ; le système ne propose rien de risqué | `calcul_capacite` |
| A8 | Personnes à charge | posé | 0, 1_2, 3_plus | (aucun : capacité) | Personnes à charge : perte supportable réduite d'un cran | `calcul_capacite` |
| A9 | Retraits prévus | posé | aucun, ponctuel, reguliers | liquidity_level, stress_loss | Montant à retirer dans moins de 3 ans : poche réservée de rôle liquidites ou obligations_amortisseur | `plafond` |
| A10 | Besoin de revenu régulier | posé | non, souhaite, essentiel | dividend_yield_ttm, income_asset, kw_rendement_dividende, kw_dividende_durabilite, kw_distribution | souhaite : préférence pour income_asset ; essentiel : exclure les actifs avec baisse de dividende ou dividendes > flux libres | `preference` |
| A11 | Patrimoine hors portefeuille | non posé | proprietaire oui/non, regime_pd oui/non | (aucun : capacité) | Patrimoine stable important : perte supportable augmentée d'un cran au maximum | `calcul_capacite` |
| A12 | Secteur d'emploi (capital humain) | posé | technologie, sante, finance, energie, industrie, commerce, education, fonction_publique, telecoms, immobili… | sector | Plafond plus bas sur le secteur de l'emploi (ex. 25 % au lieu de 40 %) : un choc sectoriel toucherait à la fois l'emploi et le portefeuille | `plafond` |

### Tolérance au risque

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| B1R | Réaction déclarée à une baisse de 20 % | posé | vendre_tout, vendre_partie, attendre, acheter_plus | (profil seulement) | vendre_tout : la tolérance déclarée est plafonnée à −20 % ; contradiction avec B1 : question de clarification (R1, R1b) | `calcul_capacite` |
| B1 | Point de rupture déclaré | posé | 5, 10, 20, 30, 40, 50_plus, jamais | stress_loss (portefeuille), kw_perte_max_historique | Vérifié sur le PORTEFEUILLE (pas actif par actif) : tension = perte de stress du portefeuille ÷ budget de perte (synthese.py) : <0,8 cohérent ; 0,8-1 à surveiller ; >1 en tension | `seuil` |
| B2 | Point de rupture observé (replay 2022) | mesuré | 5, 10, 20, 30, 40, 50_plus, non_atteint | return_2022, max_drawdown, kw_choc_2022 | Comparé à B1 : le plus prudent est retenu automatiquement ; écart >= 2 classes : H1 = grand (profil incertain sur ce point) | `seuil` |
| B3 | Expérience d'une forte baisse | posé | jamais, oui_garde, oui_vendu, oui_renforce | (confiance du profil) | Jamais ou oui_vendu : le point de rupture déclaré est moins fiable et reçoit une décote | `calcul_capacite` |
| B4 | Fréquence de consultation | posé | quotidienne, hebdomadaire, mensuelle, rarement | var95_daily, worst_month, vol_cad | Consultation quotidienne et classe >= 6 : avertissement (myopie face aux pertes, Gneezy et Potters 1997) | `information` |
| B5 | Inconfort face aux variations | posé | faible_moins_8, moderee_8_15, elevee_15_25, tres_elevee_plus_25 | kw_volatilite, risk_class | Vérifié sur le PORTEFEUILLE (pas actif par actif) : volatilité du portefeuille <= plafond de la classe acceptée (8, 15, 25 %) | `plafond` |
| B6 | Arbitrage risque/rendement choisi (fourchettes) | mesuré | prudent, equilibre, dynamique | risk_class, kw_volatilite | Contradiction avec B5 (ex. prudent choisi mais volatilité élevée déclarée) : question de clarification (R8) | `seuil` |
| B7 | Durée de récupération supportable | posé | rapide_moins_1_an, moyenne_1_2_ans, longue_plus_2_ans | kw_recuperation, recovery_days | Vérifié sur le PORTEFEUILLE (pas actif par actif) : durée sous l'eau du portefeuille <= durée supportable ; kw_recuperation (du sommet au retour) reste une information par actif ; baisse_en_cours et jamais_recupere sont signalés | `seuil` |

### Connaissances

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| C1 | Connaissances financières | mesuré | debutant, intermediaire, avance | complexity | complexity de l'actif <= score du quiz + 1 (score 0 : complexité 1 seulement) ; le score est gardé avec le niveau | `plafond` |
| C2 | Produits déjà détenus | posé | aucun, fonds_communs, fnb, actions, obligations, crypto | asset_class, complexity | Première détention d'une classe complexe : avertissement pédagogique | `information` |
| C3 | Comprendre le modèle d'affaires | non posé | essentiel, souhaite, indifferent | complexity, themes (holding) | essentiel : exclure complexity 3 et holdings ; souhaite : préférence pour complexity 1 | `preference` |

### Préférences d'exposition

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| D1 | Classes d'actifs | posé | actions, fnb_actions, obligations, or, crypto | asset_class | Classe refusée : exclusion | `exclusion` |
| D2 | Plafond crypto | posé | 0, 5, 10, 20 | asset_class = crypto | Plafond de poids ; 0 % = exclusion | `plafond` |
| D3 | Régions | posé | canada, etats_unis, europe, asie, afrique, emergents, monde | region, country | Région exclue : exclusion ; préférence : tri des suggestions | `preference` |
| D4 | Devise et risque de change | posé | cad_seulement, limite, accepte | kw_devise, fx_risk, fx_vol_contribution | cad_seulement : plafond sur la part hors CAD ; limite : plafond et avertissement si fx_risk notable ; usd_couvert signalé | `plafond` |
| D5 | Thèmes et secteurs d'intérêt | posé | ia, semi-conducteurs, logiciel, sante, energie_fossile, banque, assurance, luxe, vehicule_electrique, or, c… | themes, sector | Tri des suggestions et inclinaison dans les plafonds ; n'améliore JAMAIS la compatibilité | `preference` |
| D6 | Thèmes et secteurs à éviter | posé | ia, semi-conducteurs, logiciel, sante, energie_fossile, banque, assurance, luxe, vehicule_electrique, or, c… | themes, sector | Exclusion | `exclusion` |
| D7 | Style recherché | posé | croissance, etablie, dividende, indifferent | growth, established, income_asset, kw_sante_financiere, kw_capitalisation, kw_croissance_resultats | Préférence ; « établie » forte : exclure speculative | `preference` |
| D8 | Attrait pour la spéculation et les titres médiatisés | posé | non, parfois, oui | speculative, media_hype, kw_attention (très médiatisé, variation récente extrême, pic de volume anormal) | Profil faible ou modéré + actif spéculatif ou très médiatisé : avertissement explicite, sans acquiescer | `plafond` |
| D9 | Concentration acceptée | posé | 5, 10, 20 | kw_concentration (portefeuille) | Poids par titre et par secteur plafonnés | `plafond` |
| D10 | Recherche de diversification | non posé | essentielle, souhaitee, secondaire | corr_vt_weekly, kw_diversification, kw_beta | Préférence pour les actifs peu corrélés ; contrôle de la corrélation moyenne du portefeuille | `preference` |
| D11 | Gestion passive ou titres individuels | posé | fnb, titres, mixte | asset_class | Préférence | `preference` |
| D12 | Tolérance aux placements spéculatifs | posé | sans_speculatif, plafonne_5, plafonne_10, accepte | speculative | Somme des poids des actifs speculative <= plafond ; sans_speculatif : exclusion | `plafond` |
| D8O | Attrait observé pour un titre médiatisé (test) | mesuré | non, oui | media_hype, kw_attention, speculative | Déclaré « pas tenté » (D8) mais titre médiatisé choisi : question de clarification (R9), possibilité de plafonner le spéculatif à 5 % | `controle` |

### Valeurs et durabilité

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| E1 | Énergies fossiles | posé | exclure_directe, exclure_toute_implication, limiter, indifferent | fossil_involvement, kw_exclusions (energie_fossile) | Voir config/correspondances.json (E1) : exclusion par fossil_categorie ; les FNB exposés (energie_fossile_via_fonds) sont plafonnés, pas exclus | `exclusion` |
| E2 | Controverses | posé | aucune, pas_de_grave, indifferent | max_severity, controversy_topics | pas_de_grave : exclure « élevée » et signaler « moyenne » avec la source | `exclusion` |
| E3 | Priorité environnement / social / gouvernance | non posé | E, S, G, egal | Pilier de chaque controverse | Tri et explication ; une controverse sur le pilier prioritaire passe de « signaler » à « exclure » | `preference` |
| E4 | Approche ESG | posé | non_requis, prefere, exige, meilleurs_categorie | in_jantzi_social_index, fossil_involvement, max_severity | Montre le désaccord entre méthodes (ex. Enbridge et CNQ dans l'indice Jantzi) | `information` |
| E5 | Autres exclusions | posé | contrats_de_defense, armes, alcool, tabac, jeux_argent, tests_sur_animaux, energie_nucleaire, atteinte_droi… | kw_exclusions | Valeur exclue présente dans kw_exclusions : exclusion. Implications connues seulement (liste non exhaustive, seuil de revenus non disponible) | `exclusion` |

### Contexte économique

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| F1 | Inquiétude face à l'inflation et aux taux | non posé | oui, non | return_2022, rate_sensitivity, kw_sensibilite_macro, kw_protection_inflation | Oui : signaler les actifs « baisse si les taux montent » et montrer leur comportement en 2022 | `information` |
| F2 | Risque pays et devise instable | posé | exclure_chine, exclure_emergents, exclure_devise_instable, aucune | kw_risque_pays, country | Voir config/correspondances.json (F2) : exclure_emergents exclut marche_emergent et exposition_chine, plafonne marche_emergent_partiel | `exclusion` |

### Contraintes pratiques

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| G1 | Montant investi | posé | moins_5000, 5000_25000, 25000_100000, plus_100000 | unit_price_cad, high_unit_price | Prix unitaire > 5 % du montant : avertissement (fractions d'actions nécessaires, poids difficile à respecter) | `information` |
| G2 | Type de compte | posé | celi, reer, non_enregistre, ne_sait_pas | kw_fiscalite, foreign_dividend_withholding, dividend_yield_ttm | Information : retenue d'impôt étrangère sur les dividendes (non récupérable en CELI) ; pas un conseil fiscal | `information` |
| G3 | Accès aux bourses étrangères | posé | canada_usa, international, je_ne_sais_pas | access_canada | canada_usa : exclure les actifs non accessibles et proposer le FNB régional ou l'ADR | `exclusion` |
| G4 | Sensibilité aux frais | non posé | <0,25 %, <0,50 %, indifferent | etf_expense_ratio, kw_frais | Frais au-delà du seuil : exclusion du FNB | `plafond` |
| G5 | Temps de suivi | non posé | <1 h, 1-5 h, >5 h | asset_class, complexity | Peu de temps : préférence pour les FNB et la complexité 1 | `preference` |

### Cohérence et gouvernance

| # | Critère | État | Valeurs du profil | Critère de l'actif | Règle | Type |
|---|---|---|---|---|---|---|
| H1 | Écart entre déclaré et observé | mesuré | aucun, faible, grand, non_teste | (contrôle) | Écart fort : profil incertain et réglage le plus prudent | `controle` |
| H2 | Demande d'un titre précis | calculé | Ticker et montant | Tous les critères d'actif | Verdict = pire critère, figé avant de lire la justification de l'utilisateur | `controle` |
| H3 | Informations manquantes | calculé | Réponses absentes ou ambiguës | (contrôle) | Question de relance ; à défaut, « données insuffisantes » et réglage prudent | `controle` |

**Non posés, par choix** : A11, C3, D10, E3, F1, G4, G5. A11, C3, E3 et G5 ont un effet marginal ou font doublon ; D10 s'applique par défaut ; G4 ne départage rien (tous les FNB de l'univers coûtent 0,40 % ou moins) ; F1 reste une information.

## Correspondances de vocabulaire

[correspondances.json](../config/correspondances.json) relie chaque valeur du profil à une colonne d'actif. `python scripts/test_grille.py` échoue si une valeur du profil n'a ni correspondance, ni mention « aucun actif ».

| Valeur du profil sans actif dans l'univers | Conséquence |
|---|---|
| Thèmes : immobilier, armes, tabac, jeux d'argent | L'outil doit le dire, au lieu de laisser croire qu'un filtre agit |
| Exclusions E5 : armes, tabac, jeux d'argent, énergie nucléaire | Même chose. Ces activités ne sont pas mesurées à l'intérieur des FNB : seules leurs 10 premières positions sont connues |

## Comment les critères d'actif sont calculés

| Critère | Calcul |
|---|---|
| `risk_class` | Volatilité annualisée en CAD, bandes de type SRRI 1 à 7 |
| `underwater_days`, `kw_recuperation` | Jours du **sommet** qui précède la pire baisse jusqu'au retour à ce sommet. Sans retour : `baisse_en_cours` si le creux a moins de 12 mois, sinon `jamais_recupere` |
| `horizon_min_years` | Par classe de risque ; +2 ans seulement pour `jamais_recupere` |
| `role` | `liquidites` (obligataire, volatilité ≤ 2 %), `obligations_amortisseur` (≤ 8 %), `obligations_longues`, `coeur` (FNB d'actions), `couverture` (or), `speculatif`, puis `satellite_revenu`, `satellite_defensif`, `satellite_croissance`, `satellite` |
| `liquidity_level` | Valeur échangée par jour sur 12 mois ; `elevee` pour tout FNB indiciel (liquidité des titres sous-jacents) |
| `complexity` | 1 : FNB larges et obligataires, actions ; 2 : or, obligations longues ; 3 : cryptoactifs, holding à étages, devise instable |
| `speculative` | Cryptoactif, ou volatilité ≥ 45 %, ou perte maximale ≥ 60 % |
| `income_asset` | Rendement ≥ 3 %, pas de baisse réelle du dividende, non spéculatif |
| `dividend_cut_2022_2025` | Actions seulement : le total annuel baisse de plus de 20 % face aux deux années précédentes |
| `established` | Action rentable au moins 75 % des exercices publiés, non spéculative |
| `diversifier_vs_world` | Corrélation avec VT ≤ 0,30, non spéculatif, et pas pire que VT en 2022 |
| `media_hype` | Notoriété relative à l'univers (audience Wikipédia) ; ce n'est pas l'emballement |
| `hype_recent` | Audience des 30 derniers jours ≥ 1,5 fois la médiane sur un an, ou variation de plus de 30 % en 3 mois |
| `fossil_categorie`, `fossil_part_energie_fnb` | Catégorie selon l'activité ; pour un FNB d'actions, part du secteur énergie |
| `kw_risque_pays` | Plusieurs étiquettes ; pays émergents selon MSCI |
| `adr_us` | Symbole de la cotation américaine, écrit à la main, à vérifier |
| `themes`, `access_canada`, `kw_exclusions` | Écrits à la main dans `scripts/build_asset_criteria.py` |

Répartition actuelle des rôles : satellite 16, satellite_revenu 13, speculatif 12, coeur 8, satellite_croissance 6, satellite_defensif 5, obligations_amortisseur 3, liquidites 1, obligations_longues 1, couverture 1.
Répartition de `kw_recuperation` : longue_plus_2_ans 25, moyenne_1_2_ans 19, baisse_en_cours 11, rapide_moins_1_an 8, jamais_recupere 3.

## Limites

- **Hypothèses** : tous les seuils ([seuils_criteres.json](../config/seuils_criteres.json)) et toutes les tables de la synthèse sont des hypothèses de l'équipe.
- **Une seule crise dans la fenêtre** : 2021-2026 contient surtout 2022. Les pertes historiques sous-estiment le risque des portefeuilles riches en actions. Un scénario de stress reste à ajouter.
- **Biais du survivant** : l'univers a été choisi en 2026 parmi des titres aujourd'hui importants.
- **Mesure dans l'échantillon** : les mots-clés des actifs sont calculés sur la période qui sert aussi aux mises en situation.
- **FNB** : seules les 10 premières positions et les poids sectoriels sont connus. Les exclusions à l'intérieur d'un fonds ne sont mesurées que pour l'énergie.
- **Exclusions manuelles** : `kw_exclusions` ne couvre que des implications connues, sans seuil de revenus. « Aucune connue » ne veut pas dire « aucune ».
- **Controverses** : une au plus par entreprise, 47 actifs sans controverse trouvée dans nos sources.
- **Attention médiatique** : Wikipédia en anglais, biaisé vers le public anglophone.
- **Classement des réponses libres** : fiabilité non encore mesurée (`mvp_profil/evaluer_classement.py`).

## Reproduire

```bash
python scripts/compute_metrics.py
```

```bash
python scripts/build_asset_criteria.py
```

```bash
python scripts/sync_grille.py
```

```bash
python scripts/test_grille.py
```
