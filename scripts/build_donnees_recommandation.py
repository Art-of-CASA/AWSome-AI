"""Prépare les données que le site lit pour la recommandation : mvp_profil/recommandation/donnees/.

    python scripts/build_donnees_recommandation.py            régénère
    python scripts/build_donnees_recommandation.py --verifier  échoue si les données ne sont plus à jour

Le paquet déployé ne contient que mvp_profil/ : comme scenarios.json ou donnees_chercheur.json, les données de la
recommandation y sont donc copiées ou précalculées à partir des fichiers du dépôt, sans téléchargement.
  actifs.csv            copie de data_extended/asset_criteria.csv (l'univers : ajouter une ligne suffit)
  prix_cad.csv          prix ajustés quotidiens convertis en CAD, comme scripts/compute_metrics.py
  fnb.json              principales positions et secteurs des FNB, rattachés aux actifs de l'univers
  *.json                copies de config/ (correspondances, hypothèses, règles, sources des colonnes)
  origine.json          empreintes des fichiers sources, pour détecter des données périmées
À relancer après tout changement de asset_criteria.csv, des prix ou de config/.
"""
from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "mvp_profil" / "recommandation" / "donnees"
DEPART, ETENDU, EXTRA, CONFIG = (RACINE / "Datathon2026" / "awsome-ai_starter", RACINE / "data_extended",
                                 RACINE / "data_extra", RACINE / "config")
COPIES = {"actifs.csv": ETENDU / "asset_criteria.csv", "correspondances.json": CONFIG / "correspondances.json",
          "hypotheses_recommandation.json": CONFIG / "hypotheses_recommandation.json",
          "regles_appariement.json": CONFIG / "regles_appariement.json", "sources_colonnes.json": CONFIG / "sources_colonnes.json"}
SOURCES = [*COPIES.values(), DEPART / "prices_daily.csv", ETENDU / "prices_daily.csv", ETENDU / "fx_to_cad_daily.csv",
           EXTRA / "etf_top_holdings.csv", ETENDU / "etf_top_holdings.csv", EXTRA / "etf_sector_weights.csv",
           ETENDU / "etf_sector_weights.csv", CONFIG / "correspondances_positions_fnb.json"]


def empreintes() -> dict[str, str]:
    return {p.relative_to(RACINE).as_posix(): hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest() for p in SOURCES}


def prix_cad() -> pd.DataFrame:
    p = pd.concat([pd.read_csv(DEPART / "prices_daily.csv"), pd.read_csv(ETENDU / "prices_daily.csv")], ignore_index=True)
    p["date"] = pd.to_datetime(p["date"])
    fx = pd.read_csv(ETENDU / "fx_to_cad_daily.csv", parse_dates=["date"])
    morceaux = []
    for (tk, devise), g in p.groupby(["ticker", "currency"]):
        g = g.sort_values("date")
        f = fx[fx.currency == devise].sort_values("date")[["date", "cad_per_unit"]]
        m = pd.merge_asof(g[["date", "adj_close"]], f, on="date", direction="backward")
        m["cad"] = m.adj_close * m.cad_per_unit
        morceaux.append(m.assign(ticker=tk)[["date", "ticker", "cad"]])
    large = pd.concat(morceaux).dropna().pivot_table(index="date", columns="ticker", values="cad", aggfunc="last").sort_index()
    return large[large.index.dayofweek < 5].ffill(limit=5)  # jours ouvrables ; les cryptos cotent 7 jours sur 7


def fnb(tickers: set[str]) -> dict:
    alias = json.loads((CONFIG / "correspondances_positions_fnb.json").read_text(encoding="utf-8"))
    table = {k: v["ticker"] for bloc in ("aliases_cotation", "meme_emetteur") for k, v in alias.get(bloc, {}).items()}
    vers_gics = {k: v for k, v in json.loads((CONFIG / "correspondances.json").read_text(encoding="utf-8"))["secteurs_fnb_vers_gics"].items()
                 if not k.startswith("_")}
    positions: dict[str, dict[str, float]] = {}
    secteurs: dict[str, dict[str, float]] = {}
    for dossier in (EXTRA, ETENDU):
        for ligne in csv.DictReader((dossier / "etf_top_holdings.csv").open(encoding="utf-8", newline="")):
            symbole = (ligne.get("holding_symbol") or "").strip()
            cible = symbole if symbole in tickers else table.get(symbole)
            if cible in tickers and ligne.get("weight"):
                d = positions.setdefault(ligne["etf"], {})
                d[cible] = round(d.get(cible, 0.0) + float(ligne["weight"]), 6)
        for ligne in csv.DictReader((dossier / "etf_sector_weights.csv").open(encoding="utf-8", newline="")):
            secteur = vers_gics.get(ligne.get("sector", ""))
            if secteur and ligne.get("weight"):
                secteurs.setdefault(ligne["etf"], {})[secteur] = round(float(ligne["weight"]), 6)
    return {"positions": positions, "secteurs": secteurs,
            "limite": "Principales positions seulement (exposition minimale connue) ; secteurs selon les fiches de fonds."}


def construire():
    SORTIE.mkdir(parents=True, exist_ok=True)
    for nom, source in COPIES.items():
        (SORTIE / nom).write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
    prix = prix_cad()
    prix.index = prix.index.strftime("%Y-%m-%d")
    prix.to_csv(SORTIE / "prix_cad.csv", float_format="%.6g", lineterminator="\n")
    tickers = {l["ticker"] for l in csv.DictReader((SORTIE / "actifs.csv").open(encoding="utf-8", newline=""))}
    (SORTIE / "fnb.json").write_text(json.dumps(fnb(tickers), ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (SORTIE / "origine.json").write_text(json.dumps({"sources": empreintes(), "periode": [prix.index[0], prix.index[-1]],
                                                     "nb_actifs": len(tickers), "nb_series_de_prix": prix.shape[1]},
                                                    ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sans_prix = sorted(tickers - set(prix.columns))
    print(f"Données de recommandation : {len(tickers)} actifs, {prix.shape[1]} séries de prix du {prix.index[0]} au {prix.index[-1]}"
          + (f" ; SANS PRIX (non retenus dans un portefeuille) : {', '.join(sans_prix)}" if sans_prix else ""))


def a_jour() -> bool:
    chemin = SORTIE / "origine.json"
    return chemin.exists() and json.loads(chemin.read_text(encoding="utf-8")).get("sources") == empreintes()


if __name__ == "__main__":
    if "--verifier" in sys.argv:
        if not a_jour():
            sys.exit("Données de recommandation périmées : relancer python scripts/build_donnees_recommandation.py")
        print("Données de recommandation à jour.")
    else:
        construire()
