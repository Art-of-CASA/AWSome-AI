"""Écrans des propositions (Streamlit), dans la charte de mvp_profil/design.css. Aucune décision ici.

Quatrième étape du parcours : mini-portefeuille, recherche et fiche d'actif, comparaison, demande d'un titre,
« Et si… ? », « Pourquoi ? ». Tout vient de recommandation/analyse.py ; le profil de la session est LU, jamais modifié.
"""
from __future__ import annotations

import hashlib
import json
from html import escape

import pandas as pd
import streamlit as st

from . import agents, gouvernance
from .analyse import MENTION, Analyse
from .appariement import pct
from .traces import Journal

from criteres import CRITERES  # noqa: E402  (profil, lecture seule)

S = st.session_state
# Repères sobres, lisibles dans un tableau comme dans un texte (pas de couleur seule pour porter le sens).
ICONES = {"exclu": "✕", "compatible": "✓", "a_examiner": "◐", "peu_adapte": "!", "donnees_insuffisantes": "?", "absent": "?",
          "coherent": "✓", "a_surveiller": "◐", "en_tension": "✕", "satisfaite": "✓", "neutre": "–", "contraire": "!",
          "information": "i", "respectee": "✓", "en_conflit": "✕", "a_confirmer": "?", "sans_limite": "–", "sans_objet": "–"}
ETATS = {"coherent": "cohérent", "a_surveiller": "à surveiller", "en_tension": "en tension", "satisfaite": "préférence satisfaite",
         "neutre": "neutre", "contraire": "contraire à une préférence", "information": "information", "exclu": "exclu",
         "respectee": "respectée", "en_conflit": "en conflit", "a_confirmer": "à confirmer", "sans_limite": "sans limite chiffrée",
         "sans_objet": "sans objet"}
EFFETS = {"DURE": "Exclusion", "CALIBRAGE": "Budget de risque", "PLAFOND": "Plafond", "PREFERENCE": "Préférence", "INFORMATION": "Information"}
STYLE = """<style>
.af-reco-verdict { display: inline-flex; align-items: center; gap: 8px; padding: 5px 11px; border-radius: 999px; font-size: 12px; font-weight: 600; border: 1px solid var(--af-border); background: #fff; }
.af-reco-verdict i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.af-reco-ok i { background: var(--af-valide); } .af-reco-attention i { background: var(--af-confirmer); }
.af-reco-non i { background: var(--af-preciser); } .af-reco-neutre i { background: var(--af-analyse); }
.af-reco-phrase { font-family: Georgia, 'Times New Roman', serif; font-size: 19px; line-height: 1.5; margin: 6px 0 14px; color: var(--af-ink); }
.st-key-reco_nav [data-testid="stBaseButton-segmented_control"], .st-key-reco_nav [data-testid="stBaseButton-segmented_controlActive"] { font-size: 13px; padding: 8px 14px; }
.st-key-reco_nav { margin: 6px 0 18px; }
[class*="st-key-reco_carte_"] { background: #fff; border: 1px solid var(--af-border) !important; border-radius: 14px; padding: 20px !important; }
</style>"""
TON = {"compatible": "ok", "coherent": "ok", "a_examiner": "attention", "a_surveiller": "attention", "peu_adapte": "non",
       "en_tension": "non", "exclu": "non", "absent": "neutre", "donnees_insuffisantes": "neutre"}


def _df(lignes, **kw) -> pd.DataFrame:
    """Tableau affichable : une colonne qui mêle textes, nombres et valeurs absentes devient du texte (« — » si absent)."""
    df = pd.DataFrame(lignes, **kw)
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].map(lambda v: "—" if v is None or (isinstance(v, float) and v != v) else str(v))
    return df


def _nom_critere(code: str) -> str:
    """Nom lisible du critère pour les libellés affichés à la personne."""
    return CRITERES.get(code, {}).get("nom", code)


def _etat(code: str) -> str:
    return f"{ICONES.get(code, '')} {ETATS.get(code, code)}".strip()


def pastille(code: str, libelle: str) -> str:
    """Verdict en pastille : la couleur double le texte, elle ne le remplace pas."""
    return f'<span class="af-reco-verdict af-reco-{TON.get(code, "neutre")}"><i></i>{escape(libelle)}</span>'


def titre(sur_titre: str, texte: str, detail: str = ""):
    st.html(f'<div class="af-section-intro"><div class="af-eyebrow"><span></span> {escape(sur_titre)}</div>'
            f'<h2>{escape(texte)}</h2>' + (f'<p>{escape(detail)}</p>' if detail else "") + '</div>')


def journal() -> Journal:
    if "reco_journal" not in S:
        S.reco_journal = Journal()
    return S.reco_journal


def noter(type_: str, **donnees):
    """Une action n'est journalisée qu'une fois : un simple réaffichage de l'écran n'est pas une action."""
    j = journal()
    dernier = next((e for e in reversed(j.evenements) if e["type"] == type_), None)
    if dernier is None or any(dernier.get(k) != v for k, v in donnees.items()):
        j.noter(type_, **donnees)


def modele():
    """Modèle Bedrock si disponible et si la personne ne l'a pas coupé (mode de secours « sans modèle »)."""
    if not S.get("reco_avec_modele", True):
        return None
    if "reco_modele" not in S:
        S.reco_modele = agents.modele_par_defaut()
    return S.reco_modele


def analyse_courante() -> Analyse:
    """Analyse du profil de la session, recalculée seulement si le profil, les critères personnels ou le montant changent."""
    profil, dynamiques = S.profil, list(S.get("dynamiques") or [])
    nom = (S.get("persona") or {}).get("nom") or "Votre profil"
    cle = hashlib.sha256(json.dumps([profil, dynamiques, S.get("reco_montant")], sort_keys=True, default=str,
                                    ensure_ascii=False).encode()).hexdigest()
    if S.get("reco_cle") != cle:
        S.reco_analyse = Analyse(profil, dynamiques, montant=S.get("reco_montant"), nom=nom)
        S.reco_cle = cle
        noter("analyse_calculee", profil=nom, nb_actifs=len(S.reco_analyse.uni), decompte=S.reco_analyse.synthese()["decompte"])
    return S.reco_analyse


def tableau_preuves(preuves: list[dict], intitule: str = "Preuves (colonne, valeur, date, source)"):
    if not preuves:
        return
    with st.expander(f"{intitule} — {len(preuves)}"):
        lignes = []
        for p in preuves:
            if p["type"] == "actif":
                lignes.append({"identifiant": p["id"], "nature": p["nature"], "valeur": p["valeur"] if p["valeur"] is not None else "donnée manquante",
                               "date": p["date"], "source": p["source"], "fichier": p["fichier"], "conditions": p["conditions"]})
            elif p["type"] == "profil":
                lignes.append({"identifiant": p["id"], "nature": p["nature"], "valeur": p["valeur"] or "non renseigné", "date": "",
                               "source": p["source"] or "", "fichier": f"« {p['citation']} »" if p.get("citation") else "", "conditions": ""})
            elif p["type"] == "hypothese":
                lignes.append({"identifiant": p["id"], "nature": p["nature"], "valeur": json.dumps(p["valeur"], ensure_ascii=False),
                               "date": "", "source": p.get("explication") or "", "fichier": p["fichier"], "conditions": ""})
            else:
                lignes.append({"identifiant": p["id"], "nature": p["nature"], "valeur": p["valeur"], "date": p.get("periode") or "",
                               "source": p["methode"], "fichier": "", "conditions": ""})
        st.dataframe(_df(lignes).astype(str), hide_index=True, width="stretch")


def afficher_reponse(rep: dict):
    """Texte d'un agent, avec ses contrôles visibles."""
    st.markdown(rep["texte"])
    f, g = rep["fidelite"], rep["gouvernance"]
    st.caption(f"Rédigé par : {rep['source']}"
               + (f" — motif : {rep['motif_secours']}" if rep.get("motif_secours") else "")
               + f" · Fidélité : {f['nombres_verifies']} chiffre(s) retrouvé(s) dans les sorties d'outils, "
               + ("aucun sans origine" if f["fidele"] else f"sans origine : {', '.join(f['sans_origine'])}")
               + f" · Gouvernance : {'conforme' if g['conforme'] else 'non conforme'}")
    with st.expander(f"Outils appelés ({len(rep['appels'])})"):
        for ap in rep["appels"]:
            st.markdown(f"**{ap['outil']}** — entrée : `{json.dumps(ap['entree'], ensure_ascii=False)}`"
                        + (" · calculé par le code avant la rédaction" if ap.get("par") == "code" else ""))
            st.json(ap["sortie"], expanded=False)


def tableau_criteres(lignes: list[dict]):
    df = _df([{"critère": _nom_critere(l["critere"]), "type": EFFETS[l["effet"]], "état": _etat(l["etat"]), "ce qui est vérifié": l["libelle"],
                        "constat": l["raison"], "poids": l["poids"] or None, "preuves": ", ".join(l["preuves"])} for l in lignes])
    st.dataframe(df, hide_index=True, width="stretch")


# ---------- Écran 1 : mini-portefeuille ----------
def page_portefeuille(a: Analyse):
    s = a.synthese()
    titre("SIMULATION · AUCUN ORDRE", "Votre mini-portefeuille fictif",
          "Construit sous vos plafonds. Le risque se juge sur le portefeuille entier et sur le montant, pas actif par actif.")
    pf = a.portefeuille
    garde = gouvernance.controler_portefeuille(pf)
    if not garde["affichable"]:
        st.error(garde["motif"])
        return
    c = st.columns(4)
    c[0].metric("Perte de stress", pct(pf["perte_stress_pct"]), help="La pire de : perte maximale historique, perte de 2022, choc de taux déclaré.")
    c[1].metric("En dollars", f"{pf['perte_stress_cad']:,.0f} $".replace(",", " "), help=f"Sur un montant fictif de {pf['montant_fictif_cad']:,.0f} $".replace(",", " "))
    c[2].metric("Tension", f"{pf['ratio_tension']:.2f}", help="Perte de stress ÷ budget de perte. Moins de 0,8 : cohérent ; 0,8 à 1 : à surveiller ; plus de 1 : en tension.")
    c[3].metric("État", _etat(pf["etat_tension"]))
    if pf["message_conflit"]:
        st.warning(pf["message_conflit"] + " " + " ; ".join(pf["conflits"]))
    if pf["a_confirmer"]:
        st.info("À confirmer avec la personne : " + " ; ".join(pf["a_confirmer"]) + ".")
    if pf["seuil_entree"] < pf["seuil_entree_demande"]:
        st.info(f"Trop peu d'actifs atteignent {pf['seuil_entree_demande']} : le seuil d'entrée a été abaissé à {pf['seuil_entree']}.")
    st.subheader("Composition")
    df = _df([{"actif": l["ticker"], "nom": l["nom"], "poche": l["poche"], "rôle": l["role"], "poids": l["poids_pct"],
                        "montant ($)": l["montant_cad"], "score": l["score"], "poids max. compatible": l["poids_max_pct"],
                        "pourquoi": l["pourquoi"]} for l in pf["lignes"]])
    g, d = st.columns([3, 2])
    g.dataframe(df, hide_index=True, width="stretch",
                column_config={"poids": st.column_config.ProgressColumn("poids (%)", min_value=0, max_value=40, format="%.1f")})
    d.bar_chart(df.set_index("actif")["poids"], horizontal=True, height=380)
    st.caption(f"Entrée dans le portefeuille : score d'au moins {pf['seuil_entree']} ({pf['nb_candidats']} candidats), "
               f"{pf['hypotheses']['positions maximales']} positions au plus. Hypothèses ajustables : config/hypotheses_recommandation.json.")
    st.subheader("Chaque contrainte, avec sa preuve")
    st.dataframe(_df([{"contrainte": x["contrainte"], "critère": _nom_critere(x["critere"]), "valeur": x["valeur"],
                                "limite": x["limite"] if x["limite"] is not None else "—", "état": _etat(x["etat"]),
                                "détail": x["detail"], "preuves": ", ".join(x["preuves"])} for x in pf["controles"]]).astype(str),
                 hide_index=True, width="stretch")
    tableau_preuves(pf["preuves"])
    g, d = st.columns(2)
    with g:
        st.subheader("Mesures (faits passés)")
        m = pf["mesures"]
        st.dataframe(_df([
            ("Volatilité annualisée", pct(m["volatilite_pct"])), ("Perte maximale", pct(m["perte_max_pct"])),
            ("Du sommet au creux", f"{m['date_sommet']} → {m['date_creux']}"),
            ("Jours sous l'eau", f"{m['jours_sous_eau']}" + ("" if m["recupere"] else " (non récupéré)")),
            ("Rendement de 2022", pct(m["rendement_2022_pct"])), ("Pire mois", pct(m["pire_mois_pct"])),
            ("Période", m["periode"])], columns=["mesure", "valeur"]), hide_index=True, width="stretch")
        st.caption("Fait : calculé sur les prix en CAD, portefeuille rééquilibré chaque jour (hypothèse de calcul).")
    with d:
        st.subheader("Stress : faits et scénario fictif")
        st_ = pf["stress"]
        st.dataframe(_df([
            ("Fait", "Perte maximale historique", pct(st_["composantes_pct"]["perte_max_historique"])),
            ("Fait", "Perte de l'année 2022", pct(st_["composantes_pct"]["annee_2022"])),
            ("Hypothèse", f"Choc de taux de +{st_['choc_taux_points']:g} points (FNB obligataires)", pct(st_["composantes_pct"]["choc_taux"])),
            ("Scénario fictif", "Krach des actions (non retenu dans la tension)", pct(st_["scenario_fictif_krach_pct"]))],
            columns=["nature", "élément", "perte"]), hide_index=True, width="stretch")
        st.caption("La fenêtre 2021-2026 ne contient qu'une crise (2022) : la perte historique sous-estime le risque d'un portefeuille "
                   "riche en actions. Le scénario fictif le rappelle.")
    with st.expander("Expositions à travers les FNB"):
        e = pf["expositions"]
        g, d = st.columns(2)
        g.dataframe(_df(list(e["secteurs_pct"].items()), columns=["secteur", "exposition (%)"]), hide_index=True, width="stretch")
        d.dataframe(_df(list(e["titres_pct"].items())[:12], columns=["titre (direct + via FNB)", "exposition (%)"]), hide_index=True, width="stretch")
        st.caption(e["limite"])
    with st.expander("Ce que l'outil ne sait pas sur ce profil"):
        for b in gouvernance.bilan(a, pf):
            st.markdown(f"- **{b['controle']}** : {b['detail']}")
        if s["inconnus"]:
            st.dataframe(_df([{**x, "critere": _nom_critere(x["critere"])} for x in s["inconnus"]]).rename(columns={"critere": "critère", "etat": "état"}), hide_index=True, width="stretch")
    st.subheader("Résumé du Conseiller")
    if st.button("Rédiger le résumé", key="btn_resume"):
        with st.spinner("Le Conseiller appelle ses outils…"):
            S.reco_resume = agents.dialoguer("conseiller", "Présente ce mini-portefeuille fictif : ce qu'il respecte, ce qui limite, "
                                             "et ce qu'il faudrait confirmer avec la personne.", a, journal(), modele())
            S.reco_resume_cle = S.reco_cle
    if S.get("reco_resume") and S.get("reco_resume_cle") == S.reco_cle:
        afficher_reponse(S.reco_resume)


# ---------- Écran 2 : recherche et fiche d'actif ----------
def page_recherche(a: Analyse):
    s = a.synthese()
    titre("UN ACTIF, UN VERDICT", "Chercher un actif", "Un score, un seuil, et ce qui l'explique pour votre profil.")
    st.caption(f"Seuils (hypothèses ajustables) : {a.hyp['bandes_score']['compatible']} et plus « compatible » ; "
               f"{a.hyp['bandes_score']['a_examiner']} à {a.hyp['bandes_score']['compatible'] - 1} « à examiner » ; en dessous « peu adapté ». "
               "Une exclusion donne « exclu », quel que soit le score.")
    texte = st.text_input("Ticker ou nom", key="reco_requete", placeholder="NVDA, Shopify, XBB, bitcoin…")
    if not texte:
        d = s["decompte"]
        st.markdown(f"Pour ce profil : **{d['compatible']}** compatibles, **{d['a_examiner']}** à examiner, **{d['peu_adapte']}** peu adaptés, "
                    f"**{d['exclu']}** exclus, **{d['donnees_insuffisantes']}** sans données suffisantes.")
        filtre = st.selectbox("Voir", ["compatible", "a_examiner", "peu_adapte", "exclu"], format_func=lambda v: f"{ICONES[v]} {v.replace('_', ' ')}")
        st.dataframe(_df([{"actif": r["ticker"], "nom": r["nom"], "verdict": r["libelle_verdict"], "score": r["score"],
                                    "poids max. (%)": r["poids_max_pct"], "critère décisif": r["critere_decisif"]}
                                   for r in a.classement(filtre, n=len(a.uni))]), hide_index=True, width="stretch")
        return
    f = a.rechercher(texte)
    noter("recherche", requete=texte, ticker=f.get("ticker"), verdict=f["verdict"], score=f.get("score"))
    if f["verdict"] == "absent":
        st.warning(f["message"])
        if f["suggestions"]:
            st.markdown("Actifs proches dans l'univers : " + ", ".join(f"**{x['ticker']}** ({x['nom']})" for x in f["suggestions"]))
        return
    st.subheader(f"{f['ticker']} — {f['nom']}")
    st.html(pastille(f["verdict"], f["libelle_verdict"]))
    e = f["explication"]
    c = st.columns(4)
    c[0].metric("Verdict", f"{ICONES[f['verdict']]} {f['libelle_verdict']}")
    c[1].metric("Score", "—" if f["score"] is None else f"{f['score']} / 100")
    c[2].metric("Poids max. compatible", pct(f.get("poids_max_pct"), 0))
    c[3].metric("Critères évalués", "—" if f.get("couverture_pct") is None else pct(f["couverture_pct"], 0))
    st.markdown(f"**{e['titre']}.** {e['resume']}")
    g, d = st.columns(2)
    with g:
        st.markdown("**Ce qui soutient la compatibilité**")
        for x in e.get("soutient") or ["Rien à ce stade."]:
            st.markdown(f"- {x}")
    with d:
        st.markdown("**Ce qui pose problème ou retient**")
        for x in e.get("retient") or ["Rien à signaler."]:
            st.markdown(f"- {x}")
    for x in e.get("a_savoir") or []:
        st.caption("À savoir : " + x)
    if e.get("donnees_manquantes"):
        st.info("Données manquantes pour cet actif (non remplacées) : " + ", ".join(e["donnees_manquantes"]))
    st.subheader("Fiche de l'actif")
    if f.get("lignes"):
        tableau_criteres(f["lignes"])
    faits = f["faits"]
    st.dataframe(_df([(k.replace("_", " "), "donnée manquante" if v is None else v) for k, v in faits.items()],
                              columns=["fait (donnée datée)", "valeur"]), hide_index=True, width="stretch")
    tableau_preuves(f.get("preuves", []))
    if st.button("Demander à l'Explicateur", key="btn_expl"):
        with st.spinner("L'Explicateur relit le verdict et ses preuves…"):
            S.reco_expl = (f["ticker"], S.reco_cle, agents.dialoguer(
                "explicateur", f"Explique le verdict de {f['ticker']} pour ce profil : pourquoi c'est adapté ou moins adapté, avec les preuves.",
                a, journal(), modele()))
    if S.get("reco_expl") and S.reco_expl[:2] == (f["ticker"], S.reco_cle):
        afficher_reponse(S.reco_expl[2])


# ---------- Écran 3 : comparaison ----------
def page_comparaison(a: Analyse):
    titre("CRITÈRE PAR CRITÈRE", "Comparer deux actifs", "L'écart décisif est le premier critère qui les sépare pour votre profil.")
    tickers = a.uni.tickers()
    libelle = lambda t: f"{t} — {a.uni[t]['name']}"  # noqa: E731
    g, d = st.columns(2)
    ta = g.selectbox("Premier actif", tickers, format_func=libelle, index=tickers.index("NVDA") if "NVDA" in tickers else 0, key="reco_cmp_a")
    tb = d.selectbox("Second actif", tickers, format_func=libelle, index=tickers.index("XBB.TO") if "XBB.TO" in tickers else min(1, len(tickers) - 1), key="reco_cmp_b")
    c = a.comparer(ta, tb)
    noter("comparaison", a=ta, b=tb, ecart=c["ecart_decisif"].get("critere"))
    for col, r in ((g, c["a"]), (d, c["b"])):
        col.metric(r["ticker"], f"{ICONES[r['verdict']]} {r['libelle_verdict']}", None if r["score"] is None else f"score {r['score']}", delta_color="off")
    e = c["ecart_decisif"]
    if e.get("critere"):
        st.success(f"**Écart décisif : {e['libelle']} ({EFFETS[e['effet']].lower()})**, en faveur de **{e['en_faveur_de']}**.\n\n{e['raison']}")
    else:
        st.info(e["raison"])
    st.caption(c["regle"])
    st.dataframe(_df([{"critère": x["critere"], "type": EFFETS[x["effet"]], "vérifié": x["libelle"],
                                ta: _etat(x["etat_a"]), tb: _etat(x["etat_b"]), "diffère": "●" if x["different"] else "",
                                f"constat {ta}": x["raison_a"], f"constat {tb}": x["raison_b"]} for x in c["tableau"]]),
                 hide_index=True, width="stretch")
    st.dataframe(_df([{"fait (donnée datée)": k.replace("_", " "), ta: c["faits_a"][k], tb: c["faits_b"][k]} for k in c["faits_a"]]).astype(str),
                 hide_index=True, width="stretch")
    tableau_preuves(c["preuves"])


# ---------- Écran 4 : demande d'un titre (cas Robert) ----------
def page_demande(a: Analyse):
    titre("UNE ENVIE PRÉCISE ?", "Demander l'ajout d'un titre", "L'outil répond oui, oui mais, ou non — avec ses raisons.")
    st.caption("Le verdict est calculé et figé **avant** que la justification soit lue. La justification ne peut pas le changer : "
               "seule une réponse du profil le peut (écran « Et si… ? »).")
    tickers = a.uni.tickers()
    with st.form("form_demande"):
        g, d = st.columns([2, 1])
        tk = g.selectbox("Titre", tickers, format_func=lambda t: f"{t} — {a.uni[t]['name']}", index=tickers.index("NVDA") if "NVDA" in tickers else 0)
        part = d.slider("Part du portefeuille demandée (%)", 1, 50, 20)
        justification = st.text_area("Pourquoi ce titre ? (facultatif, lu après le verdict)", placeholder="Tout le monde en parle…")
        envoye = st.form_submit_button("Évaluer la demande")
    if envoye:
        with st.spinner("Verdict figé, puis explication…"):
            S.reco_demande = (S.reco_cle, agents.traiter_demande(a, tk, part, justification, journal(), modele()))
    if not S.get("reco_demande") or S.reco_demande[0] != S.reco_cle:
        return
    r = S.reco_demande[1]
    v, inc = r["verdict"], r["incoherence"]
    couleur = {"en_tension": st.error, "exclu": st.error, "a_surveiller": st.warning, "coherent": st.success}.get(v["verdict"], st.info)
    couleur(f"**{ICONES.get(v['verdict'], '')} {v['libelle_verdict']}** — {v['ticker']} pour {pct(v['part_demandee_pct'], 0)} du portefeuille "
            f"({v['montant_demande_cad']:,.0f} $).".replace(",", " "))
    st.caption(f"Verdict figé le {v['fige_le']} · empreinte {v['empreinte']} · revérifié après la rédaction : "
               f"{'inchangé' if r['verdict_inchange'] else 'MODIFIÉ (anomalie)'}")
    if v.get("perte_stress_apres_pct") is not None:
        c = st.columns(4)
        c[0].metric("Perte de stress avant", pct(v["perte_stress_avant_pct"]))
        c[1].metric("Après l'ajout", pct(v["perte_stress_apres_pct"]), f"{v['perte_stress_apres_pct'] - v['perte_stress_avant_pct']:+.1f} pt", delta_color="inverse")
        c[2].metric("Budget de perte", pct(v["budget_perte_pct"], 0))
        c[3].metric("Part maximale compatible", pct(v["part_max_compatible_pct"], 0))
    st.subheader("Pourquoi")
    for x in v["raisons"]:
        st.markdown(f"- {ICONES.get(x['etat'], '')} **{x['critere']}** — {x['texte']}")
    if inc["tensions"]:
        st.subheader("Demande et profil : ce qui ne va pas ensemble")
        st.markdown("Incohérence relevée par le code." if inc["incoherent"] else "Points d'attention, sans incohérence franche.")
        for p in inc["pistes"]:
            st.markdown(f"- {p}")
    st.subheader("Réponse de l'Explicateur")
    afficher_reponse(r["reponse"])
    tableau_preuves(v.get("preuves", []))
    st.caption("Ordre des actions enregistrées : " + " → ".join(r["ordre"]))


# ---------- Écran 5 : « Et si… ? » ----------
MODIFIABLES = ("A2", "A4", "A5", "B1", "B5", "B6", "B7", "D2", "D9", "D12", "D7", "E1", "E2", "E4", "G3", "D4", "C1")


def page_et_si(a: Analyse):
    titre("REPRENDRE UNE RÉPONSE", "Et si… ?", "Changez une réponse : tout est recalculé, et chaque changement est expliqué.")
    st.caption("Scénario fictif : la réponse est modifiée dans une copie, tout est recalculé, et le profil enregistré ne change pas.")
    import synthese
    g, d = st.columns(2)
    cid = g.selectbox("Réponse à modifier", MODIFIABLES, format_func=lambda c: CRITERES[c]["nom"], key="reco_si_cid")
    actuelle = (a.profil.get(cid) or {}).get("valeurs") or []
    valeur = d.selectbox("Nouvelle valeur", CRITERES[cid]["valeurs"], format_func=lambda v: synthese.libelle_valeur(cid, v), key=f"reco_si_val_{cid}")
    st.markdown("Réponse actuelle : " + (", ".join(f"**{synthese.libelle_valeur(cid, v)}**" for v in actuelle) or "**non renseignée**"))
    r = a.et_si(cid, valeur)
    noter("et_si", critere=cid, valeur=valeur, nb_changements=r.get("nb_changements_de_bande"))
    if "erreur" in r:
        st.error(r["erreur"])
    elif r["aucun_changement"]:
        st.info("Rien ne change : cette réponse ne limite pas le résultat actuel. Une autre contrainte reste la plus prudente.")
    else:
        if r["contraintes"]:
            st.subheader("Ce qui change dans les contraintes")
            st.dataframe(_df(r["contraintes"]).astype(str).rename(columns={"element": "élément", "apres": "après"}), hide_index=True, width="stretch")
        av, ap = r["portefeuille_avant"], r["portefeuille_apres"]
        if av and ap:
            c = st.columns(4)
            c[0].metric("Perte de stress", pct(ap["perte_stress_pct"]), f"{ap['perte_stress_pct'] - av['perte_stress_pct']:+.1f} pt", delta_color="off")
            c[1].metric("Part de croissance", pct(ap["part_croissance_pct"]), f"{ap['part_croissance_pct'] - av['part_croissance_pct']:+.1f} pt", delta_color="off")
            c[2].metric("Volatilité", pct(ap["volatilite_pct"]), f"{ap['volatilite_pct'] - av['volatilite_pct']:+.1f} pt", delta_color="off")
            c[3].metric("Actifs qui changent de verdict", r["nb_changements_de_bande"])
        if r["actifs_modifies"]:
            st.subheader("Actifs dont le verdict, le score ou le poids maximal change")
            st.dataframe(_df([{"actif": x["ticker"], "avant": f"{x['verdict_avant']} ({x['score_avant']})",
                                        "après": f"{x['verdict_apres']} ({x['score_apres']})",
                                        "poids max. avant": x["poids_max_avant_pct"], "poids max. après": x["poids_max_apres_pct"],
                                        "règle en cause": ", ".join(x["regles_en_cause"]), "pourquoi": x["raison"]}
                                       for x in sorted(r["actifs_modifies"], key=lambda x: (not x["change_de_bande"], x["ticker"]))]),
                         hide_index=True, width="stretch")
        if r["poids_modifies"]:
            st.subheader("Poids du mini-portefeuille")
            st.dataframe(_df(r["poids_modifies"]).rename(columns={"avant_pct": "avant (%)", "apres_pct": "après (%)", "ecart_points": "écart (points)"}),
                         hide_index=True, width="stretch")
    st.divider()
    st.subheader("Mise à l'épreuve des hypothèses")
    st.caption("Une hypothèse change à la fois : horizon d'un cran, seuils du score, seuil de tension, période sans 2022.")
    if st.button("Lancer le test de sensibilité", key="btn_sens") or (S.get("reco_sens") and S.reco_sens[0] == S.reco_cle):
        if not S.get("reco_sens") or S.reco_sens[0] != S.reco_cle:
            S.reco_sens = (S.reco_cle, a.sensibilite())
            journal().noter("sensibilite", essais=len(S.reco_sens[1]["essais"]))
        sens = S.reco_sens[1]
        st.dataframe(_df([{"axe": x["axe"], "essai": x["essai"], "actifs qui changent de verdict": x["nb_changements_de_bande"],
                                    "perte de stress (%)": (x["portefeuille"] or {}).get("perte_stress_pct"),
                                    "tension": (x["portefeuille"] or {}).get("ratio_tension"),
                                    "part de croissance (%)": (x["portefeuille"] or {}).get("part_croissance_pct")} for x in sens["essais"]]),
                     hide_index=True, width="stretch")
        ref = sens["reference"]["portefeuille"]
        if ref:
            st.caption(f"Référence : perte de stress {pct(ref['perte_stress_pct'])}, tension {ref['ratio_tension']:.2f}. "
                       f"Scénario fictif de krach : {pct(sens['reference']['scenario_fictif_krach_pct'])}. {sens['limites']}")


# ---------- Écran 6 : « Pourquoi ? » ----------
def page_pourquoi(a: Analyse):
    s = a.synthese()
    titre("TRAÇABLE, PAS MAGIQUE", "Pourquoi ? Ce qui soutient les résultats", "")
    st.markdown("Les résultats sont **traçables** : chaque conclusion renvoie à une donnée datée, à une réponse du profil ou à une "
                "hypothèse écrite. L'écran montre les **actions observables** (outils appelés, données lues), pas un raisonnement interne de modèle.")
    onglets = st.tabs(["Du profil aux contraintes", "Poser une question", "Hypothèses", "Contrôles", "Journal des actions"])
    with onglets[0]:
        st.markdown(f"**{s['phrase']}** Limité par : {', '.join(s['limite_par'])}.")
        st.markdown("**Exclusions dures** (ne se compensent jamais)")
        st.dataframe(_df(s["exclusions"] or [{"critere": "—", "libelle": "aucune", "origine": ""}]).rename(columns={"critere": "critère", "libelle": "règle"}),
                     hide_index=True, width="stretch")
        p = s["plafonds"]
        st.markdown("**Plafonds**")
        st.dataframe(_df([("Par titre individuel", p["titre_pct"]), ("Cryptoactifs", p["crypto_pct"]),
                                   ("Placements spéculatifs", "aucun plafond" if p["speculatif_pct"] is None else p["speculatif_pct"]),
                                   ("Par secteur (hypothèse)", p["secteur_pct"]),
                                   (f"Secteur de l'emploi : {', '.join(p['secteur_emploi']['secteurs']) or 'sans objet'}", p["secteur_emploi"]["pct"] if p["secteur_emploi"]["secteurs"] else "—"),
                                   ("Exposition au change", "non renseigné" if p["hors_cad_pct"] is None else p["hors_cad_pct"]),
                                   ("Par fonds (hypothèse)", p["fonds_pct"]), ("Complexité maximale", p["complexite_max"])] +
                                  [(g["libelle"], g["plafond_pct"]) for g in s["plafonds_groupes"]], columns=["plafond", "% ou niveau"]).astype(str),
                     hide_index=True, width="stretch")
        st.markdown("**Préférences pondérées** (ne compensent jamais une tension)")
        st.dataframe(_df(s["preferences"]).rename(columns={"critere": "critère", "libelle": "préférence", "poids": "multiplicateur"}), hide_index=True, width="stretch")
        if s["reglages_prudents"]:
            st.markdown("**Réglages prudents appliqués faute de réponse** (signalés, jamais présentés comme une réponse)")
            st.dataframe(_df(s["reglages_prudents"])[["critere", "nom", "libelle"]].rename(columns={"critere": "critère", "libelle": "réglage"}), hide_index=True, width="stretch")
        for x in s["sans_effet"]:
            st.caption(f"Filtre sans effet — {x['critere']} = {x['valeur']} : {x['raison']}")
        for x in s["notes_dynamiques"]:
            st.caption(f"Critère personnel non appliqué — {x['libelle']} : {x['raison']}")
    with onglets[1]:
        role = st.radio("Agent", ["explicateur", "conseiller"], horizontal=True,
                        format_func=lambda r: {"explicateur": "Explicateur (un actif, une comparaison, un « pourquoi »)",
                                               "conseiller": "Conseiller (portefeuille, « et si », sensibilité)"}[r])
        q = st.text_input("Votre question", placeholder="Pourquoi Tesla est-elle moins adaptée que Fortis ?", key="reco_q")
        if st.button("Envoyer", key="btn_q") and q.strip():
            with st.spinner("L'agent appelle ses outils…"):
                S.reco_qr = (S.reco_cle, agents.dialoguer(role, q.strip(), a, journal(), modele()))
        if S.get("reco_qr") and S.reco_qr[0] == S.reco_cle:
            afficher_reponse(S.reco_qr[1])
    with onglets[2]:
        st.markdown("Tous les seuils sont des **hypothèses d'équipe**, écrites et ajustables. Aucun n'est une norme publiée.")
        h = a.hyp
        st.dataframe(_df([(k, json.dumps(v, ensure_ascii=False), h.get("_" + k, "")) for k, v in h.items() if not k.startswith("_")],
                                  columns=["hypothèse", "valeur", "explication"]), hide_index=True, width="stretch")
        st.caption("Fichiers : config/hypotheses_recommandation.json, mvp_profil/hypotheses_profil.json, config/seuils_criteres.json.")
    with onglets[3]:
        for b in gouvernance.bilan(a, a.portefeuille):
            st.markdown(f"{'✓' if b['resultat'] == 'ok' else 'i' if b['resultat'] == 'info' else '!'} **{b['controle']}** — {b['detail']}")
        st.caption("Sources : prix, fondamentaux et fiches de fonds de Yahoo Finance (yfinance), sous leurs conditions d'utilisation ; change de la "
                   "Banque du Canada ; pages vues de Wikimedia ; controverses recherchées à la main, liste non exhaustive. "
                   "Traitement dans la région AWS us-east-1.")
    with onglets[4]:
        j = journal()
        st.caption(f"Session {j.session} · stockage : {j.stockage()} · {len(j.evenements)} action(s)")
        if j.evenements:
            st.dataframe(_df([{"rang": e["rang"], "horodatage (UTC)": e["horodatage"], "action": e["type"],
                                        "détail": json.dumps({k: v for k, v in e.items() if k not in ("session", "rang", "horodatage", "type")},
                                                             ensure_ascii=False, default=str)[:300]} for e in j.evenements]),
                         hide_index=True, width="stretch")
    st.caption(MENTION)



ECRANS = {"Mini-portefeuille": page_portefeuille, "Recherche d'actif": page_recherche, "Comparaison": page_comparaison,
          "Demande d'un titre": page_demande, "Et si… ?": page_et_si, "Pourquoi ?": page_pourquoi}


def afficher(retour=None):
    """Point d'entrée appelé par app.py quand S.phase == « recommandation ». retour : fonction qui ramène à la synthèse."""
    st.html(STYLE)
    if not S.get("profil"):
        st.info("Les propositions s'appuient sur un profil terminé. Revenez à l'accueil pour créer un profil ou charger un exemple.")
        return
    tete, action = st.columns([4, 1], vertical_alignment="bottom")
    with tete:
        titre("ÉTAPE 04 · VOS PROPOSITIONS", "Ce qui est cohérent avec votre profil, et pourquoi",
              "Un mini-portefeuille fictif, le verdict de chaque actif et les preuves qui les soutiennent. "
              "Tout est calculé par des règles écrites ; les agents expliquent, ils ne décident pas.")
    if retour is not None and action.button("← Revenir à ma synthèse", width="stretch", key="reco_retour"):
        retour()
    a = analyse_courante()
    s = a.synthese()
    if S.get("persona"):
        st.caption(f"Profil fictif de démonstration : {S.persona['nom']}. {S.persona['description']}")
    st.html(f'<p class="af-reco-phrase">{escape(s["phrase"])}</p>')
    c = st.columns(4)
    c[0].metric("Niveau de risque", f"{s['niveau']} sur 5")
    c[1].metric("Budget de perte", pct(s["budget_perte_pct"], 0), help="Le plus prudent de votre capacité, de votre tolérance déclarée et de votre tolérance observée.")
    c[2].metric("Actifs compatibles", f"{s['decompte']['compatible']} sur {s['nb_actifs']}", help=f"Données au {s['date_donnees']}.")
    c[3].metric("Actifs exclus", s["decompte"]["exclu"], help="Une exclusion ne se compense jamais par un bon score.")
    with st.expander("Réglages de la simulation"):
        g, d = st.columns(2)
        S.reco_montant = g.number_input("Montant fictif ($ CA)", min_value=500, max_value=5_000_000, step=500, value=int(a.montant),
                                        help="Sert à exprimer la tension en dollars. Aucun argent réel.")
        S.reco_avec_modele = d.toggle("Rédaction des explications par le modèle", value=S.get("reco_avec_modele", True),
                                      help="Coupé : les textes viennent des gabarits du code. Verdicts et chiffres sont identiques.")
        if int(S.reco_montant) != int(a.montant):
            st.rerun()
    with st.container(key="reco_nav"):
        ecran = st.segmented_control("Écran", list(ECRANS), default=list(ECRANS)[0], key="reco_ecran", label_visibility="collapsed")
    ECRANS[ecran or list(ECRANS)[0]](a)
