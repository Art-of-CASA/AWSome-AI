"""Mesure le classement des réponses libres sans confondre stabilité et exactitude.

Chaque phrase est rejouée N fois avec le VRAI modèle (Bedrock par défaut).
La répétabilité compare les valeurs effectivement produites ET le statut :
« validé », « retenable » ou « incertain ». Deux erreurs différentes ne sont donc
pas stables ; une même erreur répétée reste une erreur, même si elle est stable.

Les erreurs des réponses validées et des réponses retenables sont comptées
séparément. « Retenable » signifie admissible après ce débat, selon les contrôles
du moteur ; ce script ne simule pas la réponse à une reformulation du parcours.
Les confiances déclarées par les modèles ne sont pas des probabilités calibrées.

Usage :
  python mvp_profil/evaluer_classement.py --verifier          # aucun appel au modèle
  python mvp_profil/evaluer_classement.py --repetitions 10    # appels réels facturés
Sortie : mvp_profil/validation/resultats_classement.json, avec les sorties de chaque passage.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from criteres import CRITERES, MESURES

ICI = Path(__file__).parent
JEU = ICI / "validation" / "phrases_etiquetees.json"
UTILISABLES = ("validé", "retenable")


def echanges_pour(phrase: dict) -> list[tuple[str, str]]:
    """Les cas simples restent compatibles ; un cas peut aussi porter sur une conversation."""
    echanges = phrase.get("echanges")
    if echanges is None:
        echanges = [(phrase.get("question"), phrase.get("reponse"))]
    if not isinstance(echanges, (list, tuple)) or not echanges or not all(
            isinstance(e, (list, tuple)) and len(e) == 2 and all(isinstance(t, str) for t in e)
            for e in echanges):
        raise ValueError(f"{phrase.get('id', '?')} : échanges invalides")
    return [tuple(e) for e in echanges]


def charger() -> list[dict]:
    contenu = json.loads(JEU.read_text(encoding="utf-8"))
    if not isinstance(contenu, dict) or not isinstance(contenu.get("phrases"), list):
        raise ValueError("Le jeu doit contenir une liste de phrases.")
    phrases = contenu["phrases"]
    ids = set()
    for p in phrases:
        if not isinstance(p, dict) or not isinstance(p.get("id"), str) or not p["id"]:
            raise ValueError("Chaque phrase doit avoir un identifiant texte non vide.")
        if p["id"] in ids:
            raise ValueError(f"Identifiant de phrase dupliqué : {p['id']}")
        ids.add(p["id"])
        echanges_pour(p)
        if not isinstance(p.get("attendu"), dict):
            raise ValueError(f"{p['id']} : les valeurs attendues doivent former un objet.")
        for cid, vals in p["attendu"].items():
            if cid not in CRITERES or cid in MESURES:
                raise ValueError(f"{p['id']} : critère inconnu ou mesuré ({cid})")
            if not isinstance(vals, list) or any(not isinstance(v, str) or v not in CRITERES[cid]["valeurs"] for v in vals):
                raise ValueError(f"{p['id']} : valeur hors liste pour {cid} : {vals}")
            if len(vals) != len(set(vals)) or (not CRITERES[cid]["multiple"] and len(vals) > 1):
                raise ValueError(f"{p['id']} : valeurs répétées ou cardinalité invalide pour {cid}")
    return phrases


def sortie_effective(resultat) -> dict:
    """Conserve la sortie utile à l'audit, pas uniquement son verdict d'évaluation."""
    from agents import retenable

    statut = ("validé" if resultat and resultat.valide else
              "retenable" if retenable(resultat) else "incertain")
    return {"valeurs": sorted(resultat.valeurs) if resultat else [], "statut": statut,
            "citation": resultat.citation if resultat else "",
            "confiance_declaree": resultat.confiance if resultat else None,
            "accord_critique": getattr(resultat, "accord_critique", None),
            "motif": resultat.motif if resultat else "Aucun résultat"}


def signature_sortie(sortie: dict) -> tuple:
    """L'ordre d'un ensemble de valeurs et la confiance ne changent pas sa classification."""
    return tuple(sorted(sortie["valeurs"])), sortie["statut"]


def repetable(sorties: list[dict]) -> bool:
    return len(sorties) >= 2 and len({signature_sortie(s) for s in sorties}) == 1


def juger_sortie(attendu: list[str], sortie: dict) -> str:
    statut = sortie["statut"]
    if statut not in UTILISABLES:
        return "manque" if attendu else "bon_refus"
    correct = bool(attendu) and sorted(sortie["valeurs"]) == sorted(attendu)
    if statut == "validé":
        return "bon_classement" if correct else "fausse_validation"
    return "bon_classement_retenable" if correct else "fausse_retention"


def juger(attendu: list[str], resultat) -> str:
    return juger_sortie(attendu, sortie_effective(resultat))


def resumer(details: list[dict]) -> dict:
    """Statistiques indépendantes du backend, testables sans appels au modèle.

    Une absence d'observation donne None, pas un taux d'erreur artificiellement nul.
    Les dénominateurs sont exportés pour rendre les taux vérifiables.
    """
    verdicts, statuts, par_cat = Counter(), Counter(), {}
    attendus = 0
    for d in details:
        for s in d["sorties"]:
            verdict = juger_sortie(d["attendu"], s)
            verdicts[verdict] += 1
            statuts[s["statut"]] += 1
            attendus += bool(d["attendu"])
            par_cat.setdefault(d["categorie"], Counter())[verdict] += 1
    total = sum(verdicts.values())
    repetes = [d for d in details if len(d["sorties"]) >= 2]

    def taux(nombre, denominateur):
        return round(nombre / denominateur, 3) if denominateur else None

    return {
        "couples": len(details), "essais": total,
        "taux_bon_classement": taux(verdicts["bon_classement"], attendus),
        "taux_bon_classement_utilisable": taux(verdicts["bon_classement"] +
                                                verdicts["bon_classement_retenable"], attendus),
        "taux_fausse_validation": taux(verdicts["fausse_validation"], total),
        "taux_fausse_retention": taux(verdicts["fausse_retention"], total),
        "taux_erreur_parmi_valides": taux(verdicts["fausse_validation"], statuts["validé"]),
        "taux_erreur_parmi_retenables": taux(verdicts["fausse_retention"], statuts["retenable"]),
        "taux_manque": taux(verdicts["manque"], attendus),
        "repetabilite": taux(sum(repetable(d["sorties"]) for d in repetes), len(repetes)),
        "denominateurs": {"tous_essais": total, "essais_avec_valeur_attendue": attendus,
                          "sorties_validees": statuts["validé"], "sorties_retenables": statuts["retenable"],
                          "couples_rejoues": len(repetes)},
        "verdicts": dict(verdicts), "statuts": dict(statuts),
        "par_categorie": {k: dict(v) for k, v in par_cat.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--verifier", action="store_true", help="contrôle le jeu de phrases sans appeler le modèle")
    ap.add_argument("--repetitions", type=int, default=10)
    ap.add_argument("--seuil", type=float, default=0.80)
    ap.add_argument("--cle-anthropic", default="", help="secours : clé de l'API Anthropic au lieu de Bedrock")
    a = ap.parse_args()
    phrases = charger()
    n_crit = sum(len(p["attendu"]) for p in phrases)
    print(f"{len(phrases)} phrases, {n_crit} couples (phrase, critère) ; catégories : {dict(Counter(p['categorie'] for p in phrases))}")
    if a.verifier:
        print("Jeu de phrases valide. Aucun appel au modèle.")
        return
    if a.repetitions < 2:
        ap.error("La mesure de répétabilité exige au moins deux répétitions.")
    if not 0.5 <= a.seuil <= 0.95:
        ap.error("Le seuil doit être compris entre 0,50 et 0,95.")

    from agents import backend_anthropic, backend_bedrock, debattre
    backend = backend_anthropic(a.cle_anthropic) if a.cle_anthropic else backend_bedrock()
    details = []
    for p in phrases:
        echanges = echanges_pour(p)
        passages = []
        for repetition in range(1, a.repetitions + 1):
            d = debattre(backend, echanges, list(p["attendu"]), seuil=a.seuil)
            passages.append({cid: {"repetition": repetition, **sortie_effective(d.resultats.get(cid))}
                             for cid in p["attendu"]})
            sys.stdout.write("."); sys.stdout.flush()
        for cid, attendu in p["attendu"].items():
            sorties = [x[cid] for x in passages]
            for s in sorties:
                s["verdict"] = juger_sortie(attendu, s)
            details.append({"id": p["id"], "categorie": p["categorie"], "critere": cid, "attendu": attendu,
                            "echanges": echanges, "repetable": repetable(sorties), "sorties": sorties,
                            "verdicts": dict(Counter(s["verdict"] for s in sorties))})
    resume = {
        "date": datetime.now().isoformat(timespec="seconds"), "modele": backend.model, "acces": backend.nom,
        "seuil": a.seuil, "repetitions": a.repetitions, "phrases": len(phrases), **resumer(details),
        "note": "Confiances déclarées non calibrées. Retenable décrit une possibilité de maintien après ce débat ; "
                "le parcours complet avec réponse à une reformulation n'est pas simulé.",
    }
    (ICI / "validation" / "resultats_classement.json").write_text(
        json.dumps({"version_schema": 2, "resume": resume, "details": details}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n\n| Mesure | Valeur |\n|---|---|")
    for k in ("taux_bon_classement", "taux_bon_classement_utilisable", "taux_fausse_validation",
              "taux_fausse_retention", "taux_erreur_parmi_valides", "taux_erreur_parmi_retenables",
              "taux_manque", "repetabilite"):
        valeur = "non mesuré" if resume[k] is None else f"{resume[k]:.1%}"
        print(f"| {k} | {valeur} |")
    print(f"\n{resume['essais']} essais, modèle {resume['modele']}. Détail : mvp_profil/validation/resultats_classement.json")


if __name__ == "__main__":
    main()
