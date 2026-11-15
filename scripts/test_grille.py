"""Test de couverture : le vocabulaire du PROFIL rejoint-il celui des ACTIFS ?

Échoue si :
  - une valeur d'un critère diffère entre mvp_profil/criteres.py et config/criteres_appariement.csv ;
  - une valeur du profil (thèmes, secteur d'emploi, régions, classes, E1, E5, F2, G3) n'a ni correspondance vers une
    colonne d'actif, ni mention explicite « aucun_actif » ou « sans_effet » dans config/correspondances.json ;
  - une correspondance cite une colonne ou une valeur absente de data_extended/asset_criteria.csv, ou ne touche aucun actif.
Lancer : python scripts/test_grille.py
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mvp_profil"))
from criteres import CRITERES, SECTEURS_EMPLOI, THEMES  # noqa: E402

actifs = pd.read_csv(ROOT / "data_extended" / "asset_criteria.csv", dtype=str, keep_default_na=False)
corr = json.loads((ROOT / "config" / "correspondances.json").read_text(encoding="utf-8"))
grille = {l["id"]: l for l in csv.DictReader((ROOT / "config" / "criteres_appariement.csv").open(encoding="utf-8"))}

# 1. Grille et code : mêmes critères, mêmes valeurs
for cid, c in CRITERES.items():
    assert cid in grille, f"{cid} absent de la grille"
    assert grille[cid]["valeurs_profil"] == ", ".join(c["valeurs"]), f"{cid} : valeurs différentes (lancer scripts/sync_grille.py)"


def touches(cond: dict) -> set[str]:
    """Tickers concernés par une condition {colonne, valeurs} ou {toutes: [...]}."""
    if "toutes" in cond:
        ens = [touches(c) for c in cond["toutes"]]
        return set.intersection(*ens)
    assert cond["colonne"] in actifs.columns, f"colonne inconnue : {cond['colonne']}"
    etiquettes = actifs[cond["colonne"]].str.split(";")
    presentes = {e for l in etiquettes for e in l}
    for val in cond["valeurs"]:
        assert val in presentes, f"valeur « {val} » absente de la colonne {cond['colonne']}"
    return set(actifs.ticker[[bool(set(l) & set(cond["valeurs"])) for l in etiquettes]])


def verifier(nom: str, valeurs_profil: list[str], table: dict) -> dict:
    bilan = {}
    for val in valeurs_profil:
        assert val in table, f"{nom} : la valeur du profil « {val} » n'a aucune correspondance"
        c = table[val]
        if "aucun_actif" in c or "sans_effet" in c or "comme" in c:
            bilan[val] = 0
            continue
        conds = [c] if ("colonne" in c or "toutes" in c) else [x for k, x in c.items() if isinstance(x, dict)]
        n = set().union(*[touches(x) for x in conds])
        assert n, f"{nom} : « {val} » ne touche aucun actif (le déclarer en aucun_actif)"
        bilan[val] = len(n)
    return bilan


b = verifier("thèmes D5/D6", THEMES, corr["themes"])
print("Thèmes sans actif (déclarés) :", ", ".join(k for k, n in b.items() if n == 0 and k != "aucun"))
verifier("régions D3", CRITERES["D3"]["valeurs"], corr["regions"])
verifier("classes D1", CRITERES["D1"]["valeurs"], corr["classes"])
verifier("E1", CRITERES["E1"]["valeurs"], corr["E1"])
b = verifier("E5", CRITERES["E5"]["valeurs"], corr["E5"])
print("Exclusions E5 sans actif (déclarées) :", ", ".join(k for k, n in b.items() if n == 0 and k != "aucune"))
verifier("F2", CRITERES["F2"]["valeurs"], corr["F2"])
verifier("G3", CRITERES["G3"]["valeurs"], corr["G3"])
secteurs = set(actifs.sector)
for emploi in SECTEURS_EMPLOI:
    assert emploi in corr["secteur_emploi_vers_gics"], f"secteur d'emploi sans correspondance : {emploi}"
    for g in corr["secteur_emploi_vers_gics"][emploi]:
        assert g in secteurs, f"secteur GICS inconnu des actifs : {g}"
# Les valeurs communes au profil et aux mots-clés d'actif sont bien les mêmes
assert set(CRITERES["B5"]["valeurs"]) == set(actifs.kw_volatilite) | {"moderee_8_15"} or set(actifs.kw_volatilite) <= set(CRITERES["B5"]["valeurs"])
assert set(CRITERES["B7"]["valeurs"]) <= set(actifs.kw_recuperation)

# 2. Non-régression des corrections de données (cas nommés)
a = actifs.set_index("ticker")
assert a.loc["NVDA", "underwater_days"] == "535.0" and a.loc["NVDA", "kw_recuperation"] == "moyenne_1_2_ans"
assert a.loc["ZST.TO", "role"] == "liquidites" and a.loc["TLT", "role"] == "obligations_longues" != a.loc["XBB.TO", "role"]
assert a.loc["ZST.TO", "liquidity_level"] == "elevee" and a.loc["ZST.TO", "complexity"] == "1" and a.loc["XBB.TO", "complexity"] == "1"
assert a.loc["NOVO-B.CO", "role"] == "speculatif" == a.loc["GFI.JO", "role"] and a.loc["GFI.JO", "income_asset"] == "False"
assert "marche_emergent" in a.loc["VWO", "kw_risque_pays"].split(";")
assert a.loc["TTE.PA", "dividend_cut_2022_2025"] == "False" == a.loc["HSBA.L", "dividend_cut_2022_2025"] == a.loc["ZST.TO", "dividend_cut_2022_2025"]
assert a.loc["GOOGL", "established"] == "True" == a.loc["AMZN", "established"] == a.loc["MFC.TO", "established"]
assert a.loc["BTC-USD", "diversifier_vs_world"] == "False" == a.loc["SOL.JO", "diversifier_vs_world"]
assert a.loc["GOOGL", "kw_cycle"] == "cyclique" and a.loc["VOD.JO", "kw_cycle"] == "defensif"
assert a.loc["RY.TO", "country"] == "Canada" and a.loc["AAPL", "country"] == "États-Unis"
assert a.loc["XIU.TO", "fossil_part_energie_fnb"].startswith("0.18") and "energie_fossile_via_fonds" in a.loc["XIU.TO", "kw_exclusions"]
assert a.loc["TLT", "kw_recuperation"] == "jamais_recupere" and a.loc["GLD", "kw_recuperation"] == "baisse_en_cours"
assert a.loc["PG", "horizon_min_years"] == a.loc["SPY", "horizon_min_years"]  # baisse en cours : plus de pénalité
secteurs_fnb = pd.read_csv(ROOT / "data_extended" / "etf_sector_weights.csv")
assert "BNDW" not in set(secteurs_fnb.etf)
print(f"Grille OK : {len(CRITERES)} critères alignés, correspondances vérifiées sur {len(actifs)} actifs, corrections de données en place")
