"""Site entier : du profil aux propositions, dans app.py tel qu'il est déployé (sans modèle ni AWS)."""
import json
import os

from reco_tests_commun import SITE, ch, verifier

os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.chdir(SITE)
from streamlit.testing.v1 import AppTest  # noqa: E402

ECRANS = ["Mini-portefeuille", "Recherche d'actif", "Comparaison", "Demande d'un titre", "Et si… ?", "Pourquoi ?"]


def bouton(at, debut):
    return next(b for b in at.button if b.label.startswith(debut))


def ouvrir(persona: str) -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=120).run()
    verifier(not at.exception, f"accueil : {[e.value for e in at.exception]}")
    bouton(at, f"Charger {persona.capitalize()}").click().run()
    verifier(not at.exception and at.session_state["phase"] == "termine", f"synthèse de {persona}")
    return at


vus = 0
for persona in ch.personas_disponibles():
    at = ouvrir(persona)
    avant = json.dumps(at.session_state["profil"], sort_keys=True, ensure_ascii=False)
    bouton(at, "Découvrir mes propositions").click().run()
    verifier(not at.exception, f"propositions ({persona}) : {[e.value for e in at.exception]}")
    verifier(at.session_state["phase"] == "recommandation", "la quatrième étape doit s'ouvrir depuis la synthèse")
    for ecran in ECRANS:
        at.session_state["reco_ecran"] = ecran
        at.run()
        verifier(not at.exception, f"{ecran} ({persona}) : {[e.value for e in at.exception]}")
        verifier(any("Simulation éducative" in i.value for i in at.info), f"{ecran} ({persona}) : mention « simulation » absente")
        vus += 1
    verifier(json.dumps(at.session_state["profil"], sort_keys=True, ensure_ascii=False) == avant,
             f"{persona} : les propositions ne doivent jamais modifier le profil")
    bouton(at, "← Revenir").click().run()
    verifier(not at.exception and at.session_state["phase"] == "termine", "retour à la synthèse")

# Recherche : au-dessus du seuil, à examiner, exclu, absent.
at = ouvrir("robert")
bouton(at, "Découvrir mes propositions").click().run()
at.session_state["reco_ecran"] = "Recherche d'actif"
for requete, attendu in (("XSB", "Compatible"), ("nvidia", "À examiner"), ("bitcoin", "Exclu"), ("GameStop", None)):
    at.session_state["reco_requete"] = requete
    at.run()
    verifier(not at.exception, f"recherche {requete} : {[e.value for e in at.exception]}")
    if attendu:
        verifier(any(attendu in m.value for m in at.metric), f"recherche {requete} : verdict « {attendu} » attendu")
    else:
        verifier(any("n'est pas dans l'univers" in w.value for w in at.warning), "actif absent : le dire clairement")

# Demande d'un titre : Robert demande 20 % de NVDA, avec une justification.
at.session_state["reco_ecran"] = "Demande d'un titre"
at.run()
at.text_area[0].set_value("Tout le monde en parle, je ne veux pas rater ça.")
bouton(at, "Évaluer la demande").click().run()
verifier(not at.exception, f"demande : {[e.value for e in at.exception]}")
verifier(any("En tension" in e.value for e in at.error), "Robert, 20 % de NVDA : le verdict « en tension » doit s'afficher")
verifier(any("inchangé" in c.value for c in at.caption), "le verdict doit être revérifié après la rédaction")
verifier(any("verdict_fige → incoherence → justification_recue" in c.value for c in at.caption), "ordre des actions affiché")

# « Et si… ? » : test de sensibilité.
at.session_state["reco_ecran"] = "Et si… ?"
at.run()
bouton(at, "Lancer le test de sensibilité").click().run()
verifier(not at.exception, f"et si : {[e.value for e in at.exception]}")

# Sans profil terminé, l'accueil ne propose pas les propositions.
at = AppTest.from_file("app.py", default_timeout=120).run()
verifier(not any(b.label.startswith("Découvrir mes propositions") for b in at.button), "pas de propositions sans profil terminé")

print(f"Site OK : {vus} affichages (6 écrans × {len(ch.personas_disponibles())} personas) dans app.py, profil jamais modifié, "
      "recherche (4 cas), demande de titre, sensibilité, retour à la synthèse")
