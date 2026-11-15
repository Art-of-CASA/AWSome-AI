# Résultats par persona (générés)

Produit par `python scripts/tableau_personas.py` sur 111 actifs, données au 2026-11-12. Personas fictifs de l'énoncé, complétés par des réponses simulées (voir `mvp_profil/personas/`). Simulation éducative : aucun conseil financier. Les mesures décrivent le passé, elles ne prédisent rien.

## Verdicts par actif

| Persona | Budget de perte | Compatibles | À examiner | Peu adaptés | Exclus | Données insuffisantes |
|---|---|---|---|---|---|---|
| Amira | 45 % | 67 | 11 | 0 | 33 | 0 |
| Mateo | 22 % | 44 | 17 | 0 | 50 | 0 |
| Robert | 15 % | 50 | 26 | 0 | 35 | 0 |

## Mini-portefeuille fictif

| Persona | Positions | Poche de croissance | Volatilité | Perte de stress | Tension | Scénario fictif de krach |
|---|---|---|---|---|---|---|
| Amira | 12 | 92,3 % | 12,0 % | 22,5 % | 0.50 (coherent) | 44,4 % |
| Mateo | 12 | 60,0 % | 9,0 % | 12,8 % | 0.58 (coherent) | 27,0 % |
| Robert | 12 | 39,8 % | 4,4 % | 6,0 % | 0.40 (coherent) | 18,0 % |

### Amira

Niveau de risque 5 sur 5 (dynamique), limité par : capacité, tolérance observée. Budget de perte du portefeuille : 45 % (part d'actions indicative : 85 à 100 %).

| Actif | Nom | Poche | Poids | Score |
|---|---|---|---|---|
| VEA | Vanguard FTSE Developed Markets ETF | croissance | 13,3 % | 88 |
| ESGV | Vanguard ESG U.S. Stock ETF | croissance | 11,3 % | 88 |
| VT | Vanguard Total World Stock ETF | croissance | 11,3 % | 88 |
| VWO | Vanguard FTSE Emerging Markets ETF | croissance | 11,3 % | 88 |
| XEQT.TO | iShares Core Equity ETF Portfolio | croissance | 11,3 % | 88 |
| BTC-USD | Bitcoin | croissance | 10,0 % | 85 |
| FTS.TO | Fortis | croissance | 10,0 % | 88 |
| HDFCBANK.NS | HDFC Bank | croissance | 10,0 % | 88 |
| 2330.TW | Taiwan Semiconductor Manufacturing (TSMC) | croissance | 3,8 % | 88 |
| BNDW | Vanguard Total World Bond ETF | amortisseur | 2,6 % | 88 |
| CLF.TO | iShares 1-5 Year Laddered Government Bond Index ETF | amortisseur | 2,6 % | 85 |
| PSA.TO | Purpose High Interest Savings Fund | amortisseur | 2,6 % | 85 |

### Mateo

Niveau de risque 3 sur 5 (équilibré), limité par : capacité, tolérance observée. Budget de perte du portefeuille : 22 % (part d'actions indicative : 40 à 60 %).

| Actif | Nom | Poche | Poids | Score |
|---|---|---|---|---|
| CLF.TO | iShares 1-5 Year Laddered Government Bond Index ETF | amortisseur | 13,3 % | 88 |
| PSA.TO | Purpose High Interest Savings Fund | amortisseur | 13,3 % | 88 |
| XSB.TO | iShares Core Canadian Short Term Bond Index ETF | amortisseur | 13,3 % | 88 |
| ESGV | Vanguard ESG U.S. Stock ETF | croissance | 11,2 % | 96 |
| QQQ | Invesco QQQ Trust (Nasdaq-100) | croissance | 10,3 % | 88 |
| SPY | SPDR S&P 500 ETF Trust | croissance | 10,3 % | 88 |
| ZLB.TO | BMO Low Volatility Canadian Equity ETF | croissance | 10,3 % | 88 |
| CNR.TO | Canadian National Railway | croissance | 3,7 % | 96 |
| ATD.TO | Alimentation Couche-Tard | croissance | 3,6 % | 92 |
| MFC.TO | Manulife Financial | croissance | 3,6 % | 92 |
| RY.TO | Royal Bank of Canada | croissance | 3,6 % | 92 |
| SMH | VanEck Semiconductor ETF | croissance | 3,4 % | 88 |

### Robert

Niveau de risque 2 sur 5 (prudent), limité par : capacité, tolérance observée. Budget de perte du portefeuille : 15 % (part d'actions indicative : 20 à 40 %).

| Actif | Nom | Poche | Poids | Score |
|---|---|---|---|---|
| PSA.TO | Purpose High Interest Savings Fund | amortisseur | 20,0 % | 86 |
| XSB.TO | iShares Core Canadian Short Term Bond Index ETF | amortisseur | 20,0 % | 93 |
| XSH.TO | iShares Core Canadian Short Term Corporate Bond Index ETF | amortisseur | 20,0 % | 93 |
| USMV | iShares MSCI USA Min Vol Factor ETF | croissance | 6,3 % | 86 |
| VDY.TO | Vanguard FTSE Canadian High Dividend Yield Index ETF | croissance | 6,3 % | 86 |
| XIU.TO | iShares S&P/TSX 60 Index ETF | croissance | 6,3 % | 86 |
| ZLB.TO | BMO Low Volatility Canadian Equity ETF | croissance | 6,3 % | 86 |
| XEQT.TO | iShares Core Equity ETF Portfolio | croissance | 6,0 % | 82 |
| FTS.TO | Fortis | croissance | 2,5 % | 100 |
| MFC.TO | Manulife Financial | croissance | 2,1 % | 86 |
| CNQ.TO | Canadian Natural Resources | croissance | 2,0 % | 82 |
| O | Realty Income | croissance | 2,0 % | 82 |

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
| Amira | 20 % | En tension avec le profil | 10 % | 22,5 % → 21,0 % |
| Mateo | 5 % | Exclu | 0 % | — |
| Mateo | 20 % | Exclu | 0 % | — |
| Robert | 5 % | À surveiller | 5 % | 6,0 % → 8,9 % |
| Robert | 20 % | En tension avec le profil | 5 % | 6,0 % → 18,8 % |
