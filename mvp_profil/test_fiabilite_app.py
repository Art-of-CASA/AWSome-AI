"""Régressions hors ligne : livraison vocale, fraîcheur, erreurs et capacité des contrôles.

Lancer avec python -X utf8 mvp_profil/test_fiabilite_app.py.
Tous les services sont simulés ; AppTest requiert les sockets locales asyncio sous Windows.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import Future
from copy import deepcopy
import os
from pathlib import Path
import sys
from threading import Event
from time import monotonic

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"
os.environ["ANTHROPIC_API_KEY"] = "cle-factice-serveur-ne-pas-transmettre"

import agents
import entretien
import voix_composant
from agents import AgentError, Debat, Resultat
from profil import entree
from streamlit.testing.v1 import AppTest
from taches import DELAI_ANALYSE_S, ExecuteurBorne

MICRO = {"payload": None, "texte": "", "transcriptions": 0}
RENDUS = []


def composant(**kwargs):
    RENDUS.append(dict(kwargs))
    return MICRO["payload"]


def transcrire(_):
    MICRO["transcriptions"] += 1
    return MICRO["texte"]


agents.aws_identifiants_presents = lambda: True
agents.backend_bedrock = lambda: agents.Backend(None, "test", "hors ligne")
agents.backend_anthropic = lambda key: agents.Backend(None, "test", "hors ligne")
entretien.synthese_vocale = lambda texte: ("mp3:" + texte).encode()
entretien.transcrire = transcrire
voix_composant.conversation_vocale = composant


def nouveau():
    MICRO["payload"] = None
    at = AppTest.from_file(str(ICI / "app.py"), default_timeout=20).run()
    assert not at.exception, at.exception
    return at


def run(at):
    at.run()
    assert not at.exception, at.exception
    assert not at.chat_input and not at.text_area
    return RENDUS[-1]


def payload(args, *, n=1, instance="micro-1", **modifications):
    return {"kind": "audio", "n": n, "wav": "", "instance_id": instance,
            "session_id": args["session_id"], "question_id": args["question_id"],
            "playback_id": args["n"], **modifications}


def injecter(at, donnees, texte):
    MICRO.update(payload=donnees, texte=texte)
    try:
        return run(at)
    finally:
        MICRO["payload"] = None


def job(at, future, ids, *, autres=(), ancien=False):
    tous = ids + list(autres)
    return {"item": "réponse conservée", "criteres": ids, "facultatifs": list(autres), "future": future,
            "echanges": [("Quel est votre projet ?", "Pour ma retraite")],
            "versions": {cid: at.session_state.versions_profil.get(cid, 0) for cid in tous},
            "profil_depart": {cid: deepcopy(at.session_state.profil.get(cid)) for cid in tous},
            "soumis_le": monotonic() - (DELAI_ANALYSE_S + 1 if ancien else 0)}


# Chaque première entrée transmet immédiatement la nouvelle question, dans un composant monté en permanence.
at = nouveau()
assert RENDUS[-1]["veille"], "Le composant reste monté même sur l'accueil."
at.session_state.phase = "libre_oral"
at.session_state.section = 1
at.session_state.libres_en_attente = [{"id": "horizon", "criteres": ["A2"],
                                       "texte": "Dans combien d'années aurez-vous besoin de cet argent ?"}]
args_horizon = run(at)
assert args_horizon["n"] == at.session_state.vocal["n"] > 0
assert args_horizon["audio_b64"] == at.session_state.vocal["audio"]
assert args_horizon["question_text"].startswith("Dans combien")
assert not args_horizon["veille"]
assert args_horizon["attendre_reprise_explicite"]

# Une transcription vide est acquittée, mais devient un échec explicite : le navigateur n'a pas
# l'autorisation de réarmer le micro de lui-même pour la même question.
MICRO["texte"] = ""
apres_echec = injecter(at, payload(args_horizon), "")
assert apres_echec["question_id"] == args_horizon["question_id"]
assert apres_echec["echec_transcription"] == args_horizon.get("echec_transcription", 0) + 1

at.session_state.phase = "precisions"
at.session_state.precisions_pretes = True
at.session_state.file = [{"kind": "libre", "criteres": ["A5"], "echanges": [],
                          "texte": "Combien de mois de dépenses couvre votre réserve, hors placement ?"}]
args_reserve = run(at)
assert args_reserve["question_id"] != args_horizon["question_id"]
assert args_reserve["n"] == at.session_state.vocal["n"]
assert args_reserve["question_text"].startswith("Combien de mois")

# Un audio de l'horizon arrivé tard ne devient jamais une réponse sur la réserve.
avant = MICRO["transcriptions"]
injecter(at, payload(args_horizon), "six mois")
assert MICRO["transcriptions"] == avant
assert not at.session_state.profil.get("A5", {}).get("valeurs")
injecter(at, payload(args_reserve, n=2), "Ma réserve couvre six mois de dépenses, hors placement.")
assert at.session_state.profil["A5"]["valeurs"] == ["3_6_mois"]
assert MICRO["transcriptions"] == avant + 1
assert at.session_state.phase == "ouverte"
args_ouverte = RENDUS[-1]
assert args_ouverte["n"] == at.session_state.vocal["n"]
assert args_ouverte["question_id"] == "ouverte" and args_ouverte["audio_b64"]

# Un remontage de composant ne fait pas perdre l'énoncé ; les doublons et autres sessions sont ignorés.
at.session_state.phase = "libre_oral"
at.session_state.libres_en_attente = [{"id": "nouvel_horizon", "criteres": ["A2"], "texte": "Quel est votre horizon ?"}]
args = run(at)
avant = MICRO["transcriptions"]
injecter(at, payload(args, n=500, session_id="autre-session"), "15 ans")
assert MICRO["transcriptions"] == avant
reponse = payload(args, n=1, instance="micro-remonte")
injecter(at, reponse, "Mon horizon est de quinze ans.")
assert at.session_state.profil["A2"]["nombre"] == 15
injecter(at, reponse, "Mon horizon est de quinze ans.")
assert MICRO["transcriptions"] == avant + 1
print("Voix : question livrée au premier rendu, audio ancien rejeté, remontage et doublons protégés")

# Réduire un groupe déjà posé ne change pas son identité et n'efface pas le critère restant.
at = nouveau()
at.session_state.phase = "precisions"
at.session_state.precisions_pretes = True
at.session_state.file = [{"kind": "libre", "criteres": ["A6", "A7"], "echanges": [], "texte": "Votre situation et vos dettes ?"}]
args = run(at)
assert at.session_state.questions_posees["A6"]["clarifications"] == 1
at.session_state.profil["A7"] = entree(["non"], "réponse explicite")
apres = run(at)
assert at.session_state.phase == "precisions"
assert at.session_state.file[0]["criteres"] == ["A6"]
assert args["question_id"] == apres["question_id"] and args["n"] == apres["n"]

# Une exception inattendue est retirée une fois, sans perdre les paroles ni créer une clarification.
at = nouveau()
at.session_state.profil = {"A3": entree([], "réponse en analyse", statut="analyse en cours")}
future = Future()
future.set_exception(ValueError("sortie de service invalide simulée"))
at.session_state.en_cours = [job(at, future, ["A3"])]
run(at)
assert not at.session_state.en_cours and at.session_state.profil["A3"]["statut"] == "incertain"
assert at.session_state.profil["A3"]["citation"] == "Pour ma retraite"
assert len(at.session_state.echecs_analyses) == 1 and not at.session_state.file
for _ in range(3):
    run(at)
assert len(at.session_state.echecs_analyses) == 1

# Une tâche non terminée expire, et sa complétion ultérieure ne réécrit rien.
future = Future()
future.set_running_or_notify_cancel()
at.session_state.en_cours = [job(at, future, ["A3"], ancien=True)]
run(at)
assert not at.session_state.en_cours
conserve = deepcopy(at.session_state.profil)
future.set_result(Debat({"A3": Resultat("A3", ["croissance"], "Pour ma retraite", .9, True, "retard", True)}, [], ""))
run(at)
assert at.session_state.profil == conserve

# Un ancien facultatif ne remplace pas une déclaration récente et ne double pas le budget de risque.
at = nouveau()
at.session_state.profil = {"A6": entree([], "analyse", statut="analyse en cours")}
future = Future()
ancien_job = job(at, future, ["A6"], autres=["B1R"])
at.session_state.profil["B1R"] = entree(["vendre_tout"], "QCM")
at.session_state.profil["B1"] = entree(["20"], "choix numérique", nombre=20)
at.session_state.versions_profil["B1R"] = 1
future.set_result(Debat({"B1R": Resultat("B1R", ["attendre"], "Pour ma retraite", .95, True, "ancien", True)}, [], ""))
at.session_state.en_cours = [ancien_job]
run(at)
assert at.session_state.profil["B1R"]["valeurs"] == ["vendre_tout"]
assert at.session_state.profil["B1"]["valeurs"] == ["20"]
assert at.session_state.debats[-1]["ignores_perimes"] == ["B1R"]
print("Contrôles : panne et expiration sans boucle, réponse conservée, résultat ancien sans écrasement")

# Même une panne de compréhension d'un choix oral conserve les paroles et réarme une reprise fermée.
at = nouveau()
at.session_state.phase = "precisions"
at.session_state.precisions_pretes = True
at.session_state.file = [{"kind": "coherence", "id": "RTEST", "criteres": ["A2"], "texte": "Quel choix retenez-vous ?",
                          "options": [("La première réponse", {}), ("La seconde réponse", {})]}]
args = run(at)
def choix_indisponible(*args):
    raise AgentError("Service temporairement indisponible")
entretien.choisir_option = choix_indisponible
injecter(at, payload(args), "la première")
assert at.session_state.file[0]["reponse_en_attente"] == "la première"
assert RENDUS[-1]["veille"] and any(b.label == "Réessayer l'interprétation de ma réponse" for b in at.button)
run(at)
assert at.session_state.file[0]["reponse_en_attente"] == "la première"

# La clé serveur ne fait jamais partie de la valeur envoyée au navigateur.
at = nouveau()
next(r for r in at.radio if r.label == "Accès au modèle").set_value("API Anthropic (clé)")
run(at)
champ = next(t for t in at.text_input if t.label == "Clé API Anthropic")
assert champ.value == "" and champ.proto.default == ""
assert os.environ["ANTHROPIC_API_KEY"].encode() not in champ.proto.SerializeToString()

# La tolérance n'a pas de valeur sélectionnée implicitement.
at.session_state.phase = "questionnaire"
at.session_state.section = next(i for i, s in enumerate(at.session_state.sections) if any(it.get("critere") == "B1" for it in s["items"]))
run(at)
choix = next(s for s in at.selectbox if "vendriez-vous" in s.label)
assert choix.value is None and "B1" not in at.session_state.profil
next(b for b in at.button if b.label in ("Continuer", "Terminer le questionnaire")).click()
run(at)
assert "B1" not in at.session_state.profil and at.warning

# Le choix de main survit au nouveau questionnaire sans valeur implicite.
from criteres import SECTIONS
b1_item = next(it for sec in SECTIONS for it in sec["items"] if it.get("critere") == "B1")
at.session_state.sections = [{"titre": "Tolérance", "items": [b1_item]}]
at.session_state.section = 0
run(at)
next(s for s in at.selectbox if "vendriez-vous" in s.label).select(b1_item["case_jamais"])
next(b for b in at.button if b.label == "Terminer le questionnaire").click()
run(at)
assert at.session_state.profil["B1"]["valeurs"] == ["jamais"]
assert at.session_state.profil["B1"]["citation"] == b1_item["case_jamais"]

# La capacité est bornée, la place est libérée au succès comme à l'échec.
liberer = Event()
with ExecuteurBorne(max_workers=1, max_attente=0) as executor:
    tache = executor.submit(liberer.wait, 5)
    try:
        try:
            executor.submit(lambda: None)
            raise AssertionError("La surcharge doit être refusée.")
        except AgentError:
            pass
    finally:
        liberer.set()
    assert tache.result(2)
    assert executor.submit(lambda: 42).result(2) == 42
    def echouer():
        raise ValueError("échec simulé")
    try:
        executor.submit(echouer).result(2)
    except ValueError:
        pass
    assert executor.submit(lambda: 43).result(2) == 43

for invalide in (b"", b"pas un fichier WAV"):
    try:
        entretien.pcm_depuis_wav(invalide)
        raise AssertionError("Un audio invalide doit produire une erreur contrôlée.")
    except AgentError:
        pass
print("Sécurité et ressources : secret serveur absent du widget, réponse explicite, capacité bornée, WAV invalide contrôlé")
