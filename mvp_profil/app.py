"""MVP AlphaForge : profil d'investisseur.

Parcours « conversation » (recommandé) : une discussion orale ou écrite avec l'IA couvre les questions de contexte
(projet, situation, expérience, thèmes) et coche les critères au fur et à mesure ; ce qu'elle n'a pas validé revient
en QCM dans une page « Compléments », puis le parcours continue comme ci-dessous à partir de la page « Vous et le risque ».

Parcours « questionnaire classique » :
  1. Banque commune de 6 pages, ordre adaptatif : QCM, curseurs, quiz et 2 questions libres.
     Les réponses fermées donnent directement les valeurs (pas d'IA). Les réponses libres sont classées
     par deux agents Claude Haiku 5.5 qui débattent, EN ARRIÈRE-PLAN pendant que l'utilisateur continue.
  1 bis. Trois mises en situation (replay de 2022, fourchettes de résultats, effet de mode) : on mesure ce que
     l'utilisateur FAIT et on le compare à ce qu'il a déclaré (le plus prudent l'emporte).
  2. Précisions de fin de parcours : réponses vagues, « Je ne sais pas » et contradictions entre réponses.
     Chaque précision n'est posée qu'UNE fois (reformulée, seuil abaissé) ; à défaut, on retient la meilleure réponse.
  2 bis. Question ouverte finale : ce que la personne veut encore préciser devient des critères DYNAMIQUES, créés
     pour elle et exprimés avec le vocabulaire réel des actifs (criteres_dynamiques.py). Une idée que ce vocabulaire
     ne sait pas exprimer (« rien qui touche à Elon Musk ») part à l'agent chercheur (chercheur.py), EN ARRIÈRE-PLAN :
     il parcourt nos données et Wikipédia et en fait un nouveau mot-clé d'actif, preuves vérifiées à l'appui.
  3. Profil final, téléchargeable en JSON avec la trace des débats.

Lancer :  streamlit run mvp_profil/app.py
Modèle : Claude Haiku 5.5 sur Amazon Bedrock (compte AWS du datathon) ; secours : clé de l'API Anthropic.
Simulation uniquement : aucun conseil financier, aucune transaction.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
import streamlit as st

import chercheur
import criteres_dynamiques
import entretien
import moteur_conversation
from agents import (AgentError, aws_identifiants_presents, backend_anthropic, backend_bedrock, debattre, meilleur,
                    retenable, seuil_essai, _citation_presente)
from criteres import CRITERES, DECLARATIFS, SECTIONS, est_deduit
from criteres_dynamiques import AIDE_OUVERTE, QUESTION_OUVERTE
from entretien import CRITERES_CONVERSATION, MAX_TOURS, OUVERTURE, synthese_vocale, transcrire
from voix_composant import conversation_vocale
from profil import (UTILISABLES, appliquer_correctif, connu, deduire, entree, incoherences, niveau_quiz,
                    recouper_rupture, valeur_curseur, signaux_coherence)
from simulations import ETAPES
from synthese import phrase, synthetiser, libelle_valeur
from pilotage import prioriser_criteres, prioriser_items, prioriser_sections
from questions_conversation import enregistrer_question
from reponses_directes import analyser_reponses
from version_profil import version_courante

# Une réponse non validée est redemandée UNE fois, autrement formulée et avec un seuil abaissé ; ensuite on retient
# une réponse vérifiée par le critique (si elle atteint le plancher de 50 %) ; un désaccord reste incertain.
MAX_RELANCES = 1

st.set_page_config(page_title="AlphaForge · Profil", page_icon="📊", layout="wide")


def reset():
    for k in ("rp", "replay_trace", "mode_revelation", "persona"):
        st.session_state.pop(k, None)
    st.session_state.update(
        phase="accueil", section=0, sections=SECTIONS, profil={}, en_cours=[], file=[], coherences_posees=set(),
        debats=[], chat=[], precisions_pretes=False, sim_etape=0, message_rupture=None, conv=None,
        meilleurs={}, dynamiques=[], reponse_ouverte="", erreur_ouverte=None, recherches=[], questions_posees={},
        libres_en_attente=[], libres_traitees=set(), retour_libres="questionnaire", evenements_questions=[],
        # Composant vocal UNIQUE (conversation, précisions, question ouverte) : n = numéro de la dernière phrase de l'IA,
        # ack = dernier énoncé de l'utilisateur traité, etape = question en cours, actif = l'utilisateur a parlé
        vocal={"n": 0, "ack": 0, "audio": "", "fin": False, "etape": None, "actif": False}, retires=0)


if "phase" not in st.session_state:
    reset()
S = st.session_state
for nom, valeur in {"questions_posees": {}, "libres_en_attente": [], "libres_traitees": set(),
                    "retour_libres": "questionnaire", "evenements_questions": [], "erreur_ouverte": None}.items():
    S.setdefault(nom, valeur)

# ---------- Barre latérale ----------
with st.sidebar:
    st.header("Réglages")
    source = st.radio("Accès au modèle", ["AWS Bedrock (compte du datathon)", "API Anthropic (clé)"])
    if source.startswith("AWS"):
        cle = ""
        pret = aws_identifiants_presents()
        st.caption("✅ Identifiants AWS détectés" if pret else "❌ Aucun identifiant AWS sur cette machine")
    else:
        cle = st.text_input("Clé API Anthropic", value=os.environ.get("ANTHROPIC_API_KEY", ""), type="password")
        pret = bool(cle)
    seuil = st.slider("Seuil de sûreté", 0.50, 0.95, 0.80, 0.05,
                      help="Une réponse libre est validée si les deux agents sont d'accord avec au moins ce niveau de confiance.")
    max_tours = st.slider("Tours de débat maximum", 1, 3, 2)
    voix = True
    st.caption("Les questions ouvertes et leurs réponses se font à l'oral.")
    st.caption("Modèle : Claude Haiku 5.5 (classificateur et critique)")
    if st.button("Recommencer", width="stretch"):
        reset()
        st.rerun()
    st.caption("Simulation éducative. Aucun conseil financier personnalisé.")
    st.caption("Version du profil : " + version_courante())


@st.cache_resource
def backend_pour(key: str):
    return backend_anthropic(key) if key else backend_bedrock()


@st.cache_resource
def executeur() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=4)


def a_preciser(criteres: list[str], texte: str | None = None, echanges=None, motif="Réponse « Je ne sais pas »"):
    restants = []
    for cid in criteres:
        if connu(S.profil, cid):
            continue
        if S.questions_posees.get(cid, {}).get("clarifications", 0) >= 1:
            S.profil.setdefault(cid, entree([], "non établi", statut="incertain", confiance=0))
            S.profil[cid]["statut"] = "incertain"
            continue
        S.profil[cid] = entree([], "à préciser", statut="à préciser", confiance=0.0, motif=motif,
                               citation=(echanges or [("", "")])[-1][1])
        restants.append(cid)
    if restants:
        S.file.append({"kind": "libre", "criteres": restants, "essai": 0, "echanges": list(echanges or []),
                       "texte": texte or CRITERES[restants[0]]["relance"]})


def retenir_meilleure(cid: str, source: str) -> bool:
    """Après la reformulation : accord sous le seuil retenu, désaccord ou contrôle absent incertain."""
    b = S.meilleurs.get(cid)
    if retenable(b):
        S.profil[cid] = entree(b.valeurs, source, b.citation, b.confiance, "retenu",
                               f"Meilleure réponse obtenue ({b.confiance:.0%}), sous le seuil de {seuil:.0%}")
        return True
    S.profil[cid] = entree(b.valeurs if b else [], source, b.citation if b else "", b.confiance if b else 0.0,
                           "incertain", b.motif if b else "Aucune réponse exploitable")
    return False


def nature(source: str) -> str:
    """Nature d'une valeur du profil, affichée à l'utilisateur : ce qu'il a dit, ce qu'on a mesuré, ou une hypothèse."""
    s = source.lower()
    if s.startswith(("replay", "fourchettes", "test effet", "quiz", "comparaison")):
        return "mesuré"
    if "hypothèse" in s:
        return "hypothèse"
    if s.startswith(("déduit", "déduction")):
        return "déduit"
    if s.startswith("énoncé"):
        return "énoncé"
    return "déclaré"


def source_ia(r, defaut: str) -> str:
    """« déduit (IA) » quand la valeur découle de ce que l'utilisateur a dit sans qu'il l'ait dite mot pour mot."""
    return "déduit (IA)" if est_deduit(r.motif) else defaut


def facultatifs(exclus=()) -> list[str]:
    """Critères encore inconnus qu'une réponse libre pourrait renseigner au passage (ils ne seront plus demandés)."""
    return [c for c in DECLARATIFS if c not in exclus and not connu(S.profil, c)
            and S.profil.get(c, {}).get("statut") != "analyse en cours"]


def enregistrer_debat(debat, item_id: str, definitif: bool) -> list[str]:
    S.debats.append({"question": item_id, "tours": debat.tours,
                     "resultats": {c: vars(r) for c, r in debat.resultats.items()}})
    restants = []
    for cid, r in debat.resultats.items():
        S.meilleurs[cid] = meilleur(S.meilleurs.get(cid), r)
        if r.valide:
            S.profil[cid] = entree(r.valeurs, source_ia(r, "réponse libre (IA)"), r.citation, r.confiance,
                                   motif=r.motif if est_deduit(r.motif) else "")
        elif retenable(r):
            S.profil[cid] = entree(r.valeurs, source_ia(r, "réponse orale (IA)"), r.citation, r.confiance,
                                   "retenu", motif=r.motif)
        elif definitif:
            retenir_meilleure(cid, "réponse libre (IA)")
        elif getattr(r, "precision_necessaire", False) and getattr(r, "motif_precision", ""):
            restants.append(cid)
        else:
            S.profil[cid] = entree([], "réponse orale non établie", r.citation, 0, "incertain", motif=r.motif)
    return restants


# ---------- Accueil : choix du parcours ----------
def page_accueil():
    st.write("Deux façons de commencer. Dans les deux cas, vous aurez ensuite quelques questions à choix, trois mises "
             "en situation, puis votre profil.")
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("**🎙️ Conversation (recommandé)**\n\nUne courte discussion à l'oral : l'outil pose les "
                    "questions sur votre projet et votre situation, et coche les critères au fur et à mesure.")
        if st.button("Commencer en conversation", type="primary", disabled=not pret, width="stretch"):
            # suivi : {critère: nb de réponses au moment où il a été jugé « à reformuler »} ; reformules : déjà redemandés
            S.conv = moteur_conversation.creer(S.questions_posees)
            dire(OUVERTURE, "conv:0")
            S.phase = "conversation"
            st.rerun()
    with c2.container(border=True):
        st.markdown("**📝 Questionnaire classique**\n\nDes choix à l'écran, complétés par des réponses ouvertes à l'oral.")
        if st.button("Questionnaire classique", disabled=not pret, width="stretch"):
            S.phase, S.sections = "questionnaire", prioriser_sections(S.profil, SECTIONS)
            st.rerun()
    page_personas()


def charger_persona(nom: str):
    """Mode démonstration : profil fictif de l'énoncé, chargé depuis un fichier versionné (aucun appel au modèle)."""
    d = json.loads((Path(__file__).parent / "personas" / f"{nom}.json").read_text(encoding="utf-8"))
    reset()
    S.profil, S.persona, S.phase = d["profil"], d, "termine"
    st.rerun()


def page_personas():
    st.divider()
    st.markdown("**Démonstration : les trois profils fictifs de l'énoncé**")
    st.caption("Chargés depuis mvp_profil/personas/. Les valeurs tirées de l'énoncé et les hypothèses de test "
               "sont distinguées dans la colonne « source ».")
    for col, nom in zip(st.columns(3), ("amira", "mateo", "robert")):
        if col.button(f"Charger {nom.capitalize()}", width="stretch", key=f"persona_{nom}"):
            charger_persona(nom)


# ---------- Phase 0 : conversation (oral ou écrit) ----------
def sections_apres_conversation(manquants: list[str]) -> list[dict]:
    """Questions restantes : les pages sans critère de conversation + une page « Compléments » qui reprend,
    sous forme de QCM, ce que la conversation n'a pas permis de valider."""
    conv = set(CRITERES_CONVERSATION)
    restes, complements = [], []
    for sec in SECTIONS:
        items = []
        for it in sec["items"]:
            crits = it.get("criteres", [it.get("critere")])
            if not set(crits) & conv:
                items.append(it)
            elif set(crits) & set(manquants):
                complements.append({**it, "criteres": [c for c in crits if c in manquants]} if it["type"] == "libre" else it)
        if items:
            restes.append({**sec, "items": items})
    return prioriser_sections(S.profil, ([{"titre": "Compléments", "items": complements}] if complements else []) + restes)


def _clore(cid: str):
    """Le critère sort de la conversation : l'IA n'en reparlera plus."""
    c = S.conv
    if cid in c["restants"]:
        c["restants"].remove(cid)
    c["suivi"].pop(cid, None)
    c.get("relances_posees", {}).pop(cid, None)


def planifier_analyse_conversation():
    moteur_conversation.planifier(S.conv, S.profil, executeur(), backend_pour(cle), entretien.analyser, seuil)


def appliquer_verifications(reprendre: bool = True):
    c = S.conv
    moteur_conversation.integrer(c, S.profil)
    S.meilleurs.update(c["meilleurs"])
    if c["traces"]:
        S.debats.extend(c["traces"])
        c["traces"] = []
    planifier_analyse_conversation()
    if reprendre and c["attente"]:
        decision = moteur_conversation.suivante(c, S.profil, MAX_TOURS)
        if not decision["attendre"]:
            moteur_conversation.poser(c, decision)
            dire(c["question"], f"conv:{c['tours']}:{','.join(c['cibles_question'])}", fin=c["fin"])


def fin_conversation():
    c = S.conv
    with st.spinner("Vérification des réponses déjà recueillies…"):
        planifier_analyse_conversation()
        while c["jobs"]:
            for job in list(c["jobs"]):
                try:
                    job["future"].result()
                except Exception:
                    pass  # la réponse reste conservée ; une panne ne devient pas une nouvelle question
            appliquer_verifications(reprendre=False)
    manquants = [cid for cid in CRITERES_CONVERSATION if not connu(S.profil, cid)
                 and c["questions_posees"].get(cid, {}).get("clarifications", 0) == 0]
    S.sections, S.section, S.phase = sections_apres_conversation(manquants), 0, "questionnaire"
    st.rerun()


# ---------- Voix : un composant UNIQUE pour la conversation, les précisions et la question ouverte ----------
PHASES_VOCALES = ("conversation", "libre_oral", "precisions", "ouverte")


def dire(texte: str, etape: str, fin: bool = False):
    """L'IA dit une nouvelle phrase (une seule fois par étape) : MP3 Polly, lu par le composant vocal."""
    v = S.vocal
    if v["etape"] == etape:
        return
    v.update(audio=voix_b64(texte), n=v["n"] + 1, fin=fin, etape=etape)


def redire(texte: str, etape: str):
    """Répéter (l'utilisateur l'a demandé, ou sa réponse n'a pas été comprise)."""
    S.vocal["etape"] = None
    dire(texte, etape)


def barre_vocale():
    """Composant vocal toujours au MÊME endroit (haut de la colonne principale) : il n'est jamais recréé, donc
    la voix n'est pas coupée et le micro reste autorisé d'une phase à l'autre. Pendant les QCM et les mises en
    situation, il reste « en veille » (micro coupé) si l'utilisateur a déjà parlé ; il reprend aux précisions.
    Renvoie le dernier énoncé non traité : {"kind": "texte", "texte": ...} ou {"kind": "termine"}, sinon None."""
    v = S.vocal
    veille = S.phase not in PHASES_VOCALES or (S.phase == "conversation" and S.conv.get("attente", False))
    if veille and not (v["actif"] and S.phase in ("questionnaire", "simulations")):
        return None
    valeur = conversation_vocale(audio_b64=v["audio"], n=v["n"], ack=v["ack"], fin=v["fin"], voix=voix,
                                 veille=veille, key="voix")
    if veille or not valeur or valeur.get("n", 0) <= v["ack"]:
        return None
    v["ack"] = valeur["n"]
    if valeur["kind"] == "termine":
        return {"kind": "termine", "texte": ""}
    v["actif"] = True
    texte = ""
    try:
        with st.spinner("Transcription (Amazon Transcribe)…"):
            texte = transcrire(base64.b64decode(valeur["wav"]))
    except AgentError as e:
        st.warning(str(e))
    return {"kind": "texte", "texte": texte}


def entendu() -> str | None:
    """Texte dit à voix haute à cette exécution (None si rien). Un énoncé vide relance l'écoute."""
    if not ENONCE or ENONCE["kind"] != "texte":
        return None
    if not ENONCE["texte"]:
        st.rerun()
    return ENONCE["texte"]


def voix_b64(texte: str) -> str:
    """Réplique lue par Amazon Polly (MP3 en base64), ou chaîne vide si la voix est coupée ou indisponible."""
    if not voix:
        return ""
    try:
        return base64.b64encode(synthese_vocale(texte)).decode()
    except Exception:  # noqa: BLE001  (pas d'accès à Polly : la conversation continue à l'écrit)
        return ""


def repondre(texte: str):
    c = S.conv
    if entretien.demande_repetition(texte):
        redire(c["question"], f"conv:{c['tours']}:{','.join(c['cibles_question'])}")
        st.rerun()
    echos = moteur_conversation.recevoir(c, S.profil, texte)
    planifier_analyse_conversation()
    appliquer_verifications()
    decision = moteur_conversation.suivante(c, S.profil, MAX_TOURS)
    moteur_conversation.poser(c, decision, " ".join(echos) + (" " if echos else ""))
    dire(c["question"], f"conv:{c['tours']}:{','.join(c['cibles_question'])}", fin=c["fin"])
    st.rerun()


def page_conversation():
    c = S.conv
    appliquer_verifications()
    fait = sum(connu(S.profil, cid) for cid in CRITERES_CONVERSATION)
    st.progress(fait / len(CRITERES_CONVERSATION), text=f"Conversation · {fait} informations renseignées")
    if ENONCE and ENONCE["kind"] == "termine":
        fin_conversation()
    if ENONCE and ENONCE["texte"] and not c["attente"]:
        repondre(ENONCE["texte"])
    if c["attente"]:
        st.info("Vos réponses sont conservées. Le contrôle termine son travail ; inutile de les répéter.")
    st.caption("Réponses ouvertes exclusivement à l'oral. La transcription ci-dessous est une trace de vos paroles.")
    with st.expander("Transcription de la conversation", expanded=False):
        for q, r in c["echanges"]:
            st.chat_message("assistant").write(q)
            st.chat_message("user").write(r)
    st.chat_message("assistant").write(c["question"])
    if c["fin"]:
        if st.button("Continuer vers les questions suivantes", type="primary"):
            fin_conversation()
        return
    if st.button("Passer aux questions suivantes", help="Les réponses déjà données sont conservées et vérifiées."):
        fin_conversation()


@st.fragment(run_every=1)
def liste_criteres_conversation():
    """Panneau de droite pendant la conversation : critères cochés au fur et à mesure.

    Se rafraîchit chaque seconde ; dès qu'une vérification du critique se termine, toute la page est
    relancée pour afficher la coche ✅ sans attendre le message suivant de l'utilisateur.
    """
    if S.phase != "conversation":
        return
    if any(j["future"].done() for j in S.conv["jobs"]):
        st.rerun(scope="app")
    en_verif = {cid for j in S.conv["jobs"] for cid in j["criteres"]}
    for cid in CRITERES_CONVERSATION:
        v = S.profil.get(cid)
        if v and v["statut"] in UTILISABLES:
            marque = "✅" if v["statut"] == "validé" else f"☑️ retenu ({v['confiance']:.0%})"
            st.markdown(f"{marque} **{CRITERES[cid]['nom']}** : {', '.join(v['valeurs'])}  \n<small>« {v['citation']} »</small>",
                        unsafe_allow_html=True)
        elif cid in S.conv["suivi"]:
            st.markdown(f"🔁 {CRITERES[cid]['nom']} : pas assez clair, l'IA reformule une fois")
        elif cid in en_verif:
            st.markdown(f"⏳ {CRITERES[cid]['nom']} : vérification par le critique…")
        else:
            st.markdown(f"○ {CRITERES[cid]['nom']}")


# ---------- Phase 1 : questionnaire fixe ----------
def a_demander(it: dict) -> dict | None:
    """La question, réduite à ce qui reste inconnu ; None si tout est déjà su (dit ailleurs, ou déduit)."""
    if it["type"] == "libre" and it["id"] in S.libres_traitees:
        return None
    crits = it.get("criteres", [it.get("critere")])
    inconnus = [c for c in crits if not connu(S.profil, c) and S.profil.get(c, {}).get("statut") != "analyse en cours"]
    if it["type"] == "libre":
        inconnus = [c for c in inconnus if not S.questions_posees.get(c, {}).get("initiales", 0)
                    or ((S.conv or {}).get("suivi", {}).get(c)
                        and S.questions_posees.get(c, {}).get("clarifications", 0) < 1)]
    if not inconnus:
        return None
    return {**it, "criteres": inconnus} if it["type"] == "libre" else it


def page_questionnaire():
    sections = S.sections
    if not sections:
        S.phase = "simulations"
        st.rerun()
    recuperer_analyses(attendre=False)
    deduire(S.profil)
    sec = sections[S.section]
    items = prioriser_items(S.profil, [x for x in (a_demander(it) for it in sec["items"]) if x])
    retires = [it for it in sec["items"] if not a_demander(it)]
    if not items:
        avancer_questionnaire([])
    libres = [it for it in items if it["type"] == "libre"]
    fermes = [it for it in items if it["type"] != "libre"]
    if not fermes:
        avancer_questionnaire(libres)
    st.progress(S.section / len(sections), text=f"Étape {S.section + 1} sur {len(sections)} · {sec['titre']}")
    if retires:
        st.caption(f"{len(retires)} question(s) retirée(s) : vos réponses sont déjà renseignées.")
    if libres:
        st.caption("Les réponses ouvertes de cette étape seront recueillies à l'oral après ces choix.")
    with st.form(f"section_{S.section}"):
        rep = {}
        for it in fermes:
            k = f"{S.section}_{it['id']}"
            if it["type"] == "qcm":
                rep[it["id"]] = st.radio(it["texte"], [o[0] for o in it["options"]], index=None, key=k)
            elif it["type"] == "qcm_multi":
                rep[it["id"]] = st.multiselect(it["texte"], [o[0] for o in it["options"]], key=k,
                                               placeholder="Choisissez une ou plusieurs réponses")
            elif it["type"] == "curseur":
                x = st.slider(f"{it['texte']} (en {it['unite']})", it["min"], it["max"], it["defaut"], it["pas"], key=k)
                nsp = st.checkbox(it["case_nsp"], key=k + "_nsp")
                rep[it["id"]] = None if nsp else x
            elif it["type"] == "quiz":
                st.markdown(f"**{it['texte']}**")
                rep[it["id"]] = [st.radio(q["texte"], q["options"], index=None, key=f"{k}_{i}")
                                 for i, q in enumerate(it["questions"])]
        envoye = st.form_submit_button("Continuer" if S.section < len(sections) - 1 else "Terminer le questionnaire",
                                       type="primary", disabled=not pret)
    if not envoye:
        return
    manquants = [it["texte"] for it in fermes
                 if (it["type"] == "qcm" and rep[it["id"]] is None)
                 or (it["type"] == "quiz" and any(r is None for r in rep[it["id"]]))]
    if manquants:
        st.warning("Merci de répondre à : " + " · ".join(manquants))
        return
    S.retires += len(retires)
    for it in fermes:
        r = rep[it["id"]]
        if it["type"] == "qcm":
            val = dict(it["options"])[r]
            if val is None:
                a_preciser([it["critere"]])
            else:
                S.profil[it["critere"]] = entree([val], "QCM", citation=r)
        elif it["type"] == "qcm_multi":
            vals = [dict(it["options"])[x] for x in r]
            if len(vals) > 1:
                vals = [v for v in vals if v not in ("aucun", "aucune")]
            if vals:
                S.profil[it["critere"]] = entree(vals, "QCM", citation=", ".join(r))
            else:
                a_preciser([it["critere"]], motif="Aucune case cochée")
        elif it["type"] == "curseur":
            if r is None:
                a_preciser([it["critere"]])
            else:
                S.profil[it["critere"]] = entree([valeur_curseur(it, r)], "curseur", citation=f"{r} {it['unite']}", nombre=r)
        elif it["type"] == "quiz":
            idx = [q["options"].index(x) for q, x in zip(it["questions"], r)]
            niveau, score = niveau_quiz(it, idx)
            S.profil[it["critere"]] = entree([niveau], "quiz", citation=f"{score}/{len(it['questions'])} bonnes réponses", score=score)
    avancer_questionnaire(libres)


def avancer_questionnaire(libres: list[dict]):
    S.section += 1
    S.retour_libres = "simulations" if S.section >= len(S.sections) else "questionnaire"
    S.libres_en_attente = list(libres)
    S.phase = "libre_oral" if libres else S.retour_libres
    st.rerun()


def integrer_reponses_directes(question: str, texte: str, criteres: list[str]) -> list[str]:
    reponses = analyser_reponses(question, texte, criteres)["reponses"]
    for cid, reponse in reponses.items():
        S.profil[cid] = dict(reponse)
    return [cid for cid in criteres if not connu(S.profil, cid)]


def page_libre_oral():
    while S.libres_en_attente:
        it = S.libres_en_attente[0]
        ids = [cid for cid in it["criteres"] if not connu(S.profil, cid)]
        if it["id"] in S.libres_traitees or not ids:
            S.libres_en_attente.pop(0)
            continue
        break
    if not S.libres_en_attente:
        S.phase = S.retour_libres
        st.rerun()
    texte_question = it["texte"] if ids == it["criteres"] else " ".join(CRITERES[cid]["relance"] for cid in ids)
    etape = f"libre:{it['id']}"
    st.subheader("Votre réponse à l'oral")
    st.caption("Une seule réponse suffit. Le contrôle se poursuit pendant les étapes suivantes.")
    st.write(texte_question)
    if S.vocal["etape"] != etape:
        for cid in ids:
            deja = S.questions_posees.get(cid, {}).get("initiales", 0)
            question = {"criteres": [cid], "clarification": bool(deja)}
            if not deja or S.questions_posees.get(cid, {}).get("clarifications", 0) < 1:
                enregistrer_question(S.questions_posees, question, len(S.evenements_questions) + 100)
        dire(texte_question, etape)
    dit = entendu()
    if dit and entretien.demande_repetition(dit):
        redire(texte_question, etape)
        st.rerun()
    passer = st.button("Passer cette question", help="Ces informations restent inconnues ; aucune réponse ne sera inventée.")
    if not dit and not passer:
        return
    S.libres_traitees.add(it["id"])
    S.libres_en_attente.pop(0)
    if dit:
        restants = integrer_reponses_directes(texte_question, dit, ids)
        if restants:
            ech = [(texte_question, dit)]
            for cid in restants:
                S.profil[cid] = entree([], "réponse orale en analyse", statut="analyse en cours", confiance=0)
            fut = executeur().submit(debattre, backend_pour(cle), ech, restants, seuil, max_tours, facultatifs(restants))
            S.en_cours.append({"item": it["id"], "criteres": restants, "echanges": ech, "future": fut})
    else:
        for cid in ids:
            S.profil[cid] = entree([], "question passée", statut="incertain", confiance=0, motif="L'utilisateur a choisi de passer")
    st.rerun()


# ---------- Phase 1 bis : mises en situation (ce que l'utilisateur fait, pas seulement ce qu'il dit) ----------
def page_simulations():
    st.progress(S.sim_etape / len(ETAPES), text=f"Mises en situation · {S.sim_etape + 1} sur {len(ETAPES)}")
    if ETAPES[S.sim_etape](S):
        S.sim_etape += 1
        if S.sim_etape >= len(ETAPES):
            S.message_rupture = recouper_rupture(S.profil)  # déclaré vs observé : on garde le plus prudent
            S.phase = "precisions"
        st.rerun()


def retours_situations():
    """Ce que les mises en situation ont appris (affiché aux précisions ET sur la page finale)."""
    if S.get("mode_revelation"):
        st.info(f"Mise en situation 3, les titres étaient : {S.mode_revelation}.")
    if S.message_rupture:
        st.warning(S.message_rupture)


# ---------- Phase 2 : précisions ----------
def recuperer_analyses(attendre: bool = True):
    """Intègre les débats lancés en arrière-plan : tous (en attendant ceux qui ne sont pas finis), ou seulement ceux
    qui sont déjà terminés (attendre=False, à chaque page du questionnaire, pour retirer les questions devenues inutiles)."""
    jobs = S.en_cours if attendre else [j for j in S.en_cours if j["future"].done()]
    with st.spinner("Les agents terminent l'analyse de vos réponses libres…") if attendre and jobs else _rien():
        for job in jobs:
            try:
                debat = job["future"].result()
            except AgentError as e:
                st.error(str(e))
                for cid in job["criteres"]:
                    if not connu(S.profil, cid):
                        S.profil[cid] = entree([], "analyse indisponible", job["echanges"][-1][1], 0,
                                               "incertain", motif="Réponse conservée, contrôle indisponible")
                continue
            restants = enregistrer_debat(debat, job["item"], definitif=False)
            if restants:
                a_preciser(restants, texte=debat.question_relance or None, echanges=job["echanges"],
                           motif="Réponse libre insuffisante")
    S.en_cours = [j for j in S.en_cours if j not in jobs]
    if attendre:
        S.precisions_pretes = True


class _rien:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


ORDINAUX = ["Première", "Deuxième", "Troisième", "Quatrième", "Cinquième"]


def oral(item: dict) -> str:
    """Ce que l'IA dit pour une précision ; pour une contradiction, elle énonce aussi les possibilités."""
    if item["kind"] != "coherence":
        return item["texte"]
    return item["texte"] + " " + " ".join(f"{ORDINAUX[i]} possibilité : {o[0]}." for i, o in enumerate(item["options"]))


def appliquer_coherence(item: dict, choix: str):
    a_redemander = appliquer_correctif(S.profil, dict(item["options"])[choix], choix)
    S.coherences_posees.add(item["id"])
    S.chat += [{"role": "assistant", "content": item["texte"]}, {"role": "user", "content": choix}]
    S.file.pop(0)
    for cid in a_redemander:  # valeur non devinée : on la redemande (une question de précision par critère)
        a_preciser([cid], motif="Réponses contradictoires : à préciser")
    st.rerun()


def repondre_precision(item: dict, reponse: str):
    restants = integrer_reponses_directes(item["texte"], reponse, item["criteres"])
    ech = item["echanges"] + [(item["texte"], reponse)]
    S.chat += [{"role": "assistant", "content": item["texte"]}, {"role": "user", "content": reponse}]
    if not restants:
        S.file.pop(0)
        st.rerun()
    try:
        with st.spinner("Vérification de votre réponse…"):
            debat = debattre(backend_pour(cle), ech, restants, seuil=seuil,
                             max_tours=max_tours, facultatifs=facultatifs(restants))
    except AgentError as e:
        st.error(str(e))
        for cid in restants:
            S.profil[cid] = entree([], "analyse indisponible", reponse, 0, "incertain", motif="Réponse conservée")
        S.file.pop(0)
        st.rerun()
    S.file.pop(0)
    enregistrer_debat(debat, "précision orale", definitif=True)
    st.rerun()


def page_precisions():
    if not S.precisions_pretes:
        recuperer_analyses()
    deduire(S.profil)
    recouper_rupture(S.profil)  # un point de rupture redonné en précision ne dépasse jamais l'observé au replay
    for it in list(S.file):  # ce qui est devenu connu entre-temps (dit au passage, déduit) n'est plus demandé
        if it["kind"] == "libre":
            it["criteres"] = [c for c in it["criteres"] if not connu(S.profil, c)]
            if not it["criteres"]:
                S.file.remove(it)
    ordre = prioriser_criteres(S.profil, [c for it in S.file if it["kind"] == "libre" for c in it["criteres"]])
    rang = {c: i for i, c in enumerate(ordre)}
    S.file.sort(key=lambda it: -1 if it["kind"] == "coherence" else min(rang[c] for c in it["criteres"]))
    if not S.file:  # plus rien à préciser : on vérifie la cohérence d'ensemble
        nouvelles = [c for c in incoherences(S.profil) if c["id"] not in S.coherences_posees]
        if nouvelles:
            S.file.append({"kind": "coherence", **nouvelles[0]})
        else:
            S.phase = "ouverte"
            st.rerun()
    retours_situations()
    st.subheader("Quelques précisions")
    st.caption("Certaines réponses étaient incomplètes ou se contredisaient. Ces questions servent à les clarifier.")
    for m in S.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    item = S.file[0]
    etape = f"prec:{item.get('id', ','.join(item['criteres']))}:{len(S.chat)}"
    if item["kind"] == "libre" and S.vocal["etape"] != etape:
        ids = [cid for cid in item["criteres"] if S.questions_posees.get(cid, {}).get("clarifications", 0) < 1]
        if not ids:
            S.file.pop(0)
            st.rerun()
        item["criteres"] = ids
        enregistrer_question(S.questions_posees, {"criteres": ids, "clarification": True}, len(S.chat) + 1000)
    dire(oral(item), etape)
    dit = entendu()
    if dit and entretien.demande_repetition(dit):
        redire(oral(item), etape)
        st.rerun()
    if item["kind"] == "coherence":
        with st.chat_message("assistant"):
            st.write(item["texte"])
        with st.form(f"coh_{item['id']}"):
            choix = st.radio("Votre réponse", [o[0] for o in item["options"]], index=None)
            ok = st.form_submit_button("Valider", type="primary")
        if ok and choix:
            appliquer_coherence(item, choix)
        if dit:  # réponse orale : l'IA trouve la possibilité choisie (ou redemande)
            try:
                i = entretien.choisir_option(backend_pour(cle), item["texte"], [o[0] for o in item["options"]], dit)
            except AgentError as e:
                st.error(str(e))
                return
            if i >= 0:
                appliquer_coherence(item, item["options"][i][0])
            redire("Je n'ai pas bien compris. " + oral(item), etape)
            st.rerun()
        return
    with st.chat_message("assistant"):
        st.write(item["texte"])
    if st.button("Je ne peux pas préciser", help="Cette information reste inconnue et sera signalée dans le profil."):
        for cid in item["criteres"]:
            S.profil[cid] = entree([], "non renseigné", statut="incertain", confiance=0, motif="Précision passée")
        S.file.pop(0)
        S.chat.append({"role": "user", "content": "Je ne peux pas préciser"})
        st.rerun()
    reponse = dit
    if reponse:
        repondre_precision(item, reponse)


# ---------- Phase 2 bis : question ouverte -> critères dynamiques ----------
def page_ouverte():
    retours_situations()
    st.subheader("Une dernière chose, à l'oral")
    st.caption("Vos paroles peuvent compléter votre profil par une contrainte ou une préférence personnelle.")
    st.write(QUESTION_OUVERTE)
    dire(QUESTION_OUVERTE, "ouverte")
    dit = entendu()
    if dit and entretien.demande_repetition(dit):
        redire(QUESTION_OUVERTE, "ouverte")
        st.rerun()
    rien = st.button("Je n'ai rien à ajouter")
    if rien or (dit and dit.strip().casefold().strip(".! ") in ("rien", "non", "rien à ajouter", "je n'ai rien à ajouter", "non rien à ajouter")):
        S.reponse_ouverte = dit or ""
        S.phase = "termine"
        st.rerun()
    texte = dit
    if not texte and S.get("erreur_ouverte"):
        st.warning("Votre réponse est conservée. Vous pouvez relancer son analyse sans la répéter.")
        if st.button("Réessayer l'analyse de ma réponse"):
            texte = S.reponse_ouverte
    if not texte:
        return
    S.reponse_ouverte = texte.strip()
    try:
        with st.spinner("Les agents créent vos critères personnels…"):
            nouveaux = criteres_dynamiques.creer(backend_pour(cle), QUESTION_OUVERTE, S.reponse_ouverte, seuil,
                                                 deja=len(S.dynamiques))
    except AgentError as e:
        S.erreur_ouverte = str(e)
        st.error("L'analyse est indisponible ; votre réponse est conservée.")
        return
    S.erreur_ouverte = None
    S.dynamiques += nouveaux
    for c in nouveaux:
        if c.get("etiquetage") == "en_attente":
            fut = executeur().submit(chercheur.etiqueter, backend_pour(cle), c["concept"], c["effet"])
            S.recherches.append({"id": c["id"], "future": fut})
    S.phase = "termine"
    st.rerun()


def integrer_recherches() -> bool:
    """Intègre les recherches terminées du chercheur. Renvoie True s'il en reste en cours."""
    for job in [j for j in S.recherches if j["future"].done()]:
        c = next(x for x in S.dynamiques if x["id"] == job["id"])
        try:
            criteres_dynamiques.appliquer_etiquetage(c, job["future"].result())
        except Exception as e:  # noqa: BLE001  (réseau, modèle : le critère reste visible, à revoir)
            c.update(etiquetage="echec", applicable=False, motif=f"Recherche impossible : {e}")
            c["regle"] = criteres_dynamiques.regle(c)
        S.recherches.remove(job)
    return bool(S.recherches)


@st.fragment(run_every=1)
def suivi_recherches():
    """Pendant que le chercheur travaille : message d'attente, puis la page se met à jour toute seule."""
    if S.phase != "termine" or not S.recherches:
        return
    if any(j["future"].done() for j in S.recherches):
        st.rerun(scope="app")
    concepts = [x["concept"] for x in S.dynamiques if x["id"] in {j["id"] for j in S.recherches}]
    st.info("⏳ L'agent chercheur parcourt nos données et Wikipédia pour : " + " · ".join(f"« {k} »" for k in concepts))


def afficher_dynamiques(details: bool = False):
    for c in S.dynamiques:
        marque = ("✅" if c["statut"] == "validé" else f"☑️ retenu ({c['confiance']:.0%})"
                  if c["statut"] == "retenu" else "❓ À préciser — aucun filtre automatique")
        if c.get("etiquetage") == "en_attente":
            marque += " ⏳"
        st.markdown(f"{marque} **{c['id']} · {c['nom']}**  \n{c['regle']}  \n<small>« {c['citation']} »</small>",
                    unsafe_allow_html=True)
        if details and c.get("preuves") is not None:
            with st.expander(f"Preuves de {c['id']} · mot-clé {c['colonne']}"):
                st.caption(c.get("definition_mot_cle", ""))
                for v in c["preuves"]:
                    lien = f" ([source]({v['url']}))" if v.get("url") else f" ({v['source']})"
                    etat = {"oui": "lien établi", "partiel": "lien partiel", "non_concerne": "absence de lien étayée"}.get(v["valeur"], v["valeur"])
                    st.markdown(f"- **{v['ticker']}** : {etat} — « {v['preuve']} »{lien}")
                if not c["preuves"]:
                    st.markdown("- Aucun lien établi par cette recherche. Une absence de résultat ne vérifie pas l'absence d'exposition.")
                rech = c.get("recherche", {})
                couverture = rech.get("couverture", {})
                if couverture:
                    st.caption(f"Couverture : {couverture['avec_verdict']} actifs avec verdict étayé sur {couverture['total']}. "
                               f"{couverture['inconnus']} restent inconnus. Les principales positions des FNB donnent une exposition minimale connue.")
                if rech.get("inconnus"):
                    st.caption("Non vérifiés : " + ", ".join(rech["inconnus"]))
                st.caption(("Repris du cache (recherche déjà faite le " + rech.get("cree_le", "")[:10] + ")")
                           if rech.get("depuis_cache") else
                           f"Recherche en {rech.get('duree_s', '?')} s, {len(rech.get('appels_outils', []))} appel(s) "
                           f"d'outils, {len(rech.get('rejetes', []))} verdict(s) écarté(s) (preuve introuvable ou "
                           "refusée par le critique)")
        if details and criteres_dynamiques.a_confirmer(c):
            st.info(c["motif"] + ". Vous pouvez préciser la règle ici ; sinon elle reste non applicable.")
            with st.form(f"confirmation_{c['id']}"):
                pct = None
                if c["effet"] == "plafonner":
                    pct = st.number_input(f"Part maximale du portefeuille pour {c['nom']} (en %)",
                                          min_value=0, max_value=100, value=c.get("plafond_pct"), step=1)
                confirme = st.checkbox("Je confirme cette règle et la cible indiquée ci-dessus", value=False)
                envoyer = st.form_submit_button("Confirmer cette précision", type="primary")
            if envoyer:
                if not confirme:
                    st.warning("Cochez la confirmation si cette règle traduit votre intention.")
                else:
                    try:
                        criteres_dynamiques.confirmer(c, pct)
                    except ValueError as e:
                        st.warning(str(e))
                    else:
                        st.rerun()


# ---------- Phase 3 : profil ----------
def afficher_synthese():
    """Résumé chiffré du profil (synthese.py) : tout est calculé par le code, à partir d'hypothèses déclarées."""
    if S.get("persona"):
        st.info(f"Profil fictif de démonstration : **{S.persona['nom']}**. {S.persona['description']}")
    s = synthetiser(S.profil)
    st.subheader("Synthèse du profil")
    c1, c2, c3 = st.columns(3)
    c1.metric("Niveau de risque", f"{s['niveau']} sur 5 · {s['nom']}")
    c2.metric("Budget de perte du portefeuille", f"{s['budget_perte_pct']:g} %")
    c3.metric("Part d'actions indicative", f"{s['part_actions_indicative_pct'][0]} à {s['part_actions_indicative_pct'][1]} %")
    st.markdown(f"Limité par : **{', '.join(s['limite_par'])}**. Le plus prudent l'emporte.")
    lignes = []
    for nom, cle in (("Capacité (ce que vous pouvez perdre)", "capacite"), ("Tolérance déclarée", "tolerance_declaree"),
                     ("Tolérance observée (mises en situation)", "tolerance_observee")):
        for f in s[cle]["facteurs"]:
            lignes.append({"composante": nom, "critère": f["critere"], "réponse": f["valeur"], "effet": f["effet"]})
    st.dataframe(pd.DataFrame(lignes), hide_index=True, width="stretch")
    for a in s["alertes"]:
        st.warning(a)
    signaux = signaux_coherence(S.profil)
    if signaux:
        with st.expander("Observations sur vos choix — aucune réponse à répéter"):
            for signal in signaux:
                st.info(signal["texte"])
    if s["reglages_prudents_appliques"]:
        st.markdown("**Ce que l'outil ne sait pas** (réglage le plus prudent appliqué) : "
                    + ", ".join(f"{CRITERES[d['critere']]['nom']} → `{d['valeur']}`" for d in s["reglages_prudents_appliques"]))
    st.caption("Hypothèse : les tables de capacité, de stress et de part d'actions sont des hypothèses de l'équipe "
               "(hypotheses_profil.json), pas des normes. Simulation éducative : ce résumé n'est pas un conseil financier.")
    if s["synthese_provisoire"]:
        st.info("Cette synthèse reste provisoire : des réponses ou des besoins de liquidité restent à préciser.")
    st.markdown("**Les réponses qui déterminent votre profil**")
    for r in s["reponses_decisives"][:6]:
        st.markdown(f"- **{r['nom']}** : {r['raison']}")
        if r["citation"]:
            st.caption(f"Votre réponse : « {r['citation']} » · {r['source']} · {r['statut']}")
    if len(s["reponses_decisives"]) > 6:
        with st.expander("Toutes les réponses déterminantes et les contraintes"):
            st.dataframe(pd.DataFrame([{"critère": r["nom"], "pourquoi": r["raison"],
                                       "votre réponse": r["citation"] or r["valeur"], "source": r["source"]}
                                      for r in s["reponses_decisives"]]), hide_index=True, width="stretch")
    rb = s["robustesse"]
    st.markdown("**Que se passe-t-il si une réponse voisine change ?**")
    if rb["etat"] == "a_completer":
        st.write("Des informations manquent ou restent incertaines : confirmez-les avant d'interpréter la stabilité du profil.")
    elif rb["etat"] == "sensible":
        st.write("Le résultat est sensible à au moins une réponse voisine. Les points ci-dessous méritent une relecture.")
    elif rb["etat"] == "stable_localement":
        st.write("Le résultat reste stable pour les petites variations testées, une réponse à la fois.")
    if rb["variations_testees"]:
        st.caption(f"Budget de perte recalculé : de {rb['budget_min_pct']:g} à {rb['budget_max_pct']:g} %. "
                   f"{rb['variations_testees']} variantes locales testées. Il s'agit d'une sensibilité des règles, pas d'une probabilité ni d'une perte garantie.")
    with st.expander("Détail des variations et limites de cette vérification"):
        if rb["variations_sensibles"]:
            st.dataframe(pd.DataFrame([{"réponse": v["nom"], "avant": libelle_valeur(v["critere"], v["avant"]),
                                        "variante": libelle_valeur(v["critere"], v["apres"]),
                                        "budget de perte (%)": v["budget_perte_pct"], "niveau": v["niveau"],
                                        "variation (points)": v["ecart_budget_points"]}
                                       for v in rb["variations_sensibles"]]), hide_index=True, width="stretch")
        st.caption(rb["limites"])

def page_termine():
    st.success("Profil terminé. Merci !")
    retours_situations()
    n = len(S.profil)
    retenus = [c for c, v in S.profil.items() if v["statut"] == "retenu"]
    incertains = [c for c, v in S.profil.items() if v["statut"] not in UTILISABLES]
    st.write(f"**{n} critères** renseignés, dont **{n - len(retenus) - len(incertains)} validés**"
             + (f", {len(retenus)} retenus avec une confiance plus basse ({', '.join(retenus)})" if retenus else "")
             + (f" et {len(incertains)} incertains ({', '.join(incertains)}) : l'outil appliquera le réglage le plus prudent."
                if incertains else "."))
    afficher_synthese()
    integrer_recherches()
    if S.dynamiques:
        st.markdown(f"**{len(S.dynamiques)} critère(s) propre(s) à vous**, tirés de votre dernière réponse :")
        suivi_recherches()
        afficher_dynamiques(details=True)
    elif S.reponse_ouverte:
        st.caption("Votre dernière réponse n'a pas donné de critère supplémentaire.")


# ---------- Mise en page ----------
st.title("Votre profil d'investisseur")
if S.phase == "conversation" and S.conv and "versions_reponses" not in S.conv:
    # Rechargement d'une ancienne version : conserver les paroles et les faits déjà fournis.
    ancien = S.conv
    S.conv = moteur_conversation.creer(S.questions_posees)
    for question, reponse in ancien.get("echanges", []):
        S.conv["question"] = S.conv["question_cible"] = question
        moteur_conversation.recevoir(S.conv, S.profil, reponse)
    S.conv["fin"] = True
    S.sections = sections_apres_conversation([cid for cid in CRITERES_CONVERSATION if not connu(S.profil, cid)])
    S.section, S.phase = 0, "questionnaire"
    st.info("Le parcours a été mis à jour. Vos réponses sont conservées ; les informations reconnues ne seront pas redemandées.")
st.info("**Simulation éducative.** Cet outil n'exécute aucune transaction et ne fournit pas de conseil financier "
        "personnalisé. Les profils et les montants sont fictifs.", icon="ℹ️")
if not pret:
    st.warning("Aucun accès au modèle : lancez le site avec les identifiants AWS du datathon (voir mvp_profil/README.md), "
               "ou choisissez « API Anthropic » et collez une clé.")

col, col_profil = st.columns([3, 2], gap="large")
with col:
    ENONCE = barre_vocale()  # premier élément de la colonne, dans toutes les phases vocales : jamais recréé
    {"accueil": page_accueil, "conversation": page_conversation, "questionnaire": page_questionnaire,
     "simulations": page_simulations, "libre_oral": page_libre_oral, "precisions": page_precisions, "ouverte": page_ouverte,
     "termine": page_termine}[S.phase]()
    if S.debats and S.debats[-1]["tours"]:
        d = S.debats[-1]
        with st.expander(f"Journal des contrôles de la dernière réponse libre ({d['question']}, {len(d['tours'])} passage(s))"):
            st.caption("Contrôles vérifiables : valeur proposée, citation exacte de vos mots, confiance, accord ou "
                       "objection du second contrôle. Le code valide ; les modèles ne décident pas.")
            for t in d["tours"]:
                st.markdown(f"**Tour {t['tour']}** · validés : {', '.join(t['valides']) or 'aucun'}")
                c1, c2 = st.columns(2)
                with c1:
                    st.caption("Classificateur")
                    for p in t["classificateur"]["propositions"]:
                        st.markdown(f"- `{p['critere_id']}` → **{', '.join(p['valeurs']) or '—'}** ({p['confiance']:.0%}) : « {p['citation']} »")
                with c2:
                    st.caption("Critique")
                    if not t["critique"]:
                        st.markdown("- Non consulté : le classificateur n'était pas assez sûr")
                    else:
                        for a in t["critique"]["avis"]:
                            st.markdown(f"- `{a['critere_id']}` ({a['confiance']:.0%}) "
                                        + ("✅ d'accord" if a["accord"] else f"❌ {a['objection']}"))

with col_profil:
    if S.phase == "conversation":
        st.subheader("Critères de la conversation")
        liste_criteres_conversation()
        st.divider()
    st.subheader("Profil en cours")
    en_attente = sum(1 for j in S.en_cours if not j["future"].done())
    if en_attente:
        st.caption(f"⏳ {en_attente} réponse(s) libre(s) en cours d'analyse par les agents…")
    if S.profil:
        df = pd.DataFrame([{"id": c, "critère": CRITERES[c]["nom"], "valeurs": ", ".join(v["valeurs"]) or "—",
                            "nature": nature(v["source"]), "source": v["source"], "confiance": v["confiance"],
                            "statut": v["statut"]}
                           for c, v in S.profil.items()])
        st.dataframe(df, hide_index=True, width="stretch")
        if S.dynamiques:
            st.markdown("**Critères propres à vous**")
            afficher_dynamiques()
        export = {"genere_le": datetime.now().isoformat(timespec="seconds"), "version_application": version_courante(), "modele": backend_pour(cle).model,
                  "acces": backend_pour(cle).nom, "seuil": seuil, "profil": S.profil,
                  "criteres_dynamiques": S.dynamiques, "reponse_ouverte": S.reponse_ouverte, "debats": S.debats,
                  "replay": S.get("replay_trace"), "synthese": synthetiser(S.profil) if S.phase == "termine" else None,
                  "persona": (S.get("persona") or {}).get("nom"),
                  "parcours": {"questions_posees": S.questions_posees,
                               "evenements": (S.conv or {}).get("evenements", []) + S.evenements_questions,
                               "echanges_oraux": (S.conv or {}).get("echanges", [])}}
        st.download_button("Télécharger le profil (JSON)", json.dumps(export, ensure_ascii=False, indent=2, default=str),
                           file_name="profil_investisseur.json", mime="application/json", width="stretch")
    else:
        st.caption("Les critères apparaîtront ici au fil de vos réponses.")
