"""Mesure la fiabilité du classement des réponses libres (classificateur + critique) sur un jeu de phrases étiquetées.

Pourquoi : les confiances des modèles ne sont pas calibrées, et « même réponse, même profil » doit se prouver.
Ce script rejoue chaque phrase N fois avec le VRAI modèle (Amazon Bedrock par défaut) et mesure, par critère :
  - bon classement     : valeur validée, identique à l'étiquette ;
  - fausse validation  : valeur validée alors qu'elle est fausse, ou alors que rien ne devait l'être (le cas grave) ;
  - manqué             : une valeur était attendue, rien n'a été validé (la question sera simplement reposée) ;
  - bon refus          : rien n'était attendu, rien n'a été validé ;
  - répétabilité       : part des (phrase, critère) dont le résultat est identique aux N passages.

Usage :
  python mvp_profil/evaluer_classement.py --verifier          # contrôle le jeu de phrases, AUCUN appel au modèle
  python mvp_profil/evaluer_classement.py --repetitions 10    # mesure réelle (appels facturés au compte AWS)
Sortie : mvp_profil/validation/resultats_classement.json et un tableau à recopier dans la documentation technique.
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


def charger() -> list[dict]:
    phrases = json.loads(JEU.read_text(encoding="utf-8"))["phrases"]
    for p in phrases:
        for cid, vals in p["attendu"].items():
            assert cid in CRITERES and cid not in MESURES, f"{p['id']} : critère inconnu ou mesuré ({cid})"
            assert all(v in CRITERES[cid]["valeurs"] for v in vals), f"{p['id']} : valeur hors liste pour {cid} : {vals}"
            assert CRITERES[cid]["multiple"] or len(vals) <= 1, f"{p['id']} : {cid} n'accepte qu'une valeur"
    return phrases


def juger(attendu: list[str], resultat) -> str:
    valide = bool(resultat and resultat.valide)
    obtenu = sorted(resultat.valeurs) if valide else []
    if not attendu:
        return "fausse_validation" if valide else "bon_refus"
    if not valide:
        return "manque"
    return "bon_classement" if obtenu == sorted(attendu) else "fausse_validation"


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

    from agents import backend_anthropic, backend_bedrock, debattre
    backend = backend_anthropic(a.cle_anthropic) if a.cle_anthropic else backend_bedrock()
    details, verdicts, stables = [], Counter(), 0
    par_cat: dict[str, Counter] = {}
    for p in phrases:
        passages = []
        for _ in range(a.repetitions):
            d = debattre(backend, [(p["question"], p["reponse"])], list(p["attendu"]), seuil=a.seuil)
            passages.append({cid: juger(att, d.resultats.get(cid)) for cid, att in p["attendu"].items()})
            sys.stdout.write("."); sys.stdout.flush()
        for cid in p["attendu"]:
            vus = [x[cid] for x in passages]
            stables += len(set(vus)) == 1
            for v in vus:
                verdicts[v] += 1
                par_cat.setdefault(p["categorie"], Counter())[v] += 1
            details.append({"id": p["id"], "categorie": p["categorie"], "critere": cid, "attendu": p["attendu"][cid],
                            "verdicts": dict(Counter(vus))})
    total = sum(verdicts.values())
    attendus = verdicts["bon_classement"] + verdicts["manque"] + sum(
        1 for d in details if d["attendu"] for _ in range(d["verdicts"].get("fausse_validation", 0)))
    resume = {
        "date": datetime.now().isoformat(timespec="seconds"), "modele": backend.model, "acces": backend.nom,
        "seuil": a.seuil, "repetitions": a.repetitions, "phrases": len(phrases), "couples": n_crit, "essais": total,
        "taux_bon_classement": round(verdicts["bon_classement"] / max(1, attendus), 3),
        "taux_fausse_validation": round(verdicts["fausse_validation"] / max(1, total), 3),
        "taux_manque": round(verdicts["manque"] / max(1, attendus), 3),
        "repetabilite": round(stables / max(1, n_crit), 3),
        "par_categorie": {k: dict(v) for k, v in par_cat.items()},
    }
    (ICI / "validation" / "resultats_classement.json").write_text(
        json.dumps({"resume": resume, "details": details}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n\n| Mesure | Valeur |\n|---|---|")
    for k in ("taux_bon_classement", "taux_fausse_validation", "taux_manque", "repetabilite"):
        print(f"| {k} | {resume[k]:.1%} |")
    print(f"\n{resume['essais']} essais, modèle {resume['modele']}. Détail : mvp_profil/validation/resultats_classement.json")


if __name__ == "__main__":
    main()
