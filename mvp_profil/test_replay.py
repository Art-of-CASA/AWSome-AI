"""Replay continu : décisions volontaires, comptabilité exacte et événements obsolètes/bornés."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from replay_moteur import (QUOTIDIEN, appliquer_message, baisse_montree, comptabiliser, nouvel_etat,
                           resultat_final)


VALEURS = [10000.0, 9500.0, 9000.0, 8000.0, 11000.0]


def message(etat, *, cursor=4, actions=None, complete=True, seq=1, **extra):
    return {"session_id": etat["session_id"], "seq": seq, "cursor": cursor,
            "actions": actions or [], "complete": complete, **extra}


def refuse(etat, **kwargs):
    copie = deepcopy(etat)
    try:
        appliquer_message(etat, message(etat, **kwargs), VALEURS)
    except ValueError:
        assert etat == copie, "Une erreur ne modifie aucune décision déjà validée."
    else:
        raise AssertionError(f"Message invalide accepté : {kwargs}")


# Ne rien faire est un parcours complet et n'invente aucune décision.
etat = nouvel_etat("equilibre")
observe = appliquer_message(etat, message(etat), VALEURS)
assert observe["fini"] and observe["actions"] == [] and observe["decisions"] == []
assert observe["investi"] == 11000 and observe["cash"] == 0
assert abs(baisse_montree(VALEURS, 4) - 20) < 1e-8

# Réduire n'est pas tout vendre ; les liquidités ne subissent plus les variations suivantes.
actions = [{"index": 2, "action": "reduire"}]
reduit = appliquer_message(etat, message(etat, cursor=2, actions=actions, complete=False), VALEURS)
assert not reduit["fini"] and reduit["premiere_reduction"] and reduit["vente_totale"] is None
assert reduit["investi"] == 4500 and reduit["cash"] == 4500
assert resultat_final(reduit, VALEURS) == 10000
assert reduit["cursor"] == 2 and len(reduit["actions"]) == 1

# Une vente à la séance choisie termine immédiatement et ne mesure pas un creux futur.
actions = [{"index": 1, "action": "vendre"}]
vendu = appliquer_message(etat, message(etat, cursor=1, actions=actions), VALEURS)
assert vendu["fini"] and vendu["investi"] == 0 and vendu["cash"] == 9500
assert resultat_final(vendu, VALEURS) == 9500
assert abs(baisse_montree(VALEURS, vendu["cursor"]) - 5) < 1e-8
assert abs(vendu["vente_totale"]["perte"] - .05) < 1e-8

# Les apports sont du capital supplémentaire et sont suivis séparément du rendement.
compte = comptabiliser(VALEURS, [{"index": 3, "action": "renforcer"}], 4)
assert compte["apports"] == 12000 and compte["cash"] == 0 and compte["investi"] == 13750

# Identité, idempotence et chronologie : pas de double ordre ni d'altération du passé.
assert appliquer_message(etat, message(etat, session_id="ancienne-session"), VALEURS) is etat
assert appliquer_message(reduit, message(reduit, seq=1), VALEURS) is reduit
assert appliquer_message(vendu, message(vendu, seq=99), VALEURS) is vendu
for kwargs in ({"cursor": -1}, {"cursor": 100}, {"cursor": True}, {"cursor": 1.5}, {"seq": True},
               {"complete": "oui"}, {"cursor": 2}, {"actions": [{"index": 5, "action": "vendre"}]},
               {"actions": [{"index": True, "action": "vendre"}]},
               {"actions": [{"index": 2, "action": ["vendre"]}]},
               {"actions": [{"index": 2, "action": "acheter"}]},
               {"actions": [{"index": 2, "action": "vendre", "montant": 1}]},
               {"actions": [{"index": 2, "action": "vendre"}]},
               {"actions": [{"index": 2, "action": "vendre"}, {"index": 3, "action": "renforcer"}]},
               {"actions": [{"index": 3, "action": "reduire"}, {"index": 2, "action": "renforcer"}]},
               {"actions": [{"index": 1, "action": "renforcer"}] * 11},
               {"actions": [{"index": 1, "action": "reduire"}] * 33}):
    refuse(etat, **kwargs)
refuse(reduit, seq=2, actions=[])
refuse(reduit, seq=2, actions=[{"index": 1, "action": "reduire"}])
refuse(reduit, seq=2, actions=[{"index": 2, "action": "reduire"}, {"index": 1, "action": "vendre"}])

# Données quotidiennes réelles : même base et même résultat que les scénarios historiques publiés.
scenarios = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
for cle, scenario in QUOTIDIEN.items():
    values, dates, months = scenario["valeurs"], scenario["dates"], scenario["mois_positions"]
    fin = scenario["crise_fin"]
    assert len(values) == len(dates) == len(months) and values[0] == 10000
    assert all(isinstance(v, (float, int)) and v > 0 for v in values)
    assert dates[fin].startswith("2022-") and dates[fin + 1].startswith("2023-")
    assert len(values[:fin + 1]) > 240 and all(x < y for x, y in zip(months, months[1:]))
    assert abs(values[-1] - scenarios["replay"][cle]["fin"]) < 1

print("Replay continu OK : observer sans action, réductions, ventes, apports, validation et données quotidiennes.")
