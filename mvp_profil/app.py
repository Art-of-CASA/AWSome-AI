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
from agents import (AgentError, aws_identifiants_presents, backend_anthropic, backend_bedrock, debattre, meilleur,
                    retenable, seuil_essai, _citation_presente)
from criteres import CRITERES, DECLARATIFS, SECTIONS, est_deduit
from criteres_dynamiques import AIDE_OUVERTE, QUESTION_OUVERTE
from entretien import CRITERES_CONVERSATION, MAX_TOURS, OUVERTURE, synthese_vocale, transcrire
from voix_composant import conversation_vocale
from profil import (UTILISABLES, appliquer_correctif, connu, deduire, entree, incoherences, niveau_quiz,
                    recouper_rupture, valeur_curseur)
from simulations import ETAPES
from synthese import phrase, synthetiser, libelle_valeur
from pilotage import prioriser_criteres, prioriser_items, prioriser_sections

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
        meilleurs={}, dynamiques=[], reponse_ouverte="", recherches=[],
        # Composant vocal UNIQUE (conversation, précisions, question ouverte) : n = numéro de la dernière phrase de l'IA,
        # ack = dernier énoncé de l'utilisateur traité, etape = question en cours, actif = l'utilisateur a parlé
        vocal={"n": 0, "ack": 0, "audio": "", "fin": False, "etape": None, "actif": False}, retires=0)


if "phase" not in st.session_state:
    reset()
S = st.session_state

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
    voix = st.toggle("Lire les questions à voix haute (Amazon Polly)", value=True)
    st.caption("Modèle : Claude Haiku 5.5 (classificateur et critique)")
    if st.button("Recommencer", width="stretch"):
        reset()
        st.rerun()
    st.caption("Simulation éducative. Aucun conseil financier personnalisé.")


@st.cache_resource
def backend_pour(key: str):
    return backend_anthropic(key) if key else backend_bedrock()


@st.cache_resource
def executeur() -> ThreadPoolExecutor:
    return ThreadPoolExecutor(max_workers=4)


def a_preciser(criteres: list[str], texte: str | None = None, echanges=None, motif="Réponse « Je ne sais pas »"):
    for cid in criteres:
        S.profil[cid] = entree([], "à préciser", statut="à préciser", confiance=0.0, motif=motif)
    S.file.append({"kind": "libre", "criteres": list(criteres), "essai": 0, "echanges": list(echanges or []),
                   "texte": texte or CRITERES[criteres[0]]["relance"]})


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
        elif definitif:
            retenir_meilleure(cid, "réponse libre (IA)")
        else:
            restants.append(cid)
    return restants


# ---------- Accueil : choix du parcours ----------
def page_accueil():
    st.write("Deux façons de commencer. Dans les deux cas, vous aurez ensuite quelques questions à choix, trois mises "
             "en situation, puis votre profil.")
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("**🎙️ Conversation (recommandé)**\n\nUne courte discussion, à l'oral ou à l'écrit : l'IA pose les "
                    "questions sur votre projet et votre situation, et coche les critères au fur et à mesure.")
        if st.button("Commencer en conversation", type="primary", disabled=not pret, width="stretch"):
            # suivi : {critère: nb de réponses au moment où il a été jugé « à reformuler »} ; reformules : déjà redemandés
            S.conv = {"echanges": [], "question": OUVERTURE, "restants": list(CRITERES_CONVERSATION), "jobs": [],
                      "analyses_couvertes": {}, "versions_integrees": {}, "revisions": {}, "relances_posees": {},
                      "tours": 0, "fin": False, "erreur": None, "suivi": {}, "reformules": []}
            dire(OUVERTURE, "conv:0")
            S.phase = "conversation"
            st.rerun()
    with c2.container(border=True):
        st.markdown("**📝 Questionnaire classique**\n\nToutes les questions sous forme de choix et de réponses "
                    "écrites, page par page.")
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
    """Coalesce les réponses arrivées pendant un contrôle, sans analyser deux fois le même instantané."""
    c = S.conv
    n = len(c["echanges"])
    if not n:
        return
    en_verif = {cid for j in c["jobs"] for cid in j["criteres"] + j.get("facultatifs", [])}
    couvertes = c.setdefault("analyses_couvertes", {})
    revisions = list(c.setdefault("revisions", {}))
    candidats = prioriser_criteres(S.profil, list(dict.fromkeys(c["restants"] + revisions)))
    a_couvrir = [cid for cid in candidats if cid not in en_verif and couvertes.get(cid, 0) < n]
    autres = [cid for cid in facultatifs(list(CRITERES_CONVERSATION) + revisions)
              if cid not in en_verif and couvertes.get(cid, 0) < n]
    if not a_couvrir and not autres:
        return
    relances = c.setdefault("relances_posees", {})
    seuils = {cid: seuil_essai(seuil, 1 if cid in relances and n > relances[cid] else 0)
              for cid in a_couvrir + autres}
    fut = executeur().submit(entretien.analyser, backend_pour(cle), list(c["echanges"]), a_couvrir, seuils, autres)
    c["jobs"].append({"future": fut, "criteres": a_couvrir, "facultatifs": autres, "n": n,
                      "revisions": {cid: c["revisions"][cid] for cid in a_couvrir if cid in revisions}})
    couvertes.update({cid: n for cid in a_couvrir + autres})


def appliquer_verifications():
    """Intègre les vérifications du critique terminées en arrière-plan.

    - validé -> coché ✅ ;
    - abordé mais pas assez sûr -> « à reformuler » : l'IA le redemande UNE fois, autrement ; quand la réponse à cette
      reformulation est analysée, on tranche : meilleure réponse « retenue » (>= 50 %) ou renvoi au QCM des Compléments ;
    - jamais abordé (aucune valeur) -> reste à couvrir.
    """
    c = S.conv
    for job in [j for j in c["jobs"] if j["future"].done()]:
        if job["n"] < len(c["echanges"]):
            c["jobs"].remove(job)
            continue  # le rattrapage vérifiera le dernier texte, qui peut corriger l'ancien
        try:
            resultats = job["future"].result()
        except AgentError:
            resultats = {}
        for cid in job["criteres"]:
            versions = c.setdefault("versions_integrees", {})
            if job["n"] < versions.get(cid, 0):
                continue  # une ancienne tâche ne remplace jamais une réponse plus récente
            versions[cid] = job["n"]
            r = resultats.get(cid)
            revision = cid in job.get("revisions", [])
            if revision:
                tour_correction = job["revisions"][cid]
                if r and r.valide and r.valeurs == S.profil[cid]["valeurs"]:
                    c["revisions"].pop(cid, None)
                    continue  # information inchangée : ne pas la reclasser à chaque tour suivant
                if not r or not _citation_presente(r.citation, c["echanges"][tour_correction - 1:job["n"]]):
                    continue  # une ancienne citation ne prouve pas une correction de la dernière réponse
                if c["revisions"].get(cid, 0) <= job["n"]:
                    c["revisions"].pop(cid, None)
                if r.valeurs == S.profil[cid]["valeurs"]:
                    continue
                if not r.valide:
                    precedent = S.profil[cid]
                    S.profil[cid] = entree([], "correction à préciser", statut="à préciser", confiance=0.0,
                                           motif="La correction doit être clarifiée", precedent=precedent)
                    if cid not in CRITERES_CONVERSATION:
                        a_preciser([cid], echanges=list(c["echanges"]), motif="Correction à confirmer")
                        continue
                    if cid not in c["restants"]:
                        c["restants"].append(cid)
            if r is not None and r.valeurs:
                S.meilleurs[cid] = meilleur(S.meilleurs.get(cid), r)
            if r is not None and r.valide:
                S.profil[cid] = entree(r.valeurs, source_ia(r, "conversation (IA)"), r.citation, r.confiance,
                                       motif=r.motif if est_deduit(r.motif) else "")
                _clore(cid)
            elif r is not None and r.valeurs:
                if cid not in c["suivi"]:
                    c["suivi"][cid] = len(c["echanges"])  # la prochaine réplique le reformulera
                elif cid in c.get("relances_posees", {}) and job["n"] > c["relances_posees"][cid]:
                    retenir_meilleure(cid, "conversation (IA)")
                    _clore(cid)
                if cid in c["suivi"] and cid not in c["restants"]:
                    c["restants"].append(cid)
            elif cid not in c["restants"] and S.profil.get(cid, {}).get("statut") not in UTILISABLES:
                c["restants"].append(cid)
        for cid in job.get("facultatifs", []):  # dit au passage : validé, donc ne sera plus demandé
            r = resultats.get(cid)
            if r is not None and r.valide and not connu(S.profil, cid):
                S.profil[cid] = entree(r.valeurs, source_ia(r, "conversation (IA)"), r.citation, r.confiance,
                                       motif=r.motif if est_deduit(r.motif) else "")
        for cid in deduire(S.profil):
            _clore(cid)
        S.debats.append({"question": "conversation", "tours": [],
                         "resultats": {k: vars(v) for k, v in resultats.items()}})
        c["jobs"].remove(job)
    planifier_analyse_conversation()


def fin_conversation():
    c = S.conv
    with st.spinner("Les agents terminent leurs vérifications…"):
        planifier_analyse_conversation()
        while c["jobs"]:
            for job in list(c["jobs"]):
                job["future"].result() if not job["future"].exception() else None
            appliquer_verifications()
    for cid in list(c["suivi"]):  # reformulation sans réponse claire : meilleure réponse obtenue
        if cid in c["reformules"] and retenir_meilleure(cid, "conversation (IA)"):
            _clore(cid)
    manquants = [cid for cid in CRITERES_CONVERSATION if S.profil.get(cid, {}).get("statut") not in UTILISABLES]
    S.sections, S.section, S.phase = sections_apres_conversation(manquants), 0, "questionnaire"
    st.rerun()


# ---------- Voix : un composant UNIQUE pour la conversation, les précisions et la question ouverte ----------
PHASES_VOCALES = ("conversation", "precisions", "ouverte")


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
    veille = S.phase not in PHASES_VOCALES
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
    """Un tour de conversation : on n'attend que la réplique ; le classement part en arrière-plan."""
    c = S.conv
    c["echanges"].append((c["question"], texte))
    if entretien.demande_correction(texte):
        c.setdefault("revisions", {}).update({cid: len(c["echanges"]) for cid in DECLARATIFS if connu(S.profil, cid)})
    planifier_analyse_conversation()
    # L'IA reformule une seule fois ce qui a été abordé sans être clair, et ne redemande jamais un sujet déjà reformulé.
    a_reformuler = prioriser_criteres(S.profil, [cid for cid in c["restants"] if cid in c["suivi"] and cid not in c["reformules"]])[:1]
    nouveaux = prioriser_criteres(S.profil, [cid for cid in c["restants"] if cid not in c["suivi"]])
    try:
        pistes = {cid: (S.meilleurs[cid].valeurs, S.meilleurs[cid].citation) for cid in a_reformuler
                  if S.meilleurs.get(cid) and S.meilleurs[cid].valeurs}  # « si je comprends bien… ? »
        rep = entretien.replique(backend_pour(cle), c["echanges"], nouveaux, a_reformuler, pistes)
    except AgentError as e:
        c["erreur"] = str(e)
        c["question"] = "La réponse vocale est indisponible. Votre réponse est conservée ; vous pouvez continuer ou passer aux questions à choix."
        st.rerun()
    c["reformules"] += a_reformuler
    c.setdefault("relances_posees", {}).update({cid: len(c["echanges"]) for cid in a_reformuler})
    c["tours"] += 1
    fin = rep.termine or c["tours"] >= MAX_TOURS
    message = rep.message if rep.termine or not fin else \
        "Merci beaucoup, j'ai l'essentiel. On continue avec quelques questions à choix."
    c.update(question=message, fin=fin, erreur=None)
    dire(message, f"conv:{c['tours']}", fin=fin)
    st.rerun()


def page_conversation():
    c = S.conv
    appliquer_verifications()
    fait = len(CRITERES_CONVERSATION) - len(c["restants"])
    st.progress(fait / len(CRITERES_CONVERSATION), text=f"Conversation · {fait} critères sur {len(CRITERES_CONVERSATION)} cochés")
    # La voix passe par le composant unique, en haut de la page (barre_vocale) : il n'est jamais recréé.
    if ENONCE and ENONCE["kind"] == "termine":
        fin_conversation()
    if ENONCE:
        if ENONCE["texte"]:
            repondre(ENONCE["texte"])
        st.rerun()  # rien compris : l'accusé de réception relance l'écoute
    if c["erreur"]:
        st.warning(c["erreur"])
    st.caption("Transcription de la conversation")
    for q, r in c["echanges"]:
        st.chat_message("assistant").write(q)
        st.chat_message("user").write(r)
    st.chat_message("assistant").write(c["question"])
    if c["fin"]:
        if st.button("Continuer vers les questions suivantes", type="primary"):
            fin_conversation()
        return
    ecrit = st.chat_input("…ou écrivez votre réponse")
    if st.button("Passer aux questions suivantes", help="Ce qui n'est pas coché sera demandé sous forme de questions."):
        fin_conversation()
    if ecrit:
        repondre(ecrit)


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
    crits = it.get("criteres", [it.get("critere")])
    inconnus = [c for c in crits if not connu(S.profil, c) and S.profil.get(c, {}).get("statut") != "analyse en cours"]
    if not inconnus:
        return None
    return {**it, "criteres": inconnus} if it["type"] == "libre" else it


def page_questionnaire():
    SECTIONS = S.sections  # noqa: N806  (questionnaire complet, ou questions restantes après la conversation)
    if not SECTIONS:
        S.phase = "simulations"
        st.rerun()
    # Questions DYNAMIQUES : ce que les réponses libres (terminées en arrière-plan) ont appris, ou ce qui se déduit
    # d'une réponse, n'est plus demandé.
    recuperer_analyses(attendre=False)
    deduire(S.profil)
    sec = SECTIONS[S.section]
    items = prioriser_items(S.profil, [x for x in (a_demander(it) for it in sec["items"]) if x])
    retires = [it for it in sec["items"] if not a_demander(it)]
    if not items:
        S.retires += len(retires)
        S.section += 1
        if S.section >= len(SECTIONS):
            S.phase = "simulations"
        st.rerun()
    st.progress(S.section / len(SECTIONS), text=f"Étape {S.section + 1} sur {len(SECTIONS)} · {sec['titre']}")
    if retires:
        noms = ", ".join(CRITERES[c]["nom"].lower() for it in retires for c in it.get("criteres", [it.get("critere")]))
        st.caption(f"✨ {len(retires)} question(s) retirée(s) : vous y avez déjà répondu, ou cela se déduit de vos "
                   f"réponses ({noms}).")
    with st.form(f"section_{S.section}"):
        rep = {}
        for it in items:
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
            elif it["type"] == "libre":
                rep[it["id"]] = st.text_area(it["texte"], placeholder=it.get("aide", ""), key=k)
        envoye = st.form_submit_button("Continuer" if S.section < len(SECTIONS) - 1 else "Terminer le questionnaire",
                                       type="primary", disabled=not pret)
    if not envoye:
        return
    manquants = [it["texte"] for it in items
                 if (it["type"] == "qcm" and rep[it["id"]] is None)
                 or (it["type"] == "quiz" and any(r is None for r in rep[it["id"]]))]
    if manquants:
        st.warning("Merci de répondre à : " + " · ".join(manquants))
        return
    S.retires += len(retires)
    for it in items:
        r = rep[it["id"]]
        if it["type"] == "qcm":
            val = dict(it["options"])[r]
            if val is None:
                a_preciser([it["critere"]])
            else:
                S.profil[it["critere"]] = entree([val], "QCM", citation=r)
        elif it["type"] == "qcm_multi":
            vals = [dict(it["options"])[x] for x in r]
            if len(vals) > 1:  # « Aucun(e) » coché avec d'autres cases : on garde les autres
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
        elif it["type"] == "libre":
            if not r.strip():
                a_preciser(it["criteres"], motif="Réponse libre vide")
            else:
                for cid in it["criteres"]:
                    S.profil[cid] = entree([], "réponse libre (IA)", statut="analyse en cours", confiance=0.0)
                ech = [(it["texte"], r.strip())]
                fut = executeur().submit(debattre, backend_pour(cle), ech, it["criteres"], seuil, max_tours,
                                         facultatifs(it["criteres"]))  # ce qui est dit au passage est aussi gardé
                S.en_cours.append({"item": it["id"], "criteres": it["criteres"], "echanges": ech, "future": fut})
    S.section += 1
    if S.section >= len(SECTIONS):
        S.phase = "simulations"
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
                a_preciser(job["criteres"], echanges=job["echanges"], motif=str(e))
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
    ech = item["echanges"] + [(item["texte"], reponse)]
    try:
        with st.spinner("Les deux agents analysent votre réponse…"):
            # Une précision est déjà une 2e tentative (question reformulée) : seuil abaissé. Ce qui est dit au passage
            # sur d'autres critères encore inconnus est gardé aussi (facultatifs).
            debat = debattre(backend_pour(cle), ech, item["criteres"], seuil=seuil_essai(seuil, item["essai"] + 1),
                             max_tours=max_tours, facultatifs=facultatifs(item["criteres"]))
    except AgentError as e:
        st.error(str(e))
        return
    S.chat += [{"role": "assistant", "content": item["texte"]}, {"role": "user", "content": reponse}]
    S.file.pop(0)
    dernier_essai = item["essai"] + 1 >= MAX_RELANCES
    restants = enregistrer_debat(debat, "précision", definitif=dernier_essai)
    if restants:
        S.file.insert(0, {"kind": "libre", "criteres": restants, "essai": item["essai"] + 1, "echanges": ech,
                          "texte": debat.question_relance or CRITERES[restants[0]]["relance"]})
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
    etape = f"prec:{len(S.chat)}"
    dire(oral(item), etape)  # la question est lue à voix haute ; on peut répondre à l'oral ou au clavier
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
    reponse = st.chat_input("Votre réponse…", disabled=not pret) or dit
    if reponse:
        repondre_precision(item, reponse)


# ---------- Phase 2 bis : question ouverte -> critères dynamiques ----------
def page_ouverte():
    retours_situations()
    st.subheader("Une dernière chose")
    st.caption("Ce que vous dites ou écrivez ici devient des critères propres à vous, ajoutés à votre profil.")
    dire(QUESTION_OUVERTE, "ouverte")
    dit = entendu()
    if dit and entretien.demande_repetition(dit):
        redire(QUESTION_OUVERTE, "ouverte")
        st.rerun()
    with st.form("ouverte"):
        texte = st.text_area(QUESTION_OUVERTE, placeholder=AIDE_OUVERTE, height=130)
        c1, c2 = st.columns(2)
        envoyer = c1.form_submit_button("Envoyer", type="primary", disabled=not pret, width="stretch")
        rien = c2.form_submit_button("Je n'ai rien à ajouter", width="stretch")
    if dit:
        texte, envoyer = dit, True
    if rien or (envoyer and not texte.strip()):
        S.phase = "termine"
        st.rerun()
    if not envoyer:
        return
    try:
        with st.spinner("Les agents créent vos critères personnels…"):
            nouveaux = criteres_dynamiques.creer(backend_pour(cle), QUESTION_OUVERTE, texte.strip(), seuil,
                                                 deja=len(S.dynamiques))
    except AgentError as e:
        st.error(str(e))
        return
    S.dynamiques += nouveaux
    for c in nouveaux:  # idées sans valeur existante : le chercheur crée le mot-clé pendant que le profil s'affiche
        if c.get("etiquetage") == "en_attente":
            fut = executeur().submit(chercheur.etiqueter, backend_pour(cle), c["concept"], c["effet"])
            S.recherches.append({"id": c["id"], "future": fut})
    S.reponse_ouverte = texte.strip()
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
st.info("**Simulation éducative.** Cet outil n'exécute aucune transaction et ne fournit pas de conseil financier "
        "personnalisé. Les profils et les montants sont fictifs.", icon="ℹ️")
if not pret:
    st.warning("Aucun accès au modèle : lancez le site avec les identifiants AWS du datathon (voir mvp_profil/README.md), "
               "ou choisissez « API Anthropic » et collez une clé.")

col, col_profil = st.columns([3, 2], gap="large")
with col:
    ENONCE = barre_vocale()  # premier élément de la colonne, dans toutes les phases vocales : jamais recréé
    {"accueil": page_accueil, "conversation": page_conversation, "questionnaire": page_questionnaire,
     "simulations": page_simulations, "precisions": page_precisions, "ouverte": page_ouverte,
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
        export = {"genere_le": datetime.now().isoformat(timespec="seconds"), "modele": backend_pour(cle).model,
                  "acces": backend_pour(cle).nom, "seuil": seuil, "profil": S.profil,
                  "criteres_dynamiques": S.dynamiques, "reponse_ouverte": S.reponse_ouverte, "debats": S.debats,
                  "replay": S.get("replay_trace"), "synthese": synthetiser(S.profil) if S.phase == "termine" else None,
                  "persona": (S.get("persona") or {}).get("nom")}
        st.download_button("Télécharger le profil (JSON)", json.dumps(export, ensure_ascii=False, indent=2, default=str),
                           file_name="profil_investisseur.json", mime="application/json", width="stretch")
    else:
        st.caption("Les critères apparaîtront ici au fil de vos réponses.")
