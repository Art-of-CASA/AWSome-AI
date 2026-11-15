# Données complémentaires AWSome AI

Données ajoutées au jeu de départ (`Datathon2026/awsome-ai_starter`) pour couvrir ce qui manquait aux critères de l'outil. Collecte du 14 novembre 2026. Simulation uniquement : rien ici n'est un conseil financier.

Le détail de chaque fichier (source, date, traitement, limites, conditions d'utilisation) est dans [sources_extra.csv](sources_extra.csv).

## Ce qui a été ajouté

| Besoin | Fichiers | Source |
|---|---|---|
| Qualité et stabilité des entreprises (Robert) | `fundamentals_annual.csv`, `fundamentals_ratios.csv` | Yahoo Finance (yfinance) |
| Vraie diversification des FNB (Amira) | `etf_overview.csv`, `etf_top_holdings.csv`, `etf_sector_weights.csv` | Yahoo Finance (yfinance) |
| ESG et controverses (Mateo) | `esg_screens.csv`, `esg_controversies.csv`, `raw/xen_holdings_2026-11-12.csv` | BlackRock Canada (XEN), justice.gov, tribunaux, presse |
| Titre très médiatisé (Robert) | `attention_wikipedia.csv`, `news_recent.csv` | Wikimedia Pageviews, Yahoo Finance |
| Cohérence dans le temps | `macro_release_dates.csv` | ALFRED (Fed de St. Louis) |

## Points à connaître

- **États financiers :** la date `available_from` (fin d'exercice + 90 jours) est une hypothèse prudente. Avant cette date, une simulation ne doit pas utiliser l'exercice. SHOP.TO, CSU.TO et ATD.TO publient en USD alors qu'ils cotent en CAD. Pour RY, TD, JPM et MFC, les ratios industriels ne s'appliquent pas (`industrial_ratios_meaningful = False`).
- **FNB :** les frais de gestion et les compositions sont exploitables. La colonne d'actif net (`ops_Total Net Assets`) n'est pas fiable : ne pas l'utiliser.
- **ESG :** ce n'est pas une note. C'est un ensemble de faits vérifiables : implication fossile (règle sur l'activité), appartenance à l'indice Jantzi Social, controverses avec lien vers la source. L'indice Jantzi est une sélection « meilleur de sa catégorie » qui garde Enbridge et CNQ : deux méthodes ESG peuvent donc se contredire, et l'outil doit le dire. La liste des controverses est non exhaustive.
- **Sévérité des controverses (hypothèse de l'équipe) :** élevée = culpabilité reconnue, sanction acceptée ou décision défavorable sur le fond ; moyenne = poursuite en cours, règlement, mesure administrative ou rappel de sécurité ; faible = litige notable tranché en faveur de l'entreprise.
- **Attention médiatique :** les pages vues Wikipédia sont un indicateur indirect, utile pour repérer un pic (par exemple une journée où l'intérêt pour Tesla explose). Pour les FNB, l'article porte sur l'indice ou l'émetteur. ZST.TO n'a pas d'article.
- **Actualités :** 10 titres récents par actif, sans historique. Elles servent à montrer le contexte dans la démo, pas à une simulation passée.
- **Dates de publication macro :** pour l'IPC et le chômage américains, ce sont les vraies dates de première publication (archive ALFRED). Les données d'octobre 2025 n'ont jamais été publiées à cause de l'arrêt du gouvernement fédéral américain. Pour les taux quotidiens, on retient le jour ouvré suivant ; pour l'IPC canadien, le 28 du mois suivant (hypothèse prudente, pas de vintages publics).

## Reproduire

```bash
python -m venv .venv
.venv/Scripts/python -m pip install pandas yfinance requests
.venv/Scripts/python scripts/fetch_extra_data.py
.venv/Scripts/python scripts/fetch_macro_release_dates.py
.venv/Scripts/python scripts/build_esg.py
```

`build_esg.py` lit `etf_sector_weights.csv` : il faut lancer `fetch_extra_data.py` avant. Les valeurs Yahoo changent d'un téléchargement à l'autre. Les controverses sont écrites à la main dans `scripts/build_esg.py`.
