"""Données compactes pour l'agent CHERCHEUR des critères dynamiques (fichier JSON livré avec le site).

Sortie : mvp_profil/donnees_chercheur.json
  actifs       fiche courte de chacun des 66 actifs (nom, classe, secteur, pays, thèmes, exclusions, controverses)
  fnb          principales positions de chaque FNB, reliées aux tickers de l'univers quand c'est possible
  actualites   titres d'actualité récents par actif (date, titre, adresse)
  controverses controverses sourcées par actif
Le site n'embarque pas data_extra/ ni data_extended/ : ce fichier en reprend ce dont l'agent a besoin.
Lancer : python scripts/build_donnees_chercheur.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
crit = pd.read_csv(ROOT / "data_extended" / "asset_criteria.csv")
both = lambda nom: pd.concat([pd.read_csv(ROOT / d / nom) for d in ("data_extra", "data_extended")], ignore_index=True)  # noqa: E731


def txt(v) -> str:
    return "" if pd.isna(v) else str(v)


actifs = {r.ticker: {"nom": r.name, "classe": r.asset_class, "secteur": txt(r.sector), "pays": txt(r.country),
                     "region": txt(r.region), "devise": r.currency, "themes": txt(r.themes),
                     "exclusions": txt(r.kw_exclusions), "fossile": txt(r.fossil_involvement),
                     "controverses": txt(r.controversy_topics)} for r in crit.itertuples()}

# Symbole d'une position de FNB -> ticker de l'univers (RY -> RY.TO, NVDA -> NVDA, 2330 -> 2330.TW…)
par_base = {}
for tk in actifs:
    par_base.setdefault(tk.split(".")[0].replace("-B", "").replace("-USD", ""), tk)

fnb = {}
for r in both("etf_top_holdings.csv").itertuples():
    sym = txt(r.holding_symbol).split(".")[0]
    fnb.setdefault(r.etf, []).append({"symbole": txt(r.holding_symbol), "nom": txt(r.holding_name),
                                      "poids": round(float(r.weight), 6), "ticker": par_base.get(sym, "")})

actualites = {}
for r in both("news_recent.csv").sort_values("published_utc", ascending=False).itertuples():
    lst = actualites.setdefault(r.ticker, [])
    if len(lst) < 8:
        lst.append({"date": txt(r.published_utc)[:10], "titre": txt(r.title), "url": txt(r.url)})

controverses = {}
for r in both("esg_controversies.csv").itertuples():
    controverses.setdefault(r.ticker, []).append({"date": txt(r.event_date), "sujet": txt(r.topic),
                                                  "resume": txt(r.summary), "source": txt(r.source)})

out = ROOT / "mvp_profil" / "donnees_chercheur.json"
out.write_text(json.dumps({"source": "data_extra/ et data_extended/", "actifs": actifs, "fnb": fnb,
                           "actualites": actualites, "controverses": controverses},
                          ensure_ascii=False, indent=1), encoding="utf-8")
relies = sum(1 for p in sum(fnb.values(), []) if p["ticker"])
print(f"{out.relative_to(ROOT)} : {len(actifs)} actifs, {len(fnb)} FNB ({relies} positions reliées à l'univers), "
      f"{sum(map(len, actualites.values()))} actualités, {sum(map(len, controverses.values()))} controverses")
