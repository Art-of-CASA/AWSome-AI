# Résultats par persona (générés)

Produit par `python scripts/tableau_personas.py` sur 111 actifs, données au 2026-11-12. Personas fictifs de l'énoncé, complétés par des réponses simulées (voir `mvp_profil/personas/`). Simulation éducative : aucun conseil financier. Les mesures décrivent le passé, elles ne prédisent rien.

## Verdicts par actif

| Persona | Budget de perte | Compatibles | À examiner | Peu adaptés | Exclus | Données insuffisantes |
|---|---|---|---|---|---|---|
| Amira | 45 % | 59 | 11 | 0 | 41 | 0 |
| Mateo | 22 % | 37 | 17 | 0 | 57 | 0 |
| Robert | 15 % | 43 | 25 | 0 | 43 | 0 |

## Mini-portefeuille fictif

| Persona | Positions | Poche de croissance | Volatilité | Perte de stress | Tension | Scénario fictif de krach |
|---|---|---|---|---|---|---|
| Amira | 12 | 93,5 % | 11,6 % | 22,5 % | 0.50 (coherent) | 45,1 % |
| Mateo | 12 | 60,0 % | 7,2 % | 8,6 % | 0.39 (coherent) | 27,0 % |
| Robert | 11 | 40,0 % | 4,3 % | 5,3 % | 0.35 (coherent) | 18,0 % |

### Amira

Niveau de risque 5 sur 5 (dynamique), limité par : capacité, tolérance observée. Budget de perte du portefeuille : 45 % (part d'actions indicative : 85 à 100 %).

| Actif | Nom | Poche | Poids | Score |
|---|---|---|---|---|
| VEA | Vanguard FTSE Developed Markets ETF | croissance | 18,5 % | 88 |
| XEQT.TO | iShares Core Equity ETF Portfolio | croissance | 15,2 % | 88 |
| USMV | iShares MSCI USA Min Vol Factor ETF | croissance | 14,7 % | 85 |
| BTC-USD | Bitcoin | croissance | 10,0 % | 85 |
| FTS.TO | Fortis | croissance | 10,0 % | 88 |
| HDFCBANK.NS | HDFC Bank | croissance | 10,0 % | 88 |
| 2330.TW | Taiwan Semiconductor Manufacturing (TSMC) | croissance | 5,1 % | 88 |
| ASML.AS | ASML Holding | croissance | 5,1 % | 88 |
| ICLN | iShares Global Clean Energy ETF | croissance | 5,1 % | 88 |
| BNDW | Vanguard Total World Bond ETF | amortisseur | 2,2 % | 88 |
| CLF.TO | iShares 1-5 Year Laddered Government Bond Index ETF | amortisseur | 2,2 % | 85 |
| PSA.TO | Purpose High Interest Savings Fund | amortisseur | 2,2 % | 85 |

### Mateo

Niveau de risque 3 sur 5 (équilibré), limité par : capacité, tolérance observée. Budget de perte du portefeuille : 22 % (part d'actions indicative : 40 à 60 %).

| Actif | Nom | Poche | Poids | Score |
|---|---|---|---|---|
| CLF.TO | iShares 1-5 Year Laddered Government Bond Index ETF | amortisseur | 13,3 % | 88 |
| PSA.TO | Purpose High Interest Savings Fund | amortisseur | 13,3 % | 88 |
| XSB.TO | iShares Core Canadian Short Term Bond Index ETF | amortisseur | 13,3 % | 88 |
| USMV | iShares MSCI USA Min Vol Factor ETF | croissance | 11,9 % | 88 |
| ZLB.TO | BMO Low Volatility Canadian Equity ETF | croissance | 11,9 % | 88 |
| VEA | Vanguard FTSE Developed Markets ETF | croissance | 11,5 % | 85 |
| CNR.TO | Canadian National Railway | croissance | 4,3 % | 96 |
| ATD.TO | Alimentation Couche-Tard | croissance | 4,1 % | 92 |
| MFC.TO | Manulife Financial | croissance | 4,1 % | 92 |
| RY.TO | Royal Bank of Canada | croissance | 4,1 % | 92 |
| BEP-UN.TO | Brookfield Renewable Partners | croissance | 4,0 % | 88 |
| SMH | VanEck Semiconductor ETF | croissance | 4,0 % | 88 |

### Robert

Niveau de risque 2 sur 5 (prudent), limité par : capacité, tolérance observée. Budget de perte du portefeuille : 15 % (part d'actions indicative : 20 à 40 %).

| Actif | Nom | Poche | Poids | Score |
|---|---|---|---|---|
| PSA.TO | Purpose High Interest Savings Fund | amortisseur | 20,0 % | 86 |
| XSB.TO | iShares Core Canadian Short Term Bond Index ETF | amortisseur | 20,0 % | 93 |
| XSH.TO | iShares Core Canadian Short Term Corporate Bond Index ETF | amortisseur | 20,0 % | 93 |
| USMV | iShares MSCI USA Min Vol Factor ETF | croissance | 8,6 % | 86 |
| ZLB.TO | BMO Low Volatility Canadian Equity ETF | croissance | 8,6 % | 86 |
| XEQT.TO | iShares Core Equity ETF Portfolio | croissance | 8,2 % | 82 |
| FTS.TO | Fortis | croissance | 3,4 % | 100 |
| MFC.TO | Manulife Financial | croissance | 2,9 % | 86 |
| CNQ.TO | Canadian Natural Resources | croissance | 2,7 % | 82 |
| O | Realty Income | croissance | 2,7 % | 82 |
| PM | Philip Morris International | croissance | 2,7 % | 82 |

## Fiche d'un actif très médiatisé (NVDA)

| Persona | Verdict | Score | Poids maximal compatible |
|---|---|---|---|
| Amira | Compatible | 88 | 10 % |
| Mateo | Exclu | — | 0 % |
| Robert | À examiner | 66 | 5 % |

## Demande d'un titre très médiatisé (NVDA)

| Persona | Part demandée | Verdict | Part maximale compatible | Perte de stress avant → après |
|---|---|---|---|---|
| Amira | 5 % | Cohérent avec le profil | 10 % | 22,5 % → 20,1 % |
| Amira | 20 % | En tension avec le profil | 10 % | 22,5 % → 21,3 % |
| Mateo | 5 % | Exclu | 0 % | — |
| Mateo | 20 % | Exclu | 0 % | — |
| Robert | 5 % | À surveiller | 5 % | 5,3 % → 8,4 % |
| Robert | 20 % | En tension avec le profil | 5 % | 5,3 % → 18,4 % |
