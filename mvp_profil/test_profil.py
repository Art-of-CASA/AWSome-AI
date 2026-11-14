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
