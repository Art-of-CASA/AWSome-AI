"""Écrans des propositions (Streamlit), dans la charte de mvp_profil/design.css. Aucune décision ici.

Quatrième étape du parcours : mon portefeuille, parler au conseiller, chercher un actif, comparer, « Et si… ? », comprendre.
Tout vient de recommandation/analyse.py et recommandation/conversation.py. Le profil de la session est LU, jamais
modifié : les réponses que la personne met à jour pendant la conversation sont gardées à part et s'annulent d'un clic.

Affichage sobre par défaut : phrases en clair, pas d'identifiant ni de journal. « Détails techniques » (réglages) montre,
pour qui veut vérifier, les outils appelés, les contrôles de chaque texte et le journal des actions.
"""
from __future__ import annotations

import hashlib
import json
from html import escape

import pandas as pd
import streamlit as st

from . import agents, conversation as K, gouvernance
from .analyse import MENTION, SECTEURS_FR, Analyse
from .appariement import pct
from .traces import Journal

from criteres import CRITERES  # noqa: E402  (profil, lecture seule)

S = st.session_state
ETATS = {"coherent": "cohérent", "a_surveiller": "à surveiller", "en_tension": "en tension", "satisfaite": "correspond à vos préférences",
         "neutre": "neutre", "contraire": "à l'opposé d'une préférence", "information": "à savoir", "exclu": "exclu",
         "respectee": "respectée", "en_conflit": "dépassée", "a_confirmer": "à confirmer", "sans_limite": "sans limite chiffrée",
         "sans_objet": "sans objet", "compatible": "compatible", "a_examiner": "à examiner", "peu_adapte": "peu adapté",
         "donnees_insuffisantes": "données insuffisantes", "absent": "absent de l'univers"}
TON = {"compatible": "ok", "coherent": "ok", "respectee": "ok", "satisfaite": "ok", "a_examiner": "attention", "a_surveiller": "attention",
       "a_confirmer": "attention", "contraire": "attention", "peu_adapte": "non", "en_tension": "non", "exclu": "non", "en_conflit": "non"}
EFFETS = {"DURE": "Exclusion", "CALIBRAGE": "Risque", "PLAFOND": "Limite", "PREFERENCE": "Préférence", "INFORMATION": "À savoir"}
POCHES = {"croissance": "Croissance", "amortisseur": "Stabilité"}
VERTS = ["#1c4b3c", "#28624f", "#3f7d5c", "#557b47", "#6f9460", "#8bab7a", "#a6bf96", "#bfd1b1", "#d3e0c8", "#e2ead9"]
OCRES = ["#b07a22", "#c99a45", "#dcb96f", "#e9d29c"]
DEMANDE, ENCAISSE = "#b4553f", "#d5d9cf"
STYLE = """<style>
.af-pill { display: inline-flex; align-items: center; gap: 7px; padding: 4px 11px; border-radius: 999px; font-size: 11.5px; font-weight: 600; border: 1px solid var(--af-border); background: #fff; color: var(--af-ink); white-space: nowrap; }
.af-pill i { width: 7px; height: 7px; border-radius: 50%; display: inline-block; background: var(--af-analyse); }
.af-pill.ok i { background: var(--af-valide); } .af-pill.attention i { background: var(--af-confirmer); } .af-pill.non i { background: var(--af-preciser); }
.af-lede { font-family: Georgia, 'Times New Roman', serif; font-size: 19px; line-height: 1.5; margin: 4px 0 16px; color: var(--af-ink); }
.af-note { color: var(--af-muted); font-size: 12.5px; line-height: 1.7; margin: 6px 0 14px; }
.st-key-reco_nav { margin: 8px 0 20px; }
.af-table { width: 100%; border-collapse: separate; border-spacing: 0; background: #fff; border: 1px solid var(--af-border); border-radius: 14px; overflow: hidden; font-size: 13px; margin: 6px 0 14px; }
.af-table th { text-align: left; font-size: 9.5px; letter-spacing: 1.2px; text-transform: uppercase; font-weight: 650; color: #6f806f; padding: 12px 16px; background: #f3f6ee; border-bottom: 1px solid var(--af-border); }
.af-table td { padding: 12px 16px; border-bottom: 1px solid #edf1e8; vertical-align: top; line-height: 1.55; color: var(--af-ink); }
.af-table tr:last-child td { border-bottom: 0; }
.af-table td.n, .af-table th.n { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.af-table td small { display: block; color: var(--af-muted); font-size: 11.5px; margin-top: 2px; }
.af-table td b { font-weight: 600; }
.af-pos { display: grid; grid-template-columns: 12px 1fr 86px 58px; align-items: center; gap: 12px; padding: 10px 2px; border-bottom: 1px solid #edf1e8; }
.af-pos:last-child { border-bottom: 0; }
.af-pos .dot { width: 11px; height: 11px; border-radius: 3px; }
.af-pos .nom b { font-size: 13px; font-weight: 600; } .af-pos .nom small { display: block; font-size: 11px; color: var(--af-muted); margin-top: 1px; }
.af-pos .bar { height: 6px; background: #edf1e8; border-radius: 4px; overflow: hidden; } .af-pos .bar span { display: block; height: 100%; border-radius: 4px; }
.af-pos .pct { text-align: right; font-family: Georgia, serif; font-size: 16px; }
.af-card { background: #fff; border: 1px solid var(--af-border); border-radius: 14px; padding: 18px 20px; margin: 6px 0 14px; }
.af-card h4 { margin: 0 0 8px; font-size: 14px; font-weight: 650; letter-spacing: -.2px; }
.af-card ul { margin: 0; padding-left: 18px; } .af-card li { font-size: 13px; line-height: 1.6; margin-bottom: 4px; }
.af-check { display: grid; grid-template-columns: 22px 1fr auto; gap: 10px; align-items: baseline; padding: 9px 2px; border-bottom: 1px solid #edf1e8; font-size: 13px; }
.af-check:last-child { border-bottom: 0; } .af-check small { color: var(--af-muted); display: block; font-size: 11.5px; }
.af-check .v { font-variant-numeric: tabular-nums; white-space: nowrap; color: var(--af-muted); font-size: 12.5px; }
.af-mark { display: inline-grid; place-items: center; width: 18px; height: 18px; border-radius: 50%; font-size: 10px; font-weight: 700; color: #fff; background: var(--af-analyse); }
.af-mark.ok { background: var(--af-valide); } .af-mark.attention { background: var(--af-confirmer); } .af-mark.non { background: var(--af-preciser); }
.af-score { font-family: Georgia, serif; font-size: 44px; line-height: 1; } .af-score small { font-family: system-ui, sans-serif; font-size: 13px; color: var(--af-muted); }
.af-chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 0 12px; }
.af-chip { padding: 5px 11px; border-radius: 999px; background: #edf2e8; color: #33543f; font-size: 11.5px; font-weight: 600; }
.af-chip.demande { background: #f6e6e1; color: #8a3d2c; }
.st-key-reco_chat [data-testid="stChatMessage"] { padding: 14px 16px; margin-bottom: 8px; }
.st-key-reco_chat [data-testid="stChatMessage"] p { font-size: 14px; line-height: 1.65; }
.st-key-reco_attente { background: #fff; border: 1px solid var(--af-border) !important; border-left: 4px solid var(--af-confirmer) !important; border-radius: 12px; padding: 14px 16px !important; }
</style>"""


class Html(str):
    """Cellule de tableau déjà en HTML (pastille) ; tout le reste est échappé."""


def pastille(code: str, libelle: str | None = None) -> Html:
    return Html(f'<span class="af-pill {TON.get(code, "")}"><i></i>{escape(libelle or ETATS.get(code, code))}</span>')


def marque(code: str) -> str:
    ton = TON.get(code, "")
    return f'<span class="af-mark {ton}">{"✓" if ton == "ok" else "!" if ton == "attention" else "✕" if ton == "non" else "i"}</span>'


def _cellule(x) -> str:
    if isinstance(x, Html):
        return x
    if isinstance(x, tuple):   # (principal, détail)
        return f"<b>{escape(str(x[0]))}</b><small>{escape(str(x[1]))}</small>"
    return "—" if x is None or x == "" else escape(str(x))


def tableau(colonnes: list[str], lignes: list[list], nombres: tuple[int, ...] = ()):
    """Tableau dans la charte du site (pas de grille technique). nombres : indices des colonnes alignées à droite."""
    cls = lambda i: ' class="n"' if i in nombres else ""  # noqa: E731
    corps = "".join("<tr>" + "".join(f"<td{cls(i)}>{_cellule(c)}</td>" for i, c in enumerate(l)) + "</tr>" for l in lignes)
    st.html('<table class="af-table"><thead><tr>' + "".join(f"<th{cls(i)}>{escape(c)}</th>" for i, c in enumerate(colonnes))
            + f"</tr></thead><tbody>{corps}</tbody></table>")


def titre(sur_titre: str, texte: str, detail: str = ""):
    st.html(f'<div class="af-section-intro"><div class="af-eyebrow"><span></span> {escape(sur_titre)}</div>'
            f'<h2>{escape(texte)}</h2>' + (f'<p>{escape(detail)}</p>' if detail else "") + '</div>')


def carte(titre_: str, lignes: list[str], vide: str = "Rien à signaler."):
    st.html(f'<div class="af-card"><h4>{escape(titre_)}</h4><ul>' + "".join(f"<li>{escape(x)}</li>" for x in (lignes or [vide])) + "</ul></div>")


def dollars(x: float) -> str:
    return f"{x:,.0f} $".replace(",", " ")


def technique() -> bool:
    return bool(S.get("reco_technique", False))


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


def etat_conversation() -> dict:
    if "reco_conv" not in S or S.get("reco_conv_profil") != _empreinte(S.profil):
        S.reco_conv = K.etat_initial()             # nouveau profil : nouvelle conversation, aucun ajout repris
        S.reco_conv_profil = _empreinte(S.profil)
    return S.reco_conv


def _empreinte(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def contexte() -> K.Contexte:
    nom = (S.get("persona") or {}).get("nom") or "Votre profil"
    return K.Contexte(S.profil, list(S.get("dynamiques") or []), etat_conversation(), S.get("reco_montant"), nom, journal())


def analyse_courante() -> Analyse:
    """Analyse du profil de la session (avec les mises à jour confirmées et les ajouts), recalculée seulement s'ils changent."""
    etat = etat_conversation()
    cle = _empreinte([S.profil, list(S.get("dynamiques") or []), S.get("reco_montant"), etat["maj"], etat["ajouts"]])
    if S.get("reco_cle") != cle:
        S.reco_analyse = contexte().analyse
        S.reco_cle = cle
        noter("analyse_calculee", nb_actifs=len(S.reco_analyse.uni), decompte=S.reco_analyse.synthese()["decompte"],
              ajouts=dict(etat["ajouts"]), reponses_mises_a_jour=sorted(etat["maj"]))
    return S.reco_analyse


def afficher_reponse(rep: dict):
    """Texte d'un agent. Les contrôles et les outils ne s'affichent qu'en « détails techniques »."""
    st.markdown(rep["texte"])
    if not technique():
        return
    f, g = rep["fidelite"], rep["gouvernance"]
    st.caption(f"Réponse produite par : {rep['source']}" + (f" — {rep['motif_secours']}" if rep.get("motif_secours") else "")
               + f" · {f['nombres_verifies']} chiffre(s) retrouvé(s) dans les sorties d'outils"
               + ("" if f["fidele"] else f" ; sans origine : {', '.join(f['sans_origine'])}")
               + f" · formulations : {'conformes' if g['conforme'] else 'non conformes'}")
    with st.expander(f"Outils appelés ({len(rep['appels'])})"):
        for ap in rep["appels"]:
            st.markdown(f"**{ap['outil']}** — `{json.dumps(ap['entree'], ensure_ascii=False)}`")
            st.json(ap["sortie"], expanded=False)


def sources(preuves: list[dict], intitule: str = "D'où viennent ces chiffres"):
    """Sources en clair : la donnée, sa valeur, sa date, son origine. Les identifiants internes restent en détails techniques."""
    if not preuves:
        return
    with st.expander(intitule):
        lignes = []
        for p in preuves:
            ident = [p["id"]] if technique() else []
            if p["type"] == "actif":
                lignes.append([(p["ticker"], p["colonne"].replace("_", " ")), p["valeur"] if p["valeur"] is not None else "donnée manquante",
                               p["date"], p["source"]] + ident)
            elif p["type"] == "profil":
                lignes.append([("Votre profil", CRITERES.get(p["critere"], {}).get("nom", p["critere"])), p["valeur"] or "non renseigné", "",
                               f"« {p['citation']} »" if p.get("citation") else (p["source"] or "")] + ident)
            elif p["type"] == "hypothese":
                lignes.append([("Hypothèse de l'équipe", p["cle"].replace("_", " ")), "ajustable", "", p.get("explication") or ""] + ident)
            else:
                lignes.append([("Calcul", p["id"].split(":")[-1].replace("_", " ")), p["valeur"], p.get("periode") or "", p["methode"]] + ident)
        tableau(["Donnée", "Valeur", "Date ou période", "Source"] + (["Identifiant"] if technique() else []), lignes)
        st.caption("Prix et fondamentaux : Yahoo Finance, sous ses conditions d'utilisation. Change : Banque du Canada. "
                   "Controverses et exclusions : recherche manuelle, non exhaustive.")


# ---------- Camembert et liste des positions ----------
def couleurs(pf: dict) -> dict[str, str]:
    c, iv, io = {}, 0, 0
    for l in pf["lignes"]:
        if l.get("demande"):
            c[l["ticker"]] = DEMANDE
        elif l["poche"] == "amortisseur":
            c[l["ticker"]] = OCRES[io % len(OCRES)]
            io += 1
        else:
            c[l["ticker"]] = VERTS[iv % len(VERTS)]
            iv += 1
    return c


def camembert(pf: dict, hauteur: int = 320):
    import altair as alt

    teintes = couleurs(pf)
    lignes = [{"position": l["ticker"], "nom": l["nom"], "poids": l["poids_pct"], "poche": POCHES[l["poche"]], "ordre": i}
              for i, l in enumerate(pf["lignes"])]
    if pf["encaisse_pct"] >= 0.5:
        lignes.append({"position": "Encaisse", "nom": "Non investie", "poids": pf["encaisse_pct"], "poche": "Encaisse", "ordre": len(lignes)})
        teintes["Encaisse"] = ENCAISSE
    df = pd.DataFrame(lignes)
    rayon = hauteur / 2 - 14
    arcs = alt.Chart(df).mark_arc(innerRadius=rayon * 0.62, outerRadius=rayon, cornerRadius=5, padAngle=0.014).encode(
        theta=alt.Theta("poids:Q", stack=True), order=alt.Order("ordre:Q"),
        color=alt.Color("position:N", scale=alt.Scale(domain=list(df["position"]), range=[teintes[p] for p in df["position"]]), legend=None),
        tooltip=[alt.Tooltip("position:N", title="Position"), alt.Tooltip("nom:N", title="Nom"),
                 alt.Tooltip("poche:N", title="Rôle"), alt.Tooltip("poids:Q", title="Poids (%)", format=".1f")])
    centre = pd.DataFrame({"x": [0]})
    grand = alt.Chart(centre).mark_text(text=pct(pf["perte_stress_pct"]), font="Georgia", fontSize=30, color="#193d36", dy=-6)
    petit = alt.Chart(centre).mark_text(text="perte de stress", fontSize=11, color="#66746e", dy=18)
    st.altair_chart((arcs + grand + petit).properties(height=hauteur).configure_view(strokeWidth=0)
                    .configure(background="transparent"), width="stretch")


def liste_positions(pf: dict, compact: bool = False):
    teintes = couleurs(pf)
    maxi = max([l["poids_pct"] for l in pf["lignes"]] + [pf["encaisse_pct"], 1])
    lignes = []
    for l in pf["lignes"]:
        detail = POCHES[l["poche"]] + (" · ajouté à votre demande" if l.get("demande") else "") + ("" if compact else f" · {dollars(l['montant_cad'])}")
        lignes.append(f'<div class="af-pos"><span class="dot" style="background:{teintes[l["ticker"]]}"></span>'
                      f'<div class="nom"><b>{escape(l["nom"])}</b><small>{escape(l["ticker"])} · {escape(detail)}</small></div>'
                      f'<div class="bar"><span style="width:{l["poids_pct"] / maxi * 100:.0f}%;background:{teintes[l["ticker"]]}"></span></div>'
                      f'<div class="pct">{pct(l["poids_pct"])}</div></div>')
    if pf["encaisse_pct"] >= 0.5:
        lignes.append(f'<div class="af-pos"><span class="dot" style="background:{ENCAISSE}"></span><div class="nom"><b>Encaisse</b>'
                      f'<small>Non investie{"" if compact else " · " + dollars(pf["encaisse_cad"])}</small></div>'
                      f'<div class="bar"><span style="width:{pf["encaisse_pct"] / maxi * 100:.0f}%;background:{ENCAISSE}"></span></div>'
                      f'<div class="pct">{pct(pf["encaisse_pct"])}</div></div>')
    st.html('<div class="af-card" style="padding:8px 18px">' + "".join(lignes) + "</div>")


def puces_ajustements(etat: dict, a: Analyse):
    """Ce que la personne a changé pendant la conversation, toujours visible et annulable."""
    if not etat["ajouts"] and not etat["maj"]:
        return
    puces = [f'<span class="af-chip demande">Ajouté à votre demande · {escape(a.uni[t]["name"])} {pct(p, 0)}</span>' for t, p in etat["ajouts"].items()]
    puces += [f'<span class="af-chip">Réponse mise à jour · {escape(m["nom"])} : {escape(m["apres_libelle"])}</span>' for m in etat["maj"].values()]
    st.html('<div class="af-chips">' + "".join(puces) + "</div>")
    if st.button("Revenir à mon portefeuille et à mon profil d'origine", key="reco_reinit"):
        S.reco_conv = K.etat_initial()
        st.rerun()


def portefeuille_absent(pf: dict):
    st.warning(pf["erreur"])
    if pf.get("diagnostic"):
        st.markdown("**Les réponses qui écartent le plus d'actifs**")
        tableau(["Réponse du profil", "Actifs écartés"], [[K.humaniser(d["libelle"]), d["nb_actifs_exclus"]] for d in pf["diagnostic"]], nombres=(1,))
        st.caption("Dans « Parler au conseiller », nommez un actif qui vous intéresse : l'outil vous dira quelle réponse revoir.")


# ---------- Écran 1 : mon portefeuille ----------
def page_portefeuille(a: Analyse):
    titre("SIMULATION · AUCUN ORDRE", "Votre mini-portefeuille fictif",
          "Construit sous vos limites. Le risque se juge sur le portefeuille entier, pas actif par actif.")
    pf = a.portefeuille
    if "erreur" in pf:
        portefeuille_absent(pf)
        return
    if not gouvernance.controler_portefeuille(pf)["affichable"]:
        st.error("Un contrôle interne a bloqué l'affichage de ce portefeuille.")
        return
    puces_ajustements(etat_conversation(), a)
    c = st.columns(4)
    c[0].metric("Perte de stress", pct(pf["perte_stress_pct"]), help="Le pire de ce que ce portefeuille aurait perdu : plus forte baisse de 2021 à 2026, année 2022, ou hausse brutale des taux.")
    c[1].metric("Votre budget de perte", pct(pf["budget_perte_pct"]), help="Ce que vous pouvez, voulez et supportez de perdre : le plus prudent des trois.")
    c[2].metric("En dollars", dollars(pf["perte_stress_cad"]), help=f"Sur un montant fictif de {dollars(pf['montant_fictif_cad'])}.")
    c[3].metric("Cohérence", ETATS[pf["etat_tension"]].capitalize(), help="Perte de stress comparée à votre budget de perte.")
    g, d = st.columns([1, 1.25], gap="large")
    with g:
        camembert(pf)
    with d:
        liste_positions(pf)
    limite = " et ".join(pf["limite_par"])
    st.html(f'<p class="af-note">La part de croissance est de {pct(pf["part_croissance_pct"], 0)}. Ce qui la limite : <b>{escape(limite)}</b>.'
            + (f' {pct(pf["encaisse_pct"], 0)} restent en encaisse, non investis : {escape(pf["raison_encaisse"])}.' if pf["raison_encaisse"] else "")
            + (f' Trop peu d\'actifs atteignaient {pf["seuil_entree_demande"]} sur 100 : le seuil d\'entrée a été abaissé à {pf["seuil_entree"]}.'
               if pf["seuil_entree"] < pf["seuil_entree_demande"] else "") + "</p>")
    if pf["message_conflit"]:
        st.warning(pf["message_conflit"] + " " + " ; ".join(pf["conflits"]))
    if pf["a_confirmer"]:
        st.info("À confirmer avec vous : " + " ; ".join(pf["a_confirmer"]) + ".")
    g, d = st.columns(2, gap="large")
    with g:
        st.markdown("**Vos limites, une à une**")
        st.html('<div class="af-card" style="padding:6px 18px">' + "".join(
            f'<div class="af-check">{marque(x["etat"])}<div>{escape(x["contrainte"])}'
            + (f'<small>{escape(K.humaniser(x["detail"]))}</small>' if x["detail"] and x["etat"] != "respectee" else "") + "</div>"
            f'<span class="v">{escape(str(x["valeur"]).replace(".", ","))}' + ("" if x["limite"] is None else f' / {escape(str(x["limite"]))}') + "</span></div>"
            for x in pf["controles"]) + "</div>")
    with d:
        st.markdown("**Ce que ce portefeuille aurait vécu**")
        m, s_ = pf["mesures"], pf["stress"]
        tableau(["Mesure", "Valeur"], [
            ["Variation annuelle typique", pct(m["volatilite_pct"])], ["Plus forte baisse, 2021 à 2026", pct(m["perte_max_pct"])],
            ["Année 2022", pct(m["rendement_2022_pct"])], ["Jours pour revenir au sommet", str(m["jours_sous_eau"]) + ("" if m["recupere"] else " (pas encore revenu)")],
            ["Hausse des taux de 2 points", pct(s_["composantes_pct"]["choc_taux"])],
            [("Krach des actions", "scénario fictif, hors du calcul"), pct(s_["scenario_fictif_krach_pct"])]], nombres=(1,))
        st.caption("Faits passés, pas une prévision. Cinq ans de données ne contiennent qu'une crise : le scénario fictif rappelle qu'une baisse plus forte est possible.")
    sources(pf["preuves"])
    with st.expander("Ce que l'outil ne sait pas sur ce profil"):
        for b in gouvernance.bilan(a, pf):
            st.markdown(f"- **{b['controle']}** : {b['detail']}")
    if st.button("Lire le résumé du conseiller", key="btn_resume"):
        with st.spinner("Le conseiller relit le portefeuille…"):
            S.reco_resume = (S.reco_cle, agents.dialoguer(
                "conseiller", "Présente ce mini-portefeuille fictif en clair : ce qu'il respecte, ce qui limite, ce qu'il faudrait confirmer.",
                a, journal(), modele()))
    if S.get("reco_resume") and S.reco_resume[0] == S.reco_cle:
        with st.container(border=True, key="reco_carte_resume"):
            afficher_reponse(S.reco_resume[1])


# ---------- Écran 2 : parler au conseiller ----------
def _envoyer(texte: str):
    with st.spinner("Le conseiller vérifie votre demande…"):
        m = K.tour(contexte(), texte, modele())
    if S.get("reco_voix"):
        try:
            from entretien import synthese_vocale
            m["audio"] = synthese_vocale(m["texte"][:900])
        except Exception:
            m["audio"] = None
    st.rerun()


def page_conversation(a: Analyse):
    titre("ÉCRIVEZ OU PARLEZ", "Ajuster votre portefeuille avec le conseiller",
          "Dites ce que vous aimeriez ajouter. Si c'est cohérent avec votre profil, le portefeuille s'ajuste ; sinon, vous verrez ce qui s'en rapproche.")
    etat = etat_conversation()
    g, d = st.columns([1.35, 1], gap="large")
    with g, st.container(key="reco_chat"):
        for i, m in enumerate(etat["messages"]):
            with st.chat_message("assistant" if m["role"] == "assistant" else "user",
                                 avatar=":material/eco:" if m["role"] == "assistant" else ":material/person:"):
                st.markdown(m["texte"])
                if m.get("audio") and i == len(etat["messages"]) - 1:
                    st.audio(m["audio"], format="audio/mp3", autoplay=True)
                    m["audio"] = None      # lu une seule fois
                dernier = i == len(etat["messages"]) - 1
                for alt_ in (m.get("cartes") or {}).get("alternatives", []) if dernier else []:
                    if st.button(f"Ajouter {alt_['nom']}", key=f"reco_alt_{i}_{alt_['ticker']}", help=f"{alt_['lien']} · au plus {pct(alt_['poids_max_pct'], 0)}"):
                        _envoyer(f"Ajoutez {alt_['ticker']}")
                if technique() and m.get("appels") is not None:
                    st.caption(f"Réponse produite par : {m['source']} · chiffres vérifiés : {m['fidelite']['nombres_verifies']}"
                               + ("" if m["fidelite"]["fidele"] else f" · sans origine : {', '.join(m['fidelite']['sans_origine'])}"))
                    with st.expander(f"Outils appelés ({len(m['appels'])})"):
                        for ap in m["appels"]:
                            st.markdown(f"**{ap['outil']}** — `{json.dumps(ap['entree'], ensure_ascii=False)}`")
                            st.json(ap["sortie"], expanded=False)
        att = etat.get("en_attente")
        if att:
            with st.container(border=True, key="reco_attente"):
                st.markdown(f"**{att['question']}**")
                if att["type"] == "maj":
                    for ch_ in att["changements"]:
                        st.caption(f"{ch_['nom']} : {ch_['avant_libelle']} → {ch_['apres_libelle']}")
                    st.caption("Votre profil d'origine est conservé : cette mise à jour s'annule d'un clic.")
                o, n, _ = st.columns([1, 1, 2])
                if o.button("Oui", type="primary", key="reco_oui", width="stretch"):
                    _envoyer("Oui")
                if n.button("Non", key="reco_non", width="stretch"):
                    _envoyer("Non")
        texte = st.chat_input("Par exemple : « J'aimerais un peu de Nvidia » ou « plus d'or »", key="reco_saisie")
        if texte and texte.strip():
            _envoyer(texte.strip())
        vocal, lecture = st.columns([2, 1], vertical_alignment="bottom")
        if S.get("reco_voix_possible", True):
            n = S.get("reco_audio_n", 0)
            son = vocal.audio_input("Ou dites-le à voix haute", key=f"reco_audio_{n}")
            lecture.toggle("Réponses lues à voix haute", key="reco_voix")
            if son is not None:
                S.reco_audio_n = n + 1
                try:
                    from entretien import transcrire
                    dit = transcrire(son.getvalue()).strip()
                except Exception:
                    dit, S.reco_voix_possible = "", False
                    st.warning("La transcription vocale est indisponible pour le moment : écrivez votre demande.")
                if dit:
                    _envoyer(dit)
    with d:
        pf = a.portefeuille
        if "erreur" in pf:
            portefeuille_absent(pf)
        else:
            st.markdown("**Votre portefeuille, en direct**")
            camembert(pf, hauteur=240)
            st.caption(f"Perte de stress {pct(pf['perte_stress_pct'])} pour un budget de {pct(pf['budget_perte_pct'])} · {ETATS[pf['etat_tension']]}")
            liste_positions(pf, compact=True)
        puces_ajustements(etat, a)
    st.caption("Le conseiller comprend votre demande et choisit les explications ; les règles du profil décident de ce qui entre dans le portefeuille. "
               "Une réponse de votre profil n'est mise à jour qu'avec votre accord.")


# ---------- Écran 3 : chercher un actif ----------
def page_recherche(a: Analyse):
    titre("UN ACTIF, UN VERDICT", "Chercher un actif", "Un score, un seuil, et ce qui l'explique pour votre profil.")
    seuils = a.hyp["bandes_score"]
    texte = st.text_input("Nom ou symbole", key="reco_requete", placeholder="Nvidia, Shopify, XBB, bitcoin…")
    if not texte:
        d = a.synthese()["decompte"]
        st.html(f'<p class="af-note">Pour votre profil : <b>{d["compatible"]}</b> actifs compatibles ({seuils["compatible"]} sur 100 et plus), '
                f'<b>{d["a_examiner"]}</b> à examiner ({seuils["a_examiner"]} à {seuils["compatible"] - 1}), <b>{d["peu_adapte"]}</b> peu adaptés, '
                f'<b>{d["exclu"]}</b> exclus. Ces seuils sont des hypothèses ajustables.</p>')
        filtre = st.segmented_control("Voir", ["compatible", "a_examiner", "peu_adapte", "exclu"], default="compatible",
                                      format_func=lambda v: ETATS[v].capitalize(), key="reco_filtre", label_visibility="collapsed") or "compatible"
        lignes = [[(r["nom"], r["ticker"]), pastille(r["verdict"], r["libelle_verdict"]), "—" if r["score"] is None else r["score"],
                   pct(r["poids_max_pct"], 0) if r["poids_max_pct"] else "—"] for r in a.classement(filtre, n=len(a.uni))]
        tableau(["Actif", "Verdict", "Score", "Part maximale"], lignes, nombres=(2, 3)) if lignes else st.caption("Aucun actif dans cette catégorie.")
        return
    f = a.rechercher(texte)
    noter("recherche", requete=texte, ticker=f.get("ticker"), verdict=f["verdict"], score=f.get("score"))
    if f["verdict"] == "absent":
        st.warning(f["message"])
        if f["suggestions"]:
            st.markdown("Actifs proches dans l'univers : " + ", ".join(f"**{x['nom']}**" for x in f["suggestions"]))
        return
    e, faits = f["explication"], f["faits"]
    g, d = st.columns([1, 2.2], gap="large")
    with g:
        st.html(f'<div class="af-card"><div class="af-eyebrow">{escape(f["ticker"])}</div><h3 style="margin:8px 0 12px">{escape(f["nom"])}</h3>'
                + pastille(f["verdict"], f["libelle_verdict"])
                + (f'<div class="af-score" style="margin-top:16px">{f["score"]}<small> / 100</small></div>' if f["score"] is not None else "")
                + (f'<p class="af-note" style="margin:10px 0 0">Au plus {pct(f["poids_max_pct"], 0)} du portefeuille.</p>' if f.get("poids_max_pct") else "")
                + "</div>")
        if f["verdict"] not in ("exclu", "donnees_insuffisantes") and st.button("Ajouter à mon portefeuille", type="primary", key="reco_ajout_fiche", width="stretch"):
            K.tour(contexte(), f"Ajoutez {f['ticker']}", modele())
            S.reco_ecran_demande = "Parler au conseiller"
            st.rerun()
    with d:
        st.html(f'<p class="af-lede">{escape(e["resume"])}</p>')
        c1, c2 = st.columns(2)
        with c1:
            carte("Ce qui va dans le sens de votre profil", [K.humaniser(x) for x in e.get("soutient") or []], "Rien de particulier.")
        with c2:
            carte("Ce qui pose problème ou retient", [K.humaniser(x) for x in e.get("retient") or []], "Rien à signaler.")
        for x in e.get("a_savoir") or []:
            st.caption("À savoir : " + K.humaniser(x))
        if e.get("donnees_manquantes"):
            st.info("Certaines données manquent pour cet actif ; elles ne sont pas remplacées.")
    with st.expander("La fiche de l'actif"):
        nomme = {"secteur": SECTEURS_FR.get(faits["secteur"], faits["secteur"]), "pays": faits["pays"], "devise": faits["devise"],
                 "variation annuelle typique": pct(faits["volatilite_pct"]), "plus forte baisse": pct(faits["perte_max_pct"]),
                 "année 2022": pct(faits["rendement_2022_pct"]), "controverse connue": faits["controverse"],
                 "sujet": faits["sujet_controverse"], "énergies fossiles": faits["fossile"], "période observée": faits["periode"]}
        tableau(["Fait (donnée datée)", "Valeur"], [[k.capitalize(), v] for k, v in nomme.items() if v not in (None, "")])
    if f.get("lignes"):
        with st.expander("Chaque critère, un par un"):
            tableau(["Type", "Ce qui est vérifié", "Résultat", "Constat"] + (["Critère"] if technique() else []),
                    [[EFFETS[l["effet"]], l["libelle"], pastille(l["etat"]), K.humaniser(l["raison"])] + ([l["critere"]] if technique() else [])
                     for l in f["lignes"]])
    sources(f.get("preuves", []))
    if st.button("Demander une explication au conseiller", key="btn_expl"):
        with st.spinner("Le conseiller relit le verdict…"):
            S.reco_expl = (f["ticker"], S.reco_cle, agents.dialoguer(
                "explicateur", f"Explique en clair le verdict de {f['ticker']} pour ce profil : pourquoi c'est adapté ou moins adapté.",
                a, journal(), modele()))
    if S.get("reco_expl") and S.reco_expl[:2] == (f["ticker"], S.reco_cle):
        with st.container(border=True, key="reco_carte_expl"):
            afficher_reponse(S.reco_expl[2])


# ---------- Écran 4 : comparer ----------
def page_comparaison(a: Analyse):
    titre("CRITÈRE PAR CRITÈRE", "Comparer deux actifs", "L'écart décisif est le premier critère qui les sépare pour votre profil.")
    tickers = a.uni.tickers()
    libelle = lambda t: f"{a.uni[t]['name']} ({t})"  # noqa: E731
    g, d = st.columns(2)
    ta = g.selectbox("Premier actif", tickers, format_func=libelle, index=tickers.index("NVDA") if "NVDA" in tickers else 0, key="reco_cmp_a")
    tb = d.selectbox("Second actif", tickers, format_func=libelle, index=tickers.index("XBB.TO") if "XBB.TO" in tickers else min(1, len(tickers) - 1), key="reco_cmp_b")
    c = a.comparer(ta, tb)
    noter("comparaison", a=ta, b=tb, ecart=c["ecart_decisif"].get("critere"))
    for col, r in ((g, c["a"]), (d, c["b"])):
        col.html(f'<div class="af-card"><h4>{escape(a.uni[r["ticker"]]["name"])}</h4>{pastille(r["verdict"], r["libelle_verdict"])}'
                 + (f'<div class="af-score" style="margin-top:14px;font-size:34px">{r["score"]}<small> / 100</small></div>' if r["score"] is not None else "") + "</div>")
    e = c["ecart_decisif"]
    if e.get("critere"):
        gagnant = a.uni[e["en_faveur_de"]]["name"]
        st.success(f"**Ce qui les départage : {e['libelle'].lower()}**, en faveur de **{gagnant}**.\n\n{K.humaniser(e['raison'])}")
    else:
        st.info(e["raison"])
    tableau(["Type", "Ce qui est vérifié", a.uni[ta]["name"], a.uni[tb]["name"]],
            [[EFFETS[x["effet"]], x["libelle"], pastille(x["etat_a"]), pastille(x["etat_b"])] for x in c["tableau"]])
    with st.expander("Les faits, côte à côte"):
        noms = {"secteur": "Secteur", "pays": "Pays", "volatilite_pct": "Variation annuelle typique (%)", "perte_max_pct": "Plus forte baisse (%)",
                "rendement_2022_pct": "Année 2022 (%)", "controverse": "Controverse connue", "fossile": "Énergies fossiles", "acces": "Accès depuis le Canada"}
        tableau(["Fait", a.uni[ta]["name"], a.uni[tb]["name"]],
                [[n, str(c["faits_a"][k]).replace("_", " "), str(c["faits_b"][k]).replace("_", " ")] for k, n in noms.items()])
    sources(c["preuves"])


# ---------- Écran 5 : « Et si… ? » ----------
MODIFIABLES = ("A2", "A4", "A5", "B1", "B5", "B6", "B7", "D2", "D9", "D12", "D7", "E1", "E2", "E4", "G3", "D4", "C1")


def page_et_si(a: Analyse):
    import synthese
    titre("REPRENDRE UNE RÉPONSE", "Et si… ?", "Changez une réponse pour voir : tout est recalculé, et chaque changement est expliqué. Rien n'est enregistré.")
    g, d = st.columns(2)
    cid = g.selectbox("Réponse à essayer autrement", MODIFIABLES, format_func=lambda c: CRITERES[c]["nom"], key="reco_si_cid")
    actuelle = (a.profil.get(cid) or {}).get("valeurs") or []
    valeur = d.selectbox("Nouvelle valeur", CRITERES[cid]["valeurs"], format_func=lambda v: synthese.libelle_valeur(cid, v), key=f"reco_si_val_{cid}")
    st.caption("Votre réponse actuelle : " + (", ".join(synthese.libelle_valeur(cid, v) for v in actuelle) or "non renseignée"))
    r = a.et_si(cid, valeur)
    noter("et_si", critere=cid, valeur=valeur, nb_changements=r.get("nb_changements_de_bande"))
    if "erreur" in r:
        st.error(r["erreur"])
    elif r["aucun_changement"]:
        st.info("Rien ne change : cette réponse ne limite pas le résultat actuel. Une autre de vos réponses reste la plus prudente.")
    else:
        av, ap = r["portefeuille_avant"], r["portefeuille_apres"]
        if av and ap:
            c = st.columns(4)
            c[0].metric("Perte de stress", pct(ap["perte_stress_pct"]), f"{ap['perte_stress_pct'] - av['perte_stress_pct']:+.1f} pt".replace(".", ","), delta_color="off")
            c[1].metric("Part de croissance", pct(ap["part_croissance_pct"], 0), f"{ap['part_croissance_pct'] - av['part_croissance_pct']:+.0f} pt", delta_color="off")
            c[2].metric("Variation annuelle", pct(ap["volatilite_pct"]), f"{ap['volatilite_pct'] - av['volatilite_pct']:+.1f} pt".replace(".", ","), delta_color="off")
            c[3].metric("Actifs qui changent de verdict", r["nb_changements_de_bande"])
        if r["contraintes"]:
            st.markdown("**Ce qui change dans vos limites**")
            tableau(["Élément", "Avant", "Après"], [[x["element"], K.humaniser(str(x["avant"])) if x["avant"] is not None else "—",
                                                     K.humaniser(str(x["apres"])) if x["apres"] is not None else "—"] for x in r["contraintes"]])
        change = [x for x in r["actifs_modifies"] if x["change_de_bande"]]
        if change:
            st.markdown("**Actifs dont le verdict change**")
            tableau(["Actif", "Avant", "Après", "Pourquoi"],
                    [[(x["nom"], x["ticker"]), x["verdict_avant"], x["verdict_apres"], K.humaniser(x["raison"] or "")] for x in change[:25]])
        if r["poids_modifies"]:
            st.markdown("**Poids du portefeuille**")
            tableau(["Position", "Avant", "Après", "Écart"], [[a.uni[x["ticker"]]["name"], pct(x["avant_pct"]), pct(x["apres_pct"]),
                                                               f"{x['ecart_points']:+.1f} pt".replace(".", ",")] for x in r["poids_modifies"][:12]], nombres=(1, 2, 3))
    st.divider()
    st.markdown("**Et si nos propres hypothèses étaient différentes ?**")
    st.caption("Une hypothèse change à la fois : horizon d'un cran, seuils du score, seuil de cohérence, période sans 2022.")
    if st.button("Lancer le test de sensibilité", key="btn_sens") or (S.get("reco_sens") and S.reco_sens[0] == S.reco_cle):
        if not S.get("reco_sens") or S.reco_sens[0] != S.reco_cle:
            S.reco_sens = (S.reco_cle, a.sensibilite())
            noter("sensibilite", essais=len(S.reco_sens[1]["essais"]))
        sens = S.reco_sens[1]
        tableau(["Hypothèse essayée", "Actifs qui changent de verdict", "Perte de stress", "Part de croissance"],
                [[x["essai"], x["nb_changements_de_bande"], pct((x["portefeuille"] or {}).get("perte_stress_pct")),
                  pct((x["portefeuille"] or {}).get("part_croissance_pct"), 0)] for x in sens["essais"]], nombres=(1, 2, 3))
        st.caption(sens["limites"])


# ---------- Écran 6 : comprendre ----------
def page_comprendre(a: Analyse):
    titre("TRAÇABLE, PAS MAGIQUE", "Comprendre ces propositions",
          "Chaque résultat renvoie à une donnée datée, à l'une de vos réponses ou à une hypothèse écrite.")
    s = a.synthese()
    p = s["plafonds"]
    st.html(f'<p class="af-lede">{escape(s["phrase"])}</p>')
    g, d = st.columns(2, gap="large")
    with g:
        carte("Ce que vos réponses écartent", list(dict.fromkeys(K.humaniser(e["libelle"]) for e in s["exclusions"])), "Aucune exclusion.")
        carte("Ce que vous préférez", [x["libelle"] for x in s["preferences"]], "Aucune préférence déclarée.")
    with d:
        limites = [f"Un seul titre : au plus {p['titre_pct']} % du portefeuille",
                   f"Cryptoactifs : au plus {p['crypto_pct']} %",
                   "Placements spéculatifs : " + ("aucune limite déclarée" if p["speculatif_pct"] is None else f"au plus {p['speculatif_pct']} %"),
                   f"Un secteur : au plus {p['secteur_pct']} %"]
        if p["secteur_emploi"]["secteurs"]:
            limites.append(f"Le secteur où vous travaillez : au plus {p['secteur_emploi']['pct']} %, fonds compris")
        if p["hors_cad_pct"] is not None:
            limites.append(f"Exposition au change : au plus {p['hors_cad_pct']} %")
        limites += [f"{K.humaniser(x['libelle'])} : au plus {x['plafond_pct']} %" for x in s["plafonds_groupes"]]
        carte("Vos limites", limites)
        carte("Ce que l'outil ne sait pas", [f"{x['nom']} : {x['traitement']}" for x in s["inconnus"][:8]] + [K.humaniser(x) for x in s["alertes"]],
              "Toutes les réponses utiles sont connues.")
    st.markdown("**Comment un actif est jugé**")
    tableau(["Ordre", "Règle", "Effet"], [
        ["1", "Une de vos exclusions s'applique", "L'actif est exclu. Aucun bon score ne le rattrape."],
        ["2", "Le risque de l'actif face à votre budget de perte", "Une part maximale dans le portefeuille, pas un refus."],
        ["3", "Vos limites (complexité, titres à la mode, controverses)", "Le score est borné : une préférence ne compense pas une réserve."],
        ["4", "Vos préférences (thèmes, régions, style)", "Elles départagent les actifs déjà compatibles."]])
    h = a.hyp
    st.markdown("**Nos hypothèses, écrites et ajustables**")
    tableau(["Hypothèse", "Valeur retenue"], [
        ["Seuils du score", f"{h['bandes_score']['compatible']} et plus : compatible ; {h['bandes_score']['a_examiner']} à {h['bandes_score']['compatible'] - 1} : à examiner"],
        ["Cohérence du portefeuille", f"perte de stress jusqu'à {h['tension']['coherent_max']:.1f} fois le budget de perte".replace(".", ",")],
        ["Entrée dans le portefeuille", f"score d'au moins {h['portefeuille']['seuil_entree']}, {h['portefeuille']['nb_positions_max']} positions au plus"],
        ["Perte de stress", f"pire de la baisse historique, de 2022 et d'une hausse des taux de {h['stress']['choc_taux_points']:g} points"],
        ["Part ajoutée sans précision", f"{h['conversation']['part_par_defaut_pct']} % du portefeuille"]])
    st.caption("Aucune de ces valeurs n'est une norme : l'écran « Et si… ? » montre ce qui change quand on les déplace. "
               "Rôle des agents : ils comprennent, expliquent et refusent ; ils ne calculent ni verdict, ni poids, ni chiffre.")
    if technique():
        st.divider()
        st.markdown("**Détails techniques**")
        j = journal()
        st.caption(f"Session {j.session} · journal : {j.stockage()} · {len(j.evenements)} action(s)")
        if j.evenements:
            tableau(["#", "Heure (UTC)", "Action", "Détail"], [[e["rang"], e["horodatage"][11:19], e["type"],
                    json.dumps({k: v for k, v in e.items() if k not in ("session", "rang", "horodatage", "type")}, ensure_ascii=False, default=str)[:220]]
                    for e in j.evenements[-40:]])
        with st.expander("Toutes les hypothèses (fichier de configuration)"):
            st.json({k: v for k, v in h.items() if not k.startswith("_")}, expanded=False)
    st.caption(MENTION)


ECRANS = {"Mon portefeuille": page_portefeuille, "Parler au conseiller": page_conversation, "Chercher un actif": page_recherche,
          "Comparer": page_comparaison, "Et si… ?": page_et_si, "Comprendre": page_comprendre}


def afficher(retour=None):
    """Point d'entrée appelé par app.py quand S.phase == « recommandation ». retour : fonction qui ramène à la synthèse."""
    st.html(STYLE)
    S.setdefault("reco_avec_modele", True)
    S.setdefault("reco_technique", False)
    S.setdefault("reco_voix", False)
    if not S.get("profil"):
        st.info("Les propositions s'appuient sur un profil terminé. Revenez à l'accueil pour créer un profil ou charger un exemple.")
        return
    tete, action = st.columns([4, 1], vertical_alignment="bottom")
    with tete:
        titre("ÉTAPE 04 · VOS PROPOSITIONS", "Ce qui est cohérent avec votre profil, et pourquoi", "")
    if retour is not None and action.button("← Revenir à ma synthèse", width="stretch", key="reco_retour"):
        retour()
    a = analyse_courante()
    if S.get("persona"):
        st.caption(f"Profil fictif de démonstration : {S.persona['nom']}. {S.persona['description']}")
    if S.get("reco_ecran_demande"):       # un bouton d'un autre écran demande d'ouvrir celui-ci
        S.reco_ecran = S.pop("reco_ecran_demande")
    with st.container(key="reco_nav"):
        ecran = st.segmented_control("Écran", list(ECRANS), default=list(ECRANS)[0], key="reco_ecran", label_visibility="collapsed")
    ECRANS[ecran or list(ECRANS)[0]](a)
    with st.expander("Réglages de la simulation"):
        g, m, d = st.columns(3)
        montant = g.number_input("Montant fictif ($ CA)", min_value=500, max_value=5_000_000, step=500, value=int(a.montant),
                                 help="Sert à exprimer la perte en dollars. Aucun argent réel.")
        # Clés de widgets : la nouvelle valeur est connue dès le début du rendu suivant, donc par les écrans au-dessus.
        m.toggle("Assistant IA pour les explications", key="reco_avec_modele",
                 help="L'assistant choisit les outils et les points à expliquer. Les verdicts et chiffres viennent toujours des calculs.")
        d.toggle("Détails techniques", key="reco_technique",
                 help="Pour vérifier : outils appelés par les agents, contrôle de chaque texte, journal des actions.")
        if int(montant) != int(a.montant):
            S.reco_montant = montant
            st.rerun()
