"""Moteur d'appariement profil ↔ actif. Aucune IA : le code décide.

Ordre des effets : DURE (exclusion) > CALIBRAGE (budget de risque) > PLAFOND > PREFERENCE.
- Une exclusion dure donne « exclu ». Aucun score ne la compense : le score n'est même pas calculé.
- Le risque ne se juge pas actif par actif (presque tous dépassent 15 % de volatilité) : pour un actif seul,
  le moteur calcule le POIDS MAXIMAL COMPATIBLE avec le budget de perte et les plafonds de la personne.
- Une préférence ne compense jamais une tension : le score est borné par le pire critère de calibrage ou de plafond.
- Chaque ligne du résultat porte ses preuves (colonne, valeur, date, source) et la réponse qui la déclenche.
"""
from __future__ import annotations

from .chargement import Univers, etiquettes, hypotheses, nombre, vrai, NON_APPLICABLE, VIDES
from . import contraintes as C
from .preuves import Registre

LIBELLES_VERDICT = {"exclu": "Exclu", "compatible": "Compatible", "a_examiner": "À examiner",
                    "peu_adapte": "Peu adapté", "donnees_insuffisantes": "Données insuffisantes"}
ORDRE_ETAT = {"exclu": 0, "en_tension": 1, "a_surveiller": 2, "coherent": 3}


def pct(x: float | None, d: int = 1) -> str:
    """Pourcentage à la française. None reste visible : « donnée manquante »."""
    if x is None:
        return "donnée manquante"
    return f"{x:.{d}f}".replace(".", ",") + " %"


def bande(score: float, hyp: dict) -> str:
    b = hyp["bandes_score"]
    return "compatible" if score >= b["compatible"] else "a_examiner" if score >= b["a_examiner"] else "peu_adapte"


def _manque(actif: dict, colonne: str) -> bool:
    return str(actif.get(colonne, "")).strip() in VIDES


def evaluer_actif(ticker: str, ctr: dict, uni: Univers, registre: Registre | None = None,
                  montant: float | None = None, hyp: dict | None = None) -> dict:
    """Verdict, score 0-100, poids maximal compatible, critères en tension et preuves pour UN actif."""
    hyp = hyp or hypotheses()
    reg = registre if registre is not None else Registre()
    if ticker not in uni:
        return {"ticker": ticker, "verdict": "absent", "libelle_verdict": "Absent de l'univers",
                "message": "Cet actif n'est pas dans l'univers analysé : aucune évaluation n'est produite."}
    a = uni[ticker]
    base = {"ticker": ticker, "nom": a.get("name"), "classe": a.get("asset_class"), "role": a.get("role"),
            "date_donnees": a.get("last_date")}
    if ticker in uni.incomplets:
        return {**base, "verdict": "donnees_insuffisantes", "libelle_verdict": LIBELLES_VERDICT["donnees_insuffisantes"],
                "score": None, "colonnes_manquantes": uni.incomplets[ticker], "lignes": [], "preuves": [],
                "message": "Données insuffisantes pour évaluer cet actif : " + ", ".join(uni.incomplets[ticker])}

    lignes: list[dict] = []
    etats = ctr["etats"]

    def p_profil(cid: str) -> list[str]:
        e = etats.get(cid)
        if not e:
            return []
        valeur = ", ".join(e["valeurs"]) if e["valeurs"] else None
        prudent = next((r for r in ctr["reglages_prudents"] if r["critere"] == cid), None)
        if prudent and e["etat"] != "CONNU":
            return [reg.profil(cid, {"valeur": prudent["valeur"], "etat": e["etat"], "source": "réglage prudent (question sans réponse)",
                                     "statut": e["statut"], "nature": "réglage prudent, pas une réponse"})]
        return [reg.profil(cid, {"valeur": valeur, "etat": e["etat"], "source": e["source"], "citation": e["citation"],
                                 "statut": e["statut"]})]

    def ligne(critere, libelle, effet, etat, raison, colonnes=(), profil_ids=(), poids=0.0, note=None, borne=True, hyps=()):
        preuves = [reg.actif(a, c) for c in colonnes] + [i for cid in profil_ids for i in p_profil(cid)] + \
                  [reg.hypothese(h) for h in hyps]
        lignes.append({"critere": critere, "libelle": libelle, "effet": effet, "etat": etat, "raison": raison,
                       "poids": round(poids, 2), "note": note, "borne": borne, "preuves": preuves})

    # ---------- 1. DURE : exclusions ----------
    for ex in ctr["exclusions"]:
        if C.exclusion_s_applique(a, ex, uni):
            cols = C.colonnes_exclusion(ex)
            indirectes = C.positions_exclues(a, ex, uni)
            directe = C.exclusion_directe(a, ex)
            detail = ", ".join(f"{c} = {a.get(c) or 'vide'}" for c in cols if c != "ticker") if directe else ""
            raison = ex["libelle"] + (f" ({detail})" if detail else "")
            if indirectes:
                raison += ". Sous-jacents exclus connus : " + ", ".join(
                    f"{t} ({pct(p * 100)} du fonds)" for t, p in sorted(indirectes.items()))
            if ex.get("citation"):
                raison += f" — « {ex['citation']} »"
            if "réglage prudent" in ex.get("origine", ""):
                raison += " — réglage prudent appliqué faute de réponse, à confirmer"
            ligne(ex["critere"], ex["libelle"], "DURE", "exclu", raison, cols if directe else ["ticker"],
                  [ex["critere"]] if ex["critere"] in etats else [])
            if indirectes:
                lignes[-1]["preuves"].extend(reg.actif(uni[t], c) for t in indirectes for c in cols)
                lignes[-1]["preuves"].append(reg.calcul(
                    f"positions_exclues:{ticker}:{ex['critere']}", indirectes,
                    "Positions connues du fonds dans recommandation/donnees/fnb.json ; poids dans le fonds, "
                    "pas couverture complète. Sources : etf_top_holdings.csv et correspondances_positions_fnb.json.",
                    a.get("last_date")))
    exclu = [l for l in lignes if l["etat"] == "exclu"]
    if exclu:
        return {**base, "verdict": "exclu", "libelle_verdict": LIBELLES_VERDICT["exclu"], "score": None,
                "poids_max_pct": 0.0, "critere_decisif": exclu[0]["critere"],
                "criteres_en_tension": [l["critere"] for l in exclu], "lignes": lignes,
                "preuves": reg.extrait(i for l in lignes for i in l["preuves"]),
                "message": "Exclu : " + " ; ".join(l["raison"] for l in exclu) +
                           ". Une exclusion ne se compense pas par un bon score."}

    pond, notes = hyp["ponderation"], hyp["notes"]
    plaf = ctr["plafonds"]
    non_evalues: list[str] = []

    # ---------- 2. CALIBRAGE : poids maximal compatible ----------
    stress = nombre(a.get("stress_loss"))
    cible = hyp["tension"]["coherent_max"] * ctr["budget_perte_pct"]
    bornes = []
    if stress is None or stress == 0:
        non_evalues.append("stress_loss")
    else:
        bornes.append((min(100.0, cible / abs(stress * 100) * 100), f"budget de perte de {pct(ctr['budget_perte_pct'])} "
                       f"face à une perte maximale historique de {pct(abs(stress) * 100)}"))
    if C.titre_individuel(a):
        bornes.append((float(plaf["titre_pct"]), f"plafond par titre de {plaf['titre_pct']} %"))
    else:
        bornes.append((float(plaf["fonds_pct"]), f"plafond par fonds de {plaf['fonds_pct']} %"))
    if a.get("asset_class") == "crypto":
        bornes.append((float(plaf["crypto_pct"]), f"plafond de cryptoactifs de {plaf['crypto_pct']} %"))
    if C.speculatif(a) and plaf["speculatif_pct"] is not None:
        bornes.append((float(plaf["speculatif_pct"]), f"plafond de placements spéculatifs de {plaf['speculatif_pct']} %"))
    for g in ctr["plafonds_groupes"]:
        part = C.part_dans_groupe(a, g)
        if part > 0:
            bornes.append((min(100.0, g["plafond_pct"] / part), f"plafond de {g['plafond_pct']} % : {g['libelle']}"))
    poids_max, raison_max = min(bornes, key=lambda b: b[0])
    # L'état se juge sur la borne de RISQUE seule : un plafond choisi par la personne (10 % par titre, 10 % de
    # fonds exposés…) limite le poids, il ne rend pas l'actif moins cohérent avec son budget de perte.
    borne_risque = bornes[0][0] if stress else 100.0
    reference = min(hyp["poids_reference_pct"], plaf["titre_pct"] if C.titre_individuel(a) else hyp["poids_reference_pct"])
    etat = ("en_tension" if poids_max < hyp["poids_max_plancher_pct"] else
            "coherent" if borne_risque >= reference else "a_surveiller")
    ligne("B1", "Poids maximal compatible avec le budget de risque", "CALIBRAGE", etat,
          f"Au plus {pct(poids_max, 0)} du portefeuille ({raison_max}).",
          ["stress_loss", "speculative", "asset_class"], ["B1", "D9", "D2", "D12"],
          pond["CALIBRAGE"], notes[etat], hyps=["tension", "poids_reference_pct"])

    horizon_min = nombre(a.get("horizon_min_years"))
    if horizon_min is None:
        non_evalues.append("horizon_min_years")
    else:
        ok = horizon_min <= ctr["horizon_annees"]
        ligne("A2", "Horizon de placement", "CALIBRAGE", "coherent" if ok else "a_surveiller",
              (f"Horizon minimal indicatif de l'actif : {horizon_min:.0f} ans ; horizon du profil : "
               f"{C._libelle('A2', ctr['horizon']).lower()}" + ("" if ok else ". À détenir en petite part seulement.") +
               (" (horizon par défaut, question sans réponse)" if ctr["horizon_par_defaut"] else "")),
              ["horizon_min_years", "risk_class"], ["A2"], pond["CALIBRAGE"],
              notes["coherent" if ok else "a_surveiller"], borne=False)

    # ---------- 3. PLAFOND : complexité, signaux de la grille ----------
    cx = nombre(a.get("complexity"))
    ok = cx is not None and cx <= plaf["complexite_max"]
    ligne("C1", "Complexité de l'actif face aux connaissances mesurées", "PLAFOND", "coherent" if ok else "en_tension",
          f"Complexité {cx:.0f} sur 3 ; niveau accepté pour ce profil : {plaf['complexite_max']} sur 3.",
          ["complexity"], ["C1"], pond["PLAFOND"], notes["coherent" if ok else "en_tension"], hyps=["complexite_max_par_C1"])

    attention = etiquettes(a.get("kw_attention"))
    for s in ctr["signaux"]:
        mode = s.get("mode")
        m = ctr["multiplicateur_esg"] if s.get("esg") else 1.0
        if mode == "mode":
            mediatise = "tres_mediatise" in attention or vrai(a.get("hype_recent"))
            if C.speculatif(a) or mediatise:
                quoi = " et ".join(x for x, c in (("spéculatif", C.speculatif(a)), ("très médiatisé", mediatise)) if c)
                ligne("D8", "Actif spéculatif ou très médiatisé", "PLAFOND", "a_surveiller", f"Actif {quoi}. {s['texte']}.",
                      ["speculative", "kw_attention", "hype_recent"], ["D8", "D8O"], pond["PLAFOND"], notes["a_surveiller"],
                      hyps=["niveau_max_avertissement_mode"])
        elif mode == "change":
            if C.expose_change(a):
                ligne("D4", "Exposition au change", "PLAFOND", "a_surveiller", s["texte"] + f" (kw_devise = {a.get('kw_devise')}).",
                      ["fx_risk", "kw_devise"], ["D4"], pond["PLAFOND"], notes["a_surveiller"])
        elif mode == "hors_liquidites":
            if a.get("role") != "liquidites":
                ligne("A3", "Rôle de l'actif face à l'objectif", "PLAFOND", "en_tension", s["texte"] + f" (rôle : {a.get('role')}).",
                      ["role"], ["A3"], pond["PLAFOND"], notes["en_tension"])
        elif mode == "dividende_fragile":
            ratio = nombre(a.get("dividends_to_fcf_last"))
            comparable = "ratio_distribution_non_comparable" not in etiquettes(a.get("kw_dividende_durabilite"))
            if vrai(a.get("dividend_cut_2022_2025")) or (ratio is not None and ratio > 1 and comparable):
                ligne("A10", "Solidité du revenu versé", "PLAFOND", "en_tension", s["texte"] + ".",
                      ["dividend_cut_2022_2025", "dividends_to_fcf_last"], ["A10"], pond["PLAFOND"], notes["en_tension"])
        elif C.concerne(a, s["condition"]) and m > 0 and (s["critere"] == "E2" or C.titre_individuel(a)):
            cols = C.colonnes_de(s["condition"]) + (["controversy_topics"] if s["critere"] == "E2" else [])
            sujet = f" Sujet : {a.get('controversy_topics')}." if s["critere"] == "E2" and a.get("controversy_topics") else ""
            ligne(s["critere"], C._nom(s["critere"]), "PLAFOND", "a_surveiller", s["texte"] + "." + sujet,
                  cols, [s["critere"], "E4"], pond["PLAFOND"] * m, notes["a_surveiller"])

    # ---------- 4. PREFERENCE : ne compense jamais une tension ----------
    for pr in ctr["preferences"]:
        w = pond["PREFERENCE"] * pr.get("multiplicateur", 1.0)
        if w <= 0:
            continue
        cols, etat, raison = [], "neutre", ""
        if pr["type"] == "conditions":
            cols = list(dict.fromkeys(c for cond in pr["conditions"] for c in C.colonnes_de(cond)))
            ok = any(C.concerne(a, cond) for cond in pr["conditions"])
            etat, raison = ("satisfaite", "Correspond.") if ok else ("neutre", "Ne correspond pas, sans être contraire.")
        elif pr["type"] == "liste":
            cols = ["ticker"]
            ok = ticker in pr["actifs"]
            etat, raison = ("satisfaite", "Actif visé par cette préférence.") if ok else ("neutre", "Actif non visé.")
        elif pr["type"] == "style":
            cols = [pr["colonne"], "speculative"]
            if pr["colonne"] != "income_asset" and a.get("asset_class") != "equity":
                etat, raison = "neutre", "Critère de style propre aux actions : sans objet pour un fonds ou un cryptoactif."
            elif vrai(a.get(pr["colonne"])):
                etat, raison = "satisfaite", f"{pr['colonne']} = True."
            elif pr.get("contraire_si_speculatif") and C.speculatif(a):
                etat, raison = "contraire", "Actif spéculatif, à l'opposé du style « établie » recherché."
            else:
                etat, raison = "neutre", f"{pr['colonne']} = {a.get(pr['colonne'])}."
        elif pr["type"] == "forme":
            cols = ["asset_class"]
            fonds = str(a.get("asset_class", "")).startswith("etf")
            ok = fonds if pr["valeur"] == "fnb" else a.get("asset_class") == "equity"
            etat, raison = ("satisfaite" if ok else "neutre"), f"Classe : {a.get('asset_class')}."
        elif pr["type"] == "esg":
            cols = ["in_jantzi_social_index", "max_severity", "fossil_categorie", "themes"]
            sensibles = [x for x in etiquettes(a.get("kw_exclusions")) if x not in ("aucune_connue", "energie_fossile_via_fonds")]
            cols.append("kw_exclusions")
            if a.get("max_severity") in ("moyenne", "élevée") or a.get("fossil_categorie") == "directe" or sensibles:
                etat = "contraire"
                raison = (f"Controverse : {a.get('max_severity')} ; implication fossile : {a.get('fossil_categorie')} ; "
                          f"activités sensibles connues : {', '.join(sensibles) or 'aucune'}.")
            elif vrai(a.get("in_jantzi_social_index")) or "esg" in etiquettes(a.get("themes")):
                etat, raison = "satisfaite", "Présent dans l'indice Jantzi Social ou fonds filtré ESG."
            else:
                etat, raison = "neutre", ("Aucun signal ESG positif ou négatif dans nos sources ; « aucune controverse trouvée » "
                                         "ne veut pas dire « aucune controverse ».")
        elif pr["type"] == "diversification":
            cols = ["role", "diversifier_vs_world"]
            ok = a.get("role") in ("coeur", "liquidites", "obligations_amortisseur") or vrai(a.get("diversifier_vs_world"))
            etat, raison = ("satisfaite", f"Rôle {a.get('role')} ou actif peu corrélé au marché mondial.") if ok else \
                           ("neutre", f"Rôle {a.get('role')} : n'ajoute pas de diversification par lui-même.")
        ligne(pr["critere"], pr["libelle"], "PREFERENCE", etat, raison, cols,
              [pr["critere"]] if pr["critere"] in etats else [], w, notes["preference_" + etat], borne=False)

    # ---------- 5. INFORMATION : affichée, sans effet sur le score ----------
    def info(critere, libelle, raison, colonnes, profil_ids=()):
        ligne(critere, libelle, "INFORMATION", "information", raison, colonnes, profil_ids, borne=False)

    if str(a.get("asset_class", "")).startswith("etf") and any(ex.get("sous_jacents") for ex in ctr["exclusions"]):
        from .chargement import positions_fnb
        positions = positions_fnb().get(ticker, {})
        couverture_positions = min(1.0, sum(p for t, p in positions.items() if t in uni and p > 0))
        info("E2", "Couverture des exclusions dans les fonds",
             f"Sous-jacents connus : {pct(couverture_positions * 100)} du fonds. Les exclusions ESG portent sur "
             "ces positions et la fiche du fonds ; la part restante est inconnue, sans garantie d'absence d'exposition exclue.",
             ["ticker"])
        lignes[-1]["preuves"].append(reg.calcul(
            f"couverture_positions:{ticker}", round(couverture_positions * 100, 1),
            "Somme des positions rattachées à l'univers dans recommandation/donnees/fnb.json, en pourcentage du fonds.",
            a.get("last_date")))

    classe_risque = nombre(a.get("risk_class"))
    if ctr["consultation_quotidienne"] and classe_risque is not None and classe_risque >= 6:
        info("B4", "Consultation quotidienne d'un actif très variable",
             f"Classe de risque {classe_risque:.0f} sur 7 : regarder chaque jour un actif très variable rend les baisses plus pénibles.",
             ["risk_class", "var95_daily"], ["B4"])
    if a.get("kw_recuperation") in ("jamais_recupere", "baisse_en_cours"):
        info("B7", "Récupération après la pire baisse", f"État : {a.get('kw_recuperation')} sur la période observée.",
             ["kw_recuperation", "current_drawdown"], ["B7"])
    detenus = ctr["produits_detenus"]
    if detenus and a.get("asset_class") == "crypto" and "crypto" not in detenus:
        info("C2", "Première détention de cette classe", "La personne n'a jamais détenu de cryptoactif.", ["asset_class"], ["C2"])
    prix = nombre(a.get("unit_price_cad"))
    if montant and prix and prix > 0.05 * montant:
        info("G1", "Prix unitaire élevé pour le montant", f"Une unité coûte {prix:,.0f} $ CA, plus de 5 % du montant : "
             "des fractions de titre seraient nécessaires.".replace(",", " "), ["unit_price_cad"], ["G1"])
    if ctr["compte"] == "celi" and str(a.get("foreign_dividend_withholding", "")).startswith("oui"):
        info("G2", "Retenue étrangère sur les dividendes", "Dans un CELI, la retenue d'impôt étrangère n'est pas récupérable. "
             "Information générale, pas un conseil fiscal.", ["foreign_dividend_withholding", "kw_fiscalite"], ["G2"])
    for g in ctr["plafonds_groupes"]:
        if C.membre_groupe(a, g):
            info(g["critere"], "Plafond de groupe", f"{g['libelle']} : {g['plafond_pct']} % au plus pour l'ensemble du groupe "
                 f"({g['origine_chiffre']}).", C.colonnes_de(g["condition"]) if g.get("condition") else ["ticker"])
    for c in ("etf_expense_ratio", "profitable_years_share"):
        if _manque(a, c) and ((c == "etf_expense_ratio") == str(a.get("asset_class", "")).startswith("etf")):
            non_evalues.append(c)

    # ---------- Score ----------
    notees = [l for l in lignes if l["note"] is not None and l["poids"] > 0]
    total = sum(l["poids"] for l in notees)
    brut = 100 * sum(l["poids"] * l["note"] for l in notees) / total if total else 0.0
    bornantes = [l for l in lignes if l["borne"] and l["effet"] in ("CALIBRAGE", "PLAFOND")]
    pire = min((l["etat"] for l in bornantes), key=lambda e: ORDRE_ETAT[e], default="coherent")
    score = brut
    if pire == "en_tension":
        score = min(score, hyp["bornes_score"]["en_tension"])
    elif pire == "a_surveiller":
        score = min(score, hyp["bornes_score"]["a_surveiller"])
    score = round(score)
    couverture = round(100 * len(notees) / (len(notees) + len(set(non_evalues))))
    en_tension = [l for l in lignes if l["etat"] in ("en_tension", "a_surveiller", "contraire")]
    favorables = [l for l in lignes if l["etat"] in ("coherent", "satisfaite")]
    if couverture < hyp["couverture_min_pct"]:
        verdict = "donnees_insuffisantes"
    else:
        verdict = bande(score, hyp)
    decisif = next((l for l in sorted(lignes, key=lambda l: ORDRE_ETAT.get(l["etat"], 9)) if l["etat"] in ORDRE_ETAT), None)
    return {**base, "verdict": verdict, "libelle_verdict": LIBELLES_VERDICT[verdict], "score": score,
            "score_avant_borne": round(brut), "borne_appliquee": pire if score < round(brut) else None,
            "seuils": hyp["bandes_score"], "pire_critere": pire,
            "poids_max_pct": round(poids_max, 1), "raison_poids_max": raison_max,
            "couverture_pct": couverture, "donnees_manquantes": sorted(set(non_evalues)),
            "critere_decisif": decisif["critere"] if decisif and decisif["etat"] != "coherent" else None,
            "criteres_en_tension": [l["critere"] for l in en_tension],
            "criteres_favorables": [l["critere"] for l in favorables],
            "lignes": lignes, "preuves": reg.extrait(i for l in lignes for i in l["preuves"])}


def evaluer_univers(ctr: dict, uni: Univers, registre: Registre | None = None, montant: float | None = None,
                    hyp: dict | None = None) -> dict[str, dict]:
    reg = registre if registre is not None else Registre()
    return {tk: evaluer_actif(tk, ctr, uni, reg, montant, hyp) for tk in uni.tickers()}


def decompte(resultats: dict[str, dict]) -> dict[str, int]:
    out = {k: 0 for k in LIBELLES_VERDICT}
    for r in resultats.values():
        out[r["verdict"]] = out.get(r["verdict"], 0) + 1
    return out
