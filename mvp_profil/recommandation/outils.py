"""Outils des agents : la seule façon pour un modèle d'obtenir un fait, un score ou un verdict.

Chaque outil appelle le code déterministe (analyse.py) et renvoie une sortie compacte, avec les identifiants de
preuve. Le même routeur sert en mémoire (par défaut) et derrière AWS Lambda (infra/lambda_outils.py).
Aucun outil n'écrit quoi que ce soit : ni ordre, ni modification du profil.
"""
from __future__ import annotations

from . import incoherence
from .analyse import MENTION, Analyse

OUTILS = [
    {"name": "lire_contraintes", "roles": ("conseiller", "explicateur"),
     "description": "Contraintes tirées du profil de la personne : budget de perte, plafonds, exclusions, préférences, "
                    "critères inconnus et réglages prudents. À appeler avant de parler du profil.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "construire_portefeuille", "roles": ("conseiller",),
     "description": "Mini-portefeuille FICTIF calculé pour ce profil : poids, perte de stress, tension en % et en dollars, "
                    "contrôle de chaque contrainte. Simulation, aucun ordre.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "chercher_actif", "roles": ("conseiller", "explicateur"),
     "description": "Cherche un actif de l'univers par ticker ou par nom et renvoie son verdict pour ce profil : score 0-100, "
                    "seuils, poids maximal compatible, ce qui soutient et ce qui retient, preuves. Dit clairement si l'actif "
                    "est absent de l'univers ou si les données manquent.",
     "input_schema": {"type": "object", "properties": {"actif": {"type": "string", "description": "Ticker ou nom"}}, "required": ["actif"]}},
    {"name": "comparer_actifs", "roles": ("conseiller", "explicateur"),
     "description": "Compare deux actifs critère par critère pour ce profil et donne l'écart décisif.",
     "input_schema": {"type": "object", "properties": {"actif_a": {"type": "string"}, "actif_b": {"type": "string"}},
                      "required": ["actif_a", "actif_b"]}},
    {"name": "evaluer_demande", "roles": ("conseiller", "explicateur"),
     "description": "Verdict d'une demande précise « ajouter ce titre pour telle part du portefeuille ». Verdict = pire critère, "
                    "calculé sur le portefeuille et le montant, figé. Renvoie aussi les incohérences entre la demande et le profil.",
     "input_schema": {"type": "object", "properties": {"actif": {"type": "string"},
                      "part_pct": {"type": "number", "description": "Part du portefeuille demandée, en %"}},
                      "required": ["actif", "part_pct"]}},
    {"name": "et_si", "roles": ("conseiller",),
     "description": "Recalcule tout avec UNE réponse du profil modifiée (scénario fictif, le profil n'est pas changé) et "
                    "liste ce qui change et pourquoi. La valeur doit appartenir à la liste fermée du critère.",
     "input_schema": {"type": "object", "properties": {"critere": {"type": "string", "description": "Identifiant, ex. A2"},
                      "valeur": {"type": "string"}}, "required": ["critere", "valeur"]}},
    {"name": "tester_sensibilite", "roles": ("conseiller",),
     "description": "Met les résultats à l'épreuve : horizon d'un cran, seuils du score, seuil de tension, période sans 2022.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "lire_preuve", "roles": ("explicateur",),
     "description": "Détail d'une preuve par son identifiant (colonne, valeur, date, source, conditions d'utilisation).",
     "input_schema": {"type": "object", "properties": {"identifiant": {"type": "string"}}, "required": ["identifiant"]}},
]


def specifications(role: str) -> list[dict]:
    """Format « toolSpec » de l'API Converse d'Amazon Bedrock."""
    return [{"toolSpec": {"name": o["name"], "description": o["description"], "inputSchema": {"json": o["input_schema"]}}}
            for o in OUTILS if role in o["roles"]]


def _ids(preuves) -> list[str]:
    return [p["id"] if isinstance(p, dict) else p for p in preuves or []]


def _fiche_compacte(f: dict) -> dict:
    if f["verdict"] == "absent":
        return {k: f[k] for k in ("requete", "verdict", "libelle_verdict", "message", "suggestions") if k in f}
    return {"ticker": f["ticker"], "nom": f.get("nom"), "verdict": f["libelle_verdict"], "score": f.get("score"),
            "seuils": f.get("seuils"), "poids_max_pct": f.get("poids_max_pct"), "raison_poids_max": f.get("raison_poids_max"),
            "borne_appliquee": f.get("borne_appliquee"), "couverture_pct": f.get("couverture_pct"),
            "donnees_manquantes": f.get("donnees_manquantes"), "faits": f.get("faits"),
            "criteres": [{"critere": l["critere"], "effet": l["effet"], "etat": l["etat"], "libelle": l["libelle"],
                          "raison": l["raison"], "preuves": l["preuves"]} for l in f.get("lignes", [])],
            "explication": {k: f["explication"].get(k) for k in ("titre", "resume")} if f.get("explication") else None}


def _portefeuille_compact(pf: dict) -> dict:
    if "erreur" in pf:
        return pf
    return {"nature": pf["nature"], "montant_fictif_cad": pf["montant_fictif_cad"],
            "nb_positions": pf["nb_positions"],
            "lignes": [{k: l[k] for k in ("ticker", "nom", "poche", "role", "poids_pct", "montant_cad", "score", "pourquoi")} for l in pf["lignes"]],
            "part_croissance_pct": pf["part_croissance_pct"], "part_amortisseur_pct": pf["part_amortisseur_pct"],
            "seuil_entree": pf["seuil_entree"], "nb_candidats": pf["nb_candidats"],
            "budget_perte_pct": pf["budget_perte_pct"], "budget_perte_cad": pf["budget_perte_cad"],
            "perte_stress_pct": pf["perte_stress_pct"], "perte_stress_cad": pf["perte_stress_cad"],
            "ratio_tension": pf["ratio_tension"], "etat_tension": pf["etat_tension"], "stress": pf["stress"],
            "mesures": pf["mesures"],
            "controles": [{k: c[k] for k in ("contrainte", "critere", "valeur", "limite", "etat", "detail", "preuves")} for c in pf["controles"]],
            "conflits": pf["conflits"], "a_confirmer": pf["a_confirmer"], "message_conflit": pf["message_conflit"],
            "secteurs_pct": dict(list(pf["expositions"]["secteurs_pct"].items())[:6]), "limite_fnb": pf["expositions"]["limite"]}


def executer(analyse: Analyse, nom: str, entree: dict | None = None) -> dict:
    """Routeur unique des outils. Une erreur d'entrée revient en clair : le modèle doit pouvoir la dire."""
    e = entree or {}
    try:
        if nom == "lire_contraintes":
            return analyse.synthese()
        if nom == "construire_portefeuille":
            return {**_portefeuille_compact(analyse.portefeuille), "mention": MENTION}
        if nom == "chercher_actif":
            return {**_fiche_compacte(analyse.rechercher(str(e.get("actif", "")))), "mention": MENTION}
        if nom == "comparer_actifs":
            c = analyse.comparer(str(e.get("actif_a", "")), str(e.get("actif_b", "")))
            if "erreur" in c:
                return c
            return {"a": c["a"], "b": c["b"], "faits_a": c["faits_a"], "faits_b": c["faits_b"], "ecart_decisif": c["ecart_decisif"],
                    "tableau": [{k: x[k] for k in ("critere", "libelle", "effet", "etat_a", "etat_b", "different")} for x in c["tableau"]],
                    "regle": c["regle"], "mention": MENTION}
        if nom == "evaluer_demande":
            v = analyse.demande(str(e.get("actif", "")), float(e.get("part_pct", 0)))
            sortie = {k: v for k, v in v.items() if k not in ("controles", "preuves")}
            sortie["preuves"] = _ids(v.get("preuves"))
            sortie["incoherence"] = incoherence.detecter(analyse, v)
            return sortie
        if nom == "et_si":
            d = analyse.et_si(str(e.get("critere", "")), str(e.get("valeur", "")))
            if "actifs_modifies" in d:
                d = {**d, "actifs_modifies": [a for a in d["actifs_modifies"] if a["change_de_bande"]][:12] or d["actifs_modifies"][:8],
                     "poids_modifies": d["poids_modifies"][:10]}
            return d
        if nom == "tester_sensibilite":
            return analyse.sensibilite()
        if nom == "lire_preuve":
            return analyse.registre.lire(str(e.get("identifiant", ""))) or {"erreur": "Preuve inconnue : aucune donnée n'est inventée."}
    except (ValueError, TypeError, KeyError) as err:
        return {"erreur": f"Entrée invalide pour {nom} : {err}"}
    return {"erreur": f"Outil inconnu : {nom}"}
