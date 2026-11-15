# Univers étendu AWSome AI : Europe, Asie, Afrique et FNB mondiaux

35 actifs ajoutés au jeu de départ, avec les mêmes données que lui et que `data_extra` : prix, dividendes, change, états financiers, FNB, ESG, attention médiatique, actualités. Période du 12 novembre 2021 au 12 novembre 2026, collecte du 14 novembre 2026. Simulation uniquement : rien ici n'est un conseil financier.

Le détail de chaque fichier est dans [sources_extended.csv](sources_extended.csv).

## Les 35 actifs

| Région | Actifs |
|---|---|
| **Europe (10)** | ASML, LVMH, Nestlé, Novo Nordisk, SAP, Siemens, TotalEnergies, Shell, AstraZeneca, HSBC |
| **Asie (10)** | TSMC, Samsung Electronics, Toyota, Sony, Tencent, Alibaba, BYD, Reliance Industries, HDFC Bank, Infosys |
| **Afrique (10)** | Naspers, FirstRand, Standard Bank, MTN, Vodacom, Gold Fields, Sasol, Shoprite, Aspen Pharmacare (Afrique du Sud) ; Commercial International Bank (Égypte) |
| **FNB mondiaux (5)** | VT (monde), VEA (pays développés), VWO (pays émergents), XEQT.TO (portefeuille actions tout-en-un), BNDW (obligations mondiales) |

Le choix vise des sociétés grandes, liquides et de secteurs variés, avec des cas utiles aux personas : énergies fossiles (TotalEnergies, Shell, Reliance, Sasol) pour Mateo, titres très volatils et médiatisés (BYD, Novo Nordisk, Alibaba) pour Robert, régions peu corrélées à l'Amérique du Nord pour la diversification d'Amira. La liste est dans `scripts/universe_extended.csv` : on peut la modifier et tout relancer.

**Limite importante pour l'Afrique :** Yahoo Finance ne couvre ni Lagos, ni Nairobi, ni Casablanca. Neuf actions sur dix sont donc sud-africaines. Maroc Telecom, coté à Paris, a été écarté : environ 55 titres échangés par jour, des prix trop rares pour mesurer un risque. Plusieurs de ces sociétés opèrent toutefois dans de nombreux pays africains (MTN, Vodacom, Standard Bank, Shoprite).

## Fichiers

| Fichier | Contenu |
|---|---|
| `assets_universe.csv` | Les 35 actifs : classe, marché, devise, secteur GICS, région, pays |
| `prices_daily.csv` | Prix quotidiens, même format que le jeu de départ |
| `corporate_actions.csv` | Dividendes et fractionnements |
| `fx_to_cad_daily.csv` | Change vers le CAD pour 12 devises |
| `data_quality_warnings.txt` | Corrections et anomalies relevées |
| `fundamentals_annual.csv`, `fundamentals_ratios.csv` | États financiers et ratios des 30 actions |
| `quote_currency_raw.csv` | Devise de cotation brute renvoyée par Yahoo (GBp, ZAc…), avant conversion |
| `etf_overview.csv`, `etf_top_holdings.csv`, `etf_sector_weights.csv` | Frais, positions et secteurs des 5 FNB (XEQT et BNDW sont des fonds de fonds : 5 et 2 positions) |
| `esg_screens.csv`, `esg_controversies.csv` | Implication fossile et controverses sourcées |
| `attention_wikipedia.csv`, `news_recent.csv` | Attention médiatique et actualités récentes |
| `asset_metrics_cad.csv` | **Indicateurs de risque en CAD pour les 66 actifs** (jeu de départ + univers étendu) |

## Points à connaître

- **Sous-unités :** Londres cote en pence et Johannesburg en cents. Prix et dividendes sont convertis en livres et en rands (division par 100).
- **Erreurs Yahoo corrigées :** deux jours où le prix était 100 fois trop petit (Standard Bank le 2025-04-25, Vodacom le 2025-01-10) ont été remis à l'échelle. Un « fractionnement » de 5 000 pour 1 sur Naspers (2023-09-13) est une métadonnée erronée, à ignorer. Tout est consigné dans `data_quality_warnings.txt`.
- **Change :** Banque du Canada pour 10 devises. Pour la couronne danoise et la livre égyptienne, absentes de la Banque du Canada, taux croisé USD/CAD (Banque du Canada) ÷ USD/devise (Yahoo). La livre égyptienne a perdu environ les deux tiers de sa valeur face au CAD sur la période (de 0,080 à 0,027 CAD) : en CAD, c'est un risque majeur de CIB.
- **Calendriers :** chaque marché a ses jours fériés. Les prix ne sont ni remplis ni alignés. Dans les indicateurs, corrélations et bêtas sont calculés sur des rendements hebdomadaires pour neutraliser le décalage horaire.
- **Indicateurs :** `asset_metrics_cad.csv` recalcule aussi les 31 actifs du jeu de départ avec la même méthode (calendrier propre à chaque actif, change du jour). Les chiffres diffèrent donc légèrement de ceux du Google Doc de critères, calculés sur un calendrier commun.
- **ESG :** pas de note, des faits vérifiables. L'indice Jantzi ne concerne que les actions canadiennes et n'est pas utilisé ici. Sévérité des controverses (hypothèse de l'équipe) : élevée = culpabilité, sanction acceptée ou décision défavorable sur le fond ; moyenne = poursuite en cours, règlement, mesure administrative ou rappel ; faible = litige notable tranché en faveur de l'entreprise. Liste non exhaustive.
- **États financiers :** même hypothèse de publication (fin d'exercice + 90 jours). Plusieurs sociétés publient dans une autre devise que celle de cotation : la colonne `currency` donne la devise des états. Les ratios industriels ne s'appliquent pas aux banques (HSBC, HDFC Bank, FirstRand, Standard Bank, CIB).
- **Pas de données macro hors Canada et États-Unis :** taux directeurs et inflation d'Europe, d'Asie et d'Afrique ne sont pas inclus.

## Reproduire

```bash
.venv/Scripts/python scripts/build_extended_prices.py
.venv/Scripts/python scripts/fetch_extra_data.py --universe scripts/universe_extended.csv --out data_extended
.venv/Scripts/python scripts/build_esg.py --universe scripts/universe_extended.csv --out data_extended
.venv/Scripts/python scripts/compute_metrics.py
```

## Ajouts du 15 novembre 2026 : 45 actifs de plus (80 dans ce dossier, 111 avec le jeu de départ)

### Premier lot : 35 actifs pour diversifier et contraster les valeurs

Ajoutés par `scripts/ajouter_actifs.py`, qui ne retélécharge pas les 35 actifs déjà présents : leurs lignes sont restées identiques, seules des lignes ont été ajoutées. Même période (12 novembre 2021 au 12 novembre 2026), collecte du 15 novembre 2026.

| Groupe | Actifs |
|---|---|
| **États-Unis (11)** | Philip Morris, Lockheed Martin, Boeing, Meta, UnitedHealth, Coca-Cola, Costco, NextEra Energy, Palantir, Realty Income, Las Vegas Sands |
| **Canada (3)** | Cameco, Brookfield Renewable Partners, BCE |
| **Europe (7)** | British American Tobacco, Diageo, Glencore, Rheinmetall, Vestas, Iberdrola, Enel |
| **Asie (4)** | DBS (Singapour), SoftBank, SK Hynix, Nintendo |
| **Amérique latine (3)** | Vale, Petrobras (Brésil) ; Walmart de México |
| **Moyen-Orient (1)** | Saudi Aramco |
| **FNB (6)** | ICLN (énergie propre), ITA (aérospatiale et défense), VNQ (immobilier coté), SMH (semi-conducteurs), VDY.TO (dividendes canadiens), TIP (obligations indexées sur l'inflation) |

**Pourquoi ces actifs.** Pour contraster les profils selon leurs valeurs : tabac (Philip Morris, British American Tobacco), armement (Lockheed Martin, Rheinmetall, Boeing, le FNB ITA), alcool (Diageo), jeux d'argent (Las Vegas Sands), nucléaire (Cameco), énergies fossiles (Petrobras, Saudi Aramco, Glencore), face aux énergies renouvelables (Vestas, Iberdrola, Enel, Brookfield Renewable, NextEra, le FNB ICLN). Pour diversifier : immobilier, services publics, santé, consommation courante, et trois régions nouvelles. Pour le test de Robert : des titres très médiatisés et volatils (Palantir, Rheinmetall, SK Hynix, Meta).

**Nouveautés à connaître**
- **Régions nouvelles :** « Amérique latine » et « Moyen-Orient ». Les 14 actions nord-américaines ajoutées ont la région « Amérique du Nord », comme le jeu de départ.
- **Devises nouvelles :** BRL, MXN, SGD, SAR (Banque du Canada). La Banque du Canada ne publie plus le riyal saoudien après le 30 avril 2026 : la suite est un taux croisé USD/CAD ÷ 3,75 (arrimage officiel au dollar américain). Détail dans `data_quality_warnings.txt`.
- **Secteur nouveau :** « Real Estate » (Realty Income).
- **ESG :** 6 controverses sourcées ajoutées (Glencore, British American Tobacco, Boeing, Meta, Vale, Petrobras), recherche du 15 novembre 2026. Les autres actifs ajoutés ont « aucune trouvée », ce qui ne veut pas dire « aucune » : la liste n'est pas exhaustive. Les exclusions par activité (tabac, armes, alcool, jeux d'argent, nucléaire) sont écrites à la main dans `scripts/build_asset_criteria.py`, avec leur justification.
- **États financiers dans une autre devise que la cotation :** Diageo et Glencore (USD), Brookfield Renewable (USD), Vestas (EUR).
- **DBS** est une banque : les ratios industriels ne s'appliquent pas.

### Second lot : 10 actifs stables

L'univers manquait d'actifs peu risqués : 9 actifs seulement sous la classe de risque 6. Dix FNB ajoutés, tous avec cinq ans d'historique :

| Type | Actifs | Volatilité en CAD | Classe |
|---|---|---|---|
| Liquidités en dollars canadiens | PSA.TO, CASH.TO (comptes d'épargne à intérêt élevé) | 0,3 % et 0,6 % | 1 et 2 |
| Obligations canadiennes à court terme | XSB.TO (ensemble), XSH.TO (sociétés), CLF.TO (gouvernements 1 à 5 ans) | environ 3 % | 3 |
| Obligations gouvernementales canadiennes | XGB.TO | 6,9 % | 4 |
| Bons et obligations du Trésor américain à court terme | BIL (1 à 3 mois), SHY (1 à 3 ans) | 5,4 % | 4 |
| Actions à faible volatilité | ZLB.TO (Canada), USMV (États-Unis) | 9,7 % et 12,2 % | 4 et 5 |

À savoir : BIL et SHY ne bougent presque pas en dollars américains (0,3 % et 2 %) ; leur volatilité de 5,4 % en CAD vient entièrement du taux de change. Pour un investisseur canadien, les vraies liquidités sont PSA.TO et CASH.TO. XGB.TO n'a jamais retrouvé son sommet d'avant 2022 : « stable » ne veut pas dire « sans perte ».

**Devises.** Les 111 actifs sont cotés dans 17 devises : USD, CAD, ZAR, EUR, GBP, JPY, HKD, INR, DKK, KRW, BRL, CHF, TWD, EGP, SGD, MXN, SAR.

**État des fichiers calculés**
- `asset_metrics_cad.csv` et `asset_criteria.csv` : recalculés pour les 111 actifs avec les scripts de la branche (109 colonnes). Les 66 lignes précédentes sont identiques, sauf `media_hype` et `kw_attention` pour 4 actifs (LVMH, Siemens, Samsung, Sony) : la notoriété se mesure par rapport à l'univers, qui a changé.
- Fichiers dérivés du site, régénérés : `mvp_profil/vocabulaire_actifs.json` (333 valeurs) et `mvp_profil/donnees_chercheur.json` (111 actifs, 17 FNB).
