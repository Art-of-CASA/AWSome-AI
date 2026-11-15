"""Test hors ligne du parcours « conversation » (Streamlit AppTest), agents et voix simulés.

Vérifie : coche des critères au fil de la conversation (après vérification du critique en arrière-plan),
critère refusé par le critique reformulé UNE seule fois puis laissé incertain (pas de 3e question),
passage aux questions avec une page « Compléments » qui reprend en QCM ce que la conversation n'a pas
couvert, et conversion audio WAV -> PCM pour Transcribe.
Lancer : python mvp_profil/test_conversation.py
"""
from __future__ import annotations

import io
import os
import sys
import wave

sys.path.insert(0, os.path.dirname(__file__))
os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"      # identifiants factices : rien ne part vers AWS
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"

import entretien  # noqa: E402
import agents  # noqa: E402
from agents import Proposition, Resultat  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

REPLIQUES, REFORMULER, ANALYSES, SEUILS, PISTES = [], [], [], [], []


def fausse_replique(backend, echanges, restants, a_reformuler=(), pistes=None):
    PISTES.append(dict(pistes or {}))
    REPLIQUES.append(list(restants))
    REFORMULER.append(list(a_reformuler))
    fin = "c'est tout" in echanges[-1][1]
    return entretien.Replique(message="Et prévoyez-vous des retraits avant cette échéance ?", termine=fin)


def fausse_analyse(backend, echanges, a_couvrir, seuil, facultatifs=()):
    """Classificateur + critique simulés : le critique valide tout sauf A8."""
    ANALYSES.append(list(a_couvrir))
    SEUILS.append(dict(seuil))
    texte = echanges[-1][1]
    props = []
    if "retraite" in texte:
        props += [("A3", ["retraite"], "ma retraite"), ("A2", ["10_15_ans"], "dans 12 ans")]
    if "infirmier" in texte:
        props += [("A12", ["sante"], "infirmier"), ("A8", ["0"], "infirmier")]
    return {cid: Resultat(cid, v, cit, 0.9, cid != "A8", "ok" if cid != "A8" else "Désaccord du critique")
            for cid, v, cit in props if cid in a_couvrir}


def pas_de_voix(texte):
    raise RuntimeError("Polly indisponible en test")


entretien.replique, entretien.analyser, entretien.synthese_vocale = fausse_replique, fausse_analyse, pas_de_voix
agents.aws_identifiants_presents = lambda: True
agents.backend_bedrock = lambda: agents.Backend(None, agents.MODELES["bedrock"], "test hors ligne")

at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
assert at.session_state.phase == "conversation" and not at.exception, at.exception

c = at.session_state.conv
v = at.session_state.vocal
assert v["n"] == 1 and v["audio"] == "" and v["ack"] == 0 and v["etape"] == "conv:0"  # réplique d ouverture n° 1 (voix indisponible en test)
at.chat_input[0].set_value("C'est pour ma retraite, dans 12 ans. Je suis infirmier.").run()
c = at.session_state.conv
assert c["tours"] == 1 and at.session_state.vocal["n"] == 2 and len(REPLIQUES) == 1 and "A3" in ANALYSES[0]
import time; time.sleep(0.5); at.run()  # l'analyse en arrière-plan est terminée : on l'intègre
p = at.session_state.profil
assert p["A3"]["valeurs"] == ["retraite"] and p["A3"]["source"] == "conversation (IA)"
assert p["A2"]["statut"] == "validé" and p["A12"]["valeurs"] == ["sante"]
assert "A8" not in p and "A8" in at.session_state.conv["suivi"]  # refusé par le critique : à reformuler une fois
assert any("✅" in m.value for m in at.markdown) and any("🔁" in m.value for m in at.markdown)

# Le tour suivant n'analyse plus les critères déjà cochés ; A8 est reformulé (une seule fois), avec un seuil abaissé
at.chat_input[0].set_value("Non, je n'y toucherai pas.").run()
assert "A3" not in ANALYSES[-1] and "A8" in ANALYSES[-1] and "A3" not in REPLIQUES[-1]
assert PISTES[-1] == {"A8": (["0"], "infirmier")}  # l IA demande confirmation de ce qu elle a cru comprendre
assert REFORMULER[-1] == ["A8"] and "A8" not in REPLIQUES[-1] and SEUILS[-1]["A8"] == 0.8 and SEUILS[-1]["A9"] == 0.8
time.sleep(0.5); at.chat_input[0].set_value("Oui c'est ça.").run()
assert REFORMULER[-1] == [] and "A8" not in REPLIQUES[-1]  # jamais redemandé une 2e fois
assert SEUILS[-1]["A8"] == 0.65  # seulement après la réponse à la précision réellement posée

# Passage aux questions : page « Compléments » avec seulement ce qui manque
[b for b in at.button if b.label == "Passer aux questions suivantes"][0].click(); at.run()
secs = at.session_state.sections
assert at.session_state.phase == "questionnaire" and secs[0]["titre"] == "Compléments", [s["titre"] for s in secs]
ids = [it["id"] for it in secs[0]["items"]]
assert "q_a3" not in ids and "q_a2" not in ids and "q_a9" in ids, ids
situation = next(it for it in secs[0]["items"] if it["id"] == "q_situation")
assert situation["criteres"] == ["A6", "A8", "A7"], situation["criteres"]  # A8 contesté reste à préciser
a8 = at.session_state.profil["A8"]
assert a8["statut"] == "incertain", a8
assert [s["titre"] for s in secs[1:]] == ["Vous et le risque", "Vos connaissances", "Vos valeurs et votre compte", "Vos préférences"]
assert not any(it["id"] in ("q_b3", "q_c2", "q_d3", "q_themes") for s in secs[1:] for it in s["items"])

# Audio : WAV 16 bits stéréo -> PCM mono pour Amazon Transcribe
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x01\x00\x02\x00" * 1600)
pcm, taux = entretien.pcm_depuis_wav(buf.getvalue())
assert taux == 16000 and len(pcm) == 3200 and pcm[:2] == b"\x01\x00"
print(f"Conversation OK : {sum(v['statut'] == 'validé' for v in p.values())} critères cochés au 1er tour, "
      f"A8 contesté gardé incertain, page Compléments de {len(ids)} questions")

# Fin de conversation : la réplique de conclusion est marquée « fin » et un bouton permet de continuer à l'écrit
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.chat_input[0].set_value("Je crois que c'est tout.").run()
assert at.session_state.conv["fin"] and any(b.label == "Continuer vers les questions suivantes" for b in at.button)
print("Fin de conversation OK")

# Déduction certaine : retraite -> secteur retraite ; préférence dite au passage gardée sans autre question.
def analyse_deduction(backend, echanges, a_couvrir, seuil, facultatifs=()):
    ANALYSES.append(list(a_couvrir)); FACULTATIFS_VUS.append(list(facultatifs))
    out = {}
    if "A12" in a_couvrir:
        out["A12"] = Resultat("A12", ["retraite"], "je suis à la retraite", 0.9, True,
                              "Déduit : la retraite renseigne le secteur retraite")
    if "D7" in facultatifs:
        out["D7"] = Resultat("D7", ["dividende"], "je préfère les entreprises qui versent des dividendes", 0.9, True, "ok")
    return out


FACULTATIFS_VUS = []
entretien.analyser = analyse_deduction
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.chat_input[0].set_value("je suis à la retraite, et je préfère les entreprises "
                           "qui versent des dividendes.").run()
assert "D7" in FACULTATIFS_VUS[-1] and "A3" not in FACULTATIFS_VUS[-1] and "C1" not in FACULTATIFS_VUS[-1]
time.sleep(0.5); at.run()
p = at.session_state.profil
assert p["A12"]["source"] == "déduit (IA)" and p["A12"]["motif"].startswith("Déduit") and "A12" not in at.session_state.conv["restants"]
assert p["D7"]["valeurs"] == ["dividende"] and p["D7"]["statut"] == "validé"
at.chat_input[0].set_value("Je reviens tout de suite.").run()
assert "A12" not in REPLIQUES[-1]
print("Déduction certaine et préférence dite au passage : OK")

# Une correction explicite d'un critère déjà coché est revue avec une citation récente.
from profil import entree


def analyse_correction(backend, echanges, a_couvrir, seuil, facultatifs=()):
    if "A2" not in a_couvrir:
        return {}
    texte = echanges[-1][1]
    court = "deux ans" in texte
    return {"A2": Resultat("A2", ["moins_3_ans" if court else "10_15_ans"],
                            "deux ans" if court else "12 ans", 0.9, True, "correction explicite")}


entretien.analyser = analyse_correction
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.session_state.profil["A2"] = entree(["10_15_ans"], "conversation (IA)", "12 ans", 0.95)
at.session_state.conv["restants"].remove("A2")
at.chat_input[0].set_value("En fait, je voulais dire deux ans.").run()
time.sleep(0.2); at.run()
assert at.session_state.profil["A2"]["valeurs"] == ["moins_3_ans"], at.session_state.profil["A2"]
assert at.session_state.profil["A2"]["citation"] == "deux ans"
print("Correction d'un critère déjà validé : OK")

# Une réponse arrivée pendant le contrôle est vérifiée par rattrapage ; l'ancien résultat est ignoré.
from threading import Event

liberer = Event()
instantanes = []


def analyse_retardee(backend, echanges, a_couvrir, seuil, facultatifs=()):
    instantanes.append(len(echanges))
    if len(echanges) == 1:
        liberer.wait(20)
    return analyse_correction(backend, echanges, a_couvrir, seuil, facultatifs)


entretien.analyser = analyse_retardee
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
try:
    at.chat_input[0].set_value("C'est pour dans 12 ans.").run()
    at.chat_input[0].set_value("En fait ce sera dans deux ans.").run()
finally:
    liberer.set()
for _ in range(5):
    time.sleep(0.2); at.run()
    if not at.session_state.conv["jobs"]:
        break
assert 1 in instantanes and 2 in instantanes, instantanes
assert at.session_state.profil["A2"]["valeurs"] == ["moins_3_ans"], at.session_state.profil
assert at.session_state.profil["A2"]["citation"] == "deux ans"
print("Rattrapage asynchrone et exclusion des instantanés périmés : OK")

# L'échec d'une réplique conserve l'échange analysé ; la réponse suivante a un numéro distinct.
echecs = []


def replique_en_panne(backend, echanges, restants, a_reformuler=(), pistes=None):
    if not echecs:
        echecs.append(True)
        raise agents.AgentError("Indisponibilité simulée")
    return fausse_replique(backend, echanges, restants, a_reformuler, pistes)


entretien.replique, entretien.analyser = replique_en_panne, analyse_correction
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.chat_input[0].set_value("C'est pour dans 12 ans.").run()
assert not at.exception and len(at.session_state.conv["echanges"]) == 1
at.chat_input[0].set_value("En fait dans deux ans.").run()
time.sleep(0.2); at.run()
assert len(at.session_state.conv["echanges"]) == 2
assert at.session_state.profil["A2"]["valeurs"] == ["moins_3_ans"]
print("Réplique indisponible : réponse conservée et reprise sans ancien classement : OK")

# Plusieurs ambiguïtés : seule la précision posée peut être considérée répondue ou bénéficier du seuil réduit.
entretien.replique = fausse_replique
seuils_par_tour = []


def ambigu(backend, echanges, a_couvrir, seuil, facultatifs=()):
    seuils_par_tour.append(dict(seuil))
    return {cid: Resultat(cid, ["faible_moins_25" if cid == "A4" else "0"],
                          echanges[-1][1], 0.6, False, "Confiance 60 % sous le seuil")
            for cid in ("A4", "A8") if cid in a_couvrir}


entretien.analyser = ambigu
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.chat_input[0].set_value("Il faut préciser ma situation.").run()
time.sleep(0.2); at.run()
at.chat_input[0].set_value("Je vous écoute.").run()
poses = list(at.session_state.conv["reformules"])
assert len(poses) == 1 and len(REFORMULER[-1]) == 1, poses
autre = next(cid for cid in ("A4", "A8") if cid not in poses)
at.chat_input[0].set_value("Voici ma précision.").run()
time.sleep(0.2); at.run()
assert at.session_state.conv["analyses_couvertes"][autre] == 3
assert seuils_par_tour[-1][autre] == 0.8, seuils_par_tour
assert autre in at.session_state.conv["restants"], at.session_state.conv
print("Une reformulation effectivement posée par tour, seuil réduit seulement pour sa réponse : OK")

# Une correction d'une valeur déjà connue reste prouvée par son propre tour,
# même si la personne répond à un autre sujet pendant le contrôle asynchrone.
controle_correction = Event()
correction_commencee = Event()
instantanes_correction = []


def correction_puis_autre_sujet(backend, echanges, a_couvrir, seuil, facultatifs=()):
    if "A2" not in a_couvrir:
        return {}
    instantanes_correction.append(len(echanges))
    if len(echanges) == 1:
        correction_commencee.set()
        controle_correction.wait(20)
    # Le vrai classificateur lit tout l'historique : le dernier énoncé ne répète pas forcément la correction.
    if any("deux ans" in reponse for _, reponse in echanges):
        return {"A2": Resultat("A2", ["moins_3_ans"], "deux ans", 0.9, True,
                               "Correction explicite de l'horizon, les autres réponses sont sans rapport", True)}
    return {}


entretien.replique, entretien.analyser = fausse_replique, correction_puis_autre_sujet
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.session_state.profil["A2"] = entree(["10_15_ans"], "conversation (IA)", "dans 12 ans", 0.95)
at.session_state.conv["restants"].remove("A2")
try:
    at.chat_input[0].set_value("En fait, je me corrige : ce sera dans deux ans.").run()
    assert not at.exception, at.exception
    assert correction_commencee.wait(5), "Le contrôle de la correction doit être lancé avant la réponse suivante"
    at.chat_input[0].set_value("Je n'ai pas de dettes à taux élevé.").run()
    assert not at.exception, at.exception
    assert at.session_state.profil["A2"]["valeurs"] == ["10_15_ans"]
finally:
    controle_correction.set()
for _ in range(10):
    time.sleep(0.2); at.run()
    if not at.session_state.conv["jobs"]:
        break
assert 1 in instantanes_correction and 2 in instantanes_correction, instantanes_correction
assert at.session_state.profil["A2"]["valeurs"] == ["moins_3_ans"], at.session_state.profil["A2"]
assert at.session_state.profil["A2"]["citation"] == "deux ans"
assert "A2" not in at.session_state.conv["revisions"]
print("Correction connue puis réponse sur un autre sujet pendant le contrôle : citation du tour de correction préservée, OK")
