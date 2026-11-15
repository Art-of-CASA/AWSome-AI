"""Mesures d'un parcours à partir d'événements annotés indépendamment.

Aucune confiance de modèle n'est une étiquette de vérité. Les événements non
annotés sont comptés mais exclus des taux qui exigent une annotation humaine.
Les intervalles de Wilson portent sur des proportions d'événements annotés,
sous hypothèse de cas indépendants ; répéter le même cas ne crée pas de nouveaux
cas représentatifs. Le rapport ne prétend pas mesurer une fiabilité population.

Schéma minimal :
  reponse : conversation, critere, tour, attendu (liste), obtenu (liste),
            utilisable (bool), clarte (claire/ambigue/hors_sujet/vide).
  question : conversation, critere, tour, nature (initiale/clarification),
             justifiee (bool, annotation optionnelle), raison (optionnelle).
  session : conversation, etat (terminee/abandonnee/en_cours), duree_s (optionnel).

CLI : python mvp_profil/evaluation_questions.py evenements.json [--sortie rapport.json]
Le JSON d'entrée est une liste, ou un objet contenant la clé evenements.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median


def proportion(succes: int, total: int) -> dict:
    """Proportion observée et intervalle bilatéral Wilson 95 %, sans fausse précision."""
    if type(succes) is not int or type(total) is not int or total < 0 or not 0 <= succes <= total:
        raise ValueError("Les effectifs doivent être des entiers et vérifier 0 <= succès <= total.")
    if not total:
        return {"nombre": 0, "denominateur": 0, "taux": None, "wilson_95": None}
    z = 1.959963984540054
    p, z2 = succes / total, z * z
    div = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / div
    marge = z * math.sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / div
    return {"nombre": succes, "denominateur": total, "taux": round(p, 6),
            "wilson_95": [round(max(0, centre - marge), 6), round(min(1, centre + marge), 6)]}


def _valeurs(event: dict, cle: str) -> list[str]:
    valeurs = event[cle]
    if not isinstance(valeurs, list) or any(not isinstance(x, str) for x in valeurs):
        raise ValueError(f"{cle} doit être une liste de chaînes.")
    return sorted(valeurs)


def resumer_questions(evenements: list[dict]) -> dict:
    """Ne compte que les observations réellement annotées ; expose tous les dénominateurs."""
    if not isinstance(evenements, list):
        raise ValueError("Les événements doivent être fournis dans une liste.")
    compteurs = Counter()
    premiers = {}
    questions_par_critere = {}
    sessions = {}
    durees = []
    par_raison = Counter()
    for event in evenements:
        if not isinstance(event, dict) or not isinstance(event.get("conversation"), str) or not event["conversation"]:
            raise ValueError("Chaque événement doit nommer une conversation.")
        type_event = event.get("type")
        compteurs["evenements"] += 1
        if type_event == "session":
            etat = event.get("etat")
            if etat not in ("terminee", "abandonnee", "en_cours"):
                raise ValueError("État de session inconnu.")
            # Un état récent remplace le précédent, sans gonfler le dénominateur.
            sessions[event["conversation"]] = event
            continue
        if type_event not in ("reponse", "question"):
            raise ValueError("Type d'événement inconnu.")
        if not isinstance(event.get("critere"), str) or type(event.get("tour")) is not int or event["tour"] < 0:
            raise ValueError("Un critère et un numéro de tour entier sont requis.")
        cle = (event["conversation"], event["critere"])
        if type_event == "question":
            nature = event.get("nature")
            if nature not in ("initiale", "clarification"):
                raise ValueError("Une question doit être initiale ou de clarification.")
            compteurs["questions"] += 1
            questions_par_critere.setdefault(cle, Counter())[nature] += 1
            if "justifiee" in event:
                if type(event["justifiee"]) is not bool:
                    raise ValueError("justifiee doit être un booléen annoté.")
                compteurs["questions_annotees"] += 1
                compteurs["questions_injustifiees"] += not event["justifiee"]
                if nature == "clarification":
                    compteurs["clarifications_annotees"] += 1
                    compteurs["clarifications_injustifiees"] += not event["justifiee"]
                if not event["justifiee"]:
                    par_raison[str(event.get("raison", "raison non renseignée"))] += 1
            else:
                compteurs["questions_non_annotees"] += 1
            continue
        compteurs["reponses"] += 1
        if "attendu" not in event or "clarte" not in event:
            compteurs["reponses_non_annotees"] += 1
            premier = premiers.get(cle)
            if premier is None or event["tour"] < premier["tour"]:
                premiers[cle] = {"tour": event["tour"], "claire": False, "annotee": False,
                                 "correcte_acceptee": False}
            continue
        attendu, obtenu = _valeurs(event, "attendu"), _valeurs(event, "obtenu")
        if type(event.get("utilisable")) is not bool:
            raise ValueError("utilisable doit être un booléen.")
        clarte = event["clarte"]
        if clarte not in ("claire", "ambigue", "hors_sujet", "vide"):
            raise ValueError("Clarté annotée inconnue.")
        compteurs["reponses_annotees"] += 1
        utilisee = event["utilisable"]
        correcte = bool(attendu) and obtenu == attendu
        compteurs["reponses_utilisables_annotees"] += utilisee
        compteurs["fausses_validations"] += utilisee and not correcte
        if not attendu:
            compteurs["refus_attendus"] += 1
            compteurs["bons_refus"] += not utilisee
        if clarte == "claire" and attendu:
            compteurs["reponses_claires"] += 1
            compteurs["claires_correctes_acceptees"] += utilisee and correcte
            compteurs["abstentions_sur_claires"] += not utilisee
        premier = premiers.get(cle)
        if premier is None or event["tour"] < premier["tour"]:
            premiers[cle] = {"tour": event["tour"], "claire": clarte == "claire" and bool(attendu),
                             "annotee": True, "correcte_acceptee": utilisee and correcte}
    premieres_claires = [e for e in premiers.values() if e["claire"]]
    compteurs["premieres_reponses_non_annotees"] = sum(not e["annotee"] for e in premiers.values())
    for session in sessions.values():
        duree = session.get("duree_s")
        if session["etat"] != "en_cours" and duree is not None:
            if isinstance(duree, bool) or not isinstance(duree, (int, float)) or not math.isfinite(duree) or duree < 0:
                raise ValueError("Une durée doit être finie et positive ou nulle.")
            durees.append(duree)
    etats = Counter(s["etat"] for s in sessions.values())
    exces = [{"conversation": c, "critere": cid, **dict(q)} for (c, cid), q in questions_par_critere.items()
             if q["initiale"] > 1 or q["clarification"] > 1]
    return {
        "effectifs": dict(compteurs),
        "acceptation_correcte_premiere_reponse_claire": proportion(
            sum(e["correcte_acceptee"] for e in premieres_claires), len(premieres_claires)),
        "acceptation_correcte_reponses_claires": proportion(
            compteurs["claires_correctes_acceptees"], compteurs["reponses_claires"]),
        "erreur_parmi_reponses_utilisables": proportion(
            compteurs["fausses_validations"], compteurs["reponses_utilisables_annotees"]),
        "abstention_sur_reponses_claires": proportion(
            compteurs["abstentions_sur_claires"], compteurs["reponses_claires"]),
        "bons_refus": proportion(compteurs["bons_refus"], compteurs["refus_attendus"]),
        "questions_injustifiees": proportion(compteurs["questions_injustifiees"], compteurs["questions_annotees"]),
        "clarifications_injustifiees": proportion(
            compteurs["clarifications_injustifiees"], compteurs["clarifications_annotees"]),
        "questions_par_critere": [{"conversation": c, "critere": cid, "initiales": q["initiale"],
                                   "clarifications": q["clarification"]}
                                  for (c, cid), q in questions_par_critere.items()],
        "exces_questions_par_critere": exces,
        "raisons_questions_injustifiees": dict(par_raison),
        "sessions": {"observees": len(sessions), **dict(etats),
                     "completion_sessions_closes": proportion(etats["terminee"], etats["terminee"] + etats["abandonnee"]),
                     "durees_closes_observees": len(durees), "duree_mediane_s": median(durees) if durees else None},
        "limites": ["Annotations indépendantes requises : une confiance du modèle n'est pas une vérité terrain.",
                    "Wilson 95 % décrit des proportions observées sous hypothèse de cas indépendants. Les réponses d'une même conversation sont corrélées.",
                    "Ne pas compter les répétitions d'une même phrase comme autant de cas distincts représentatifs.",
                    "Le taux de complétion exclut les sessions encore en cours ; tous les états et dénominateurs sont exposés."]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("evenements", type=Path)
    ap.add_argument("--sortie", type=Path)
    args = ap.parse_args()
    contenu = json.loads(args.evenements.read_text(encoding="utf-8"))
    if isinstance(contenu, dict) and "evenements" not in contenu:
        raise ValueError("L'objet d'entrée doit contenir une liste evenements.")
    rapport = resumer_questions(contenu["evenements"] if isinstance(contenu, dict) else contenu)
    texte = json.dumps(rapport, ensure_ascii=False, indent=2)
    if args.sortie:
        args.sortie.write_text(texte, encoding="utf-8")
    else:
        print(texte)


if __name__ == "__main__":
    main()
