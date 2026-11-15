"""Profil dynamique : la sortie du profil de CET utilisateur devient des contraintes exécutables.

Entrée  : le profil (critères fixes), les critères dynamiques, lus tels quels. Rien n'est écrit dans le profil.
Sortie  : exclusions dures, plafonds, budget de risque, préférences pondérées, et la liste explicite de ce
          qui reste inconnu. Un critère inconnu n'est jamais comblé par une valeur inventée :
          - risque : le réglage prudent déjà déclaré dans mvp_profil/hypotheses_profil.json s'applique, signalé ;
          - exclusions et préférences : aucun filtre n'est appliqué, et c'est dit.
Aucune IA ici.
"""
from __future__ import annotations

import re

from .chargement import correspondances, etiquettes, hypotheses, nombre, vrai

import synthese  # noqa: E402  (mvp_profil, lecture seule)
from criteres import CRITERES  # noqa: E402

UTILISABLES = ("validé", "retenu")
NEUTRES = {"D4": {"accepte"}, "D5": {"aucun"}, "D6": {"aucun"}, "E1": {"indifferent"}, "E2": {"indifferent"},
           "E4": {"non_requis"}, "E5": {"aucune"}, "F2": {"aucune"}, "D7": {"indifferent"}, "D11": {"mixte"},
           "A10": {"non"}, "D8": set()}
SEVERITES = ("faible", "moyenne", "élevée")


def etat_critere(profil: dict, cid: str) -> dict:
    """État d'un critère du profil parmi : CONNU, INCERTAIN, INCONNU. (NON_APPLICABLE : valeur neutre.)"""
    e = profil.get(cid)
    if not e:
        return {"critere": cid, "etat": "INCONNU", "valeurs": [], "source": None, "citation": None, "statut": "absent",
                "confiance": None, "motif": "question non posée ou sans réponse"}
    base = {"critere": cid, "valeurs": list(e.get("valeurs") or []), "source": e.get("source"),
            "citation": e.get("citation") or None, "statut": e.get("statut"), "confiance": e.get("confiance"),
            "motif": e.get("motif") or None}
    if e.get("statut") in UTILISABLES and e.get("valeurs"):
        neutre = set(e["valeurs"]) <= NEUTRES.get(cid, set()) and bool(NEUTRES.get(cid))
        return {**base, "etat": "NON_APPLICABLE" if neutre else "CONNU",
                "confiance_reduite": e.get("statut") == "retenu"}
    return {**base, "etat": "INCERTAIN" if e.get("statut") == "incertain" else "INCONNU"}


def _libelle(cid: str, valeur: str) -> str:
    try:
        return synthese.libelle_valeur(cid, valeur)
    except Exception:
        return str(valeur).replace("_", " ")


def _nom(cid: str) -> str:
    return CRITERES.get(cid, {}).get("nom", cid)


def concerne(actif: dict, condition: dict) -> bool:
    """Une condition de config/correspondances.json s'applique-t-elle à cet actif ?"""
    if "toutes" in condition:
        return all(concerne(actif, c) for c in condition["toutes"])
    if "colonne" not in condition:
        return False
    presentes = set(etiquettes(actif.get(condition["colonne"])))
    return bool(presentes & set(condition["valeurs"]))


def colonnes_de(condition: dict) -> list[str]:
    if "toutes" in condition:
        return [c for sous in condition["toutes"] for c in colonnes_de(sous)]
    return [condition["colonne"]] if "colonne" in condition else []


def construire(profil: dict, dynamiques: list[dict] | None = None, hyp: dict | None = None) -> dict:
    """Contraintes de la personne. Fonction pure : même profil, mêmes contraintes."""
    hyp = hyp or hypotheses()
    corr = correspondances()
    dynamiques = dynamiques or []
    synth = synthese.synthetiser(profil)
    etats = {cid: etat_critere(profil, cid) for cid in CRITERES}
    prudents = {d["critere"]: d["valeur"] for d in synth["reglages_prudents_appliques"]}

    def connu(cid: str) -> list[str]:
        return etats[cid]["valeurs"] if etats[cid]["etat"] == "CONNU" else []

    def origine(cid: str) -> str:
        return "réglage prudent (question sans réponse)" if cid in prudents else "réponse de la personne"

    exclusions, groupes, planchers, preferences, signaux, sans_effet, notes = [], [], [], [], [], [], []

    def exclure(cid, libelle, condition=None, mode="contient", **extra):
        exclusions.append({"critere": cid, "libelle": libelle, "condition": condition, "mode": mode,
                           "origine": origine(cid), **extra})

    def plafonner_groupe(cid, libelle, plafond_pct, condition=None, actifs=None, chiffre="hypothèse d'équipe"):
        groupes.append({"critere": cid, "libelle": libelle, "plafond_pct": plafond_pct, "condition": condition,
                        "actifs": actifs, "origine_chiffre": chiffre})

    # ---------- D1 : classes d'actifs ----------
    d1 = connu("D1")
    if d1:
        acceptees = sorted({v for c in d1 for v in corr["classes"].get(c, {}).get("valeurs", [])})
        exclure("D1", "Classe d'actifs non retenue parmi les placements acceptés",
                {"colonne": "asset_class", "valeurs": acceptees}, mode="hors")

    # ---------- D2, D12, G3 : la synthèse donne déjà la valeur retenue (réponse ou réglage prudent) ----------
    plaf = synth["plafonds"]
    if plaf["crypto_pct"] == 0:
        exclure("D2", "Part de cryptoactifs fixée à 0 %", {"colonne": "asset_class", "valeurs": ["crypto"]})
    if plaf["speculatif_pct"] == 0:
        exclure("D12", "Aucun placement spéculatif accepté", {"colonne": "speculative", "valeurs": ["True"]})
    if synth["acces"] == "canada_usa":
        exclure("G3", "Actif non accessible avec un accès aux marchés canadiens et américains", mode="acces_canada_usa")
    else:
        exclure("G3", "Actif accessible seulement à travers un fonds",
                {"colonne": "access_canada", "valeurs": ["via_fnb_seulement"]})

    # ---------- D6, E5 : thèmes et activités refusés ----------
    for cid, table in (("D6", corr["themes"]), ("E5", corr["E5"])):
        for v in connu(cid):
            regle = table.get(v, {})
            if "colonne" in regle or "toutes" in regle:
                exclure(cid, f"Refus déclaré : {_libelle(cid, v)}", regle, valeur=v)
            elif "aucun_actif" in regle:
                sans_effet.append({"critere": cid, "valeur": v, "raison": regle["aucun_actif"]})

    # ---------- E1, F2 : exclure ou plafonner selon la table ----------
    plafond_expose = hyp["plafond_groupe_expose_pct"]
    for cid in ("E1", "F2"):
        for v in connu(cid):
            regle = corr[cid].get(v, {})
            if "exclure" in regle:
                exclure(cid, f"{_nom(cid)} : {_libelle(cid, v)}", regle["exclure"], valeur=v)
            if "plafonner" in regle:
                plafonner_groupe(cid, f"{_nom(cid)} : {_libelle(cid, v)} (exposition partielle plafonnée)",
                                 plafond_expose, regle["plafonner"])
                signaux.append({"critere": cid, "effet": "PLAFOND", "condition": regle["plafonner"], "esg": cid == "E1",
                                "texte": f"Exposition partielle plafonnée à {plafond_expose} % du portefeuille ({_libelle(cid, v)})"})

    # ---------- E2 : controverses ----------
    e2 = connu("E2")
    if e2 == ["aucune"]:
        exclure("E2", "Toute controverse connue est refusée", {"colonne": "max_severity", "valeurs": list(SEVERITES)})
    elif e2 == ["pas_de_grave"]:
        exclure("E2", "Controverse de sévérité élevée refusée", {"colonne": "max_severity", "valeurs": ["élevée"]})
        signaux.append({"critere": "E2", "effet": "PLAFOND", "esg": True,
                        "condition": {"colonne": "max_severity", "valeurs": ["moyenne"]},
                        "texte": "Controverse de sévérité moyenne : signalée avec sa source"})

    # ---------- Critères dynamiques applicables (créés pour cette personne) ----------
    for c in dynamiques:
        base = {"critere": c.get("id", "X"), "libelle": c.get("nom") or c.get("regle", ""), "citation": c.get("citation"),
                "regle": c.get("regle")}
        if not c.get("applicable"):
            notes.append({**base, "statut": c.get("statut"), "raison": "non appliqué : cible, pourcentage ou confirmation manquants"
                          if c.get("effet") != "note" else "note pour le conseiller, aucun filtre automatique"})
            continue
        actifs = list(c.get("actifs") or [])
        if c["effet"] == "exclure":
            exclusions.append({**base, "condition": None, "mode": "liste", "actifs": actifs,
                               "origine": "critère propre à la personne"})
            fnb = c.get("fnb_exposes") or {}
            if fnb:
                plafonner_groupe(base["critere"], f"Fonds qui détiennent une cible exclue ({base['libelle']})",
                                 plafond_expose, actifs=sorted(fnb))
        elif c["effet"] == "plafonner":
            plafonner_groupe(base["critere"], base["libelle"], c["plafond_pct"], actifs=actifs, chiffre="chiffre de la personne")
        elif c["effet"] == "minimum":
            planchers.append({**base, "minimum_pct": c["minimum_pct"], "actifs": actifs})
        elif c["effet"] == "privilegier":
            preferences.append({**base, "type": "liste", "actifs": actifs, "multiplicateur": 1.0})

    # ---------- Préférences (ne compensent jamais une tension) ----------
    mult = hyp["multiplicateurs_personne"]

    def m_statut(cid):
        return mult["statut_retenu"] if etats[cid].get("confiance_reduite") else 1.0

    d5 = [v for v in connu("D5") if v != "aucun"]
    conds = [corr["themes"][v] for v in d5 if "colonne" in corr["themes"].get(v, {})]
    for v in d5:
        if "aucun_actif" in corr["themes"].get(v, {}):
            sans_effet.append({"critere": "D5", "valeur": v, "raison": corr["themes"][v]["aucun_actif"]})
    if conds:
        preferences.append({"critere": "D5", "libelle": "Thèmes d'intérêt : " + ", ".join(_libelle("D5", v) for v in d5),
                            "type": "conditions", "conditions": conds, "multiplicateur": m_statut("D5")})
    d3 = connu("D3")
    conds = [corr["regions"][v] for v in d3 if v in corr["regions"]]
    if conds:
        preferences.append({"critere": "D3", "libelle": "Régions souhaitées : " + ", ".join(_libelle("D3", v) for v in d3),
                            "type": "conditions", "conditions": conds, "multiplicateur": m_statut("D3")})
    d7 = connu("D7")
    if d7:
        col = {"croissance": "growth", "etablie": "established", "dividende": "income_asset"}[d7[0]]
        preferences.append({"critere": "D7", "libelle": f"Style recherché : {_libelle('D7', d7[0])}", "type": "style",
                            "colonne": col, "contraire_si_speculatif": d7[0] == "etablie", "multiplicateur": m_statut("D7")})
    d11 = connu("D11")
    if d11:
        preferences.append({"critere": "D11", "libelle": f"Forme préférée : {_libelle('D11', d11[0])}", "type": "forme",
                            "valeur": d11[0], "multiplicateur": m_statut("D11")})
    a10, a3 = connu("A10"), connu("A3")
    if a10 or a3 == ["revenu"]:
        m = mult["A10"].get(a10[0], 1.0) if a10 else 1.0
        preferences.append({"critere": "A10" if a10 else "A3", "libelle": "Actif qui verse un revenu régulier", "type": "style",
                            "colonne": "income_asset", "contraire_si_speculatif": False, "multiplicateur": m})
    e4 = connu("E4")
    m_esg = mult["E4"].get(e4[0], 1.0) if e4 else 1.0
    if e4:
        preferences.append({"critere": "E4", "libelle": f"Exigence ESG : {_libelle('E4', e4[0])}", "type": "esg",
                            "multiplicateur": m_esg})
    preferences.append({"critere": "D10", "libelle": "Diversification (appliquée par défaut, question non posée)",
                        "type": "diversification", "multiplicateur": 1.0})

    # ---------- Signaux par actif (à surveiller ou en tension, selon la grille) ----------
    if a10 == ["essentiel"]:
        signaux.append({"critere": "A10", "effet": "PLAFOND", "mode": "dividende_fragile", "etat": "en_tension",
                        "texte": "Revenu essentiel : dividende en baisse ou supérieur aux flux de trésorerie libres"})
    if a3 == ["coussin_securite"]:
        signaux.append({"critere": "A3", "effet": "PLAFOND", "mode": "hors_liquidites", "etat": "en_tension",
                        "texte": "Coussin de sécurité : seul le rôle « liquidités » est cohérent"})
    d4 = connu("D4")
    if d4 == ["cad_seulement"]:
        signaux.append({"critere": "D4", "effet": "PLAFOND", "mode": "change",
                        "texte": "Exposition au change, alors que la personne veut rester en dollars canadiens"})
    if synth["niveau"] <= hyp["niveau_max_avertissement_mode"]:
        signaux.append({"critere": "D8", "effet": "PLAFOND", "mode": "mode",
                        "texte": f"Actif spéculatif ou très médiatisé face à un profil de niveau {synth['niveau']} sur 5 : "
                                 "à ne pas ajouter sans regarder le risque"})

    # ---------- Plafonds chiffrés ----------
    a12 = connu("A12")
    secteurs_emploi = corr["secteur_emploi_vers_gics"].get(a12[0], []) if a12 else []
    c1 = etats["C1"]
    niveau_c1 = c1["valeurs"][0] if c1["etat"] == "CONNU" else prudents.get("C1", "debutant")
    complexite_max = hyp["complexite_max_par_C1"][niveau_c1]
    score = re.match(r"\s*(\d)\s*/", str(profil.get("C1", {}).get("motif") or ""))
    if c1["etat"] == "CONNU" and score:
        complexite_max = max(1, min(3, int(score.group(1)) + 1))
    plafonds = {
        "titre_pct": plaf["titre_pct"], "crypto_pct": plaf["crypto_pct"], "speculatif_pct": plaf["speculatif_pct"],
        "secteur_pct": hyp["plafond_secteur_pct"],
        "secteur_emploi": {"secteurs": secteurs_emploi, "pct": hyp["plafond_secteur_emploi_pct"],
                           "emploi": a12[0] if a12 else None},
        "hors_cad_pct": hyp["plafond_hors_cad_pct"].get(d4[0]) if d4 else None,
        "fonds_pct": hyp["plafond_par_fonds_pct"], "complexite_max": complexite_max,
    }

    a2 = etats["A2"]["valeurs"][0] if etats["A2"]["etat"] == "CONNU" else prudents.get("A2", "moins_3_ans")
    inconnus = [{"critere": cid, "nom": _nom(cid), "etat": e["etat"],
                 "traitement": (f"réglage prudent appliqué : {_libelle(cid, prudents[cid])}" if cid in prudents
                                else "aucun filtre ni préférence appliqué sur ce point")}
                for cid, e in etats.items() if e["etat"] in ("INCONNU", "INCERTAIN")]
    return {
        "niveau": synth["niveau"], "nom_niveau": synth["nom"], "limite_par": synth["limite_par"],
        "budget_perte_pct": synth["budget_perte_pct"], "composantes_pct": synth["composantes_pct"],
        "volatilite_max_pct": synth["volatilite_max_pct"],
        "duree_sous_eau_max_jours": synth["duree_sous_eau_max_jours"], "duree_par_defaut": "B7" in prudents,
        "horizon": a2, "horizon_annees": hyp["horizon_annees_max"][a2], "horizon_par_defaut": "A2" in prudents,
        "part_croissance_max_pct": synth["part_actions_indicative_pct"][1],
        "montant_repere_cad": hyp["montant_par_G1_cad"].get((connu("G1") or [None])[0]),
        "consultation_quotidienne": connu("B4") == ["quotidienne"],
        "produits_detenus": connu("C2"), "compte": (connu("G2") or [None])[0],
        "attrait_mode_declare": (connu("D8") or [None])[0], "attrait_mode_observe": (connu("D8O") or [None])[0],
        "style": (d7 or [None])[0], "multiplicateur_esg": m_esg,
        "exclusions": exclusions, "plafonds": plafonds, "plafonds_groupes": groupes, "planchers": planchers,
        "preferences": preferences, "signaux": signaux, "sans_effet": sans_effet, "notes_dynamiques": notes,
        "etats": etats, "inconnus": inconnus,
        "reglages_prudents": [{"critere": c, "nom": _nom(c), "valeur": v, "libelle": _libelle(c, v)} for c, v in prudents.items()],
        "alertes": list(synth["alertes"]), "synthese_provisoire": synth["synthese_provisoire"],
        "besoins_liquidite": synth["besoins_liquidite"],
        "phrase": synthese.phrase(synth),
    }


def accessible_canada_usa(actif: dict) -> bool:
    regle = correspondances()["G3"]["canada_usa"]["accessible"]
    return actif.get(regle["colonne"]) in regle["valeurs"] or bool(str(actif.get("adr_us") or "").strip())


def exclusion_s_applique(actif: dict, ex: dict) -> bool:
    if ex["mode"] == "liste":
        return actif["ticker"] in ex.get("actifs", [])
    if ex["mode"] == "acces_canada_usa":
        return not accessible_canada_usa(actif)
    touche = concerne(actif, ex["condition"])
    return (not touche) if ex["mode"] == "hors" else touche


def colonnes_exclusion(ex: dict) -> list[str]:
    if ex["mode"] == "liste":
        return ["ticker"]
    if ex["mode"] == "acces_canada_usa":
        return ["access_canada", "adr_us"]
    return colonnes_de(ex["condition"])


def membre_groupe(actif: dict, groupe: dict) -> bool:
    if groupe.get("actifs") is not None:
        return actif["ticker"] in groupe["actifs"]
    return concerne(actif, groupe["condition"])


def part_dans_groupe(actif: dict, groupe: dict) -> float:
    """Part de l'actif qui compte dans le groupe. Un fonds exposé aux énergies fossiles ne compte que pour sa part
    d'énergie connue (fossil_part_energie_fnb) : plafonner tout le fonds serait disproportionné."""
    if not membre_groupe(actif, groupe):
        return 0.0
    if groupe.get("condition") and actif.get("fossil_categorie") == "fonds_part_energie" and \
            set(colonnes_de(groupe["condition"])) & {"fossil_categorie", "kw_exclusions"}:
        part = nombre(actif.get("fossil_part_energie_fnb"))
        if part is not None:
            return max(0.0, min(1.0, part))
    return 1.0


def titre_individuel(actif: dict) -> bool:
    return actif.get("asset_class") in ("equity", "crypto")


def speculatif(actif: dict) -> bool:
    return vrai(actif.get("speculative"))
