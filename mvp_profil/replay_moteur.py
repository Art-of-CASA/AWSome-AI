"""État et comptabilité déterministes du replay ; les valeurs du navigateur ne font jamais foi."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from uuid import uuid4

QUOTIDIEN = json.loads((Path(__file__).parent / "replay_quotidien.json").read_text(encoding="utf-8"))
ACTIONS = {"reduire": "Réduire de moitié", "vendre": "Tout vendre", "renforcer": "Renforcer (ajouter 2 000 $)"}


def nouvel_etat(cle: str) -> dict:
    return {"cle": cle, "session_id": uuid4().hex, "cursor": 0, "seq": 0, "actions": [], "decisions": [],
            "investi": 10000.0, "cash": 0.0, "apports": 10000.0, "premiere_reduction": None,
            "vente_totale": None, "fini": False}


def _entier(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def comptabiliser(values: list[float], actions: list[dict], cursor: int) -> dict:
    """Rejoue les ordres au prix réellement affiché, puis valorise au curseur demandé."""
    investi, cash, apports, precedent = 10000.0, 0.0, 10000.0, 0
    reduction = vente = None
    decisions = []
    for a in actions:
        index, action = a["index"], a["action"]
        investi *= values[index] / values[precedent]
        variation = values[index] / 10000 - 1
        observation = {"perte": -variation, "decision": ACTIONS[action], "index": index}
        if action == "reduire":
            cash += investi / 2
            investi /= 2
            if reduction is None:
                reduction = observation
        elif action == "vendre":
            cash += investi
            investi = 0.0
            vente = observation
        else:
            investi += 2000.0
            apports += 2000.0
        decisions.append({"seance": index, "variation_marche": round(variation, 4), "decision": ACTIONS[action]})
        precedent = index
    investi *= values[cursor] / values[precedent]
    return {"investi": investi, "cash": cash, "apports": apports, "premiere_reduction": reduction,
            "vente_totale": vente, "decisions": decisions}


def appliquer_message(etat: dict, message, values: list[float]) -> dict:
    """Valide tout le journal avant mutation ; les événements anciens sont sans effet.

    Une fin anticipée n'est possible qu'après une vente totale. Une pause n'est jamais une vente.
    Les prix et les montants des actions sont exclusivement recalculés ici.
    """
    if not isinstance(message, dict) or message.get("session_id") != etat["session_id"]:
        return etat
    seq = message.get("seq")
    if not _entier(seq) or seq < 1:
        raise ValueError("Numéro du replay invalide.")
    if seq <= etat["seq"] or etat["fini"]:
        return etat
    cursor, actions, complete = message.get("cursor"), message.get("actions"), message.get("complete")
    if not _entier(cursor) or not etat["cursor"] <= cursor < len(values):
        raise ValueError("Position du replay invalide.")
    if not isinstance(actions, list) or len(actions) > 32 or not isinstance(complete, bool):
        raise ValueError("Journal du replay invalide.")
    if actions[:len(etat["actions"])] != etat["actions"]:
        raise ValueError("Une décision déjà enregistrée ne peut pas être effacée.")
    precedent, vendu, ajouts = 0, False, 0
    for a in actions:
        if not isinstance(a, dict) or set(a) != {"index", "action"}:
            raise ValueError("Décision de replay invalide.")
        index, action = a["index"], a["action"]
        if (not _entier(index) or not precedent <= index <= cursor or not isinstance(action, str)
                or action not in ACTIONS or vendu):
            raise ValueError("Ordre des décisions de replay invalide.")
        ajouts += action == "renforcer"
        if ajouts > 10:
            raise ValueError("La simulation limite les apports supplémentaires à 20 000 $.")
        vendu = action == "vendre"
        precedent = index
    # Une nouvelle décision ne peut pas être placée rétroactivement avant un curseur reçu.
    if any(a["index"] < etat["cursor"] for a in actions[len(etat["actions"]):]):
        raise ValueError("Une décision ne peut pas être ajoutée dans le passé.")
    if complete and cursor != len(values) - 1 and not vendu:
        raise ValueError("Le replay doit arriver à son terme avant la révélation.")
    if vendu and actions[-1]["index"] != cursor:
        raise ValueError("La vente termine le replay à la séance affichée.")
    resultat = deepcopy(etat)
    resultat.update(cursor=cursor, seq=seq, actions=deepcopy(actions), fini=complete or cursor == len(values) - 1 or vendu)
    resultat.update(comptabiliser(values, actions, cursor))
    return resultat


def baisse_montree(values: list[float], cursor: int) -> float:
    """Perte depuis le capital initial la plus forte réellement visible avant la fin de l'expérience."""
    return max(0.0, 1 - min(values[:cursor + 1]) / 10000) * 100


def resultat_final(etat: dict, values: list[float]) -> float:
    """Suite historique du portefeuille après les décisions, sans changer l'observation B2."""
    compte = comptabiliser(values, etat["actions"], len(values) - 1)
    return compte["investi"] + compte["cash"]
