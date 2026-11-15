"""Contrôles de gouvernance, visibles et exécutés par le code (les Guardrails Bedrock les doublent côté modèle).

- Simulation uniquement : aucune fonction d'exécution d'ordre n'existe dans ce dépôt.
- Aucun conseil financier personnalisé, aucune prédiction de rendement à partir du passé.
- Données manquantes visibles ; faits, hypothèses et scénarios fictifs distingués.
"""
from __future__ import annotations

import re

from .analyse import MENTION

INTERDITS = [
    (r"\bje (?:vous|te) (?:conseille|recommande)\b", "conseil personnalisé"),
    (r"\b(?:vous devriez|tu devrais|il faut|vous devez) (?:acheter|vendre|investir)\b", "conseil personnalisé"),
    (r"\b(?:achetez|vendez|n'hésitez pas à acheter)\b", "incitation à agir"),
    (r"\b(?:garanti|garantie|sans risque|sûr de gagner|ne peut pas perdre)\b", "promesse"),
    (r"\b(?:va|vont|devrait|devraient) (?:monter|grimper|doubler|rebondir|surperformer|rapporter)\b", "prédiction de rendement"),
    (r"\b(?:rapportera|rapporteront|montera|monteront|grimpera|doublera|doubleront|gagnera|gagnerez|progressera|rebondira|surperformera)\b",
     "prédiction de rendement"),
    (r"\brendement (?:attendu|futur|prévu) de \d", "prédiction de rendement"),
    (r"\b100 ?% explicable\b", "formulation trompeuse (dire « traçable »)"),
]
NATURES = {"fait": "Fait : donnée publique datée", "hypothese": "Hypothèse : seuil choisi par l'équipe, ajustable",
           "scenario": "Scénario fictif : ce qui se passerait si…", "reglage": "Réglage prudent : question sans réponse"}


def controler_texte(texte: str) -> dict:
    """Refuse un texte qui conseille, promet ou prédit. Insensible à la casse."""
    trouves = [{"motif": nature, "extrait": m.group(0)} for motif, nature in INTERDITS
               for m in re.finditer(motif, texte, flags=re.IGNORECASE)]
    return {"conforme": not trouves, "infractions": trouves}


def finaliser(texte: str) -> str:
    """La mention « simulation » est ajoutée par le code : elle ne dépend pas du modèle."""
    return texte.rstrip() + "\n\n— " + MENTION if MENTION not in texte else texte


def controler_portefeuille(pf: dict) -> dict:
    """Garde-fou avant affichage : un portefeuille qui contient un actif exclu ou dépasse un plafond est signalé."""
    if "erreur" in pf:
        return {"affichable": False, "motif": pf["erreur"], "controles": []}
    lignes = [{"contrainte": c["contrainte"], "etat": c["etat"], "valeur": c["valeur"], "limite": c["limite"]} for c in pf["controles"]]
    bloquants = [c for c in pf["controles"] if c["etat"] == "en_conflit" and c["critere"] == "H2"]
    return {"affichable": not bloquants, "conflits": pf["conflits"], "a_confirmer": pf["a_confirmer"], "controles": lignes,
            "somme_poids_pct": round(sum(l["poids_pct"] for l in pf["lignes"]) + pf["non_investi_pct"], 1),
            "motif": "Un actif exclu figure dans le portefeuille : affichage bloqué." if bloquants else None}


def bilan(analyse, pf: dict | None = None) -> list[dict]:
    """Contrôles visibles à l'écran, chacun avec son résultat."""
    c = analyse.contraintes
    out = [
        {"controle": "Simulation uniquement", "resultat": "ok", "detail": "Aucun ordre réel : aucune fonction d'exécution n'existe."},
        {"controle": "Profils fictifs", "resultat": "ok", "detail": "Aucune donnée de client réel n'est utilisée par la démonstration."},
        {"controle": "Critères inconnus", "resultat": "info" if c["inconnus"] else "ok",
         "detail": f"{len(c['inconnus'])} critère(s) sans réponse utilisable ; {len(c['reglages_prudents'])} réglage(s) prudent(s) appliqué(s) et signalé(s)."},
        {"controle": "Filtres sans effet", "resultat": "info" if c["sans_effet"] else "ok",
         "detail": "; ".join(f"{s['critere']} {s['valeur']} : {s['raison']}" for s in c["sans_effet"]) or "Aucun."},
        {"controle": "Profil provisoire", "resultat": "info" if c["synthese_provisoire"] else "ok",
         "detail": " ".join(c["alertes"]) or "Aucune alerte."},
    ]
    if pf is not None:
        g = controler_portefeuille(pf)
        out.append({"controle": "Contraintes du portefeuille", "resultat": "ok" if g["affichable"] and not g.get("conflits") else "alerte",
                    "detail": ("Conflits : " + ", ".join(g.get("conflits") or [])) if g.get("conflits") else
                              ("À confirmer : " + ", ".join(g.get("a_confirmer") or [])) if g.get("a_confirmer") else "Toutes respectées."})
    return out
