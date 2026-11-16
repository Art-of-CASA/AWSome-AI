"""Régressions : vente précoce au replay et sélection des fonds défensifs."""
from copy import deepcopy

from reco_tests_commun import Analyse, ch
from profil import entree
from recommandation.appariement import pct


for perte in (0.3, 1.0):
    profil = deepcopy(ch.charger_persona("mateo")["profil"])
    profil["B2"] = entree(["5"], "replay", perte=perte)
    avant = deepcopy(profil)
    a = Analyse(profil)
    pf = a.portefeuille
    assert "erreur" not in pf, pf
    assert pf["nb_positions"] >= 3 and pf["encaisse_pct"] == 0, pf
    assert not pf["conflits"] and not pf["conflit_construction"], pf
    assert pf["budget_perte_pct"] == perte
    assert all(p <= 0.4 for p in pf["poids"].values())
    assert all(a.resultats[t]["verdict"] == "compatible" for t in pf["poids"])
    assert profil == avant

# Un budget réellement trop bas ne doit pas être relevé pour forcer un résultat.
profil["B2"] = entree(["5"], "replay", perte=0.1)
a = Analyse(profil)
assert a.contraintes["budget_perte_pct"] == 0.1
assert "erreur" in a.portefeuille
assert "0,1" in a.portefeuille["erreur"]
assert pct(0.3) != pct(0)
print("Profils personnels : liquidités compatibles diversifiées, limites conservées, cas impossible expliqué.")
