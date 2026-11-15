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
from copy import deepcopy
from pathlib import Path

from criteres import CRITERES, SECTIONS

HYP = json.loads((Path(__file__).parent / "hypotheses_profil.json").read_text(encoding="utf-8"))
UTILISABLES = ("validé", "retenu")
POURCENT_RUPTURE = {"5": 5, "10": 10, "20": 20, "30": 30, "40": 40, "50_plus": 50}


def calculer_base(profil: dict, hyp: dict = HYP) -> dict:
    """Calcul seul, réutilisé par les contrefactuels sans récursion ni appel à un modèle."""
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

    liquidite = besoins_liquidite(profil)
    if liquidite["a_preciser"]:
        alertes.append("Disponibilité de l'argent à préciser : " + " ; ".join(liquidite["motifs"]) +
                       ". Le budget calculé reste provisoire : il ne détermine pas la somme à garder disponible.")

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
        "besoins_liquidite": liquidite,
        "nature": "hypothèses déclarées (hypotheses_profil.json) ; simulation éducative, aucun conseil financier",
    }


def v_connu(profil: dict, cid: str) -> str | None:
    """Valeur seulement si elle est utilisable (pas de réglage par défaut : critères mesurés ou facultatifs)."""
    e = profil.get(cid)
    return e["valeurs"][0] if e and e.get("statut") in UTILISABLES and e.get("valeurs") else None


def besoins_liquidite(profil: dict) -> dict:
    """Signale ce qui manque sans inventer de plafond à partir d'un besoin non chiffré."""
    a9, a10 = v_connu(profil, "A9"), v_connu(profil, "A10")
    motifs, manquantes = [], []
    if a9 is None:
        motifs.append("les retraits avant l'échéance ne sont pas renseignés")
        manquantes.append("retraits prévus avant l'échéance")
    elif a9 in ("ponctuel", "reguliers"):
        motifs.append("des retraits sont prévus avant l'échéance")
        manquantes.extend(("montant des retraits", "dates des retraits"))
        if a9 == "reguliers":
            manquantes.append("fréquence des retraits")
    if a10 is None:
        motifs.append("le besoin de revenu régulier n'est pas renseigné")
        manquantes.append("besoin de revenu régulier")
    elif a10 == "essentiel":
        motifs.append("le revenu du placement est nécessaire aux dépenses courantes")
        manquantes.extend(("montant du revenu nécessaire", "date du premier versement", "autres revenus disponibles"))
    return {"a_preciser": bool(motifs), "motifs": motifs,
            "informations_manquantes": list(dict.fromkeys(manquantes))}


# Un seul cran sur des échelles ordonnées ; aucun ordre artificiel entre objectifs,
# secteurs, types de compte ou comportements déjà observés au replay.
ECHELLES_VOISINES = {
    cid: CRITERES[cid]["valeurs"] for cid in
    ("A2", "A4", "A5", "A8", "A9", "A10", "B1", "B5", "B7", "D2", "D9", "D12")
}
CRITERES_CALCULES = tuple(dict.fromkeys((*ECHELLES_VOISINES, "A6", "A7", "B1R", "B3", "G3")))
CRITERES_CAPACITE = ("A2", "A4", "A5", "A6", "A7", "A8")


def avec_valeur(profil: dict, cid: str, valeur: str) -> dict:
    """Copie d'analyse. Ne touche ni le profil d'origine ni la mesure du replay."""
    p = deepcopy(profil)
    p[cid] = {**p.get(cid, {}), "valeurs": [valeur], "statut": "validé"}
    # B1 conserve le déclaré d'avant replay. Une variation du déclaré doit changer
    # ce champ aussi, tandis que B2 conserve le point de rupture réellement observé.
    if cid == "B1" and "declare" in p[cid]:
        p[cid]["declare"] = valeur
    return p


def changements(a: dict, b: dict) -> list[str]:
    """Dimensions du résultat réellement modifiées, sans compter les traces ou libellés."""
    dimensions = (("budget_perte_pct", "budget de perte"), ("niveau", "niveau de risque"),
                  ("volatilite_max_pct", "volatilité maximale"),
                  ("duree_sous_eau_max_jours", "durée sous l'eau"),
                  ("plafonds", "plafonds de concentration"), ("acces", "marchés accessibles"))
    out = [nom for cle, nom in dimensions if a[cle] != b[cle]]
    if a["besoins_liquidite"]["informations_manquantes"] != b["besoins_liquidite"]["informations_manquantes"]:
        out.append("besoin de liquidités à préciser")
    return out


def _source(profil: dict, cid: str, hyp: dict) -> dict:
    e = profil.get(cid, {})
    connue = bool(e.get("statut") in UTILISABLES and e.get("valeurs"))
    return {"critere": cid, "nom": CRITERES[cid]["nom"],
            "valeur": ", ".join(e["valeurs"]) if connue else hyp["reglages_prudents"].get(cid),
            "source": e.get("source", "") if connue else "réglage prudent (information manquante)",
            "statut": e.get("statut", "à préciser"), "citation": e.get("citation", "")}


def libelle_valeur(cid: str, valeur: str) -> str:
    """Réutilise les libellés du questionnaire plutôt que les codes du modèle."""
    for sec in SECTIONS:
        for item in sec["items"]:
            if item.get("critere") == cid and item.get("type") in ("qcm", "qcm_multi"):
                for texte, code in item.get("options", []):
                    if code == valeur:
                        return texte
    libelles = {
        "A6": {"stables": "revenus stables", "variables": "revenus variables", "incertains": "revenus incertains",
               "retraite": "revenus de retraite"},
        "A8": {"0": "aucune personne à charge", "1_2": "une ou deux personnes à charge",
               "3_plus": "trois personnes à charge ou davantage"},
        "B6": {"prudent": "prudent", "equilibre": "équilibré", "dynamique": "dynamique"},
        "D6": {"energie_fossile": "énergies fossiles", "sante": "santé", "ia": "intelligence artificielle"},
    }
    if cid in ("B1", "B2") and valeur in POURCENT_RUPTURE:
        return f"{POURCENT_RUPTURE[valeur]:g} %" + (" ou davantage" if valeur == "50_plus" else "")
    return libelles.get(cid, {}).get(valeur, valeur.replace("_", " "))


def _role_composante(nom: str, base: dict) -> str:
    valeur = base["composantes_pct"].get(nom)
    if valeur is None:
        return "Cette composante n'est pas encore chiffrée."
    if nom in base["limite_par"]:
        return f"La {nom} est une composante limitante du budget actuel de {base['budget_perte_pct']:g} %."
    return (f"La {nom} correspond à {valeur:g} % dans ce calcul ; le budget actuel est limité à "
            f"{base['budget_perte_pct']:g} % par {', '.join(base['limite_par'])}.")


def _raison_calculee(cid: str, valeur: str, profil: dict, base: dict, hyp: dict) -> str:
    libelle = libelle_valeur(cid, valeur)
    if cid in CRITERES_CAPACITE:
        effets = []
        for f in base["capacite"]["facteurs"]:
            if cid not in f["critere"].split(", "):
                continue
            effet = f["effet"]
            if effet == "−1":
                effets.append("un cran de capacité retiré")
            elif effet == "+1":
                effets.append("un cran de capacité rétabli grâce à une faible part d'épargne et une réserve solide")
            elif effet.startswith("plafond "):
                effets.append(f"capacité plafonnée au niveau {effet.split()[-1]} sur 5")
        regle = "; ".join(effets) if effets else "aucune restriction supplémentaire appliquée pour ce critère"
        return (f"Réponse « {libelle} » : {regle}. Capacité retenue : niveau {base['capacite']['niveau']} sur 5. "
                + _role_composante("capacité", base))
    if cid in ("B1", "B1R", "B3"):
        if cid == "B1":
            debut = f"Point de vente déclaré : {libelle} de baisse"
            if "declare" in profil[cid]:
                debut += " (déclaration conservée avant le replay)"
        else:
            debut = f"Réponse « {libelle} »"
        regles = [f["effet"] for f in base["tolerance_declaree"]["facteurs"]
                  if f["critere"] == cid and cid != "B1"]
        precision = " Règle appliquée : " + "; ".join(regles) + "." if regles else ""
        return (f"{debut}. Tolérance déclarée calculée : {base['tolerance_declaree']['perte_pct']:g} %."
                + precision + " " + _role_composante("tolérance déclarée", base))
    if cid in ("A9", "A10"):
        if base["besoins_liquidite"]["a_preciser"]:
            return (f"Réponse « {libelle} ». À préciser : " +
                    ", ".join(base["besoins_liquidite"]["informations_manquantes"]) +
                    ". Le budget reste provisoire tant que la somme à garder disponible n'est pas établie.")
        return f"Réponse « {libelle} » : aucun besoin de liquidité à chiffrer n'est identifié par ces deux réponses."
    if cid == "B5":
        x = base["volatilite_max_pct"]
        return (f"Réponse « {libelle} » : " + (f"plafond de volatilité du portefeuille fixé à {x:g} % dans la grille."
                if x is not None else "aucun plafond de volatilité chiffré dans cette catégorie."))
    if cid == "B7":
        jours = base["duree_sous_eau_max_jours"]
        return (f"Réponse « {libelle} » : " + (f"durée maximale sous l'eau fixée à {jours} jours dans la grille."
                if jours is not None else "aucune durée maximale chiffrée dans cette catégorie."))
    if cid in ("D2", "D9", "D12"):
        cles = {"D2": ("crypto_pct", "aux cryptoactifs"), "D9": ("titre_pct", "à une entreprise individuelle"),
                "D12": ("speculatif_pct", "aux placements spéculatifs")}
        cle, cible = cles[cid]
        plafond = base["plafonds"][cle]
        return (f"Réponse « {libelle} » : " + (f"au plus {plafond:g} % du portefeuille alloués {cible}."
                if plafond is not None else "aucun plafond chiffré pour les placements spéculatifs.") +
                " Cette contrainte devra être contrôlée dans les solutions comparées.")
    if cid == "G3":
        if valeur == "je_ne_sais_pas":
            return "Accès non confirmé : la grille retient provisoirement les marchés canadiens et américains."
        return (f"Réponse « {libelle} » : les solutions devront respecter l'accès " +
                ("aux marchés canadiens et américains." if base["acces"] == "canada_usa" else "aux marchés internationaux."))
    return f"Réponse « {libelle} » : contrainte utilisée dans le calcul."


def reponses_decisives(profil: dict, base: dict, hyp: dict = HYP) -> list[dict]:
    """Dépendances vérifiables du résultat, sans attribution inventée par une IA.

    Pour une réponse utilisée par le calcul, les autres valeurs autorisées sont
    essayées une à une. L'effet annoncé porte sur le calcul actuel, pas sur une
    estimation du vrai risque. Les contraintes explicites restent déterminantes
    pour l'appariement, même quand elles ne changent pas le budget.
    """
    out = []
    for cid in CRITERES_CALCULES:
        current = v_connu(profil, cid)
        if cid == "B1" and current is not None:
            current = profil[cid].get("declare", current)
        if current is None:
            continue  # un défaut prudent n'est jamais présenté comme une réponse
        essais = [calculer_base(avec_valeur(profil, cid, val), hyp)
                  for val in CRITERES[cid]["valeurs"] if val not in (current, "je_ne_sais_pas")]
        effets = list(dict.fromkeys(nom for s in essais for nom in changements(base, s)))
        if not effets:
            continue
        ecart = max((abs(s["budget_perte_pct"] - base["budget_perte_pct"]) for s in essais), default=0)
        raison = _raison_calculee(cid, current, profil, base, hyp)
        source = _source(profil, cid, hyp)
        if cid == "B1" and "declare" in profil[cid]:
            source.update(valeur_declaree=current, valeur_retenue=profil[cid]["valeurs"][0])
        out.append({**source, "raison": raison, "effets": effets,
                    "variation_budget_max_points": round(ecart, 1)})
    # La mesure réelle reste une cause directe du plafond observé ; elle n'est
    # jamais déplacée ou effacée pour fabriquer une variation de réponse.
    for cid in ("B2", "B6"):
        e = profil.get(cid, {})
        if v_connu(profil, cid) is not None and (cid != "B2" or e["valeurs"] != ["non_atteint"]):
            if cid == "B2":
                perte = e.get("perte") or POURCENT_RUPTURE[e["valeurs"][0]]
                raison = f"Vente totale observée à {perte:g} % de baisse : le replay fixe cette borne de tolérance."
            else:
                niveau = hyp["niveau_par_fourchette"][e["valeurs"][0]]
                plafond = hyp["stress_max_par_niveau_pct"][str(niveau)]
                raison = (f"Fourchette choisie : « {libelle_valeur(cid, e['valeurs'][0])} ». Selon la table de l'équipe, "
                          f"ce choix borne la tolérance observée à {plafond:g} %.")
            out.append({**_source(profil, cid, hyp),
                        "raison": raison + " " + _role_composante("tolérance observée", base),
                        "effets": ["tolérance observée"], "variation_budget_max_points": 0})
    # Ces contraintes ne font pas encore partie du calcul de budget. Dire leur
    # rôle explicitement évite de prétendre qu'elles ont modifié le niveau.
    contraintes = {"D1": "Les classes d'actifs acceptées délimitent les solutions à comparer.",
                   "D4": "La contrainte de change devra être contrôlée sur les solutions comparées.",
                   "D6": "Les secteurs refusés devront être écartés ou signalés selon la couverture des données.",
                   "E1": "La contrainte sur les énergies fossiles devra être contrôlée.",
                   "E2": "La tolérance aux controverses devra être respectée.",
                   "E4": "Le niveau d'exigence ESG détermine la force du filtre ou de la préférence.",
                   "E5": "Les exclusions d'activités devront être respectées.",
                   "F2": "Les exclusions de pays ou de marchés devront être respectées."}
    neutres = {"D4": {"accepte"}, "D6": {"aucun"}, "E1": {"indifferent"}, "E2": {"indifferent"},
               "E4": {"non_requis"}, "E5": {"aucune"}, "F2": {"aucune"}}
    for cid, raison in contraintes.items():
        e = profil.get(cid, {})
        if v_connu(profil, cid) is not None and any(x not in neutres.get(cid, set()) for x in e["valeurs"]):
            out.append({**_source(profil, cid, hyp),
                        "raison": "Réponse « " + ", ".join(libelle_valeur(cid, x) for x in e["valeurs"]) + " ». " + raison,
                        "effets": ["contrainte pour la comparaison future"], "variation_budget_max_points": 0})
    return sorted(out, key=lambda x: -x["variation_budget_max_points"])


def evaluer_robustesse(profil: dict, base: dict, hyp: dict = HYP) -> dict:
    """Sensibilité locale, un critère à la fois. Ce n'est pas une probabilité d'exactitude."""
    essais, sensibles = [], []
    for cid, echelle in ECHELLES_VOISINES.items():
        valeur = v_connu(profil, cid)
        if cid == "B1":
            valeur = (profil.get(cid) or {}).get("declare", valeur)
        if valeur not in echelle:
            continue
        i = echelle.index(valeur)
        for j in (i - 1, i + 1):
            if not 0 <= j < len(echelle):
                continue
            autre = calculer_base(avec_valeur(profil, cid, echelle[j]), hyp)
            changements_observes = changements(base, autre)
            cas = {"critere": cid, "nom": CRITERES[cid]["nom"], "avant": valeur, "apres": echelle[j],
                   "budget_perte_pct": autre["budget_perte_pct"], "niveau": autre["niveau"],
                   "ecart_budget_points": round(autre["budget_perte_pct"] - base["budget_perte_pct"], 1),
                   "changements": changements_observes}
            essais.append(cas)
            if changements_observes:
                sensibles.append(cas)
    a_confirmer = list(dict.fromkeys(
        [d["critere"] for d in base["reglages_prudents_appliques"]] +
        [cid for cid in (*CRITERES_CAPACITE, "B1", "A9", "A10") if v_connu(profil, cid) is None] +
        [cid for cid in CRITERES_CALCULES if profil.get(cid, {}).get("statut") == "retenu"] +
        (["G3"] if v_connu(profil, "G3") == "je_ne_sais_pas" else [])))
    etat = "a_completer" if a_confirmer or base["besoins_liquidite"]["a_preciser"] else (
        "sensible" if sensibles else "stable_localement" if essais else "non_evalue")
    budgets = [base["budget_perte_pct"], *(x["budget_perte_pct"] for x in essais)]
    return {"etat": etat, "budget_min_pct": min(budgets), "budget_max_pct": max(budgets),
            "budget_sensible": min(budgets) != max(budgets),
            "niveaux_possibles": sorted({base["niveau"], *(x["niveau"] for x in essais)}),
            "variations_testees": len(essais),
            "variations_sensibles": sorted(sensibles, key=lambda x: -abs(x["ecart_budget_points"])),
            "criteres_a_confirmer": a_confirmer,
            "limites": "Un cran voisin sur une seule réponse ordonnée à la fois, les autres réponses et les mesures "
                       "restent fixes. Cette plage décrit la sensibilité des règles de l'équipe ; elle n'est ni un "
                       "intervalle de confiance, ni une prévision de perte, ni une validation du profil."}


def synthetiser(profil: dict, hyp: dict = HYP) -> dict:
    """Calcul, explication des réponses déterminantes et vérification locale des hypothèses."""
    base = calculer_base(profil, hyp)
    base["reponses_decisives"] = reponses_decisives(profil, base, hyp)
    base["robustesse"] = evaluer_robustesse(profil, base, hyp)
    base["synthese_provisoire"] = base["robustesse"]["etat"] == "a_completer"
    return base


def phrase(s: dict) -> str:
    """Résumé en une phrase, construit uniquement à partir des valeurs calculées."""
    return (f"Niveau de risque {s['niveau']} sur 5 ({s['nom'].lower()}), limité par : {', '.join(s['limite_par'])}. "
            f"Budget de perte du portefeuille : {s['budget_perte_pct']:g} % "
            f"(part d'actions indicative : {s['part_actions_indicative_pct'][0]} à {s['part_actions_indicative_pct'][1]} %).")
