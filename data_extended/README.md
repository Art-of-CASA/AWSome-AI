# Univers étendu AlphaForge AI : Europe, Asie, Afrique et FNB mondiaux

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
