"""Tests de la synthèse du profil (capacité, tolérance, budget de perte) sur les trois personas de l'énoncé.
Lancer : python mvp_profil/test_synthese.py
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from criteres import CRITERES
from profil import entree
from synthese import HYP, phrase, synthetiser

ICI = Path(__file__).parent
personas = {n: json.loads((ICI / "personas" / f"{n}.json").read_text(encoding="utf-8")) for n in ("amira", "mateo", "robert")}

# Les personas n'utilisent que des critères et des valeurs de la liste fermée
for nom, p in personas.items():
    for cid, e in p["profil"].items():
        assert cid in CRITERES, (nom, cid)
        assert all(x in CRITERES[cid]["valeurs"] for x in e["valeurs"]), (nom, cid, e["valeurs"])
        assert e["source"] in ("énoncé", "hypothèse de test")

s = {n: synthetiser(p["profil"]) for n, p in personas.items()}
for n, x in s.items():
    print(f"{n:7s} {phrase(x)}")
# Trois budgets distincts et ordonnés : Robert < Mateo < Amira
assert s["robert"]["budget_perte_pct"] < s["mateo"]["budget_perte_pct"] < s["amira"]["budget_perte_pct"], s
assert s["robert"]["niveau"] < s["mateo"]["niveau"] < s["amira"]["niveau"]
assert s["robert"]["limite_par"] and "capacité" in s["robert"]["limite_par"]       # horizon de 3 à 5 ans
assert s["amira"]["plafonds"]["crypto_pct"] == 10 and s["mateo"]["plafonds"]["speculatif_pct"] == 0

# Sensibilité : changer UNE réponse change le résultat dans le sens attendu
base = personas["mateo"]["profil"]
p = copy.deepcopy(base); p["A2"]["valeurs"] = ["moins_3_ans"]
assert synthetiser(p)["niveau"] == 1
p = copy.deepcopy(base); p["A5"]["valeurs"] = ["aucun"]
assert synthetiser(p)["niveau"] <= 2 and any("fonds d'urgence" in a for a in synthetiser(p)["alertes"])
p = copy.deepcopy(base); p["A7"]["valeurs"] = ["oui"]
assert synthetiser(p)["niveau"] == 1
p = copy.deepcopy(personas["amira"]["profil"]); p["B3"]["valeurs"] = ["jamais"]
assert synthetiser(p)["tolerance_declaree"]["perte_pct"] == 40 and s["amira"]["tolerance_declaree"]["perte_pct"] == 50

# Observé plus prudent que déclaré : la perte réelle du replay borne le budget (pas d'effet de seuil de classe)
p = copy.deepcopy(personas["amira"]["profil"])
p["B2"] = entree(["10"], "replay", citation="Tout vendre au mois 6", perte=14.9, baisse_max_montree=15.0)
x = synthetiser(p)
assert x["budget_perte_pct"] == 14.9 and x["limite_par"] == ["tolérance observée"], x
p["B2"]["perte"] = 15.1   # 0,2 point de plus : le budget bouge de 0,2 point, pas d'une classe entière
assert synthetiser(p)["budget_perte_pct"] == 15.1
assert (s["robert"]["budget_perte_pct"], s["mateo"]["budget_perte_pct"], s["amira"]["budget_perte_pct"]) == (15, 22, 45)

# Profil vide : tout est au réglage le plus prudent, et c'est signalé
x = synthetiser({})
assert x["niveau"] == 1 and x["budget_perte_pct"] == 5 and len(x["reglages_prudents_appliques"]) >= 8
assert set(HYP["reglages_prudents"]) <= set(CRITERES)
print("Synthèse OK : Robert < Mateo < Amira, sensibilité dans le bon sens, réglages prudents signalés")
