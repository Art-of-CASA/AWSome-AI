"""Conversation orale hors ligne : réponse unique, questions ciblées et analyses retardées.

Les modèles, Transcribe et Polly sont simulés. Le véritable pilote de questions
et le parseur des réponses explicites sont exercés dans Streamlit AppTest.
Lancer : python mvp_profil/test_conversation.py
Sous Windows, asyncio doit pouvoir ouvrir ses sockets locales internes.
"""
from __future__ import annotations

from copy import deepcopy
import io
import os
from pathlib import Path
import sys
from threading import Event
import time
import wave

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

import agents  # noqa: E402
import criteres_dynamiques  # noqa: E402
import entretien  # noqa: E402
import voix_composant  # noqa: E402
from agents import Debat, Resultat  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402


VOIX = {"n": 0, "texte": None}
APPELS = []
LECTURES = []
OUVERTES = []
MODE = {"analyse": lambda *args, **kwargs: {}}


def composant_simule(**kw):
    return {"kind": "audio", "n": VOIX["n"], "wav": ""} if VOIX["texte"] is not None else None


def lecture_simulee(texte):
    LECTURES.append(texte)
    return b""


def analyse_simulee(backend, echanges, a_couvrir, seuil, facultatifs=()):
    APPELS.append({"n": len(echanges), "criteres": list(a_couvrir), "facultatifs": list(facultatifs),
                   "echanges": list(echanges)})
    return MODE["analyse"](backend, echanges, a_couvrir, seuil, facultatifs)


def debat_simule(backend, echanges, criteres_ids, seuil=0.8, max_tours=2, facultatifs=()):
    res = analyse_simulee(backend, echanges, criteres_ids, seuil, facultatifs)
    return Debat(res, [], "Pouvez-vous préciser ce point ?")


def decouverte_simulee(backend, question, reponse, seuil, deja=0):
    OUVERTES.append(reponse)
    return []


def replique_interdite(*args, **kwargs):
    raise AssertionError("Un modèle ne doit plus choisir ni reformuler librement la prochaine question.")


agents.aws_identifiants_presents = lambda: True
agents.backend_bedrock = lambda: agents.Backend(None, agents.MODELES["bedrock"], "test hors ligne")
agents.debattre = debat_simule
entretien.analyser = analyse_simulee
entretien.replique = replique_interdite
entretien.transcrire = lambda wav: VOIX["texte"]
entretien.synthese_vocale = lecture_simulee
voix_composant.conversation_vocale = composant_simule
criteres_dynamiques.creer = decouverte_simulee


def verifier_interface_orale(at):
    assert not at.exception, at.exception
    assert not at.chat_input, "Une réponse libre doit passer par le micro, pas par une saisie de chat."
    assert not at.text_area, "Une réponse libre ne doit pas demander de saisie écrite."


def nouvelle_conversation():
    VOIX["texte"] = None
    at = AppTest.from_file(str(ICI / "app.py"), default_timeout=30)
    at.run()
    [b for b in at.button if b.label == "Commencer en conversation"][0].click()
    at.run()
    verifier_interface_orale(at)
    assert at.session_state.phase == "conversation"
    assert set(at.session_state.conv["cibles_question"]) == {"A3", "A2"}
    return at


def parler(at, texte):
    VOIX["n"] += 1
    VOIX["texte"] = texte
    at.run()
    verifier_interface_orale(at)


def terminer_analyses(at):
    for _ in range(30):
        time.sleep(0.05)
        at.run()
        verifier_interface_orale(at)
        if not at.session_state.conv["jobs"]:
            return
    raise AssertionError("Les analyses simulées ne se terminent pas.")


def nb_initiales(at, cid):
    info = at.session_state.conv["questions_posees"].get(cid, {})
    return info if isinstance(info, int) else info.get("initiales", 0)


def est_regle(entree):
    return "règle" in entree["source"].casefold() or "déterministe" in entree["source"].casefold()


# Réponses chiffrées claires : le profil est renseigné immédiatement, même si le modèle est bloqué.
liberer = Event()
demarree = Event()


def analyse_retardee(backend, echanges, a_couvrir, seuil, facultatifs=()):
    demarree.set()
    if not liberer.wait(20):
        raise AssertionError("Le test n'a pas libéré l'analyse retardée.")
    texte = " ".join(r for _, r in echanges)
    res = {}
    if "ma retraite" in texte:
        res["A3"] = Resultat("A3", ["retraite"], "ma retraite", 0.95, True, "déclaration claire", True)
    # Une contradiction provenant d'un modèle ne doit jamais écraser la réponse directe plus récente.
    res["A2"] = Resultat("A2", ["3_5_ans"], "15 ans", 0.95, True, "sortie simulée erronée", True)
    res["A5"] = Resultat("A5", ["moins_3_mois"], "six mois", 0.95, True, "sortie simulée erronée", True)
    return res


MODE["analyse"] = analyse_retardee
APPELS.clear()
at = nouvelle_conversation()
try:
    parler(at, "C'est pour ma retraite, j'aurai besoin de cet argent dans 15 ans.")
    assert demarree.wait(2), "Le test doit réellement exercer une analyse en arrière-plan."
    p = at.session_state.profil
    assert p["A2"]["valeurs"] == ["10_15_ans"] and est_regle(p["A2"]), p.get("A2")
    assert p["A2"].get("nombre") == 15
    assert "A2" not in at.session_state.conv["cibles_question"]
    assert "A3" not in at.session_state.conv["cibles_question"], "Le projet répondu est en cours de contrôle."
    assert at.session_state.conv["cibles_question"], "Le contrôle transverse ne doit pas bloquer tous les autres sujets."
    initiales_reserve = nb_initiales(at, "A5")

    parler(at, "J'ai six mois de dépenses de côté en dehors de ce placement.")
    p = at.session_state.profil
    assert p["A5"]["valeurs"] == ["3_6_mois"] and est_regle(p["A5"]), p.get("A5")
    assert p["A5"].get("nombre") == 6
    assert not {"A2", "A5"} & set(at.session_state.conv["cibles_question"])
    assert nb_initiales(at, "A2") == 1 and nb_initiales(at, "A5") == initiales_reserve <= 1
finally:
    liberer.set()

terminer_analyses(at)
p = at.session_state.profil
assert p["A2"]["valeurs"] == ["10_15_ans"] and p["A5"]["valeurs"] == ["3_6_mois"], p
assert p["A3"]["valeurs"] == ["retraite"], "Une réponse antérieure sur un autre sujet doit être conservée."
assert nb_initiales(at, "A2") == 1 and nb_initiales(at, "A5") == initiales_reserve <= 1
assert not {"A2", "A5"} & set(at.session_state.conv["cibles_question"])
assert est_regle(p["A2"]) and est_regle(p["A5"])
print("15 ans et six mois : validés en une réponse ; aucune répétition ; résultat LLM contradictoire ignoré")

# Demander explicitement de répéter relit la question sans consommer une nouvelle question ni analyser l'énoncé.
avant_question = at.session_state.conv["question"]
avant_echanges = list(at.session_state.conv["echanges"])
avant_compteurs = deepcopy(at.session_state.conv["questions_posees"])
avant_lectures = len(LECTURES)
parler(at, "Pouvez-vous répéter ?")
assert at.session_state.conv["question"] == avant_question
assert at.session_state.conv["echanges"] == avant_echanges
assert at.session_state.conv["questions_posees"] == avant_compteurs
assert len(LECTURES) > avant_lectures and LECTURES[-1] == avant_question
print("Répétition uniquement demandée par l'utilisateur : relecture sans nouvelle collecte")

# Une correction claire s'applique immédiatement, même si l'horizon avait déjà été coché.
MODE["analyse"] = lambda *args, **kwargs: {}
parler(at, "Je me corrige : j'aurai besoin de cet argent dans deux ans.")
assert at.session_state.profil["A2"]["valeurs"] == ["moins_3_ans"], at.session_state.profil["A2"]
assert "deux ans" in at.session_state.profil["A2"]["citation"]
assert est_regle(at.session_state.profil["A2"])
assert "A2" not in at.session_state.conv["cibles_question"]
terminer_analyses(at)
print("Correction récente de quinze à deux ans : appliquée sans redemander l'horizon")

# Les précisions libres sont orales, puis la question ouverte finale est elle aussi orale.
def situation_precisee(backend, echanges, a_couvrir, seuil, facultatifs=()):
    if "A4" in a_couvrir:
        return {"A4": Resultat("A4", ["faible_moins_25"], echanges[-1][1], 0.95, True, "réponse claire", True)}
    return {}


MODE["analyse"] = situation_precisee
at.session_state.profil.pop("A4", None)
at.session_state.phase = "precisions"
at.session_state.precisions_pretes = True
at.session_state.file = [{"kind": "libre", "criteres": ["A4"], "texte": "Quelle part de votre épargne représente ce placement ?",
                          "essai": 0, "echanges": []}]
at.run()
verifier_interface_orale(at)
parler(at, "Ce placement représente moins du quart de mon épargne totale.")
assert at.session_state.profil["A4"]["valeurs"] == ["faible_moins_25"]
at.session_state.phase = "ouverte"
at.run()
verifier_interface_orale(at)
parler(at, "Je n'ai rien à ajouter.")
assert at.session_state.phase == "termine" and at.session_state.reponse_ouverte == "Je n'ai rien à ajouter."
print("Précisions et question ouverte finale : réponses au micro, aucun chat ni zone de texte libre")

# La conversion audio reste vérifiée sans Transcribe réel.
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(16000)
    w.writeframes(b"\x01\x00\x02\x00" * 1600)
pcm, taux = entretien.pcm_depuis_wav(buf.getvalue())
assert taux == 16000 and len(pcm) == 3200 and pcm[:2] == b"\x01\x00"
print("Audio WAV stéréo vers PCM mono : OK")
