"""MVP AlphaForge : profil d'investisseur.

Parcours « conversation » (recommandé) : une discussion orale ou écrite avec l'IA couvre les questions de contexte
(projet, situation, expérience, thèmes) et coche les critères au fur et à mesure ; ce qu'elle n'a pas validé revient
en QCM dans une page « Compléments », puis le parcours continue comme ci-dessous à partir de la page « Vous et le risque ».

Parcours « questionnaire classique » :
  1. Questionnaire FIXE (identique pour tous) en 6 pages : QCM, curseurs, quiz, et 2 questions libres.
     Les réponses fermées donnent directement les valeurs (pas d'IA). Les réponses libres sont classées
     par deux agents Claude Haiku 5.5 qui débattent, EN ARRIÈRE-PLAN pendant que l'utilisateur continue.
  1 bis. Trois mises en situation (replay de 2022, fourchettes de résultats, effet de mode) : on mesure ce que
     l'utilisateur FAIT et on le compare à ce qu'il a déclaré (le plus prudent l'emporte).
  2. Précisions de fin de parcours : réponses vagues, « Je ne sais pas » et contradictions entre réponses.
  3. Profil final, téléchargeable en JSON avec la trace des débats.

Lancer :  streamlit run mvp_profil/app.py
Modèle : Claude Haiku 5.5 sur Amazon Bedrock (compte AWS du datathon) ; secours : clé de l'API Anthropic.
Simulation uniquement : aucun conseil financier, aucune transaction.
"""
from __future__ import annotations

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pandas as pd
import streamlit as st

from agents import AgentError, aws_identifiants_presents, backend_anthropic, backend_bedrock, debattre
from criteres import CRITERES, SECTIONS
from entretien import CRITERES_CONVERSATION, MAX_TOURS, OUVERTURE, analyser, replique, synthese_vocale, transcrire
from voix_composant import conversation_vocale
from profil import appliquer_correctif, entree, incoherences, niveau_quiz, recouper_rupture, valeur_curseur
from simulations import ETAPES

MAX_RELANCES = 2  # précisions par critère avant de le marquer « incertain »

st.set_page_config(page_title="AlphaForge · Profil", page_icon="📊", layout="wide")


def reset():
    for k in ("rp", "replay_trace", "mode_revelation"):
        st.session_state.pop(k, None)
    st.session_state.update(
        phase="accueil", section=0, sections=SECTIONS, profil={}, en_cours=[], file=[], coherences_posees=set(),
        debats=[], chat=[], precisions_pretes=False, sim_etape=0, message_rupture=None, conv=None)


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


def enregistrer_debat(debat, item_id: str, definitif: bool) -> list[str]:
    S.debats.append({"question": item_id, "tours": debat.tours,
                     "resultats": {c: vars(r) for c, r in debat.resultats.items()}})
    restants = []
    for cid, r in debat.resultats.items():
        if r.valide:
            S.profil[cid] = entree(r.valeurs, "réponse libre (IA)", r.citation, r.confiance)
        elif definitif:
            S.profil[cid] = entree(r.valeurs, "réponse libre (IA)", r.citation, r.confiance, "incertain", r.motif)
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
            S.conv = {"echanges": [], "question": OUVERTURE, "restants": list(CRITERES_CONVERSATION), "jobs": [],
                      "tours": 0, "audio": voix_b64(OUVERTURE), "n": 1, "ack": 0, "fin": False, "erreur": None}
            S.phase = "conversation"
            st.rerun()
    with c2.container(border=True):
        st.markdown("**📝 Questionnaire classique**\n\nToutes les questions sous forme de choix et de réponses "
                    "écrites, page par page.")
        if st.button("Questionnaire classique", disabled=not pret, width="stretch"):
            S.phase, S.sections = "questionnaire", SECTIONS
            st.rerun()


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
    return ([{"titre": "Compléments", "items": complements}] if complements else []) + restes


def appliquer_verifications():
    """Intègre les vérifications du critique terminées en arrière-plan (coche ✅ ou remet à couvrir)."""
    c = S.conv
    for job in [j for j in c["jobs"] if j["future"].done()]:
        try:
            resultats = job["future"].result()
        except AgentError:
            resultats = {}
        for cid in job["criteres"]:
            r = resultats.get(cid)
            if r is not None and r.valide:
                S.profil[cid] = entree(r.valeurs, "conversation (IA)", r.citation, r.confiance)
                if cid in c["restants"]:
                    c["restants"].remove(cid)
            elif cid not in c["restants"]:
                c["restants"].append(cid)
        S.debats.append({"question": "conversation", "tours": [],
                         "resultats": {k: vars(v) for k, v in resultats.items()}})
        c["jobs"].remove(job)


def fin_conversation():
    c = S.conv
    with st.spinner("Les agents terminent leurs vérifications…"):
        for job in c["jobs"]:
            job["future"].result() if not job["future"].exception() else None
    appliquer_verifications()
    manquants = [cid for cid in CRITERES_CONVERSATION if cid not in S.profil or S.profil[cid]["statut"] != "validé"]
    S.sections, S.section, S.phase = sections_apres_conversation(manquants), 0, "questionnaire"
    st.rerun()


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
    en_verif = {cid for j in c["jobs"] for cid in j["criteres"]}
    a_couvrir = [cid for cid in c["restants"] if cid not in en_verif]
    c["echanges"].append((c["question"], texte))
    if a_couvrir:  # classificateur puis critique, pendant que l'IA parle et que l'utilisateur répond
        fut = executeur().submit(analyser, backend_pour(cle), list(c["echanges"]), a_couvrir, seuil)
        c["jobs"].append({"future": fut, "criteres": a_couvrir})
    try:
        rep = replique(backend_pour(cle), c["echanges"], c["restants"])
    except AgentError as e:
        c["echanges"].pop()
        c["erreur"] = str(e)
        st.rerun()
    c["tours"] += 1
    fin = rep.termine or c["tours"] >= MAX_TOURS
    message = rep.message if rep.termine or not fin else \
        "Merci beaucoup, j'ai l'essentiel. On continue avec quelques questions à choix."
    c.update(question=message, fin=fin, audio=voix_b64(message), n=c["n"] + 1, erreur=None)
    st.rerun()


def page_conversation():
    c = S.conv
    appliquer_verifications()
    fait = len(CRITERES_CONVERSATION) - len(c["restants"])
    st.progress(fait / len(CRITERES_CONVERSATION), text=f"Conversation · {fait} critères sur {len(CRITERES_CONVERSATION)} cochés")
    # Composant vocal à une position FIXE (juste sous la barre de progression) : il n'est jamais recréé quand la
    # page se rafraîchit, donc la voix de l'IA n'est plus coupée et le micro reste actif.
    valeur = conversation_vocale(audio_b64=c["audio"], n=c["n"], ack=c["ack"], fin=c["fin"], voix=voix, key="voix")
    if valeur and valeur.get("n", 0) > c["ack"]:
        c["ack"] = valeur["n"]
        if valeur["kind"] == "termine":
            fin_conversation()
        texte = ""
        try:
            with st.spinner("Transcription (Amazon Transcribe)…"):
                texte = transcrire(base64.b64decode(valeur["wav"]))
        except AgentError as e:
            c["erreur"] = str(e)
        if texte:
            repondre(texte)
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
        if v and v["statut"] == "validé":
            st.markdown(f"✅ **{CRITERES[cid]['nom']}** : {', '.join(v['valeurs'])}  \n<small>« {v['citation']} »</small>",
                        unsafe_allow_html=True)
        elif cid in en_verif:
            st.markdown(f"⏳ {CRITERES[cid]['nom']} : vérification par le critique…")
        else:
            st.markdown(f"○ {CRITERES[cid]['nom']}")


# ---------- Phase 1 : questionnaire fixe ----------
def page_questionnaire():
    SECTIONS = S.sections  # noqa: N806  (questionnaire complet, ou questions restantes après la conversation)
    if not SECTIONS:
        S.phase = "simulations"
        st.rerun()
    sec = SECTIONS[S.section]
    st.progress(S.section / len(SECTIONS), text=f"Étape {S.section + 1} sur {len(SECTIONS)} · {sec['titre']}")
    with st.form(f"section_{S.section}"):
        rep = {}
        for it in sec["items"]:
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
    manquants = [it["texte"] for it in sec["items"]
                 if (it["type"] == "qcm" and rep[it["id"]] is None)
                 or (it["type"] == "quiz" and any(r is None for r in rep[it["id"]]))]
    if manquants:
        st.warning("Merci de répondre à : " + " · ".join(manquants))
        return
    for it in sec["items"]:
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
                S.profil[it["critere"]] = entree([valeur_curseur(it, r)], "curseur", citation=f"{r} {it['unite']}")
        elif it["type"] == "quiz":
            idx = [q["options"].index(x) for q, x in zip(it["questions"], r)]
            niveau, score = niveau_quiz(it, idx)
            S.profil[it["critere"]] = entree([niveau], "quiz", citation=f"{score}/{len(it['questions'])} bonnes réponses")
        elif it["type"] == "libre":
            if not r.strip():
                a_preciser(it["criteres"], motif="Réponse libre vide")
            else:
                for cid in it["criteres"]:
                    S.profil[cid] = entree([], "réponse libre (IA)", statut="analyse en cours", confiance=0.0)
                ech = [(it["texte"], r.strip())]
                fut = executeur().submit(debattre, backend_pour(cle), ech, it["criteres"], seuil, max_tours)
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
def recuperer_analyses():
    """Récupère les débats lancés en arrière-plan (attend ceux qui ne sont pas finis)."""
    with st.spinner("Les agents terminent l'analyse de vos réponses libres…"):
        for job in S.en_cours:
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
    S.en_cours = []
    S.precisions_pretes = True


def page_precisions():
    if not S.precisions_pretes:
        recuperer_analyses()
    if not S.file:  # plus rien à préciser : on vérifie la cohérence d'ensemble
        nouvelles = [c for c in incoherences(S.profil) if c["id"] not in S.coherences_posees]
        if nouvelles:
            S.file.append({"kind": "coherence", **nouvelles[0]})
        else:
            S.phase = "termine"
            st.rerun()
    retours_situations()
    st.subheader("Quelques précisions")
    st.caption("Certaines réponses étaient incomplètes ou se contredisaient. Ces questions servent à les clarifier.")
    for m in S.chat:
        with st.chat_message(m["role"]):
            st.write(m["content"])
    item = S.file[0]
    if item["kind"] == "coherence":
        with st.chat_message("assistant"):
            st.write(item["texte"])
        with st.form(f"coh_{item['id']}"):
            choix = st.radio("Votre réponse", [o[0] for o in item["options"]], index=None)
            ok = st.form_submit_button("Valider", type="primary")
        if ok and choix:
            appliquer_correctif(S.profil, dict(item["options"])[choix], choix)
            S.coherences_posees.add(item["id"])
            S.chat += [{"role": "assistant", "content": item["texte"]}, {"role": "user", "content": choix}]
            S.file.pop(0)
            st.rerun()
        return
    with st.chat_message("assistant"):
        st.write(item["texte"])
    reponse = st.chat_input("Votre réponse…", disabled=not pret)
    if not reponse:
        return
    ech = item["echanges"] + [(item["texte"], reponse)]
    try:
        with st.spinner("Les deux agents analysent votre réponse…"):
            debat = debattre(backend_pour(cle), ech, item["criteres"], seuil=seuil, max_tours=max_tours)
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


# ---------- Phase 3 : profil ----------
def page_termine():
    st.success("Profil terminé. Merci !")
    retours_situations()
    n = len(S.profil)
    incertains = [c for c, v in S.profil.items() if v["statut"] != "validé"]
    st.write(f"**{n} critères** renseignés, dont **{n - len(incertains)} validés**"
             + (f" et {len(incertains)} incertains ({', '.join(incertains)}) : l'outil appliquera le réglage le plus prudent."
                if incertains else "."))


# ---------- Mise en page ----------
st.title("Votre profil d'investisseur")
if not pret:
    st.warning("Aucun accès au modèle : lancez le site avec les identifiants AWS du datathon (voir mvp_profil/README.md), "
               "ou choisissez « API Anthropic » et collez une clé.")

col, col_profil = st.columns([3, 2], gap="large")
with col:
    {"accueil": page_accueil, "conversation": page_conversation, "questionnaire": page_questionnaire,
     "simulations": page_simulations, "precisions": page_precisions, "termine": page_termine}[S.phase]()
    if S.debats and S.debats[-1]["tours"]:
        d = S.debats[-1]
        with st.expander(f"Dernier débat des agents ({d['question']}, {len(d['tours'])} tour(s))"):
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
                            "source": v["source"], "confiance": v["confiance"], "statut": v["statut"]}
                           for c, v in S.profil.items()])
        st.dataframe(df, hide_index=True, width="stretch")
        export = {"genere_le": datetime.now().isoformat(timespec="seconds"), "modele": backend_pour(cle).model,
                  "acces": backend_pour(cle).nom, "seuil": seuil, "profil": S.profil, "debats": S.debats,
                  "replay": S.get("replay_trace")}
        st.download_button("Télécharger le profil (JSON)", json.dumps(export, ensure_ascii=False, indent=2, default=str),
                           file_name="profil_investisseur.json", mime="application/json", width="stretch")
    else:
        st.caption("Les critères apparaîtront ici au fil de vos réponses.")
