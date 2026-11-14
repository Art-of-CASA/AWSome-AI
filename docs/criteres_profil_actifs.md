# Grille de critères : profil de l'investisseur ↔ actifs

Version du 14 novembre 2026. Simulation uniquement : cette grille sert à expliquer une compatibilité, pas à donner un conseil financier.

## Principe

Chaque critère existe **des deux côtés** :

- **Côté profil :** une question posée par l'agent. La réponse est classée dans une **liste fermée de valeurs**, ce qui rend le profil reproductible.
- **Côté actif :** une valeur **calculée par du code** à partir de nos données datées, pour chacun des 66 actifs ([asset_criteria.csv](../data_extended/asset_criteria.csv)).
- **Entre les deux :** une **règle d'appariement** écrite à l'avance.

Chaque règle a un type :

| Type | Effet |
|---|---|
| `exclusion` | L'actif est retiré |
| `plafond` | Poids ou niveau maximal |
| `seuil` | Comparaison chiffrée qui donne un verdict : cohérent, à surveiller ou en tension |
| `preference` | Trie les suggestions. **N'améliore jamais la compatibilité** |
| `calcul_capacite` | Entre dans le calcul de la perte maximale supportable |
| `information` | Affiché à l'utilisateur, sans effet sur le verdict |
| `controle` | Vérification de gouvernance |

**Verdict = le pire critère**, figé avant que le modèle lise la justification de l'utilisateur. Tous les seuils sont des hypothèses, réunis dans [seuils_criteres.json](../config/seuils_criteres.json). La table complète, lisible par le code, est [criteres_appariement.csv](../config/criteres_appariement.csv) (50 critères, dont 3 mesurés par des mises en situation : B2 replay, B6 fourchettes, D13 effet de mode).

## A. Situation et capacité financière

Ces critères disent combien l'investisseur **peut** perdre, indépendamment de ce qu'il **accepte** de perdre.

| # | Question au profil → valeurs | Critère de l'actif | Règle |
|---|---|---|---|
| A1 | Âge et étape de vie → études, début / milieu de carrière, pré-retraite, retraite | — | Cohérence de l'horizon, capacité à reconstituer des pertes |
| A2 | **Horizon** → <3 ans, 3-5, 5-10, 10-15, >15 | `horizon_min_years`, `recovery_days` | Horizon minimal de l'actif ≤ horizon : cohérent ; jusqu'à 2 fois l'horizon : à surveiller ; au-delà : en tension. Pondéré par le poids de la position |
| A3 | **Objectif** → coussin, projet daté, retraite, revenu, croissance, transmission | `role` (stabilisateur, défensif, revenu, cœur, croissance, spéculatif, couverture) | Coussin : stabilisateurs seulement ; projet daté : défensif près de l'échéance |
| A4 | Part de l'épargne totale → <25 %, 25-60 %, >60 % | `stress_loss` | Avec l'horizon : table de capacité, donc perte maximale supportable |
| A5 | Fonds d'urgence → aucun, <3 mois, 3-6, >6 | — | Moins de 3 mois : alerte, classe de risque plafonnée à 4 |
| A6 | Stabilité des revenus → stables, variables, incertains, retraite | — | Revenus incertains : perte supportable réduite d'un cran |
| A7 | Dettes à taux élevé → oui / non | — | Oui : alerte « rembourser d'abord » |
| A8 | Personnes à charge → 0, 1-2, 3+ | — | Perte supportable réduite d'un cran |
| A9 | Retraits prévus → aucun, ponctuel (date, montant), réguliers | `liquidity_level`, `stress_loss` | Argent requis dans moins de 3 ans : classe ≤ 3 et liquidité suffisante |
| A10 | Besoin de revenu → non, souhaité, essentiel | `dividend_yield_ttm`, `income_asset`, `dividend_cut_2022_2025`, `dividends_to_fcf_last` | Essentiel : exclure les actifs dont le dividende a baissé ou dépasse les flux libres |
| A11 | Patrimoine hors portefeuille → propriétaire, régime à prestations déterminées | — | Peut augmenter la capacité d'un cran au maximum |
| A12 | **Secteur d'emploi** (capital humain) → secteurs GICS | `sector` | Plafond plus bas sur son propre secteur : Amira travaille dans le logiciel |

## B. Tolérance au risque

| # | Question → valeurs | Critère de l'actif | Règle |
|---|---|---|---|
| B1 | **Point de rupture déclaré** : baisse à laquelle on vendrait → 5 à 50 % et plus | `stress_loss` (portefeuille) | Tension = perte de stress du portefeuille ÷ perte supportable : <0,8 cohérent ; 0,8-1 à surveiller ; >1 en tension |
| B2 | **Point de rupture observé** : replay de 2022 avec quatre arrêts | `return_2022`, `max_drawdown` | Écart fort avec B1 : on retient le plus prudent, profil « incertain » |
| B3 | Déjà vécu une baisse de 20 % ? → jamais, gardé, vendu, renforcé | — | Jamais ou vendu : décote sur le déclaré |
| B4 | Fréquence de consultation → quotidienne… rarement | `var95_daily`, `worst_month`, `vol_cad` | Quotidienne + classe ≥ 6 : avertissement (myopie face aux pertes) |
| B5 | Variation annuelle acceptée → <5 %, 5-10, 10-15, 15-25, >25 % | `vol_cad`, `risk_class` (1 à 7) | Classe de l'actif ≤ classe acceptée |
| B6 | Gain sûr de 5 % ou pile ou face +20 % / −10 % ? | `risk_class` | Recoupe B5 ; un écart déclenche une question de clarification |
| B7 | **Durée de récupération supportable** → moins d'un an, 1-2 ans, plus de 2 ans | `kw_recuperation` | Récupération historique de l'actif ≤ durée supportable ; « non récupéré » : en tension |

## C. Connaissances

| # | Question → valeurs | Critère de l'actif | Règle |
|---|---|---|---|
| C1 | Trois questions de culture financière → score 0 à 3 | `complexity` (1 simple, 2 intermédiaire, 3 complexe) | Complexité ≤ score + 1 |
| C2 | Produits déjà détenus → aucun, FNB, actions, obligations, crypto | `asset_class`, `complexity` | Première fois sur une classe complexe : avertissement pédagogique |
| C3 | Comprendre le modèle d'affaires → essentiel, souhaité, indifférent | `complexity`, `themes` (holding) | Essentiel : exclure la complexité 3 et les holdings |

## D. Préférences d'exposition

| # | Question → valeurs | Critère de l'actif | Règle |
|---|---|---|---|
| D1 | Classes acceptées → actions, FNB, obligations, or, crypto | `asset_class` | Classe refusée : exclusion |
| D2 | Part maximale en crypto → 0, 5, 10, 20 % | `asset_class = crypto` | Plafond ; 0 % = exclusion |
| D3 | Régions → Canada, Amérique du Nord, monde, émergents, régions exclues | `region`, `country` | Exclusion ou tri |
| D4 | Devise de dépense, change accepté → non, limité, oui | `currency`, `fx_risk`, `fx_vol_contribution` | Plafond sur la part hors CAD ; ZAR et EGP signalés |
| D5 | Thèmes d'intérêt → IA, semi-conducteurs, santé, énergie, luxe, véhicule électrique, or… | `themes`, `sector` | Préférence seulement |
| D6 | Secteurs refusés | `themes`, `sector` | Exclusion |
| D7 | Style → croissance, établie, dividende | `growth`, `established`, `income_asset`, `profitable_years_share` | Préférence ; « établie » fort : exclure le spéculatif |
| D8 | **Tentation d'un titre dont tout le monde parle** → non, parfois, oui | `speculative`, `media_hype`, `attention_spike_last_30d` | Profil faible ou modéré + actif spéculatif ou très médiatisé : avertissement, sans acquiescer |
| D9 | Concentration → poids maximal par titre, nombre de positions | (portefeuille) | Plafonds par titre et par secteur |
| D10 | Importance de la diversification | `corr_vt_weekly`, `diversifier_vs_world`, `beta_vt_weekly` | Préférence pour les actifs peu corrélés |
| D11 | Fonds indiciels ou titres individuels | `asset_class` | Préférence |
| D12 | **Placements spéculatifs** → aucun, ≤ 5 %, ≤ 10 %, acceptés | `speculative` | Plafond sur la somme des poids spéculatifs |

## E. Valeurs et durabilité

| # | Question → valeurs | Critère de l'actif | Règle |
|---|---|---|---|
| E1 | Énergies fossiles → exclure l'implication directe, toute implication, limiter, indifférent | `fossil_involvement` (directe, partielle, part énergie d'un FNB) | Directe : exclusion ; partielle : plafond ou avertissement |
| E2 | Controverses → aucune, pas de grave, indifférent | `max_severity`, `controversy_topics` + lien vers la source | Pas de grave : exclure « élevée », signaler « moyenne » |
| E3 | Priorité E, S ou G | Pilier de chaque controverse | Une controverse sur le pilier prioritaire devient une exclusion |
| E4 | Exclusion de secteurs ou meilleur de sa catégorie | `in_jantzi_social_index`, `fossil_involvement` | Montrer le désaccord entre méthodes (Enbridge et CNQ dans l'indice Jantzi) |
| E5 | Exclusions : armement, contrats de défense, alcool, tabac, jeux, tests sur animaux, nucléaire, droits autochtones | `kw_exclusions` | Exclusion. Implications connues seulement (liste non exhaustive) |

## F. Contexte économique

| # | Question → valeurs | Critère de l'actif | Règle |
|---|---|---|---|
| F1 | Inquiétude face à l'inflation et aux taux | `return_2022`, `rate_sensitivity` (sensibilité au taux américain à 10 ans) | Signaler les actifs qui baissent quand les taux montent |
| F2 | Marchés émergents ou frontières acceptés ? | `country`, `fx_risk`, `access_canada` | Non : exclure hors pays développés ; devise instable (EGP) signalée |

## G. Contraintes pratiques

| # | Question → valeurs | Critère de l'actif | Règle |
|---|---|---|---|
| G1 | Montant investi | `unit_price_cad`, `high_unit_price` | Prix unitaire > 5 % du montant : avertissement |
| G2 | CELI, REER ou non enregistré | `foreign_dividend_withholding`, `dividend_yield_ttm` | Information sur la retenue étrangère (pas un conseil fiscal) |
| G3 | Accès du courtier aux bourses étrangères | `access_canada` (directe, courtier international, via ADR ou FNB, FNB seulement) | Exclure ce qui est inaccessible et proposer le FNB régional |
| G4 | Frais acceptés | `etf_expense_ratio` | Plafond |
| G5 | Temps consacré au suivi | `asset_class`, `complexity` | Peu de temps : FNB et complexité 1 |

## H. Cohérence et gouvernance

| # | Contrôle | Règle |
|---|---|---|
| H1 | Écart entre déclaré et observé | Profil incertain et réglage le plus prudent |
| H2 | Demande d'un titre précis | Tous les critères d'actif ; verdict = pire critère, figé avant la justification |
| H3 | Informations manquantes | Question de relance, sinon « données insuffisantes » et réglage prudent |

## Comment les critères d'actif sont calculés

| Critère | Calcul (fichier source) |
|---|---|
| `risk_class` | Volatilité annualisée en CAD, bandes de type SRRI 1 à 7 |
| `horizon_min_years` | Par classe : 1→1 an … 5→5, 6→7, 7→10 ; +2 ans si le sommet d'avant la pire baisse n'est pas retrouvé |
| `stress_loss` | Le pire entre la perte maximale et le rendement de 2022 |
| `liquidity_level` | Valeur moyenne échangée par jour sur 12 mois, en CAD : élevée ≥ 50 M$, moyenne ≥ 5 M$ |
| `fx_risk`, `fx_vol_contribution` | Volatilité en CAD − volatilité en devise locale |
| `rate_sensitivity` | Bêta des rendements hebdomadaires sur la variation du taux américain à 10 ans (% par point) |
| `income_asset` | Rendement en dividendes sur 12 mois ≥ 3 % et aucune baisse de dividende de plus de 20 % entre 2022 et 2025 |
| `established` | Action rentable chaque exercice publié, dividende chaque année de 2022 à 2025, non spéculative |
| `growth` | Croissance moyenne des revenus ≥ 15 % (neutralisée pour la livre égyptienne : croissance gonflée par l'inflation) |
| `speculative` | Crypto, ou volatilité ≥ 45 %, ou perte maximale ≥ 60 % |
| `defensive` | Volatilité ≤ 20 % et bêta monde ≤ 0,6, ou classe ≤ 4 |
| `diversifier_vs_world` | Corrélation hebdomadaire avec VT ≤ 0,30 |
| `media_hype` | Audience Wikipédia dans le tiers supérieur de l'univers ET pics d'attention dans le quart supérieur → « très médiatisé » |
| `themes`, `complexity`, `access_canada` | **Écrits à la main** dans `scripts/build_asset_criteria.py` (hypothèses à justifier) |

## Mots-clés des actifs (tableau de l'équipe)

Les critères du tableau « critères et mots-clés résultants » de l'équipe ont été retenus quand nos données permettent de les calculer. Ils sont dans les colonnes `kw_*` de [asset_criteria.csv](../data_extended/asset_criteria.csv), pour les 66 actifs. Quand c'est possible, le profil utilise **les mêmes valeurs** que les mots-clés, pour une comparaison directe.

| Critère du tableau | Colonne | Mots-clés (règle de calcul) | Critère du profil |
|---|---|---|---|
| Point de rupture (perte maximale tolérée) | `kw_perte_max_historique` | moins de 10 %, 10-20, 20-30, 30-40, plus de 40 % (perte maximale 2021-2026, en CAD) | B1 |
| Tolérance au risque déclarée (volatilité) | `kw_volatilite` | moins de 8 %, 8-15, 15-25, plus de 25 % | B5 |
| Durée de récupération supportable | `kw_recuperation` | moins d'un an, 1-2 ans, plus de 2 ans, non récupéré | B7, A2 |
| Résilience lors du choc de 2022 | `kw_choc_2022` | hausse, baisse limitée (moins de 10 %), modérée (10-25), forte (plus de 25) | B2, F1 |
| Bêta et sensibilité au marché | `kw_beta` | moins de 0,7 ; 0,7-1,2 ; plus de 1,2 (hebdomadaire, contre VT) | D10 |
| Pouvoir de diversification | `kw_diversification` | corrélation négative, faible (≤ 0,3), corrélé aux actions, corrélé aux obligations (≥ 0,5 avec BNDW) | D10 |
| Rendement du dividende | `kw_rendement_dividende` | aucun, moins de 1 %, 1-3, 3-5, plus de 5 % (à examiner) | A10 |
| Dividende : croissance et durabilité | `kw_dividende_durabilite` | croissance (+10 % de 2022 à 2025), stable, réduit ; ratio de distribution soutenable (≤ 75 % des flux libres) ou élevé | A10 |
| Distribution des revenus | `kw_distribution` | capitalisant, distribuant, mensuelle (≥ 10 versements par an) | A10 |
| Capitalisation boursière | `kw_capitalisation` | grande (> 10 G$ US), moyenne, petite, micro ([market_caps.csv](../data_extended/market_caps.csv)) | D7 |
| Santé financière | `kw_sante_financiere` | faible endettement, rentabilité élevée, flux libres positifs, couverture des intérêts, résultats stables, pertes récurrentes ; ratios spécifiques pour banques et assureurs | D7 |
| Croissance des résultats | `kw_croissance_resultats` | plus de 15 %, modérée, stable, en déclin ; non comparable en devise à forte inflation | D7 |
| Sensibilité macroéconomique (cyclique / défensif) | `kw_cycle`, `kw_sensibilite_macro` | cyclique, défensif (secteur GICS) ; sensible aux taux, au pétrole, aux devises | A3, F1 |
| Protection contre l'inflation | `kw_protection_inflation` | or, matières premières et énergie, a résisté en 2022, sans protection démontrée (règle simple, à affiner) | F1 |
| Frais de gestion (RFG) | `kw_frais` | moins de 0,15 %, 0,15-0,50, 0,50-1, plus de 1 % | G4 |
| Concentration de l'actif | `kw_concentration` | titre individuel, fonds diversifié, forte pondération des 10 premières positions (> 40 %), fonds de fonds, actif unique | D9, D11 |
| Attention médiatique et effet de mode | `kw_attention` | très médiatisé, très suivi, peu médiatisé ; variation récente extrême (\|3 mois\| > 30 %) ; pic de volume anormal (> 3 fois la médiane annuelle) | D8 |
| Efficience rendement/risque | `kw_efficience` | ratio faible, moyen, élevé (Sharpe ; Sortino en colonne). **Information seulement**, jamais dans le score | — |
| Risque pays | `kw_risque_pays` | pays développé, marché émergent, exposition Chine (directe ou partielle via VWO et VT), devise instable | F2 |
| Devise et risque de change | `kw_devise` | CAD, USD, autre devise, USD couvert (BNDW), CAD avec actifs étrangers non couverts (XEQT), sans devise souveraine | D4 |
| Fiscalité (nature du revenu) | `kw_fiscalite` | dividendes canadiens admissibles, dividendes étrangers, revenu d'intérêts, gains en capital seulement | G2 |
| Exclusions (armement, alcool, énergie, droits humains…) | `kw_exclusions` | énergie fossile, alcool (LVMH), contrats de défense (Microsoft, Amazon, Alphabet : contrat JWCC), tests sur animaux (pharmacie), droits autochtones (Enbridge) | E1, E5 |

**Critères du tableau non retenus pour l'instant**, faute de données ou parce qu'aucun actif de l'univers n'est concerné :
- **Obligations** (type d'émetteur, qualité de crédit, échéance) : seulement 5 FNB obligataires, sans données de crédit. La sensibilité aux taux est déjà mesurée.
- **Produits absents de l'univers** : CPG et protection du capital, levier et dérivés, méthode de réplication, capital-investissement, stablecoins.
- **Données non disponibles** : valorisation (C/B : bénéfices déclarés dans d'autres devises, dont le yuan, absent de nos taux de change), gouvernance (droits de vote, contrôle), notes ESG (non licenciées), seuils de revenus des activités exclues, filtres religieux, ancienneté et taille des fonds (actif net de Yahoo non fiable), maturité de l'entreprise (date d'introduction en bourse).

## Test sur les trois personas

Test simple, actif par actif, avec des réglages hypothétiques :
- **Amira :** horizon 15 ans, classe maximale 7, perte supportable 50 %.
- **Mateo :** horizon 10 ans, classe maximale 6, perte 30 %, exclusions fossiles, controverses graves et spéculatif.
- **Robert :** horizon 4 ans, classe maximale 5, perte 20 %, pas de crypto ni de complexité 3.

| Verdict | Amira | Mateo | Robert |
|---|---|---|---|
| Cohérent | 45 | 18 | 4 |
| À surveiller | 21 | 6 | 3 |
| En tension | 0 | 22 | 55 |
| Exclu | 0 | 20 | 4 |

- **Le même actif change de verdict selon le profil.** Tesla : à surveiller (Amira), exclu (Mateo), en tension (Robert). Enbridge : cohérent, exclu, en tension. Bitcoin : à surveiller, exclu, exclu.
- **Jugé seul, presque tout est trop risqué pour Robert.** Seuls les FNB obligataires passent. C'est attendu : un SPY à 100 % n'a pas le même risque qu'un SPY à 30 % dans un portefeuille avec des obligations. Le moteur doit donc calculer la tension **au niveau du portefeuille et du montant**, et pas actif par actif.

## Limites

- **Seuils :** tous sont des hypothèses, à valider en équipe et à déclarer.
- **Calculs historiques :** les indicateurs décrivent 2021-2026 et ne prédisent rien.
- **Attention médiatique :** Wikipédia anglais est un indicateur indirect, biaisé vers le public anglophone (Nestlé, Infosys et Reliance sortent « très médiatisés »).
- **Critères manuels :** thèmes, complexité et accès depuis le Canada sont écrits à la main.
- **Fiscalité :** information générale, à vérifier, jamais un conseil.
- **Manques côté données :** pas de ratio cours/bénéfice ni de données de gouvernance ; les exclusions (`kw_exclusions`) ne couvrent que les implications connues, sans seuil de revenus.

## Reproduire

```bash
.venv/Scripts/python scripts/fetch_market_caps.py
.venv/Scripts/python scripts/build_asset_criteria.py
```
