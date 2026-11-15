"""Tests de la logique déterministe : curseur, quiz, règles de cohérence, structure du questionnaire.
Lancer : python mvp_profil/test_profil.py
"""
from __future__ import annotations

from criteres import CRITERES, SECTIONS
from profil import appliquer_correctif, entree, incoherences, niveau_quiz, valeur_curseur

items = {it["id"]: it for s in SECTIONS for it in s["items"]}

# Questionnaire : chaque option pointe vers une valeur autorisée du critère, chaque critère existe
for it in items.values():
    for cid in it.get("criteres", [it.get("critere")]):
        assert cid in CRITERES, cid
    for _, val in it.get("options", []):
        assert val is None or val in CRITERES[it["critere"]]["valeurs"], (it["id"], val)
    if it["type"] == "curseur":
        assert all(v in CRITERES[it["critere"]]["valeurs"] for _, v in it["classes"])
    if it["type"] == "quiz":
        assert all(v in CRITERES[it["critere"]]["valeurs"] for v in it["niveaux"].values())

# Curseur -> classe
b1 = items["q_b1"]
assert [valeur_curseur(b1, x) for x in (5, 10, 20, 25, 30, 40, 45, 50, 60)] == \
       ["5", "10", "20", "20", "30", "40", "40", "50_plus", "50_plus"]

# Quiz -> niveau
quiz = items["q_c1"]
assert niveau_quiz(quiz, [1, 0, 1]) == ("avance", 3)
assert niveau_quiz(quiz, [1, 0, 3]) == ("intermediaire", 2)
assert niveau_quiz(quiz, [3, 3, 3]) == ("debutant", 0)

# Cohérence
P = lambda **kw: {k: entree(v, "QCM") for k, v in kw.items()}  # noqa: E731
assert [c["id"] for c in incoherences(P(B1R=["vendre_tout"], B1=["40"]))] == ["R1"]
assert [c["id"] for c in incoherences(P(B1R=["acheter_plus"], B1=["5"]))] == ["R1b"]
assert incoherences(P(B1R=["attendre"], B1=["40"])) == []
assert [c["id"] for c in incoherences(P(A3=["coussin_securite"], A2=["plus_15_ans"]))] == ["R2"]
assert [c["id"] for c in incoherences(P(D1=["actions"], D2=["10"]))] == ["R3"]
assert incoherences(P(D1=["actions", "crypto"], D2=["10"])) == []
assert [c["id"] for c in incoherences(P(E1=["exclure_directe"], D5=["energie_fossile", "ia"]))] == ["R4"]

# Correctif : la contradiction disparaît
profil = P(B1R=["vendre_tout"], B1=["40"])
r1 = incoherences(profil)[0]
appliquer_correctif(profil, r1["options"][0][1], r1["options"][0][0])
assert profil["B1"]["valeurs"] == ["20"] and profil["B1"]["source"] == "cohérence" and incoherences(profil) == []

n_crit = len({c for it in items.values() for c in it.get("criteres", [it.get("critere")])})
print(f"Logique déterministe OK : {len(items)} questions fixes, {n_crit} critères, règles R1 à R4 testées")

# Nouvelles règles (critères ajoutés)
assert [c["id"] for c in incoherences(P(D12=["sans_speculatif"], D2=["10"]))] == ["R5"]
assert [c["id"] for c in incoherences(P(B5=["faible_moins_8"], B1=["40"]))] == ["R6"]
assert [c["id"] for c in incoherences(P(E5=["alcool", "tabac"], D5=["alcool", "ia"]))] == ["R7"]
assert incoherences(P(E5=["aucune"], D5=["aucun"])) == []
print("Règles R5, R6, R7 OK")

# Déductions certaines : ce qui se déduit d'une réponse n'est plus demandé
from profil import connu, deduire  # noqa: E402
p = {"A12": entree(["retraite"], "QCM"), "C2": entree(["aucun"], "QCM"), "D1": entree(["actions", "obligations"], "QCM"),
     "B3": entree(["oui_garde"], "QCM")}
ajoutes = deduire(p)
assert sorted(ajoutes) == ["A6", "D2"], ajoutes  # B3 déjà répondu : pas écrasé
assert p["A6"]["valeurs"] == ["retraite"] and p["A6"]["source"] == "déduction (règle)" and p["D2"]["valeurs"] == ["0"]
assert p["B3"]["valeurs"] == ["oui_garde"] and connu(p, "A6") and not connu(p, "A8")
assert deduire({"D1": entree(["actions", "crypto"], "QCM")}) == []
print("Déductions certaines OK : retraite -> revenus de retraite, pas de crypto acceptée -> 0 %")

# Déclaré vs observé (replay) : le plus prudent l'emporte
from profil import recouper_rupture
p = P(B1=["40"], B2=["10"])
msg = recouper_rupture(p)
assert p["B1"]["valeurs"] == ["10"] and p["H1"]["valeurs"] == ["grand"] and "−10 %" in msg
p = P(B1=["20"], B2=["10"]); recouper_rupture(p); assert p["B1"]["valeurs"] == ["10"] and p["H1"]["valeurs"] == ["faible"]
p = P(B1=["20"], B2=["non_atteint"]); assert recouper_rupture(p) is None and p["B1"]["valeurs"] == ["20"]
p = P(B1=["10"], B2=["30"]); recouper_rupture(p); assert p["B1"]["valeurs"] == ["10"]  # déclaré déjà plus prudent
assert [c["id"] for c in incoherences(P(B5=["elevee_15_25"], B6=["prudent"]))] == ["R8"]
assert [c["id"] for c in incoherences(P(D8=["non"], D8O=["oui"]))] == ["R9"]

# Scénarios précalculés : le compromis risque/rendement est cohérent, 2 titres médiatisés sur 4
import json, pathlib
sc = json.loads((pathlib.Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
f = list(sc["fourchettes"].values())
assert all(a["mauvaise"] >= b["mauvaise"] and a["typique"] <= b["typique"] for a, b in zip(f, f[1:])), "fourchettes non monotones"
assert sum(c["mediatise"] for c in sc["mode"]) == 2 and len(sc["replay"]) == 3
assert all(len(r["arrets"]) == 4 for r in sc["replay"].values())
print("Replay, fourchettes, effet de mode : logique et scénarios OK")
# La série du replay commence à 10 000 $ et chaque arrêt affiche la valeur de la série (bogue de décalage corrigé)
for r in sc["replay"].values():
    assert r["valeurs"][0] == 10000 and r["mois"][0] == "départ"
    assert all(abs(r["valeurs"][a["mois_index"]] - a["valeur"]) < 1 for a in r["arrets"])
print("Replay : série et arrêts alignés")


# ---------- Le plus prudent l'emporte TOUJOURS, et aucune valeur n'est inventée ----------
from profil import appliquer_correctif as _corr  # noqa: E402

# 1. Vendu à −5 % au replay, puis la règle R1b : « je rachèterais » ne remonte plus le point de rupture à 30.
p = P(B1=["40"], B1R=["acheter_plus"])
p["B2"] = entree(["5"], "replay", citation="Tout vendre au mois 3", perte=5.4, baisse_max_montree=15.0)
recouper_rupture(p)
assert p["B1"]["valeurs"] == ["5"] and p["B1"]["declare"] == "40" and p["H1"]["valeurs"] == ["grand"]
r1b = [c for c in incoherences(p) if c["id"] == "R1b"][0]
a_redemander = _corr(p, r1b["options"][1][1], r1b["options"][1][0])
assert a_redemander == ["B1"] and p["B1"]["statut"] == "à préciser" and p["B1"]["valeurs"] == []  # redemandé, pas deviné
p["B1"] = entree(["30"], "réponse libre (IA)", citation="vers trente pour cent")              # la personne répond 30
recouper_rupture(p)
assert p["B1"]["valeurs"] == ["5"] and p["B1"]["declare"] == "30", p["B1"]                         # l'observé l'emporte
recouper_rupture(p)                                                                               # rappel sans effet
assert p["B1"]["valeurs"] == ["5"] and p["H1"]["valeurs"] == ["grand"]

# 2. Aucun correctif n'écrit une valeur que l'option choisie n'énonce pas.
for prof in (P(B1R=["acheter_plus"], B1=["5"]), P(B5=["faible_moins_8"], B1=["40"])):
    for c in incoherences(prof):
        for texte, correctif in c["options"]:
            for cid, vals in correctif.items():
                assert vals is None or cid != "B1" or any(ch.isdigit() for ch in texte), (c["id"], texte)

# 3. « non atteint » ne confirme le déclaré que jusqu'à la baisse montrée.
p = P(B1=["40"]); p["B2"] = entree(["non_atteint"], "replay", baisse_max_montree=15.0, reduction=None)
recouper_rupture(p); assert p["H1"]["valeurs"] == ["non_teste"] and p["B1"]["valeurs"] == ["40"]
p = P(B1=["10"]); p["B2"] = entree(["non_atteint"], "replay", baisse_max_montree=15.0, reduction=None)
recouper_rupture(p); assert p["H1"]["valeurs"] == ["aucun"]

# 4. R3 ne se déclenche pas quand D1 n'est pas encore connu ; R9 n'assouplit jamais D12.
p = P(D2=["5"]); p["D1"] = entree([], "à préciser", statut="à préciser", confiance=0.0)
assert "R3" not in [c["id"] for c in incoherences(p)]
r9 = incoherences(P(D8=["non"], D8O=["oui"], D12=["sans_speculatif"]))[0]
assert "D12" not in r9["options"][0][1]

# 5. Le portefeuille du replay suit le risque et l'horizon déclarés, pas le thème d'intérêt.
import simulations as _sim  # noqa: E402
assert _sim.portefeuille_replay(P(B5=["moderee_8_15"], A2=["3_5_ans"], D5=["ia"])) == "equilibre"
assert _sim.portefeuille_replay(P(B5=["tres_elevee_plus_25"], A2=["plus_15_ans"])) == "technologie"
assert _sim.portefeuille_replay(P(B5=["tres_elevee_plus_25"], A2=["3_5_ans"])) == "equilibre"
print("Prudence garantie OK : R1b ne remonte plus la rupture, correctifs sans valeur inventée, non_teste, R3, R9, replay")
