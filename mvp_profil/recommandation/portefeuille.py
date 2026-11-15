"""Mini-portefeuille FICTIF construit pour cette personne, et verdict d'une demande précise (cas Robert).

Construction déterministe, sans bibliothèque d'optimisation, pour rester explicable :
  1. candidats : actifs non exclus dont le score atteint le seuil d'entrée (hypothèse ajustable) ;
  2. deux poches selon le rôle : amortisseur (liquidités, obligations) et croissance (le reste) ;
  3. poids proportionnels au score, rabotés par les plafonds de la personne, l'excédent étant redistribué ;
  4. la part de croissance est la plus grande qui garde la perte de stress sous 0,8 × le budget de perte ;
  5. une contrainte impossible à tenir est NOMMÉE, jamais masquée.
La tension se calcule au niveau du portefeuille et du montant, pas actif par actif.
Simulation uniquement : aucun ordre n'est passé, aucune fonction d'exécution n'existe.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from . import contraintes as C
from . import mesures as M
from .appariement import pct
from .chargement import hypotheses
from .preuves import Registre

AMORTISSEURS = ("liquidites", "obligations_amortisseur")
EPS = 1e-9


def _groupes_plafonnes(ctr: dict, uni, tickers: list[str]) -> list[dict]:
    """Plafonds de groupe, avec la part de chaque actif dans le groupe (un FNB n'appartient qu'en partie à un secteur)."""
    plaf = ctr["plafonds"]
    groupes = []
    membres = {t: 1.0 for t in tickers if uni[t]["asset_class"] == "crypto"}
    if membres:
        groupes.append({"nom": "Cryptoactifs", "critere": "D2", "plafond": plaf["crypto_pct"] / 100, "membres": membres})
    if plaf["speculatif_pct"] is not None:
        membres = {t: 1.0 for t in tickers if C.speculatif(uni[t])}
        if membres:
            groupes.append({"nom": "Placements spéculatifs", "critere": "D12", "plafond": plaf["speculatif_pct"] / 100,
                            "membres": membres})
    for g in ctr["plafonds_groupes"]:
        membres = {t: C.part_dans_groupe(uni[t], g) for t in tickers}
        membres = {t: f for t, f in membres.items() if f > 0}
        if membres:
            groupes.append({"nom": g["libelle"], "critere": g["critere"], "plafond": g["plafond_pct"] / 100, "membres": membres})
    secteurs = sorted({uni[t]["sector"] for t in tickers if uni[t]["asset_class"] == "equity"} |
                      {s for t in tickers for s in M.ch.secteurs_fnb().get(t, {})})
    emploi = set(plaf["secteur_emploi"]["secteurs"])
    for s in secteurs:
        membres = {t: M.part_secteur(t, s, uni) for t in tickers}
        membres = {t: f for t, f in membres.items() if f > 0}
        if s in emploi:
            groupes.append({"nom": f"Secteur de l'emploi : {s}", "critere": "A12", "secteur": s,
                            "plafond": plaf["secteur_emploi"]["pct"] / 100, "membres": membres})
        else:
            groupes.append({"nom": f"Secteur : {s}", "critere": "D9", "secteur": s,
                            "plafond": plaf["secteur_pct"] / 100, "membres": membres})
    if len(emploi) > 1:  # l'emploi couvre plusieurs secteurs (technologie = TI + communications) : plafond commun
        membres = {t: sum(M.part_secteur(t, s, uni) for s in emploi) for t in tickers}
        groupes.append({"nom": "Secteurs de l'emploi réunis", "critere": "A12", "plafond": plaf["secteur_emploi"]["pct"] / 100,
                        "membres": {t: f for t, f in membres.items() if f > 0}})
    if plaf["hors_cad_pct"] is not None:
        membres = {t: 1.0 for t in tickers if uni[t].get("fx_risk") not in ("aucun", "", None)}
        if membres:
            groupes.append({"nom": "Exposition au change", "critere": "D4", "plafond": plaf["hors_cad_pct"] / 100, "membres": membres})
    return groupes


def plafonner(cible: dict[str, float], plafonds: dict[str, float], groupes: list[dict], refuge: list[str],
              fixes: tuple = ()) -> tuple[dict, float]:
    """Applique plafonds individuels et de groupe ; redistribue l'excédent, d'abord aux actifs libres, puis au refuge.

    Renvoie (poids, part non investie). Déterministe : mêmes entrées, mêmes poids.
    """
    w = dict(cible)
    figes: set[str] = set(fixes)  # poids imposés (titre demandé) : jamais réduits ni augmentés
    for _ in range(300):
        for t in w:
            if w[t] > plafonds[t] + EPS and t not in fixes:
                w[t] = plafonds[t]
                figes.add(t)
        for g in groupes:
            expo = sum(w.get(t, 0.0) * f for t, f in g["membres"].items())
            if expo > g["plafond"] + EPS:
                forts = [t for t, f in g["membres"].items() if f >= 0.2 and w.get(t, 0.0) > 0 and t not in fixes]
                part_forte = sum(w[t] * g["membres"][t] for t in forts)
                if part_forte <= EPS:
                    continue
                facteur = max(0.0, (g["plafond"] - (expo - part_forte)) / part_forte)
                for t in forts:
                    w[t] *= facteur
                    figes.add(t)
        reste = 1.0 - sum(w.values())
        if reste < 1e-7:
            break
        libres = [t for t in w if t not in figes and w[t] < plafonds[t] - EPS]
        if not libres:
            libres = [t for t in refuge if w[t] < plafonds[t] - EPS and not any(
                t in g["membres"] and sum(w.get(x, 0.0) * f for x, f in g["membres"].items()) >= g["plafond"] - EPS
                for g in groupes)]
            if not libres:
                break
        base = sum(cible[t] for t in libres) or float(len(libres))
        for t in libres:
            w[t] += reste * ((cible[t] / base) if sum(cible[t] for t in libres) else 1 / len(libres))
    return w, max(0.0, 1.0 - sum(w.values()))


def _choisir(resultats: dict, uni, ctr: dict, hyp: dict) -> dict:
    """Sélection des candidats, par paliers de score."""
    p = hyp["portefeuille"]
    prefs = lambda r: sum(1 for l in r["lignes"] if l["etat"] == "satisfaite")  # noqa: E731
    avec_prix = set(M.ch.prix_cad().columns)  # un actif sans série de prix ne peut pas entrer dans un portefeuille mesuré
    for seuil in p["seuil_entree_paliers"]:
        cands = [r for r in resultats.values() if r["verdict"] == "compatible" and (r["score"] or 0) >= seuil
                 and (r.get("poids_max_pct") or 0) > 0 and r["ticker"] in avec_prix]
        amort = [r for r in cands if r["role"] in AMORTISSEURS]
        crois = [r for r in cands if r["role"] not in AMORTISSEURS]
        if len(amort) >= 1 and len(amort[: p["nb_amortisseurs"]]) + len(crois) >= p["nb_positions_min"]:
            break
    cle = lambda r: (-r["score"], uni[r["ticker"]].get("fx_risk") != "aucun", abs(M.nombre(uni[r["ticker"]]["stress_loss"]) or 0), r["ticker"])  # noqa: E731
    liquides = sorted([r for r in amort if r["role"] == "liquidites"], key=cle)[:1]
    oblig = sorted([r for r in amort if r["role"] == "obligations_amortisseur"], key=cle)
    choisis_amort = (liquides + oblig)[: p["nb_amortisseurs"]] or sorted(amort, key=cle)[: p["nb_amortisseurs"]]
    place = p["nb_positions_max"] - len(choisis_amort)
    coeurs = sorted([r for r in crois if r["role"] == "coeur"],
                    key=lambda r: (-r["score"], -prefs(r), uni[r["ticker"]].get("region") != "Monde", r["ticker"]))[:3]
    choisis = list(coeurs)
    par_secteur: dict[str, int] = {}
    ordre = lambda r: (-r["score"], -prefs(r), abs(M.nombre(uni[r["ticker"]]["stress_loss"]) or 0), r["ticker"])  # noqa: E731
    reste = sorted([r for r in crois if r not in coeurs], key=ordre)

    emploi = set(ctr["plafonds"]["secteur_emploi"]["secteurs"])

    def ajouter(r):
        s = uni[r["ticker"]]["sector"]
        if r in choisis or len(choisis) >= place or par_secteur.get(s, 0) >= p["max_titres_par_secteur"]:
            return
        # Le secteur de l'emploi est plafonné plus bas : inutile d'y choisir plus de titres que le plafond n'en porte.
        if s in emploi and sum(par_secteur.get(x, 0) for x in emploi) >= p["max_titres_secteur_emploi"]:
            return
        par_secteur[s] = par_secteur.get(s, 0) + 1
        choisis.append(r)

    # « Inclinaison dans les plafonds » (grille, D5) : un représentant par thème d'intérêt déclaré, s'il est candidat.
    for pr in ctr["preferences"]:
        for cond in pr.get("conditions", []) if pr["critere"] == "D5" else []:
            vise = [r for r in reste if C.concerne(uni[r["ticker"]], cond)]
            if vise:
                ajouter(vise[0])
    for r in reste:
        ajouter(r)
    # Parts minimales demandées par la personne : au moins un actif du groupe doit figurer.
    for pl in ctr["planchers"]:
        presents = [r for r in choisis + choisis_amort if r["ticker"] in pl["actifs"]]
        if not presents:
            dispo = sorted([r for r in resultats.values() if r["ticker"] in pl["actifs"] and r["verdict"] not in ("exclu", "absent", "donnees_insuffisantes")],
                           key=lambda r: (-(r["score"] or 0), r["ticker"]))
            if dispo:
                (choisis_amort if dispo[0]["role"] in AMORTISSEURS else choisis).append(dispo[0])
    return {"seuil": seuil, "candidats": len(cands), "croissance": choisis, "amortisseur": choisis_amort}


def _poids(part_croissance: float, selection: dict, ctr: dict, uni, hyp: dict, imposes: dict | None = None) -> tuple[dict, float]:
    """Poids pour une part de croissance donnée. Ce qui ne peut être investi sous les plafonds reste en ENCAISSE
    (non investie, sans risque ni rendement dans les mesures) : c'est dit, jamais caché.

    imposes : {ticker: part} demandés par la personne et déjà jugés compatibles ; leur poids est fixe, le reste
    du portefeuille se réorganise autour d'eux sous les mêmes plafonds.
    """
    imposes = imposes or {}
    mult = hyp["portefeuille"]["multiplicateur_coeur"]
    crois = [r for r in selection["croissance"] if r["ticker"] not in imposes]
    amort = [r for r in selection["amortisseur"] if r["ticker"] not in imposes]
    imp_c = sum(p for t, p in imposes.items() if uni[t]["role"] not in AMORTISSEURS)
    imp_a = sum(p for t, p in imposes.items() if uni[t]["role"] in AMORTISSEURS)
    brut_c = {r["ticker"]: r["score"] * (mult if r["role"] == "coeur" else 1.0) for r in crois}
    tot = sum(brut_c.values()) or 1.0
    g = max(part_croissance, imp_c)
    cible = {t: max(0.0, g - imp_c) * v / tot for t, v in brut_c.items()}
    reste_amort = max(0.0, 1.0 - g - imp_a)
    for r in amort:
        cible[r["ticker"]] = reste_amort / len(amort)
    cible.update(imposes)
    plafonds = {r["ticker"]: (r["poids_max_pct"] or 0) / 100 for r in crois + amort}
    plafonds.update(imposes)
    w, encaisse = plafonner(cible, plafonds, _groupes_plafonnes(ctr, uni, list(cible)), [r["ticker"] for r in amort],
                            fixes=tuple(imposes))
    for pl in ctr["planchers"]:  # part minimale demandée : remontée, le reste réduit en proportion
        dans = [t for t in w if t in pl["actifs"]]
        actuel, vise = sum(w[t] for t in dans), pl["minimum_pct"] / 100
        if dans and actuel < vise - EPS:
            autres = [t for t in w if t not in dans and t not in imposes]
            total_autres = sum(w[t] for t in autres)
            ajout = min(vise - actuel, total_autres)
            for t in dans:
                w[t] += ajout * ((w[t] / actuel) if actuel > EPS else 1 / len(dans))
            for t in autres:
                w[t] -= ajout * (w[t] / total_autres) if total_autres > EPS else 0.0
    return {t: x for t, x in w.items() if x > 1e-6}, encaisse


def _etat_tension(ratio: float, hyp: dict) -> str:
    t = hyp["tension"]
    return "coherent" if ratio <= t["coherent_max"] + 1e-9 else "a_surveiller" if ratio <= t["a_surveiller_max"] + 1e-9 else "en_tension"


def controles(poids: dict, ctr: dict, uni, hyp: dict, registre: Registre, st: dict | None = None, **periode) -> dict:
    """Contrôle de chaque contrainte sur le PORTEFEUILLE : valeur, limite, état, preuves. Sert aussi de garde-fou."""
    st = st or M.stress(poids, uni, hyp, **periode)
    m, expo = st["mesures"], M.expositions(poids, uni)
    budget = ctr["budget_perte_pct"]
    ratio = st["perte_stress_pct"] / budget if budget else float("inf")
    lignes = []

    def ctl(nom, critere, valeur, limite, etat, detail="", preuves=()):
        lignes.append({"contrainte": nom, "critere": critere, "valeur": valeur, "limite": limite, "etat": etat,
                       "detail": detail, "preuves": list(preuves)})

    p_stress = registre.calcul("portefeuille:perte_stress", st["perte_stress_pct"],
                               "pire de : perte maximale historique, perte de 2022, choc de taux déclaré", m["periode"])
    ctl("Perte de stress face au budget de perte", "B1", st["perte_stress_pct"], budget, _etat_tension(ratio, hyp),
        f"Tension = {pct(st['perte_stress_pct'])} ÷ {pct(budget, 0)} = {ratio:.2f} ; cause : {st['cause'].replace('_', ' ')}.",
        [p_stress, registre.hypothese("tension"), registre.hypothese("stress")])
    vmax = ctr["volatilite_max_pct"]
    p_vol = registre.calcul("portefeuille:volatilite", m["volatilite_pct"], "écart-type des rendements quotidiens en CAD, annualisé", m["periode"])
    ctl("Volatilité du portefeuille", "B5", m["volatilite_pct"], vmax,
        "sans_limite" if vmax is None else "respectee" if m["volatilite_pct"] <= vmax else "en_conflit",
        "Aucun plafond chiffré pour cette réponse." if vmax is None else "", [p_vol])
    dmax = ctr["duree_sous_eau_max_jours"]
    p_dur = registre.calcul("portefeuille:jours_sous_eau", m["jours_sous_eau"], "jours du sommet précédant la pire baisse jusqu'au retour à ce sommet", m["periode"])
    if dmax is None:
        etat, detail = "sans_limite", "Aucune durée maximale chiffrée pour cette réponse."
    elif m["jours_sous_eau"] <= dmax:
        etat, detail = "respectee", ""
    elif ctr["duree_par_defaut"] and not hyp["portefeuille"]["duree_sous_eau_par_defaut_bloquante"]:
        etat, detail = "a_confirmer", ("Limite issue d'un réglage par défaut : la question n'a pas reçu de réponse. "
                                       "Dépassement signalé, à confirmer avec la personne.")
    else:
        etat, detail = "en_conflit", ""
    if not m["recupere"]:
        detail += " Le sommet n'était pas retrouvé à la fin de la période."
    ctl("Durée sous l'eau du portefeuille (jours)", "B7", m["jours_sous_eau"], dmax, etat, detail.strip(), [p_dur])
    plaf = ctr["plafonds"]
    croissance = round(sum(w for t, w in poids.items() if uni[t]["role"] not in AMORTISSEURS) * 100, 1)
    ctl("Part de la poche de croissance (hors liquidités et obligations)", "A2", croissance, ctr["part_croissance_max_pct"],
        "respectee" if croissance <= ctr["part_croissance_max_pct"] + 0.05 else "a_surveiller",
        f"Repère indicatif pour un profil de niveau {ctr['niveau']} sur 5, pas un plafond.")
    ctl("Part de cryptoactifs", "D2", expo["crypto_pct"], plaf["crypto_pct"],
        "respectee" if expo["crypto_pct"] <= plaf["crypto_pct"] + 0.05 else "en_conflit")
    if plaf["speculatif_pct"] is not None:
        ctl("Part de placements spéculatifs", "D12", expo["speculatif_pct"], plaf["speculatif_pct"],
            "respectee" if expo["speculatif_pct"] <= plaf["speculatif_pct"] + 0.05 else "en_conflit")
    titres = {t: round(w * 100, 1) for t, w in poids.items() if C.titre_individuel(uni[t])}
    if titres:
        gros = max(titres, key=titres.get)
        ctl("Poids du plus gros titre individuel", "D9", titres[gros], plaf["titre_pct"],
            "respectee" if titres[gros] <= plaf["titre_pct"] + 0.05 else "en_conflit", f"Titre : {gros}.")
    emploi = plaf["secteur_emploi"]["secteurs"]
    if emploi:
        v = round(sum(expo["secteurs_pct"].get(s, 0.0) for s in emploi), 1)
        ctl(f"Exposition effective au secteur de l'emploi ({', '.join(emploi)})", "A12", v, plaf["secteur_emploi"]["pct"],
            "respectee" if v <= plaf["secteur_emploi"]["pct"] + 0.05 else "en_conflit",
            "FNB compris, selon leur répartition sectorielle.", [registre.hypothese("plafond_secteur_emploi_pct")])
    autres = {s: v for s, v in expo["secteurs_pct"].items() if s not in emploi}
    if autres:
        s = max(autres, key=autres.get)
        ctl("Exposition effective au secteur le plus lourd", "D9", autres[s], plaf["secteur_pct"],
            "respectee" if autres[s] <= plaf["secteur_pct"] + 0.05 else "en_conflit", f"Secteur : {s}.",
            [registre.hypothese("plafond_secteur_pct")])
    if plaf["hors_cad_pct"] is not None:
        ctl("Part exposée au change", "D4", expo["hors_cad_pct"], plaf["hors_cad_pct"],
            "respectee" if expo["hors_cad_pct"] <= plaf["hors_cad_pct"] + 0.05 else "en_conflit")
    for g in ctr["plafonds_groupes"]:
        v = round(sum(w * C.part_dans_groupe(uni[t], g) for t, w in poids.items()) * 100, 1)
        ctl(g["libelle"], g["critere"], v, g["plafond_pct"], "respectee" if v <= g["plafond_pct"] + 0.05 else "en_conflit",
            f"Chiffre : {g['origine_chiffre']}. Un fonds compte pour sa part connue.")
    for pl in ctr["planchers"]:
        v = round(sum(w for t, w in poids.items() if t in pl["actifs"]) * 100, 1)
        ctl(f"Part minimale demandée : {pl['libelle']}", pl["critere"], v, pl["minimum_pct"],
            "respectee" if v >= pl["minimum_pct"] - 0.05 else "en_conflit", "Minimum demandé par la personne.")
    exclus = [t for t in poids if any(C.exclusion_s_applique(uni[t], ex) for ex in ctr["exclusions"])]
    ctl("Aucun actif exclu dans le portefeuille", "H2", len(exclus), 0, "respectee" if not exclus else "en_conflit",
        ("Actifs exclus présents : " + ", ".join(exclus)) if exclus else "")
    return {"lignes": lignes, "ratio_tension": round(ratio, 2), "etat_tension": _etat_tension(ratio, hyp),
            "conflits": [l["contrainte"] for l in lignes if l["etat"] == "en_conflit"],
            "a_confirmer": [l["contrainte"] for l in lignes if l["etat"] == "a_confirmer"],
            "stress": st, "expositions": expo}


LIMITES = {"stress": "votre budget de perte", "volatilite": "la variation annuelle que vous acceptez",
           "duree": "la durée de récupération que vous supportez"}


def diagnostic_exclusions(resultats: dict, n: int = 5) -> list[dict]:
    """Quelles réponses écartent le plus d'actifs ? Sert à dire quoi revoir quand presque rien n'est compatible."""
    compte: dict[tuple, int] = {}
    for r in resultats.values():
        for l in r.get("lignes", []):
            if l["etat"] == "exclu":
                compte[(l["critere"], l["libelle"])] = compte.get((l["critere"], l["libelle"]), 0) + 1
    return [{"critere": c, "libelle": lib, "nb_actifs_exclus": k}
            for (c, lib), k in sorted(compte.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def construire(ctr: dict, resultats: dict, uni, montant: float | None = None, hyp: dict | None = None,
               registre: Registre | None = None, imposes: dict | None = None, **periode) -> dict:
    """Mini-portefeuille fictif : poids, encaisse, mesures, tension en % et en dollars, contrôles et preuves.

    imposes : {ticker: part en %} ajoutés à la demande de la personne (déjà jugés compatibles par evaluer_demande).
    """
    hyp = hyp or hypotheses()
    reg = registre if registre is not None else Registre()
    montant = montant or hyp["montant_fictif_defaut_cad"]
    imposes = {t: p / 100 for t, p in (imposes or {}).items() if t in resultats and resultats[t]["verdict"] not in ("exclu", "absent", "donnees_insuffisantes")}
    sel = _choisir(resultats, uni, ctr, hyp)
    if not sel["amortisseur"] and not sel["croissance"] and not imposes:
        return {"erreur": "Aucun actif n'atteint le seuil de compatibilité avec ce profil : aucun portefeuille n'est proposé.",
                "seuil_entree": sel["seuil"], "diagnostic": diagnostic_exclusions(resultats)}
    pas = hyp["portefeuille"]["pas_part_croissance_pct"]
    cible = hyp["tension"]["coherent_max"] * ctr["budget_perte_pct"]
    bloque_duree = not (ctr["duree_par_defaut"] and not hyp["portefeuille"]["duree_sous_eau_par_defaut_bloquante"])
    essais: list[dict] = []

    def juger(w: dict, encaisse: float, libelle: str):
        st = M.stress(w, uni, hyp, **periode)
        m = st["mesures"]
        echecs = [k for k, non in (
            ("stress", st["perte_stress_pct"] > cible),
            ("volatilite", ctr["volatilite_max_pct"] is not None and m["volatilite_pct"] > ctr["volatilite_max_pct"]),
            ("duree", bloque_duree and ctr["duree_sous_eau_max_jours"] is not None and m["jours_sous_eau"] > ctr["duree_sous_eau_max_jours"])) if non]
        essais.append({"essai": libelle, "encaisse_pct": round(encaisse * 100, 1), "perte_stress_pct": st["perte_stress_pct"],
                       "volatilite_pct": m["volatilite_pct"], "jours_sous_eau": m["jours_sous_eau"], "accepte": not echecs, "echecs": echecs})
        return st, echecs

    meilleur = retenu = None
    depart = int(min(100, ctr["part_croissance_max_pct"]) // pas * pas)
    # 1. La plus grande part de croissance qui respecte tout, en partant du repère du niveau de risque.
    for g in range(depart, -1, -pas):
        w, encaisse = _poids(g / 100, sel, ctr, uni, hyp, imposes)
        st, echecs = juger(w, encaisse, f"part de croissance de {g} %")
        if meilleur is None or st["perte_stress_pct"] < meilleur[1]["perte_stress_pct"]:
            meilleur = (w, st, encaisse)
        if not echecs:
            retenu = (w, st, encaisse)
            break
    # 2. Si même la répartition la plus prudente dépasse une limite : garder une part en encaisse, par pas de 5 points.
    if retenu is None:
        w0, _, e0 = meilleur
        libres = {t: x for t, x in w0.items() if t not in imposes}
        # Les fonds de liquidités compatibles passent avant l'encaisse : ils restent investis, presque sans variation.
        liquides = sorted((r for r in resultats.values() if r["role"] == "liquidites" and r["verdict"] == "compatible"
                           and r["ticker"] not in imposes and r["ticker"] in set(M.ch.prix_cad().columns)),
                          key=lambda r: (-(r["score"] or 0), uni[r["ticker"]].get("fx_risk") != "aucun", r["ticker"]))[:3]
        for k in range(100 - pas, -1, -pas):
            w = {**{t: x * k / 100 for t, x in libres.items() if x * k / 100 > 1e-6 and uni[t]["role"] != "liquidites"}, **imposes}
            for r in liquides:
                place = max(0.0, 1.0 - sum(w.values()))
                w[r["ticker"]] = min(place / max(1, len(liquides) - liquides.index(r)), (r["poids_max_pct"] or 0) / 100)
            w = {t: x for t, x in w.items() if x > 1e-6}
            encaisse = max(0.0, 1.0 - sum(w.values()))
            st, echecs = juger(w, encaisse, f"{100 - k} % du reste en liquidités ou en encaisse")
            if not echecs:
                retenu = (w, st, encaisse)
                break
        else:
            meilleur = (w, st, encaisse)   # même le titre demandé seul dépasse une limite : conflit nommé
    conflit_construction = retenu is None
    w, st, encaisse = retenu or meilleur
    rejets = [e for e in essais if not e["accepte"]]
    if conflit_construction:
        limite_par = [LIMITES[k] for k in essais[-1]["echecs"]]
    elif rejets:
        limite_par = [LIMITES[k] for k in rejets[-1]["echecs"]]
    else:
        limite_par = ["la part d'actions indicative de votre niveau de risque"]
    ct = controles(w, ctr, uni, hyp, reg, st, **periode)
    lignes = []
    for t, x in sorted(w.items(), key=lambda kv: (-kv[1], kv[0])):
        r, a = resultats[t], uni[t]
        lignes.append({"ticker": t, "nom": a["name"], "role": a["role"], "classe": a["asset_class"],
                       "poche": "amortisseur" if a["role"] in AMORTISSEURS else "croissance",
                       "poids_pct": round(x * 100, 1), "montant_cad": round(x * montant, 2), "score": r["score"],
                       "poids_max_pct": r["poids_max_pct"], "demande": t in imposes,
                       "pourquoi": ("ajouté à votre demande ; " if t in imposes else "") +
                                   ("; ".join(l["libelle"] for l in r["lignes"] if l["etat"] == "satisfaite") or
                                    "cohérent avec le budget de risque et les plafonds"),
                       "preuves": [reg.actif(a, "stress_loss"), reg.actif(a, "role")]})
    part = lambda poche: round(sum(x for t, x in w.items() if (uni[t]["role"] in AMORTISSEURS) == (poche == "amortisseur")) * 100, 1)  # noqa: E731
    encaisse_pct = round(encaisse * 100, 1)
    raison_encaisse = None
    if encaisse_pct >= 0.5:
        raison_encaisse = ("aucun actif défensif (liquidités, obligations courtes) n'est compatible avec vos réponses"
                           if not sel["amortisseur"] else
                           "même la répartition la plus prudente dépassait " + " et ".join(limite_par)
                           if len(essais) > (depart // pas + 1) else "vos plafonds par titre et par fonds laissent une part sans emploi")
    return {
        "nature": "Mini-portefeuille FICTIF, simulation éducative : aucun ordre, aucun conseil financier personnalisé.",
        "montant_fictif_cad": montant, "lignes": lignes, "nb_positions": len(lignes),
        "part_croissance_pct": part("croissance"), "part_amortisseur_pct": part("amortisseur"),
        "encaisse_pct": encaisse_pct, "encaisse_cad": round(encaisse * montant, 2), "raison_encaisse": raison_encaisse,
        "non_investi_pct": encaisse_pct,
        "limite_par": limite_par, "repere_part_croissance_pct": ctr["part_croissance_max_pct"],
        "ajouts": {t: round(p * 100, 1) for t, p in imposes.items()},
        "seuil_entree": sel["seuil"], "seuil_entree_demande": hyp["portefeuille"]["seuil_entree"], "nb_candidats": sel["candidats"],
        "mesures": st["mesures"], "stress": {k: v for k, v in st.items() if k != "mesures"},
        "budget_perte_pct": ctr["budget_perte_pct"], "budget_perte_cad": round(ctr["budget_perte_pct"] / 100 * montant, 2),
        "perte_stress_pct": st["perte_stress_pct"], "perte_stress_cad": round(st["perte_stress_pct"] / 100 * montant, 2),
        "ratio_tension": ct["ratio_tension"], "etat_tension": ct["etat_tension"],
        "controles": ct["lignes"], "conflits": ct["conflits"], "a_confirmer": ct["a_confirmer"],
        "conflit_construction": conflit_construction,
        "message_conflit": ("Aucune répartition ne respecte toutes les contraintes à la fois : la plus prudente est montrée, "
                            "avec les contraintes en conflit.") if conflit_construction or ct["conflits"] else None,
        "expositions": ct["expositions"], "essais": essais,
        "poids": {t: round(x, 6) for t, x in w.items()},
        "preuves": reg.extrait(i for l in ct["lignes"] for i in l["preuves"]),
        "hypotheses": {"rééquilibrage": "quotidien aux poids cibles", "période": st["mesures"]["periode"],
                       "seuil d'entrée": sel["seuil"], "positions maximales": hyp["portefeuille"]["nb_positions_max"]},
    }


# ---------- Demande d'un titre précis (H2) : verdict = pire critère, figé avant toute justification ----------

def _avec_titre(poids: dict, ticker: str, part: float) -> dict:
    w = {t: x * (1 - part) for t, x in poids.items()}
    w[ticker] = w.get(ticker, 0.0) + part
    return w


def evaluer_demande(ticker: str, part_pct: float, portefeuille: dict, ctr: dict, resultats: dict, uni,
                    hyp: dict | None = None, registre: Registre | None = None) -> dict:
    """Verdict d'une demande « ajouter ce titre pour telle part ». Le texte de justification n'est PAS un paramètre :
    le verdict ne peut pas en dépendre. Il est horodaté et signé d'une empreinte dès sa création."""
    hyp = hyp or hypotheses()
    reg = registre if registre is not None else Registre()
    montant = portefeuille["montant_fictif_cad"]
    base = {"ticker": ticker, "part_demandee_pct": part_pct, "montant_demande_cad": round(part_pct / 100 * montant, 2),
            "nature": "Simulation : aucun ordre n'est passé."}

    def figer(d: dict) -> dict:
        d["fige_le"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        noyau = {k: d[k] for k in ("ticker", "part_demandee_pct", "verdict", "raisons", "part_max_compatible_pct") if k in d}
        d["empreinte"] = hashlib.sha256(json.dumps(noyau, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
        return d

    if ticker not in uni:
        return figer({**base, "verdict": "absent", "libelle_verdict": "Absent de l'univers", "raisons": [
            {"critere": "H3", "etat": "absent", "texte": "Cet actif n'est pas dans l'univers analysé : aucune évaluation n'est produite."}]})
    r = resultats[ticker]
    if r["verdict"] in ("exclu", "donnees_insuffisantes"):
        return figer({**base, "nom": r.get("nom"), "verdict": r["verdict"], "libelle_verdict": r["libelle_verdict"],
                      "part_max_compatible_pct": 0.0,
                      "raisons": [{"critere": l["critere"], "etat": l["etat"], "texte": l["raison"], "preuves": l["preuves"]}
                                  for l in r["lignes"] if l["etat"] == "exclu"] or
                                 [{"critere": "H3", "etat": "donnees_insuffisantes", "texte": r.get("message", "")}],
                      "preuves": r.get("preuves", [])})

    def examiner(part: float) -> tuple[str, list[dict], dict]:
        # Le portefeuille est réajusté AUTOUR du titre demandé : les autres positions cèdent la place sous les mêmes
        # plafonds. La demande n'est donc en tension que si le titre lui-même dépasse une limite ou le budget de perte.
        cible = _avec_titre(portefeuille["poids"], ticker, part / 100)
        plafonds = {t: (resultats[t].get("poids_max_pct") or 0) / 100 for t in cible}
        refuge = [t for t in cible if uni[t]["role"] in AMORTISSEURS]
        w, _ = plafonner(cible, plafonds, _groupes_plafonnes(ctr, uni, list(cible)), refuge, fixes=(ticker,))
        w = {t: x for t, x in w.items() if x > 1e-6}
        ct = controles(w, ctr, uni, hyp, Registre())
        raisons = []
        if part > r["poids_max_pct"] + 1e-6:
            raisons.append({"critere": "B1", "etat": "en_tension",
                            "texte": f"La part demandée ({pct(part, 0)}) dépasse le poids maximal compatible de cet actif "
                                     f"({pct(r['poids_max_pct'], 0)} : {r['raison_poids_max']})."})
        for l in ct["lignes"]:
            if l["etat"] == "en_conflit":
                raisons.append({"critere": l["critere"], "etat": "en_tension",
                                "texte": f"{l['contrainte']} : {pct(l['valeur'])} pour une limite de {pct(l['limite'], 0)}. {l['detail']}".strip()})
        for l in ct["lignes"]:
            if l["etat"] == "a_surveiller" and l["critere"] in ("B1", "A2"):
                raisons.append({"critere": l["critere"], "etat": "a_surveiller",
                                "texte": f"{l['contrainte']} : {pct(l['valeur'])} pour un repère de {pct(l['limite'], 0)}. {l['detail']}".strip()})
            elif l["etat"] == "en_tension":
                raisons.append({"critere": l["critere"], "etat": "en_tension", "texte": l["detail"]})
        pire = "en_tension" if any(x["etat"] == "en_tension" for x in raisons) else \
               "a_surveiller" if raisons else "coherent"
        return pire, raisons, ct

    pire, raisons, ct = examiner(part_pct)
    signaux = [{"critere": l["critere"], "etat": l["etat"], "texte": l["raison"], "preuves": l["preuves"]}
               for l in r["lignes"] if l["etat"] in ("a_surveiller", "en_tension", "contraire")]
    if pire == "coherent" and signaux:
        pire = "a_surveiller"
    part_max = 0.0
    for p in range(int(min(100, max(part_pct, r["poids_max_pct"]))) , 0, -1):
        if examiner(float(p))[0] != "en_tension":
            part_max = float(p)
            break
    avant = portefeuille["perte_stress_pct"]
    apres = ct["stress"]["perte_stress_pct"]
    p_av = reg.calcul("demande:perte_stress_avant", avant, "perte de stress du portefeuille avant l'ajout", ct["stress"]["mesures"]["periode"])
    p_ap = reg.calcul("demande:perte_stress_apres", apres, "perte de stress du portefeuille après l'ajout", ct["stress"]["mesures"]["periode"])
    a = uni[ticker]
    libelles = {"coherent": "Cohérent avec le profil", "a_surveiller": "À surveiller", "en_tension": "En tension avec le profil"}
    return figer({
        **base, "nom": r["nom"], "verdict": pire, "libelle_verdict": libelles[pire],
        "regle": "Verdict = pire critère, calculé sur le portefeuille et le montant, figé avant toute justification.",
        "raisons": raisons + signaux, "score_actif": r["score"], "poids_max_actif_pct": r["poids_max_pct"],
        "part_max_compatible_pct": part_max, "montant_max_compatible_cad": round(part_max / 100 * montant, 2),
        "perte_stress_avant_pct": avant, "perte_stress_apres_pct": apres, "budget_perte_pct": ctr["budget_perte_pct"],
        "perte_stress_apres_cad": round(apres / 100 * montant, 2), "budget_perte_cad": round(ctr["budget_perte_pct"] / 100 * montant, 2),
        "ratio_tension_apres": ct["ratio_tension"],
        "faits_actif": {"volatilite_pct": round((M.nombre(a["vol_cad"]) or 0) * 100, 1),
                        "perte_max_pct": round(abs(M.nombre(a["max_drawdown"]) or 0) * 100, 1),
                        "rendement_2022_pct": round((M.nombre(a["return_2022"]) or 0) * 100, 1) if M.nombre(a["return_2022"]) is not None else None,
                        "attention": a.get("kw_attention"), "speculatif": C.speculatif(a)},
        "controles": ct["lignes"],
        "preuves": reg.extrait([p_av, p_ap, reg.actif(a, "vol_cad"), reg.actif(a, "max_drawdown"), reg.actif(a, "return_2022"),
                                reg.actif(a, "kw_attention"), reg.actif(a, "speculative")] +
                               [i for s in signaux for i in s.get("preuves", [])]),
    })
