"""Synthèse déterministe du profil : capacité, tolérance, niveau de risque et budget de perte.

Le profil est une liste de critères ; le moteur d'appariement a besoin d'un RÉSUMÉ chiffré :
  - capacité            : ce que la personne PEUT perdre (horizon, épargne, fonds d'urgence, revenus, charges) ;
  - tolérance déclarée  : ce qu'elle DIT accepter (point de rupture B1, réaction à −20 % B1R) ;
  - tolérance observée  : ce qu'elle a FAIT dans les mises en situation (replay B2, fourchettes B6) ;
  - budget de perte du portefeuille = le PLUS PRUDENT des trois, en % ; la composante qui limite est nommée ;
  - niveau de risque (1 à 5) : étiquette lisible déduite du budget ; le moteur utilise le budget, pas l'étiquette ;
  - plafond de volatilité (B5) et durée sous l'eau supportable (B7), à vérifier sur le PORTEFEUILLE.
Aucune IA. Toutes les tables sont des HYPOTHÈSES déclarées, dans hypotheses_profil.json.
Un critère inconnu ou incertain reçoit le réglage le plus prudent, et cette substitution est signalée.
Simulation éducative : ce résumé ne constitue pas un conseil financier.
"""
from __future__ import annotations

import json
from pathlib import Path

HYP = json.loads((Path(__file__).parent / "hypotheses_profil.json").read_text(encoding="utf-8"))
UTILISABLES = ("validé", "retenu")
POURCENT_RUPTURE = {"5": 5, "10": 10, "20": 20, "30": 30, "40": 40, "50_plus": 50}


def synthetiser(profil: dict, hyp: dict = HYP) -> dict:
    defauts: list[dict] = []   # réglages prudents appliqués faute de réponse utilisable
    alertes: list[str] = []

    def v(cid: str) -> str | None:
        """Valeur du critère ; à défaut, réglage prudent (signalé) ; None si aucun réglage n'est prévu."""
        e = profil.get(cid)
        if e and e.get("statut") in UTILISABLES and e.get("valeurs"):
            return e["valeurs"][0]
        d = hyp["reglages_prudents"].get(cid)
        if d is not None and cid not in [x["critere"] for x in defauts]:
            defauts.append({"critere": cid, "valeur": d})
        return d

    # ---------- Capacité ----------
    horizon = v("A2")
    plafond = hyp["plafond_capacite_par_horizon"][horizon]
    capacite, facteurs = plafond, [{"critere": "A2", "valeur": horizon, "effet": f"plafond {plafond}"}]
    for cid, valeurs in hyp["crans_en_moins"].items():
        x = v(cid)
        if x in valeurs:
            capacite -= 1
            facteurs.append({"critere": cid, "valeur": x, "effet": "−1"})
    if all(v(cid) in vals for cid, vals in hyp["cran_en_plus_si"].items()) and capacite < plafond:
        capacite += 1
        facteurs.append({"critere": "A4, A5", "valeur": "épargne peu engagée et fonds d'urgence solide", "effet": "+1"})
    capacite = max(1, min(plafond, capacite))
    if v("A5") == "aucun" and capacite > hyp["plafond_sans_fonds_urgence"]:
        capacite = hyp["plafond_sans_fonds_urgence"]
        facteurs.append({"critere": "A5", "valeur": "aucun", "effet": f"plafond {capacite}"})
    if v("A5") == "aucun":
        alertes.append("Aucun fonds d'urgence : une dépense imprévue obligerait à vendre, peut-être au mauvais moment.")
    a7 = profil.get("A7")
    if a7 and a7.get("statut") in UTILISABLES and a7["valeurs"] == ["oui"]:
        capacite = hyp["plafond_dettes_taux_eleve"]
        facteurs.append({"critere": "A7", "valeur": "oui", "effet": f"plafond {capacite}"})
        alertes.append("Dettes à taux élevé : les rembourser d'abord rapporte en général plus, sans risque, que les placer.")
    elif not (a7 and a7.get("statut") in UTILISABLES):
        alertes.append("Dettes à taux élevé : information manquante, à vérifier.")

    # ---------- Tolérance déclarée (en % de perte) ----------
    ordre = list(POURCENT_RUPTURE)
    rupture = v("B1")
    declare = (profil.get("B1") or {}).get("declare", rupture)  # ce que la personne avait dit avant le replay
    f_d = [{"critere": "B1", "valeur": declare, "effet": f"−{POURCENT_RUPTURE[declare]} %"}]
    if v("B3") in hyp["decote_experience"]:
        declare = ordre[max(0, ordre.index(declare) - 1)]
        f_d.append({"critere": "B3", "valeur": v("B3"), "effet": "une classe de moins (tolérance jamais mise à l'épreuve, ou vente passée)"})
    tol_d = float(POURCENT_RUPTURE[declare])
    if v_connu(profil, "B1R") == "vendre_tout" and tol_d > hyp["rupture_max_si_vendre_tout_a_20_pct"]:
        tol_d = float(hyp["rupture_max_si_vendre_tout_a_20_pct"])
        f_d.append({"critere": "B1R", "valeur": "vendre_tout", "effet": f"plafond −{tol_d:g} %"})

    # ---------- Tolérance observée (en % de perte) ----------
    tol_o, f_o = None, []
    e_b2 = profil.get("B2")
    if e_b2 and e_b2.get("statut") in UTILISABLES and e_b2["valeurs"][0] != "non_atteint":
        # perte réelle au moment de la vente si elle est connue (pas d'effet de seuil de classe), sinon la classe
        tol_o = float(e_b2.get("perte") or POURCENT_RUPTURE[e_b2["valeurs"][0]])
        f_o.append({"critere": "B2", "valeur": e_b2["valeurs"][0], "effet": f"a tout vendu à −{tol_o:g} %"})
    b6 = v_connu(profil, "B6")
    if b6:
        s6 = float(hyp["stress_max_par_niveau_pct"][str(hyp["niveau_par_fourchette"][b6])])
        tol_o = s6 if tol_o is None else min(tol_o, s6)
        f_o.append({"critere": "B6", "valeur": b6, "effet": f"portefeuille choisi : stress de −{s6:g} % au plus"})
    if e_b2 and e_b2.get("reduction") is not None:
        f_o.append({"critere": "B2", "valeur": f"a réduit de moitié à −{e_b2['reduction']} %", "effet": "signal, sans effet sur le budget"})
    if v_connu(profil, "H1") == "non_teste":
        alertes.append("La tolérance déclarée n'a pas été mise à l'épreuve par le replay : elle repose sur la seule déclaration.")
    if v_connu(profil, "H1") == "grand":
        alertes.append("Écart fort entre le point de rupture déclaré et le comportement observé : profil incertain sur ce point.")

    # ---------- Budget de perte = le plus prudent des trois ; le niveau en découle ----------
    stress = hyp["stress_max_par_niveau_pct"]
    composantes = {"capacité": float(stress[str(capacite)]), "tolérance déclarée": tol_d}
    if tol_o is not None:
        composantes["tolérance observée"] = tol_o
    budget = min(composantes.values())
    limite_par = [k for k, x in composantes.items() if x == budget]
    # Niveau = le plus haut niveau dont le stress maximal ne dépasse pas le budget. Le moteur utilise le BUDGET
    # (continu) ; le niveau n'est qu'une étiquette lisible.
    niveau = max([int(n) for n, x in stress.items() if x <= budget] or [1])
    b5, b7 = v("B5"), v("B7")
    return {
        "niveau": niveau, "nom": hyp["niveaux"][str(niveau)], "limite_par": limite_par,
        "budget_perte_pct": round(budget, 1),
        "composantes_pct": {k: round(x, 1) for k, x in composantes.items()},
        "capacite": {"niveau": capacite, "facteurs": facteurs},
        "tolerance_declaree": {"perte_pct": tol_d, "facteurs": f_d},
        "tolerance_observee": {"perte_pct": tol_o, "facteurs": f_o},
        "part_actions_indicative_pct": hyp["part_actions_indicative_pct"][str(niveau)],
        "volatilite_max_pct": hyp["volatilite_max_par_B5_pct"][b5],
        "duree_sous_eau_max_jours": hyp["duree_sous_eau_max_jours_par_B7"][b7],
        "plafonds": {"crypto_pct": int(v("D2")), "titre_pct": int(v("D9")),
                     "speculatif_pct": {"sans_speculatif": 0, "plafonne_5": 5, "plafonne_10": 10, "accepte": None}[v("D12")]},
        "acces": v("G3") if v("G3") != "je_ne_sais_pas" else hyp["reglages_prudents"]["G3"],
        "reglages_prudents_appliques": defauts, "alertes": alertes,
        "nature": "hypothèses déclarées (hypotheses_profil.json) ; simulation éducative, aucun conseil financier",
    }


def v_connu(profil: dict, cid: str) -> str | None:
    """Valeur seulement si elle est utilisable (pas de réglage par défaut : critères mesurés ou facultatifs)."""
    e = profil.get(cid)
    return e["valeurs"][0] if e and e.get("statut") in UTILISABLES and e.get("valeurs") else None


def phrase(s: dict) -> str:
    """Résumé en une phrase, construit uniquement à partir des valeurs calculées."""
    return (f"Niveau de risque {s['niveau']} sur 5 ({s['nom'].lower()}), limité par : {', '.join(s['limite_par'])}. "
            f"Budget de perte du portefeuille : {s['budget_perte_pct']:g} % "
            f"(part d'actions indicative : {s['part_actions_indicative_pct'][0]} à {s['part_actions_indicative_pct'][1]} %).")
