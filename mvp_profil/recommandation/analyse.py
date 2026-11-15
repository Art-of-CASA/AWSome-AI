"""Point d'entrée unique de la recommandation : une Analyse = un profil + l'univers + des hypothèses.

Tout ce que l'interface et les agents affichent sort d'ici. Aucune IA dans ce fichier.
  - recherche d'un actif (score, seuil, explication, preuves) ;
  - comparaison de deux actifs, avec l'écart décisif ;
  - mini-portefeuille fictif et demande d'un titre ;
  - « Et si… ? » : recalcul sur une COPIE du profil, et sensibilité aux hypothèses.
"""
from __future__ import annotations

import copy
import difflib

from . import appariement as A
from . import chargement as ch
from . import contraintes as C
from . import portefeuille as P
from .preuves import Registre

import synthese  # noqa: E402  (mvp_profil, lecture seule)
from criteres import CRITERES  # noqa: E402

RANG_EFFET = {"DURE": 0, "CALIBRAGE": 1, "PLAFOND": 2, "PREFERENCE": 3, "INFORMATION": 4}
VALEUR_ETAT = {"exclu": 0, "en_tension": 1, "contraire": 1.5, "a_surveiller": 2, "neutre": 2.5, "coherent": 3, "satisfaite": 3,
               "information": 2.75}
MENTION = ("Simulation éducative sur des données publiques : ni conseil financier personnalisé, ni ordre réel. "
           "Les mesures décrivent le passé sur la période indiquée ; elles ne prédisent pas les rendements futurs.")


class Analyse:
    def __init__(self, profil: dict, dynamiques: list[dict] | None = None, montant: float | None = None,
                 hyp: dict | None = None, univers: ch.Univers | None = None, nom: str | None = None, periode: dict | None = None):
        self.profil, self.dynamiques = profil, list(dynamiques or [])
        self.hyp = hyp or ch.hypotheses()
        self.uni = univers or ch.univers()
        self.nom = nom
        self.periode = periode or {}
        self.registre = Registre()
        self.contraintes = C.construire(profil, self.dynamiques, self.hyp)
        self.montant = float(montant or self.contraintes["montant_repere_cad"] or self.hyp["montant_fictif_defaut_cad"])
        self.resultats = A.evaluer_univers(self.contraintes, self.uni, self.registre, self.montant, self.hyp)
        self._portefeuille = None

    # ---------- Portefeuille ----------
    @property
    def portefeuille(self) -> dict:
        if self._portefeuille is None:
            self._portefeuille = P.construire(self.contraintes, self.resultats, self.uni, self.montant, self.hyp,
                                              self.registre, **self.periode)
        return self._portefeuille

    def demande(self, ticker: str, part_pct: float) -> dict:
        """Verdict figé d'une demande de titre. Aucun texte libre n'entre ici."""
        trouve = self.trouver(ticker)
        return P.evaluer_demande(trouve or ticker, float(part_pct), self.portefeuille, self.contraintes, self.resultats,
                                 self.uni, self.hyp, self.registre)

    # ---------- Recherche ----------
    def trouver(self, texte: str) -> str | None:
        """Ticker exact ou nom, sans tenir compte des accents ni de la casse. None si rien de sûr."""
        q = ch.sans_accents(texte).strip()
        if not q:
            return None
        par_ticker = {ch.sans_accents(t): t for t in self.uni.tickers()}
        if q in par_ticker:
            return par_ticker[q]
        racines = {ch.sans_accents(t).split(".")[0].split("-")[0]: t for t in reversed(self.uni.tickers())}
        if q in racines:
            return racines[q]
        noms = {ch.sans_accents(a["name"]): t for t, a in self.uni.actifs.items()}
        if q in noms:
            return noms[q]
        partiels = [t for n, t in noms.items() if q in n.split() or n.startswith(q)]
        return partiels[0] if len(partiels) == 1 else None

    def suggestions(self, texte: str, n: int = 5) -> list[dict]:
        q = ch.sans_accents(texte).strip()
        cles = {}
        for t, a in self.uni.actifs.items():
            cles[ch.sans_accents(t)] = t
            cles[ch.sans_accents(a["name"])] = t
        proches = [cles[k] for k in cles if q and q in k] + \
                  [cles[k] for k in difflib.get_close_matches(q, list(cles), n=n, cutoff=self.hyp["recherche_score_min_suggestion"])]
        return [{"ticker": t, "nom": self.uni[t]["name"]} for t in list(dict.fromkeys(proches))[:n]]

    def rechercher(self, texte: str) -> dict:
        """Score, seuil et explication d'un actif cherché par ticker ou par nom."""
        tk = self.trouver(texte)
        if tk is None:
            return {"requete": texte, "verdict": "absent", "libelle_verdict": "Absent de l'univers",
                    "message": f"« {texte} » n'est pas dans l'univers analysé ({len(self.uni)} actifs au {self.uni.date_donnees()}). "
                               "Aucune évaluation n'est produite pour un actif sans données.",
                    "suggestions": self.suggestions(texte), "mention": MENTION}
        return self.fiche(tk)

    def fiche(self, ticker: str) -> dict:
        r = dict(self.resultats[ticker])
        a = self.uni[ticker]
        r["requete"] = ticker
        r["faits"] = {
            "secteur": a.get("sector"), "pays": a.get("country"), "devise": a.get("currency"),
            "volatilite_pct": _p(a.get("vol_cad")), "perte_max_pct": _p(a.get("max_drawdown"), absolu=True),
            "rendement_2022_pct": _p(a.get("return_2022")), "classe_risque": a.get("risk_class"),
            "recuperation": a.get("kw_recuperation"), "controverse": a.get("max_severity"),
            "sujet_controverse": a.get("controversy_topics") or None, "fossile": a.get("fossil_categorie"),
            "exclusions_connues": a.get("kw_exclusions"), "attention": a.get("kw_attention"), "themes": a.get("themes") or None,
            "acces": a.get("access_canada"), "periode": f"{a.get('first_date')} au {a.get('last_date')}"}
        r["explication"] = expliquer(r, self.hyp)
        r["mention"] = MENTION
        return r

    # ---------- Comparaison ----------
    def comparer(self, texte_a: str, texte_b: str) -> dict:
        ta, tb = self.trouver(texte_a), self.trouver(texte_b)
        manquants = [x for x, t in ((texte_a, ta), (texte_b, tb)) if t is None]
        if manquants:
            return {"erreur": "Absent de l'univers : " + ", ".join(manquants) + ". Aucune comparaison n'est produite.",
                    "suggestions": {x: self.suggestions(x) for x in manquants}}
        ra, rb = self.resultats[ta], self.resultats[tb]
        index = lambda r: {(l["critere"], l["libelle"]): l for l in r["lignes"]}  # noqa: E731
        ia, ib = index(ra), index(rb)
        tableau = []
        for cle in dict.fromkeys(list(ia) + list(ib)):
            la, lb = ia.get(cle), ib.get(cle)
            ref = la or lb
            ea, eb = (la or {}).get("etat", "sans_objet"), (lb or {}).get("etat", "sans_objet")
            tableau.append({"critere": cle[0], "libelle": cle[1], "effet": ref["effet"],
                            "etat_a": ea, "raison_a": (la or {}).get("raison", "Sans objet pour cet actif."),
                            "etat_b": eb, "raison_b": (lb or {}).get("raison", "Sans objet pour cet actif."),
                            "different": ea != eb,
                            "preuves": (la or {}).get("preuves", []) + (lb or {}).get("preuves", [])})
        tableau.sort(key=lambda x: (RANG_EFFET[x["effet"]], x["critere"]))
        decisif = next((x for x in tableau if x["different"] and x["effet"] != "INFORMATION"), None)
        if decisif:
            va, vb = VALEUR_ETAT.get(decisif["etat_a"], 2.9), VALEUR_ETAT.get(decisif["etat_b"], 2.9)
            mieux = ta if va > vb else tb
            ecart = {"critere": decisif["critere"], "libelle": decisif["libelle"], "effet": decisif["effet"],
                     "en_faveur_de": mieux,
                     "raison": f"{ta} : {decisif['raison_a']} {tb} : {decisif['raison_b']}", "preuves": decisif["preuves"]}
        else:
            ecart = {"critere": None, "en_faveur_de": None,
                     "raison": "Aucun critère ne départage ces deux actifs pour ce profil ; seuls les faits descriptifs diffèrent."}
        faits = lambda t: self.fiche(t)["faits"]  # noqa: E731
        return {"a": _resume(ra), "b": _resume(rb), "faits_a": faits(ta), "faits_b": faits(tb), "tableau": tableau,
                "ecart_decisif": ecart, "regle": "Écart décisif = premier critère qui diffère, dans l'ordre : exclusion, "
                "budget de risque, plafond, préférence.",
                "preuves": self.registre.extrait(i for x in tableau for i in x["preuves"]), "mention": MENTION}

    # ---------- « Et si… ? » ----------
    def et_si(self, critere: str, valeurs: list[str] | str) -> dict:
        """Recalcule profil, verdicts et portefeuille avec UNE réponse modifiée. Le profil d'origine n'est pas touché."""
        valeurs = [valeurs] if isinstance(valeurs, str) else list(valeurs)
        if critere not in CRITERES:
            return {"erreur": f"Critère inconnu : {critere}."}
        invalides = [v for v in valeurs if v not in CRITERES[critere]["valeurs"]]
        if invalides or not valeurs:
            return {"erreur": f"Valeur hors de la liste fermée du critère {critere} : {', '.join(invalides) or 'aucune'}.",
                    "valeurs_possibles": CRITERES[critere]["valeurs"]}
        p2 = copy.deepcopy(self.profil)
        avant = list((self.profil.get(critere) or {}).get("valeurs") or [])
        p2[critere] = {**p2.get(critere, {}), "valeurs": valeurs, "statut": "validé", "source": "scénario « Et si… ? »",
                       "citation": "", "confiance": 1.0, "motif": "Valeur d'essai, non enregistrée dans le profil"}
        if critere == "B1" and "declare" in p2[critere]:
            p2[critere]["declare"] = valeurs[0]
        autre = Analyse(p2, self.dynamiques, self.montant, self.hyp, self.uni, self.nom, self.periode)
        d = self.comparer_a(autre)
        d["modification"] = {"critere": critere, "nom": CRITERES[critere]["nom"], "avant": avant or ["non renseigné"],
                             "apres": valeurs, "nature": "scénario fictif : le profil enregistré n'est pas modifié"}
        return d

    def comparer_a(self, autre: "Analyse") -> dict:
        """Ce qui change entre deux analyses, et la règle responsable de chaque changement."""
        c1, c2 = self.contraintes, autre.contraintes
        cles = (("budget_perte_pct", "Budget de perte (%)"), ("niveau", "Niveau de risque (1 à 5)"),
                ("volatilite_max_pct", "Volatilité maximale (%)"), ("duree_sous_eau_max_jours", "Durée sous l'eau maximale (jours)"),
                ("horizon", "Horizon"), ("part_croissance_max_pct", "Part de croissance indicative maximale (%)"))
        contraintes = [{"element": nom, "avant": c1[k], "apres": c2[k]} for k, nom in cles if c1[k] != c2[k]]
        for k, nom in (("titre_pct", "Plafond par titre (%)"), ("crypto_pct", "Plafond de cryptoactifs (%)"),
                       ("speculatif_pct", "Plafond de placements spéculatifs (%)"), ("hors_cad_pct", "Plafond d'exposition au change (%)"),
                       ("complexite_max", "Complexité maximale")):
            if c1["plafonds"][k] != c2["plafonds"][k]:
                contraintes.append({"element": nom, "avant": c1["plafonds"][k], "apres": c2["plafonds"][k]})
        ex = lambda c: sorted({f"{e['critere']} : {e['libelle']}" for e in c["exclusions"]})  # noqa: E731
        for e in sorted(set(ex(c2)) - set(ex(c1))):
            contraintes.append({"element": "Exclusion ajoutée", "avant": None, "apres": e})
        for e in sorted(set(ex(c1)) - set(ex(c2))):
            contraintes.append({"element": "Exclusion retirée", "avant": e, "apres": None})
        actifs = []
        for t in self.uni.tickers():
            r1, r2 = self.resultats[t], autre.resultats[t]
            if r1["verdict"] != r2["verdict"] or r1.get("score") != r2.get("score") or r1.get("poids_max_pct") != r2.get("poids_max_pct"):
                l1 = {(l["critere"], l["libelle"]): l["etat"] for l in r1["lignes"]}
                l2 = {(l["critere"], l["libelle"]): l for l in r2["lignes"]}
                causes = [k[0] for k in dict.fromkeys(list(l1) + list(l2)) if l1.get(k) != (l2.get(k) or {}).get("etat")]
                raison = next((l2[k]["raison"] for k in l2 if k[0] in causes), None) or r2.get("raison_poids_max")
                actifs.append({"ticker": t, "nom": r1.get("nom"), "verdict_avant": r1["libelle_verdict"], "verdict_apres": r2["libelle_verdict"],
                               "score_avant": r1.get("score"), "score_apres": r2.get("score"),
                               "poids_max_avant_pct": r1.get("poids_max_pct"), "poids_max_apres_pct": r2.get("poids_max_pct"),
                               "change_de_bande": r1["verdict"] != r2["verdict"],
                               "regles_en_cause": list(dict.fromkeys(causes)) or ["B1"], "raison": raison})
        pf1, pf2 = self.portefeuille, autre.portefeuille
        poids = []
        if "erreur" not in pf1 and "erreur" not in pf2:
            for t in sorted(set(pf1["poids"]) | set(pf2["poids"])):
                w1, w2 = round(pf1["poids"].get(t, 0) * 100, 1), round(pf2["poids"].get(t, 0) * 100, 1)
                if abs(w1 - w2) >= 0.1:
                    poids.append({"ticker": t, "avant_pct": w1, "apres_pct": w2, "ecart_points": round(w2 - w1, 1)})
            poids.sort(key=lambda x: -abs(x["ecart_points"]))
        resume = lambda pf: None if "erreur" in pf else {  # noqa: E731
            "perte_stress_pct": pf["perte_stress_pct"], "ratio_tension": pf["ratio_tension"], "etat_tension": pf["etat_tension"],
            "volatilite_pct": pf["mesures"]["volatilite_pct"], "part_croissance_pct": pf["part_croissance_pct"],
            "nb_positions": pf["nb_positions"], "conflits": pf["conflits"]}
        return {"contraintes": contraintes, "decompte_avant": A.decompte(self.resultats), "decompte_apres": A.decompte(autre.resultats),
                "actifs_modifies": actifs, "nb_actifs_modifies": len(actifs),
                "nb_changements_de_bande": sum(1 for a in actifs if a["change_de_bande"]),
                "portefeuille_avant": resume(pf1), "portefeuille_apres": resume(pf2), "poids_modifies": poids,
                "aucun_changement": not contraintes and not actifs and not poids, "mention": MENTION}

    def sensibilite(self) -> dict:
        """Mise à l'épreuve : horizon (un cran), seuils du score (± 5), seuil de tension, période (sans 2022).
        Ce n'est ni un intervalle de confiance ni une prévision : c'est la sensibilité des règles de l'équipe."""
        essais = []

        def ajouter(axe, libelle, autre):
            d = self.comparer_a(autre)
            essais.append({"axe": axe, "essai": libelle, "nb_changements_de_bande": d["nb_changements_de_bande"],
                           "decompte": d["decompte_apres"], "portefeuille": d["portefeuille_apres"],
                           "contraintes": d["contraintes"]})

        echelle = CRITERES["A2"]["valeurs"]
        actuel = self.contraintes["horizon"]
        i = echelle.index(actuel)
        for j in (i - 1, i + 1):
            if 0 <= j < len(echelle):
                p2 = copy.deepcopy(self.profil)
                p2["A2"] = {**p2.get("A2", {}), "valeurs": [echelle[j]], "statut": "validé", "source": "sensibilité"}
                ajouter("horizon", f"Horizon : {C._libelle('A2', echelle[j])} au lieu de {C._libelle('A2', actuel)}",
                        Analyse(p2, self.dynamiques, self.montant, self.hyp, self.uni, self.nom, self.periode))
        for delta in (-5, 5):
            h = copy.deepcopy(self.hyp)
            h["bandes_score"] = {k: v + delta for k, v in h["bandes_score"].items()}
            h["portefeuille"]["seuil_entree_paliers"] = [v + delta for v in h["portefeuille"]["seuil_entree_paliers"]]
            ajouter("seuils", f"Seuils du score à {h['bandes_score']['compatible']} / {h['bandes_score']['a_examiner']} "
                    f"et entrée dans le portefeuille à {h['portefeuille']['seuil_entree_paliers'][0]}",
                    Analyse(self.profil, self.dynamiques, self.montant, h, self.uni, self.nom, self.periode))
        for cible in (0.7, 0.9):
            h = copy.deepcopy(self.hyp)
            h["tension"]["coherent_max"] = cible
            ajouter("seuils", f"Zone « cohérent » jusqu'à {cible:.1f} × le budget de perte (au lieu de {self.hyp['tension']['coherent_max']:.1f})",
                    Analyse(self.profil, self.dynamiques, self.montant, h, self.uni, self.nom, self.periode))
        ajouter("periode", "Mesures du portefeuille sans l'année 2022 (les critères des actifs restent calculés sur toute la période)",
                Analyse(self.profil, self.dynamiques, self.montant, self.hyp, self.uni, self.nom, {"sans_annee": 2022}))
        base = self.portefeuille
        return {"reference": {"decompte": A.decompte(self.resultats),
                              "portefeuille": None if "erreur" in base else {
                                  "perte_stress_pct": base["perte_stress_pct"], "ratio_tension": base["ratio_tension"],
                                  "volatilite_pct": base["mesures"]["volatilite_pct"], "part_croissance_pct": base["part_croissance_pct"]},
                              "scenario_fictif_krach_pct": None if "erreur" in base else base["stress"]["scenario_fictif_krach_pct"]},
                "essais": essais,
                "limites": "Une hypothèse change à la fois. La plage décrit la sensibilité des règles de l'équipe : ce n'est ni un "
                           "intervalle de confiance, ni une prévision. La fenêtre 2021-2026 ne contient qu'une crise (2022).",
                "mention": MENTION}

    # ---------- Vue d'ensemble ----------
    def synthese(self) -> dict:
        c = self.contraintes
        return {"persona": self.nom, "phrase": c["phrase"], "budget_perte_pct": c["budget_perte_pct"], "niveau": c["niveau"],
                "limite_par": c["limite_par"], "horizon": C._libelle("A2", c["horizon"]),
                "plafonds": c["plafonds"], "exclusions": [{"critere": e["critere"], "libelle": e["libelle"], "origine": e["origine"]} for e in c["exclusions"]],
                "preferences": [{"critere": p["critere"], "libelle": p["libelle"], "poids": p["multiplicateur"]} for p in c["preferences"]],
                "plafonds_groupes": [{"critere": g["critere"], "libelle": g["libelle"], "plafond_pct": g["plafond_pct"]} for g in c["plafonds_groupes"]],
                "inconnus": c["inconnus"], "nb_inconnus": len(c["inconnus"]),
                "reglages_prudents": c["reglages_prudents"], "sans_effet": c["sans_effet"],
                "notes_dynamiques": c["notes_dynamiques"], "alertes": c["alertes"], "synthese_provisoire": c["synthese_provisoire"],
                "decompte": A.decompte(self.resultats), "nb_actifs": len(self.uni), "date_donnees": self.uni.date_donnees(),
                "montant_fictif_cad": self.montant, "mention": MENTION}

    def classement(self, verdict: str | None = None, n: int = 15) -> list[dict]:
        rs = [r for r in self.resultats.values() if verdict in (None, r["verdict"])]
        rs.sort(key=lambda r: (-(r["score"] if r["score"] is not None else -1), r["ticker"]))
        return [_resume(r) for r in rs[:n]]


def _p(valeur, absolu: bool = False) -> float | None:
    x = ch.nombre(valeur)
    return None if x is None else round((abs(x) if absolu else x) * 100, 1)


def _resume(r: dict) -> dict:
    return {"ticker": r["ticker"], "nom": r.get("nom"), "verdict": r["verdict"], "libelle_verdict": r["libelle_verdict"],
            "score": r.get("score"), "poids_max_pct": r.get("poids_max_pct"), "critere_decisif": r.get("critere_decisif"),
            "criteres_en_tension": r.get("criteres_en_tension", [])}


def expliquer(r: dict, hyp: dict) -> dict:
    """Explication déterministe d'un verdict : ce qui soutient, ce qui retient, ce qui manque. Sans jugement sur la personne."""
    seuil = hyp["bandes_score"]
    if r["verdict"] == "exclu":
        return {"titre": "Exclu pour ce profil", "soutient": [],
                "retient": [l["raison"] for l in r["lignes"] if l["etat"] == "exclu"],
                "resume": "Une règle d'exclusion s'applique. Une exclusion ne se compense pas par un score."}
    if r["verdict"] == "donnees_insuffisantes":
        return {"titre": "Données insuffisantes", "soutient": [], "retient": [],
                "resume": "Trop de données manquent pour donner un score fiable : " + ", ".join(r.get("colonnes_manquantes") or r.get("donnees_manquantes") or [])}
    soutient = [f"{l['libelle']} — {l['raison']}" for l in r["lignes"] if l["etat"] in ("coherent", "satisfaite")]
    retient = [f"{l['libelle']} — {l['raison']}" for l in r["lignes"] if l["etat"] in ("en_tension", "a_surveiller", "contraire")]
    a_savoir = [f"{l['libelle']} — {l['raison']}" for l in r["lignes"] if l["etat"] == "information"]
    if r["verdict"] == "compatible":
        titre = f"Score {r['score']} sur 100 : au-dessus du seuil de {seuil['compatible']}"
        resume = f"Cohérent avec le profil saisi, pour au plus {A.pct(r['poids_max_pct'], 0)} du portefeuille."
    elif r["verdict"] == "a_examiner":
        titre = f"Score {r['score']} sur 100 : zone « à examiner » ({seuil['a_examiner']} à {seuil['compatible'] - 1})"
        resume = "Des éléments soutiennent la compatibilité, d'autres la retiennent : à regarder avant d'aller plus loin."
    else:
        titre = f"Score {r['score']} sur 100 : sous le seuil de {seuil['a_examiner']}"
        resume = "Moins adapté à ce profil : voici ce qui pose problème, données à l'appui."
    if r.get("borne_appliquee"):
        resume += (f" Le score est borné à {r['score']} parce qu'un critère de risque ou de plafond est "
                   f"« {r['borne_appliquee'].replace('_', ' ')} » : une préférence ne compense pas une tension.")
    return {"titre": titre, "resume": resume, "soutient": soutient, "retient": retient, "a_savoir": a_savoir,
            "donnees_manquantes": r.get("donnees_manquantes", []), "couverture_pct": r.get("couverture_pct")}
