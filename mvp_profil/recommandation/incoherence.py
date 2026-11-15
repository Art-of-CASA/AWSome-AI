"""Détecteur d'incohérence entre une DEMANDE et le PROFIL (code, pas un agent). Cas de référence : Robert.

Il ne lit jamais la justification de la personne : il compare la demande aux contraintes et au verdict figé.
Sa sortie nomme la tension, la preuve, et ce que la personne pourrait vouloir revoir, sans moraliser.
"""
from __future__ import annotations


def detecter(analyse, verdict: dict) -> dict:
    c = analyse.contraintes
    tensions = [{"critere": r["critere"], "gravite": r["etat"], "constat": r["texte"], "preuves": r.get("preuves", [])}
                for r in verdict.get("raisons", []) if r["etat"] in ("en_tension", "exclu", "a_surveiller", "contraire")]
    faits = verdict.get("faits_actif") or {}
    declare, observe = c.get("attrait_mode_declare"), c.get("attrait_mode_observe")
    mediatise = "tres_mediatise" in str(faits.get("attention") or "")
    if mediatise and declare == "non" and observe == "oui":
        tensions.append({"critere": "D8O", "gravite": "a_surveiller", "preuves": ["profil:D8", "profil:D8O"],
                         "constat": "La personne se dit peu tentée par les titres médiatisés, mais en a choisi un dans la mise en situation."})
    elif mediatise and (declare in ("parfois", "oui") or observe == "oui"):
        tensions.append({"critere": "D8", "gravite": "a_surveiller", "preuves": ["profil:D8"],
                         "constat": "Titre très médiatisé, et le profil signale un attrait pour ce type de titre : "
                                    "l'intérêt du moment est à distinguer des objectifs."})
    graves = [t for t in tensions if t["gravite"] in ("en_tension", "exclu")]
    pistes = []
    if verdict.get("part_max_compatible_pct"):
        pistes.append(f"Une part de {verdict['part_max_compatible_pct']:.0f} % au plus resterait compatible avec les plafonds du profil.")
    elif verdict.get("verdict") in ("en_tension", "exclu"):
        pistes.append("Aucune part de ce titre n'est compatible avec le profil tel qu'il est saisi.")
    if graves:
        pistes.append("Si la demande reflète un vrai changement, c'est le profil qu'il faut revoir (écran « Et si… ? »), "
                      "pas le verdict : il est recalculé à partir des réponses.")
    return {"incoherent": bool(graves), "nb_tensions": len(tensions), "tensions": tensions, "pistes": pistes,
            "regle": "La justification écrite ne modifie jamais le verdict : seule une réponse du profil le peut."}
