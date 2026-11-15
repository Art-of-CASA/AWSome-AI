"""Site entier : du profil aux propositions, dans app.py tel qu'il est déployé (sans modèle ni AWS)."""
import json
import os

from reco_tests_commun import SITE, ch, verifier

os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
os.chdir(SITE)
from streamlit.testing.v1 import AppTest  # noqa: E402

ECRANS = ["Mon portefeuille", "Parler au conseiller", "Chercher un actif", "Comparer", "Et si… ?", "Comprendre"]


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

# Recherche : compatible, à examiner, exclu, absent. L'écran ne doit ni planter ni noter un actif absent.
at = ouvrir("robert")
bouton(at, "Découvrir mes propositions").click().run()
at.session_state["reco_ecran"] = "Chercher un actif"
for requete in ("XSB", "nvidia", "bitcoin", "GameStop"):
    at.session_state["reco_requete"] = requete
    at.run()
    verifier(not at.exception, f"recherche {requete} : {[e.value for e in at.exception]}")
    if requete == "GameStop":
        verifier(any("n'est pas dans l'univers" in w.value for w in at.warning), "actif absent : le dire clairement")
        verifier(not any(b.label == "Ajouter à mon portefeuille" for b in at.button), "pas de bouton d'ajout pour un actif absent")
    elif requete == "bitcoin":
        verifier(not any(b.label == "Ajouter à mon portefeuille" for b in at.button), "pas de bouton d'ajout pour un actif exclu")

# Conversation : Robert demande 20 % de NVDA ; une part réduite est proposée, puis acceptée d'un clic.
at.session_state["reco_requete"] = ""
at.session_state["reco_ecran"] = "Parler au conseiller"
at.run()
at.chat_input[0].set_value("J'aimerais 20 % de Nvidia, tout le monde en parle").run()
verifier(not at.exception, f"conversation : {[e.value for e in at.exception]}")
conv = at.session_state["reco_conv"]
verifier(not conv["ajouts"] and conv["en_attente"]["part_pct"] == 5, "20 % de NVDA : rien n'est ajouté, 5 % sont proposés")
bouton(at, "Oui").click().run()
verifier(not at.exception, f"confirmation : {[e.value for e in at.exception]}")
verifier(at.session_state["reco_conv"]["ajouts"] == {"NVDA": 5.0}, "après « Oui », NVDA entre pour 5 %")
at.session_state["reco_ecran"] = "Mon portefeuille"
at.run()
verifier(not at.exception and abs(at.session_state["reco_analyse"].portefeuille["poids"]["NVDA"] - 0.05) < 1e-6,
         "l'écran du portefeuille reflète l'ajout fait dans la conversation")
bouton(at, "Revenir à mon portefeuille").click().run()
verifier(not at.exception and not at.session_state["reco_conv"]["ajouts"], "retour au portefeuille d'origine en un clic")

# Affichage sobre par défaut ; les détails techniques sont un choix explicite.
at.session_state["reco_ecran"] = "Comprendre"
at.run()
verifier(not any("journal" in c.value.lower() for c in at.caption), "pas de journal technique dans l'affichage courant")
at.session_state["reco_technique"] = True
at.run()
verifier(not at.exception and any("journal" in c.value.lower() for c in at.caption), "le journal apparaît avec « Détails techniques »")
at.session_state["reco_technique"] = False

# « Et si… ? » : test de sensibilité.
at.session_state["reco_ecran"] = "Et si… ?"
at.run()
bouton(at, "Lancer le test de sensibilité").click().run()
verifier(not at.exception, f"et si : {[e.value for e in at.exception]}")

# Sans profil terminé, l'accueil ne propose pas les propositions.
at = AppTest.from_file("app.py", default_timeout=120).run()
verifier(not any(b.label.startswith("Découvrir mes propositions") for b in at.button), "pas de propositions sans profil terminé")

print(f"Site OK : {vus} affichages (6 écrans × {len(ch.personas_disponibles())} personas) dans app.py, profil jamais modifié, "
      "recherche (4 cas), conversation et ajout, affichage sobre, sensibilité, retour à la synthèse")
