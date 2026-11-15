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

# Une explication désigne des réponses et des effets réellement calculés, jamais
# un réglage par défaut présenté comme une déclaration de l'utilisateur.
p = copy.deepcopy(personas["robert"]["profil"])
p["A9"], p["A10"] = entree(["aucun"], "QCM"), entree(["non"], "QCM")
for d in synthetiser(p)["reglages_prudents_appliques"]:
    p[d["critere"]] = entree([d["valeur"]], "QCM")
avant = copy.deepcopy(p)
x = synthetiser(p)
assert p == avant, "L'analyse de sensibilité ne doit pas modifier le profil"
horizon = next(d for d in x["reponses_decisives"] if d["critere"] == "A2")
assert "budget de perte" in horizon["effets"] and horizon["source"] == p["A2"]["source"]
assert horizon["variation_budget_max_points"] > 0
assert not synthetiser({})["reponses_decisives"]
r = x["robustesse"]
assert r["variations_testees"] > 0
assert r["budget_min_pct"] <= x["budget_perte_pct"] <= r["budget_max_pct"]
assert r["etat"] == "sensible" and any(c["critere"] == "A2" for c in r["variations_sensibles"])
assert "intervalle de confiance" in r["limites"]
incomplet = copy.deepcopy(p)
del incomplet["B7"]
assert "B7" in synthetiser(incomplet)["robustesse"]["criteres_a_confirmer"]
assert synthetiser(incomplet)["synthese_provisoire"]

# Une limite observée ne disparaît jamais dans les variations du déclaré.
p = copy.deepcopy(personas["amira"]["profil"])
p["B1"]["declare"] = "50_plus"
p["B2"] = entree(["10"], "replay", perte=14.9)
x = synthetiser(p)
assert x["robustesse"]["budget_max_pct"] <= 14.9
assert all(c["critere"] not in ("B2", "H1") for c in x["robustesse"]["variations_sensibles"])
assert any(d["critere"] == "B2" for d in x["reponses_decisives"])

# Des retraits/revenus essentiels rendent le montant disponible à préciser.
# Aucun plafond financier arbitraire n'est inventé pour combler l'information.
p = copy.deepcopy(personas["amira"]["profil"])
p["A9"], p["A10"] = entree(["reguliers"], "QCM"), entree(["essentiel"], "QCM")
x = synthetiser(p)
assert x["budget_perte_pct"] == 45
assert x["synthese_provisoire"] and x["besoins_liquidite"]["a_preciser"]
assert "montant des retraits" in x["besoins_liquidite"]["informations_manquantes"]
assert any("budget calculé reste provisoire" in a for a in x["alertes"])
assert x["robustesse"]["etat"] == "a_completer"
assert synthetiser({})["robustesse"]["etat"] == "a_completer"

# Une contrainte d'exclusion est expliquée sans prétendre modifier le budget.
p["E5"] = entree(["tabac"], "QCM", citation="Tabac")
tabac = next(d for d in synthetiser(p)["reponses_decisives"] if d["critere"] == "E5")
assert tabac["effets"] == ["contrainte pour la comparaison future"]
assert tabac["variation_budget_max_points"] == 0
print("Explication et robustesse OK : réponses décisives sourcées, variations locales, replay préservé, liquidités à préciser")

# Les raisons expliquent la réponse actuelle et la règle chiffrée réelle, avec
# des libellés lisibles. Elles séparent une borne active d'une contrainte future.
for nom, plafond in (("robert", 2), ("amira", 5)):
    exp = next(d for d in s[nom]["reponses_decisives"] if d["critere"] == "A2")
    assert f"capacité plafonnée au niveau {plafond} sur 5" in exp["raison"], exp
    assert "composante limitante" in exp["raison"], exp
    assert "plus_15_ans" not in exp["raison"] and "3_5_ans" not in exp["raison"]
    fourchette = next(d for d in s[nom]["reponses_decisives"] if d["critere"] == "B6")
    assert "Selon la table de l'équipe" in fourchette["raison"]
    print(f"{nom} : {exp['raison']}")
p = copy.deepcopy(personas["amira"]["profil"])
p["A7"] = entree(["oui"], "QCM")
dettes = next(d for d in synthetiser(p)["reponses_decisives"] if d["critere"] == "A7")
assert "niveau 1 sur 5" in dettes["raison"]
p["E2"] = entree(["aucune"], "QCM")  # « aucune controverse » est le filtre le plus strict
e2 = next(d for d in synthetiser(p)["reponses_decisives"] if d["critere"] == "E2")
assert "Je les refuse toutes" in e2["raison"]
assert e2["effets"] == ["contrainte pour la comparaison future"]
print("Raisons concrètes OK : horizon/plafond, capacité limitante, mesure observée et exclusions strictes")
