"""Fiches du chercheur et expositions FNB produites depuis les fichiers locaux.

Les identifiants sont rapprochés par égalité ou table explicite, jamais par
préfixe. Une classe d'action du même émetteur contribue à l'exposition à
l'entreprise, sans devenir un titre équivalent pour l'exécution ou les prix.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "config" / "correspondances_positions_fnb.json"


def txt(v) -> str:
    return "" if pd.isna(v) else str(v)


def resoudre_position(symbole: str, actifs: dict, table: dict) -> tuple[str, str]:
    """Ticker de référence et nature du lien ; une absence reste inconnue."""
    symbole = symbole.strip()
    if symbole in actifs:
        return symbole, "titre_exact"
    for rubrique, nature in (("aliases_cotation", "alias_cotation"), ("meme_emetteur", "meme_emetteur")):
        correspondance = table.get(rubrique, {}).get(symbole)
        if correspondance:
            cible = correspondance.get("ticker")
            if cible not in actifs:
                raise ValueError(f"Cible de position absente de l'univers : {symbole} -> {cible}")
            return cible, nature
    return "", "non_relie"


def construire(racine: Path = ROOT) -> dict:
    crit = pd.read_csv(racine / "data_extended" / "asset_criteria.csv")
    table = json.loads((racine / "config" / TABLE.name).read_text(encoding="utf-8"))

    def both(nom):
        return pd.concat([pd.read_csv(racine / d / nom) for d in ("data_extra", "data_extended")], ignore_index=True)

    actifs = {r.ticker: {"nom": r.name, "classe": r.asset_class, "secteur": txt(r.sector), "pays": txt(r.country),
                         "region": txt(r.region), "devise": r.currency, "themes": txt(r.themes),
                         "exclusions": txt(r.kw_exclusions), "fossile": txt(r.fossil_involvement),
                         "controverses": txt(r.controversy_topics)} for r in crit.itertuples()}
    fnb = {}
    for r in both("etf_top_holdings.csv").itertuples():
        symbole = txt(r.holding_symbol)
        reference, nature = resoudre_position(symbole, actifs, table)
        fnb.setdefault(r.etf, []).append({"symbole": symbole, "nom": txt(r.holding_name),
                                        "poids": round(float(r.weight), 6), "ticker": reference,
                                        "nature_lien": nature})
    actualites = {}
    for r in both("news_recent.csv").sort_values("published_utc", ascending=False).itertuples():
        lst = actualites.setdefault(r.ticker, [])
        if len(lst) < 8:
            lst.append({"date": txt(r.published_utc)[:10], "titre": txt(r.title), "url": txt(r.url)})
    controverses = {}
    for r in both("esg_controversies.csv").itertuples():
        controverses.setdefault(r.ticker, []).append({"date": txt(r.event_date), "sujet": txt(r.topic),
                                                     "resume": txt(r.summary), "source": txt(r.source)})
    return {"source": "data_extra/ et data_extended/", "correspondances_positions": "config/" + TABLE.name,
            "actifs": actifs, "fnb": fnb, "actualites": actualites, "controverses": controverses}


if __name__ == "__main__":
    donnees = construire()
    out = ROOT / "mvp_profil" / "donnees_chercheur.json"
    out.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
    relies = sum(bool(p["ticker"]) for positions in donnees["fnb"].values() for p in positions)
    print(f"{out.relative_to(ROOT)} : {len(donnees['actifs'])} actifs, {len(donnees['fnb'])} FNB, "
          f"{relies} positions reliées explicitement à l'univers")
