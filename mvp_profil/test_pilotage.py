"""Ordre des questions : sécurité, utilité, groupes intacts et absence de mutation.
Lancer : python mvp_profil/test_pilotage.py (aucun appel au modèle).
"""
from copy import deepcopy
import json
from pathlib import Path

from criteres import SECTIONS
from pilotage import expliquer_priorite, prioriser_criteres, prioriser_items, prioriser_sections
from profil import entree


p = {}
candidats = ["D5", "D6", "G3", "B1", "A7", "A2", "A3", "A9"]
ordre = prioriser_criteres(p, candidats)
assert set(ordre) == set(candidats) and len(ordre) == len(candidats)
assert ordre.index("A2") < ordre.index("B1") < ordre.index("D5")
assert ordre.index("A7") < ordre.index("D5")
assert ordre.index("D6") < ordre.index("D5") and ordre.index("G3") < ordre.index("D5")
assert ordre == prioriser_criteres(p, candidats), "Ordre reproductible"

# Une information connue ne monopolise plus le prochain tour, même si sa bande
# est normalement prioritaire. Le tri ne supprime aucune réponse à recueillir.
p["A2"] = entree(["plus_15_ans"], "QCM")
assert prioriser_criteres(p, ["A2", "D6"])[0] == "D6"
avant = deepcopy(p)
prioriser_criteres(p, candidats)
assert p == avant

# Le moteur considère aussi la capacité masquée par un autre facteur limitant :
# avec le B1 prudent par défaut, l'horizon a encore une valeur d'information.
contexte = {cid: entree([val], "QCM") for cid, val in
            (("A4", "moyenne_25_60"), ("A5", "3_6_mois"), ("A6", "stables"), ("A8", "0"), ("A7", "non"))}
info = expliquer_priorite(contexte, "A2")
assert info["impact_composantes_points"] > 0
assert info["inconnu"] and "projet" in info["raison"]

# La hiérarchie de sécurité résiste à un grand impact potentiel sur le budget.
personas = Path(__file__).parent / "personas"
p = json.loads((personas / "amira.json").read_text(encoding="utf-8"))["profil"]
del p["A7"]
assert prioriser_criteres(p, ["D5", "A7", "B1"])[0] == "A7"

# Les questions regroupées restent atomiques ; tous les critères sont conservés.
items = [SECTIONS[1]["items"][-1], SECTIONS[0]["items"][0], SECTIONS[1]["items"][2]]
avant = deepcopy(items)
tries = prioriser_items({}, items)
assert tries[0]["critere"] == "A3"
assert next(x for x in tries if x["type"] == "libre")["criteres"] == ["A6", "A12", "A8", "A7"]
assert items == avant

# Ordre de pages explicite : les exclusions et l'accès précèdent les goûts.
avant = deepcopy(SECTIONS)
sections = prioriser_sections({}, SECTIONS)
titres = [s["titre"] for s in sections]
assert titres == ["Votre projet", "Votre situation", "Vous et le risque", "Vos connaissances",
                  "Vos valeurs et votre compte", "Vos préférences"], titres
assert SECTIONS == avant
assert sorted(it["id"] for sec in sections for it in sec["items"]) == sorted(
    it["id"] for sec in SECTIONS for it in sec["items"])
print("Pilotage OK : projet, sécurité, contraintes avant préférences ; impact calculé, groupes et questions préservés")
