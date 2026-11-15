"""Ordre déterministe des questions selon leur utilité pour le profil courant.

Le code choisit ce qu'il reste utile de demander ; le modèle formule la question.
Le classement est une heuristique explicite, pas une promesse d'optimum ou une
estimation de probabilité. Il ne supprime aucune question, ne transforme pas une
absence de réponse en consentement, et n'abaisse aucun seuil de validation.

Ordre des prérequis : projet/horizon, disponibilité de l'argent et réserve/dettes,
capacité et risque, contraintes impératives et accès, puis préférences. À priorité
égale, la variation potentielle du résultat calculé aide à choisir. Une question
groupée couvre plusieurs inconnues ; son effort est exprimé en unités relatives,
jamais en secondes prétendument mesurées.
"""
from __future__ import annotations

from criteres import CRITERES
from synthese import CRITERES_CALCULES, avec_valeur, calculer_base, changements, v_connu


BANDES = {
    0: ("A3", "A2"),
    1: ("A9", "A10", "A5", "A7"),
    2: ("A4", "A6", "A8", "B1", "B1R", "B3", "B5", "B7", "C1"),
    3: ("D1", "D2", "D9", "D12", "D4", "D6", "E1", "E2", "E4", "E5", "F2", "G3"),
    4: ("A1", "A12", "C2", "G1", "G2", "B4"),
    5: ("D3", "D5", "D7", "D8", "D11"),
}
BANDE = {cid: niveau for niveau, ids in BANDES.items() for cid in ids}
ORDRE = {cid: i for i, cid in enumerate(cid for ids in BANDES.values() for cid in ids)}
RAISONS = {
    0: "Préciser d'abord le projet et sa date, qui donnent le contexte des réponses suivantes.",
    1: "Vérifier la disponibilité de l'argent, la réserve et les dettes avant d'affiner le risque.",
    2: "Compléter la capacité financière, la tolérance au risque ou les connaissances.",
    3: "Recueillir une contrainte impérative, un plafond ou une limite d'accès avant les préférences.",
    4: "Compléter le contexte nécessaire à l'interprétation du profil.",
    5: "Affiner les préférences après les contraintes et la sécurité.",
}


def expliquer_priorite(profil: dict, cid: str) -> dict:
    """Impact potentiel des valeurs autorisées, sans inventer leur fréquence."""
    inconnu = v_connu(profil, cid) is None
    bande = BANDE.get(cid, 4)
    budget, composantes, limites = 0.0, 0.0, False
    if cid in CRITERES_CALCULES:
        base = calculer_base(profil)
        essais = [calculer_base(avec_valeur(profil, cid, v))
                  for v in CRITERES[cid]["valeurs"] if v != "je_ne_sais_pas"]
        if essais:
            budgets = [s["budget_perte_pct"] for s in essais]
            budget = max(budgets) - min(budgets)
            composantes = max((max(s["composantes_pct"].get(c, 0) for s in essais) -
                               min(s["composantes_pct"].get(c, 0) for s in essais)
                               for c in ("capacité", "tolérance déclarée", "tolérance observée")), default=0)
            limites = any(changements(base, s) for s in essais)
    return {"critere": cid, "inconnu": inconnu, "bande": bande,
            "raison": RAISONS.get(bande, RAISONS[4]),
            "impact_budget_points": round(budget, 1),
            "impact_composantes_points": round(composantes, 1), "modifie_limites": limites}


def _cle(p: dict) -> tuple:
    return (not p["inconnu"], p["bande"], -p["impact_budget_points"],
            -p["impact_composantes_points"], not p["modifie_limites"], ORDRE.get(p["critere"], 100))


def prioriser_criteres(profil: dict, criteres_ids: list[str]) -> list[str]:
    """Réordonne les candidats sans en perdre, et sans modifier le profil."""
    details = {c: expliquer_priorite(profil, c) for c in dict.fromkeys(criteres_ids)}
    return sorted(criteres_ids, key=lambda c: _cle(details[c]))


def _ids(item: dict) -> list[str]:
    return list(item.get("criteres") or ([item["critere"]] if item.get("critere") else []))


def _cle_item(profil: dict, item: dict, details: dict[str, dict]) -> tuple:
    ids = _ids(item)
    inconnus = [c for c in ids if details[c]["inconnu"]]
    if not inconnus:
        return (True, 99, 0)
    bande = min(details[c]["bande"] for c in inconnus)
    cout = {"qcm": 1, "curseur": 1, "qcm_multi": 1.3, "libre": 2,
            "quiz": max(1, len(item.get("questions", [])))}.get(item.get("type"), 1)
    utilite = sum(1 + details[c]["impact_budget_points"] / 5 +
                  details[c]["impact_composantes_points"] / 10 + details[c]["modifie_limites"]
                  for c in inconnus) / cout
    return (False, bande, -utilite)


def prioriser_items(profil: dict, items: list[dict]) -> list[dict]:
    """Garde les groupes de questions intacts, y compris les quiz et questions libres."""
    details = {c: expliquer_priorite(profil, c) for it in items for c in _ids(it)}
    return sorted(items, key=lambda it: _cle_item(profil, it, details))


def prioriser_sections(profil: dict, sections: list[dict]) -> list[dict]:
    """Réordonne des pages non commencées ; ne doit pas déplacer la page déjà ouverte.

    Les pages sources restent intactes. Après la conversation, les « Compléments »
    sont triés selon leurs inconnues ; les pages entièrement connues restent en fin.
    """
    priorites = {"Votre projet": 0, "Votre situation": 1, "Vous et le risque": 2,
                 "Vos connaissances": 3, "Vos valeurs et votre compte": 4, "Vos préférences": 5}
    details = {c: expliquer_priorite(profil, c) for sec in sections for it in sec["items"] for c in _ids(it)}

    def cle(sec):
        inconnus = [c for it in sec["items"] for c in _ids(it) if details[c]["inconnu"]]
        if not inconnus:
            return (True, 99)
        rang = priorites.get(sec["titre"], min(details[c]["bande"] for c in inconnus))
        return (False, rang)

    return [{**sec, "items": prioriser_items(profil, sec["items"])} for sec in sorted(sections, key=cle)]
