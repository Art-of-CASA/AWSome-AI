"""Test hors ligne du parcours « conversation » (Streamlit AppTest), agents et voix simulés.

Vérifie : coche des critères au fil de la conversation (après vérification du critique en arrière-plan),
critère refusé par le critique remis « à couvrir », passage aux questions avec une page « Compléments »
qui reprend en QCM ce que la conversation n'a pas validé, et conversion audio WAV -> PCM pour Transcribe.
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

REPLIQUES, ANALYSES = [], []


def fausse_replique(backend, echanges, restants):
    REPLIQUES.append(list(restants))
    fin = "c'est tout" in echanges[-1][1]
    return entretien.Replique(message="Et prévoyez-vous des retraits avant cette échéance ?", termine=fin)


def fausse_analyse(backend, echanges, a_couvrir, seuil):
    """Classificateur + critique simulés : le critique valide tout sauf A8."""
    ANALYSES.append(list(a_couvrir))
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
assert c["n"] == 1 and c["audio"] == "" and c["ack"] == 0  # réplique d'ouverture n° 1 (voix indisponible en test)
at.chat_input[0].set_value("C'est pour ma retraite, dans 12 ans. Je suis infirmier.").run()
c = at.session_state.conv
assert c["tours"] == 1 and c["n"] == 2 and len(REPLIQUES) == 1 and "A3" in ANALYSES[0]
import time; time.sleep(0.5); at.run()  # l'analyse en arrière-plan est terminée : on l'intègre
p = at.session_state.profil
assert p["A3"]["valeurs"] == ["retraite"] and p["A3"]["source"] == "conversation (IA)"
assert p["A2"]["statut"] == "validé" and p["A12"]["valeurs"] == ["sante"]
assert "A8" not in p and "A8" in at.session_state.conv["restants"]  # refusé par le critique : reste à couvrir
assert any("✅" in m.value for m in at.markdown)

# Le tour suivant n'analyse plus les critères déjà cochés, mais reprend A8
at.chat_input[0].set_value("Non, je n'y toucherai pas.").run()
assert "A3" not in ANALYSES[-1] and "A8" in ANALYSES[-1] and "A3" not in REPLIQUES[-1]

# Passage aux questions : page « Compléments » avec seulement ce qui manque
[b for b in at.button if b.label == "Passer aux questions suivantes"][0].click(); at.run()
secs = at.session_state.sections
assert at.session_state.phase == "questionnaire" and secs[0]["titre"] == "Compléments", [s["titre"] for s in secs]
ids = [it["id"] for it in secs[0]["items"]]
assert "q_a3" not in ids and "q_a2" not in ids and "q_a9" in ids, ids
situation = next(it for it in secs[0]["items"] if it["id"] == "q_situation")
assert situation["criteres"] == ["A6", "A8", "A7"], situation["criteres"]  # A12 déjà validé
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
      f"A8 refusé par le critique puis repris, page Compléments de {len(ids)} questions")

# Fin de conversation : la réplique de conclusion est marquée « fin » et un bouton permet de continuer à l'écrit
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Commencer en conversation"][0].click(); at.run()
at.chat_input[0].set_value("Je crois que c'est tout.").run()
assert at.session_state.conv["fin"] and any(b.label == "Continuer vers les questions suivantes" for b in at.button)
print("Fin de conversation OK")
