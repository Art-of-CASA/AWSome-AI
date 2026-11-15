"""Test hors ligne du parcours « conversation » (Streamlit AppTest), agents et voix simulés.

Vérifie : coche des critères au fil de la conversation (après vérification du critique en arrière-plan),
critère refusé par le critique reformulé UNE seule fois puis « retenu » avec la meilleure réponse obtenue (pas de
3e question), passage aux questions avec une page « Compléments » qui reprend en QCM ce que la conversation n'a pas
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
assert REFORMULER[-1] == ["A8"] and "A8" not in REPLIQUES[-1] and SEUILS[-1]["A8"] == 0.65 and SEUILS[-1]["A9"] == 0.8
time.sleep(0.5); at.chat_input[0].set_value("Oui c'est ça.").run()
assert REFORMULER[-1] == [] and "A8" not in REPLIQUES[-1]  # jamais redemandé une 2e fois

# Passage aux questions : page « Compléments » avec seulement ce qui manque
[b for b in at.button if b.label == "Passer aux questions suivantes"][0].click(); at.run()
secs = at.session_state.sections
assert at.session_state.phase == "questionnaire" and secs[0]["titre"] == "Compléments", [s["titre"] for s in secs]
ids = [it["id"] for it in secs[0]["items"]]
assert "q_a3" not in ids and "q_a2" not in ids and "q_a9" in ids, ids
situation = next(it for it in secs[0]["items"] if it["id"] == "q_situation")
assert situation["criteres"] == ["A6", "A7"], situation["criteres"]  # A12 validé, A8 retenu
a8 = at.session_state.profil["A8"]
assert a8["statut"] == "retenu" and a8["valeurs"] == ["0"] and a8["confiance"] == 0.9, a8  # meilleure réponse obtenue
assert [s["titre"] for s in secs[1:]] == ["Vous et le risque", "Vos connaissances", "Vos préférences", "Vos valeurs et votre compte"]
assert not any(it["id"] in ("q_b3", "q_c2", "q_d3", "q_themes") for s in secs[1:] for it in s["items"])

# Audio : WAV 16 bits stéréo -> PCM mono pour Amazon Transcribe
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x01\x00\x02\x00" * 1600)
pcm, taux = entretien.pcm_depuis_wav(buf.getvalue())
assert taux == 16000 and len(pcm) == 3200 and pcm[:2] == b"\x01\x00"
print(f"Conversation OK : {sum(v['statut'] == 'validé' for v in p.values())} critères cochés au 1er tour, "
      f"A8 refusé, reformulé une fois puis retenu (meilleure réponse), page Compléments de {len(ids)} questions")

# Fin de conversation : la réplique de conclusion est marquée « fin » et un bouton permet de continuer à l'écrit
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.chat_input[0].set_value("Je crois que c'est tout.").run()
assert at.session_state.conv["fin"] and any(b.label == "Continuer vers les questions suivantes" for b in at.button)
print("Fin de conversation OK")

# Déduction et critère facultatif : « le crédit pour les études de mon fils » -> une personne à charge (déduit), et
# « je préfère les dividendes » (hors conversation) -> style D7, gardé pour ne plus le demander dans les QCM.
def analyse_deduction(backend, echanges, a_couvrir, seuil, facultatifs=()):
    ANALYSES.append(list(a_couvrir)); FACULTATIFS_VUS.append(list(facultatifs))
    out = {}
    if "A8" in a_couvrir:
        out["A8"] = Resultat("A8", ["1_2"], "le crédit pour les études de mon fils", 0.9, True,
                             "Déduit : payer les études de son fils implique au moins une personne à charge")
    if "D7" in facultatifs:
        out["D7"] = Resultat("D7", ["dividende"], "je préfère les entreprises qui versent des dividendes", 0.9, True, "ok")
    return out


FACULTATIFS_VUS = []
entretien.analyser = analyse_deduction
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.chat_input[0].set_value("Je rembourse le crédit pour les études de mon fils, et je préfère les entreprises "
                           "qui versent des dividendes.").run()
assert "D7" in FACULTATIFS_VUS[-1] and "A3" not in FACULTATIFS_VUS[-1] and "C1" not in FACULTATIFS_VUS[-1]
time.sleep(0.5); at.run()
p = at.session_state.profil
assert p["A8"]["source"] == "déduit (IA)" and p["A8"]["motif"].startswith("Déduit") and "A8" not in at.session_state.conv["restants"]
assert p["D7"]["valeurs"] == ["dividende"] and p["D7"]["statut"] == "validé"
at.chat_input[0].set_value("Je reviens tout de suite.").run()
assert "A8" not in REPLIQUES[-1]  # l'IA ne demande plus combien de personnes sont à charge
print("Déduction OK : « études de mon fils » -> personne à charge (déduit), dividendes -> style D7 gardé pour les QCM")
