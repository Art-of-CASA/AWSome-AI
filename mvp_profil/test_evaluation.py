"""Tests hors ligne des mesures de stabilité/exactitude, sans client ni appel au modèle."""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import agents
import evaluer_classement as evaluation
from agents import Resultat
from evaluer_classement import (charger, echanges_pour, juger_sortie, repetable, resumer,
                               signature_sortie, sortie_effective)


def sortie(valeurs, statut="validé", confiance=0.9):
    return {"valeurs": valeurs, "statut": statut, "confiance_declaree": confiance}


# Les deux résultats sont faux, mais leurs valeurs différentes interdisent de les déclarer répétables.
faux1, faux2 = sortie(["3_5_ans"]), sortie(["5_10_ans"])
assert juger_sortie(["plus_15_ans"], faux1) == juger_sortie(["plus_15_ans"], faux2) == "fausse_validation"
assert not repetable([faux1, faux2])

# Stabilité et exactitude restent indépendantes : une erreur stable reste une fausse validation.
assert repetable([faux1, dict(faux1)])
assert juger_sortie(["plus_15_ans"], faux1) == "fausse_validation"

# Ordre d'une sélection multiple et confiance fluctuante ne changent pas la classification effective.
multi1 = sortie(["ia", "sante"], confiance=0.90)
multi2 = sortie(["sante", "ia"], confiance=0.87)
assert signature_sortie(multi1) == signature_sortie(multi2) and repetable([multi1, multi2])
assert not repetable([multi1]) and not repetable([])

# Refus, réponse retenable et réponse validée sont des états différents, même avec les mêmes valeurs.
refus = sortie(["3_5_ans"], "incertain")
retenu = sortie(["3_5_ans"], "retenable")
assert not repetable([refus, retenu]) and not repetable([retenu, faux1])
assert juger_sortie([], refus) == "bon_refus"
assert juger_sortie([], retenu) == "fausse_retention"
assert juger_sortie(["3_5_ans"], retenu) == "bon_classement_retenable"
assert juger_sortie(["3_5_ans"], refus) == "manque"

# Le statut exporté suit les contrôles effectifs : un refus explicite à 95 % reste incertain.
conteste = Resultat("A2", ["3_5_ans"], "dans quatre ans", .95, False, "Désaccord du critique", False)
faible_accord = Resultat("A2", ["3_5_ans"], "dans quatre ans", .70, False, "Confiance 70 % sous le seuil de 80 %", True)
valide = Resultat("A2", ["3_5_ans"], "dans quatre ans", .92, True, "ok", True)
assert sortie_effective(conteste)["statut"] == "incertain"
assert sortie_effective(faible_accord)["statut"] == "retenable"
assert sortie_effective(valide)["statut"] == "validé"
assert sortie_effective(None)["valeurs"] == [] and sortie_effective(None)["statut"] == "incertain"

# Des dénominateurs distincts évitent de diluer les erreurs des réponses retenables dans toutes les réponses.
details = [
    {"categorie": "variation", "attendu": ["plus_15_ans"], "sorties": [faux1, faux2]},
    {"categorie": "stable_faux", "attendu": ["plus_15_ans"], "sorties": [faux1, dict(faux1)]},
    {"categorie": "refus", "attendu": [], "sorties": [refus, retenu]},
    {"categorie": "retenu_correct", "attendu": ["3_5_ans"], "sorties": [retenu, dict(retenu)]},
]
s = resumer(details)
assert s["essais"] == 8 and s["repetabilite"] == 0.5
assert s["verdicts"]["fausse_validation"] == 4 and s["verdicts"]["fausse_retention"] == 1
assert s["taux_bon_classement"] == 0 and s["taux_bon_classement_utilisable"] == 0.333
assert s["taux_erreur_parmi_valides"] == 1 and s["taux_erreur_parmi_retenables"] == 0.333
assert s["denominateurs"]["sorties_retenables"] == 3
assert resumer([])["repetabilite"] is None and resumer([])["taux_erreur_parmi_retenables"] is None

# Un cas multi-tour transmet toute la correction, le jeu existant reste valide sans modèle.
p = {"id": "test", "echanges": [["Horizon ?", "Douze ans"], ["Toujours ?", "Non, quatre ans"]]}
assert echanges_pour(p)[-1] == ("Toujours ?", "Non, quatre ans")
assert charger()

# Le programme complet exporte les sorties réelles de chaque passage, sans construire de client cloud.
anciens = (evaluation.ICI, evaluation.charger, agents.backend_bedrock, agents.debattre, sys.argv)
cas = {"id": "simulation", "categorie": "correction", "echanges": p["echanges"],
       "attendu": {"A2": ["plus_15_ans"]}}
predictions = iter([valide, faible_accord])
appels = []


def faux_debat(backend, echanges, ids, seuil):
    appels.append(echanges)
    return SimpleNamespace(resultats={"A2": next(predictions)})


try:
    with tempfile.TemporaryDirectory(prefix="alphaforge-evaluation-") as dossier:
        evaluation.ICI = Path(dossier)
        (evaluation.ICI / "validation").mkdir()
        evaluation.charger = lambda: [cas]
        agents.backend_bedrock = lambda: SimpleNamespace(model="modele_simule", nom="hors ligne")
        agents.debattre = faux_debat
        sys.argv = ["evaluer_classement.py", "--repetitions", "2"]
        with contextlib.redirect_stdout(io.StringIO()):
            evaluation.main()
        rapport = json.loads((evaluation.ICI / "validation" / "resultats_classement.json").read_text(encoding="utf-8"))
        assert rapport["version_schema"] == 2 and rapport["resume"]["repetabilite"] == 0
        trace = rapport["details"][0]
        assert [s["statut"] for s in trace["sorties"]] == ["validé", "retenable"]
        assert [s["verdict"] for s in trace["sorties"]] == ["fausse_validation", "fausse_retention"]
        assert trace["sorties"][0]["citation"] == "dans quatre ans"
        assert len(appels) == 2 and appels[0][-1] == ("Toujours ?", "Non, quatre ans")
finally:
    evaluation.ICI, evaluation.charger, agents.backend_bedrock, agents.debattre, sys.argv = anciens

print("Évaluation OK : valeurs + statuts, stabilité indépendante de l'exactitude, erreurs des retenables et traces vérifiables.")
