"""Orchestration testable : une question choisie, une réponse conservée, aucun doublon dû au modèle.

Les faits numériques explicites passent par des règles avant toute analyse IA.
La fraîcheur est suivie par critère : parler des dettes ne périme pas l'horizon.
Le registre des questions reste indépendant du temps de réponse des services.
"""
from __future__ import annotations

from concurrent.futures import Future
from time import monotonic

from agents import AgentError, _citation_presente, meilleur, retenable
from criteres import DECLARATIFS
from entretien import CRITERES_CONVERSATION, OUVERTURE, demande_correction
from profil import connu, deduire, entree
from questions_conversation import choisir_question, enregistrer_question
from reponses_directes import analyser_reponses
from taches import expiree, suivre_tache


def creer(questions_posees: dict | None = None) -> dict:
    c = {"echanges": [], "question": OUVERTURE, "question_cible": OUVERTURE, "cibles_question": ["A3", "A2"],
         "restants": list(CRITERES_CONVERSATION), "jobs": [], "analyses_couvertes": {},
         "versions_integrees": {}, "versions_reponses": {}, "versions_directes": {}, "revisions": {},
         "reponses_recues": {}, "questions_posees": questions_posees if questions_posees is not None else {},
         "meilleurs": {}, "traces": [], "evenements": [], "tours": 0, "fin": False, "attente": False,
         "erreur": None, "suivi": {}, "reformules": [], "relances_posees": {}}
    enregistrer_question(c["questions_posees"], {"criteres": c["cibles_question"]}, 0)
    for cid in c["cibles_question"]:
        c["evenements"].append({"type": "question", "conversation": "profil", "critere": cid,
                                "tour": 0, "nature": "initiale", "raison": "projet et horizon"})
    return c


def _clore(c: dict, cid: str) -> None:
    if cid in c["restants"]:
        c["restants"].remove(cid)
    c["suivi"].pop(cid, None)
    c["revisions"].pop(cid, None)


def recevoir(c: dict, profil: dict, texte: str) -> list[str]:
    """Enregistre immédiatement les réponses explicites et le référent des autres réponses."""
    question, cibles = c["question"], list(c["cibles_question"])
    c["echanges"].append((question, texte))
    c["tours"] += 1
    n = len(c["echanges"])
    for cid in cibles:
        c["reponses_recues"][cid] = n
        c["versions_reponses"][cid] = n
    if demande_correction(texte):
        for cid in DECLARATIFS:
            if connu(profil, cid):
                c["revisions"][cid] = n
                c["versions_reponses"][cid] = n
    lecture = analyser_reponses(c.get("question_cible", question), texte, DECLARATIFS, criteres_question=cibles)
    echos = []
    for cid, reponse in lecture["reponses"].items():
        profil[cid] = dict(reponse)
        c["versions_directes"][cid] = n
        c["versions_reponses"][cid] = n
        c["versions_integrees"][cid] = n
        _clore(c, cid)
        c["evenements"].append({"type": "reponse", "conversation": "profil", "critere": cid,
                                "tour": n, "obtenu": list(reponse["valeurs"]), "utilisable": True,
                                "source": reponse["source"], "citation": reponse["citation"]})
        nombre = reponse.get("nombre")
        minimum = reponse.get("nombre_min")
        if cid == "A2":
            echos.append(f"Horizon retenu : {'au moins ' if nombre is None else ''}{nombre if nombre is not None else minimum:g} ans."
                         if nombre is not None or minimum is not None else "Votre horizon est enregistré.")
        elif cid == "A5":
            echos.append(f"Réserve retenue : {'au moins ' if nombre is None else ''}{nombre if nombre is not None else minimum:g} mois de dépenses."
                         if nombre is not None or minimum is not None else "Votre réserve est enregistrée.")
    for cid, precision in lecture["a_preciser"].items():
        if cid in cibles or cid in c["revisions"]:
            c["suivi"][cid] = precision["motif"]
            if cid in c["revisions"] and connu(profil, cid):
                precedent = profil[cid]
                profil[cid] = entree([], "correction ambiguë", texte, 0, "incertain",
                                      motif=precision["motif"], precedent=precedent)
                if cid in CRITERES_CONVERSATION and cid not in c["restants"]:
                    c["restants"].append(cid)
    for cid in deduire(profil):
        _clore(c, cid)
    return echos


def planifier(c: dict, profil: dict, executeur, backend, analyser, seuil: float) -> None:
    n = len(c["echanges"])
    if not n:
        return
    en_cours = {cid for j in c["jobs"] for cid in j["criteres"] + j["facultatifs"]}
    candidats = list(dict.fromkeys(c["restants"] + list(c["revisions"])))
    demandes = [cid for cid in candidats if cid not in en_cours and
                c["analyses_couvertes"].get(cid, 0) < n and
                c["versions_directes"].get(cid, 0) < c["revisions"].get(cid, n)]
    autres = [cid for cid in DECLARATIFS if cid not in candidats and cid not in en_cours and not connu(profil, cid)
              and c["analyses_couvertes"].get(cid, 0) < n]
    if not demandes and not autres:
        return
    # La sûreté n'est pas assouplie parce que le modèle a tardé à répondre.
    seuils = {cid: seuil for cid in demandes + autres}
    historique = list(c["echanges"])
    try:
        fut = executeur.submit(analyser, backend, historique, demandes, seuils, autres)
    except AgentError as exc:
        fut = Future()
        fut.set_exception(exc)
    c["jobs"].append(suivre_tache({"future": fut, "criteres": demandes, "facultatifs": autres, "n": n,
                      "echanges": historique, "soumis_le": monotonic(),
                      "versions": {cid: c["versions_reponses"].get(cid, 0) for cid in demandes + autres},
                      "revisions": {cid: c["revisions"][cid] for cid in demandes if cid in c["revisions"]}}))
    c["analyses_couvertes"].update({cid: n for cid in demandes + autres})


def integrer(c: dict, profil: dict) -> None:
    for job in [j for j in c["jobs"] if j["future"].done() or expiree(j)]:
        try:
            if expiree(job):
                job["future"].cancel()
                raise AgentError("Délai du contrôle dépassé ; réponse conservée.")
            resultats = job["future"].result()
        except Exception as e:  # une panne ne signifie pas que la personne doit redire sa réponse
            c["traces"].append({"question": "conversation", "tours": [], "resultats": {},
                                "erreur": str(e), "tour": job["n"]})
            for cid in job["criteres"]:
                if cid in c["reponses_recues"] and not connu(profil, cid):
                    profil[cid] = entree([], "analyse indisponible", statut="incertain", confiance=0,
                                          citation=job["echanges"][-1][1], motif="Réponse conservée ; contrôle indisponible")
            c["jobs"].remove(job)
            continue
        for cid in job["criteres"] + job["facultatifs"]:
            r = resultats.get(cid)
            version = job["versions"].get(cid, 0)
            if version < c["versions_reponses"].get(cid, 0):
                continue
            if c["versions_directes"].get(cid, -1) >= version:
                continue  # une inférence IA ne remplace pas une valeur explicite lue par une règle
            revision = cid in job["revisions"]
            if connu(profil, cid) and not revision:
                continue
            if revision:
                debut = job["revisions"][cid] - 1
                if not r or not _citation_presente(r.citation, job["echanges"][debut:]):
                    if r and r.valide and r.valeurs == profil[cid]["valeurs"]:
                        c["revisions"].pop(cid, None)
                    continue
                c["revisions"].pop(cid, None)
            if r and r.valeurs and _citation_presente(r.citation, job["echanges"]):
                c["meilleurs"][cid] = meilleur(c["meilleurs"].get(cid), r)
                if r.valide or retenable(r):
                    profil[cid] = entree(r.valeurs, "conversation (IA)", r.citation, r.confiance,
                                          "validé" if r.valide else "retenu", r.motif)
                    c["versions_integrees"][cid] = job["n"]
                    _clore(c, cid)
                    c["evenements"].append({"type": "reponse", "conversation": "profil", "critere": cid,
                                            "tour": job["n"], "obtenu": list(r.valeurs), "utilisable": True,
                                            "source": "conversation (IA)", "citation": r.citation})
                    continue
            # Une clarification exige un manque identifié, pas un simple score de confiance.
            if cid in c["reponses_recues"] or revision:
                raison = getattr(r, "motif_precision", "") if r else ""
                explicite = bool(r and getattr(r, "precision_necessaire", False) and raison)
                if explicite:
                    c["suivi"][cid] = raison
                if not connu(profil, cid) or revision:
                    profil[cid] = entree([], "conversation à préciser", statut="incertain", confiance=0,
                                          citation=r.citation if r else job["echanges"][-1][1],
                                          motif=raison or (r.motif if r else "Information non établie"))
        for cid in deduire(profil):
            _clore(c, cid)
        c["traces"].append({"question": "conversation", "tours": [],
                            "resultats": {cid: vars(r) for cid, r in resultats.items()}, "tour": job["n"]})
        c["jobs"].remove(job)


def suivante(c: dict, profil: dict, max_tours: int) -> dict:
    actifs = {cid for j in c["jobs"] for cid in j["criteres"] + j["facultatifs"]}
    attente = [cid for cid in c["reponses_recues"] if cid in actifs and not connu(profil, cid)]
    if c["tours"] >= max_tours:
        return {"message": "Je termine la vérification de vos réponses." if c["jobs"] else
                "Merci, vos réponses sont conservées. Passons aux choix et aux mises en situation.",
                "criteres": [], "clarification": False, "attendre": bool(c["jobs"]),
                "termine": not c["jobs"], "raison": "budget de conversation atteint"}
    return choisir_question(profil, c["restants"], c["questions_posees"], en_analyse=attente,
                            a_clarifier=c["suivi"])


def poser(c: dict, decision: dict, prefixe: str = "") -> None:
    enregistrer_question(c["questions_posees"], decision, c["tours"])
    c.update(question=prefixe + decision["message"], question_cible=decision["message"], cibles_question=list(decision["criteres"]),
             fin=decision["termine"], attente=decision["attendre"])
    for cid in decision["criteres"]:
        if decision["clarification"]:
            c["reformules"].append(cid)
        c["evenements"].append({"type": "question", "conversation": "profil", "critere": cid,
                                "tour": c["tours"], "nature": "clarification" if decision["clarification"] else "initiale",
                                "raison": c["suivi"].get(cid, decision["raison"])})
