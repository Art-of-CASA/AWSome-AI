"""Vocabulaire des actifs pour les critères dynamiques (fichier JSON livré avec le site).

Sortie : mvp_profil/vocabulaire_actifs.json
  Pour chaque « dimension » d'un actif (titre, classe, région, pays, devise, secteur, thème, mots-clés kw_*…) :
  une description, et pour chaque valeur possible la liste des tickers qui l'ont.
Un critère dynamique (créé à partir de la question ouverte de fin de parcours) doit s'exprimer avec ces
valeurs, et seulement elles : c'est ce qui le rend vérifiable et comparable aux actifs, comme les critères fixes.
Lancer : python scripts/build_vocabulaire.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
crit = pd.read_csv(ROOT / "data_extended" / "asset_criteria.csv")

# dimension -> (colonne de asset_criteria.csv, description donnée aux agents)
DIMENSIONS = {
    "titre": ("ticker", "un titre précis de l'univers (ticker), par exemple l'employeur de la personne ou une entreprise qu'elle refuse"),
    "classe": ("asset_class", "classe d'actif : action, FNB d'actions, FNB d'obligations, FNB de matières premières, cryptoactif"),
    "region": ("region", "grande région de cotation ou d'activité"),
    "pays": ("country", "pays de l'émetteur"),
    "devise": ("currency", "devise de cotation"),
    "secteur": ("sector", "secteur d'activité (classification GICS) ou type de fonds"),
    "theme": ("themes", "thème d'activité précis (plusieurs par actif)"),
    "exclusion": ("kw_exclusions", "activité controversée détectée (mot-clé kw_exclusions)"),
    "risque_pays": ("kw_risque_pays", "exposition à un risque pays (mot-clé kw_risque_pays)"),
    "exposition_devise": ("kw_devise", "exposition au change pour un investisseur canadien (mot-clé kw_devise)"),
    "taille": ("kw_capitalisation", "taille de l'entreprise (mot-clé kw_capitalisation)"),
    "distribution": ("kw_distribution", "verse ou non des distributions (mot-clé kw_distribution)"),
    "cycle": ("kw_cycle", "comportement dans le cycle économique (mot-clé kw_cycle)"),
    "concentration": ("kw_concentration", "titre individuel ou fonds diversifié (mot-clé kw_concentration)"),
    "attention": ("kw_attention", "attention médiatique (mot-clé kw_attention)"),
    "fiscalite": ("kw_fiscalite", "nature fiscale des revenus pour un résident canadien (mot-clé kw_fiscalite)"),
    "role": ("role", "rôle de l'actif dans un portefeuille"),
}


def valeurs(cellule) -> list[str]:
    if pd.isna(cellule):
        return []
    return [v.strip() for v in str(cellule).split(";") if v.strip()]


sortie = {"source": "data_extended/asset_criteria.csv", "nb_actifs": len(crit),
          "noms": dict(zip(crit.ticker, crit.name)), "dimensions": {}}
for dim, (col, desc) in DIMENSIONS.items():
    index: dict[str, list[str]] = {}
    for tk, cell in zip(crit.ticker, crit[col]):
        for v in valeurs(cell):
            index.setdefault(v, []).append(tk)
    sortie["dimensions"][dim] = {"colonne": col, "description": desc, "valeurs": dict(sorted(index.items()))}

out = ROOT / "mvp_profil" / "vocabulaire_actifs.json"
out.write_text(json.dumps(sortie, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{out.relative_to(ROOT)} : {len(DIMENSIONS)} dimensions, "
      f"{sum(len(d['valeurs']) for d in sortie['dimensions'].values())} valeurs, {len(crit)} actifs")
