"""Test hors ligne du parcours complet dans l'interface (Streamlit AppTest), agents simulés.

Scénario : 6 pages fixes avec un « Je ne sais pas », une réponse libre floue et trois contradictions
volontaires ; puis précisions (relances et questions de cohérence) jusqu'au profil final.
Lancer : python mvp_profil/test_app.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"      # identifiants factices : les agents sont simulés,
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"        # aucun appel ne part vers AWS

import agents  # noqa: E402
from agents import Debat, Resultat  # noqa: E402
from criteres import CRITERES  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APPELS = []


def faux_debat(backend, echanges, criteres_ids, seuil=0.8, max_tours=2):
    APPELS.append(list(criteres_ids))
    flou = "flou" in echanges[-1][1]
    res = {c: Resultat(c, [] if flou else [CRITERES[c]["valeurs"][0]], "x", 0.3 if flou else 0.9, not flou,
                       "Classificateur peu sûr" if flou else "ok") for c in criteres_ids}
    return Debat(res, [{"tour": 1, "classificateur": {"propositions": []}, "critique": None, "valides": []}],
                 "Pouvez-vous préciser ?" if flou else "")


agents.debattre = faux_debat
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
assert not at.exception, at.exception
assert at.session_state.phase == "accueil"
[b for b in at.button if b.label == "Questionnaire classique"][0].click(); at.run()
assert at.session_state.phase == "questionnaire"


def radio(key, val):
    at.radio(key=key).set_value(val)


def suivant():
    [b for b in at.button if b.label in ("Continuer", "Terminer le questionnaire")][0].click()
    at.run()
    assert not at.exception, at.exception


# Page 1 : coussin de sécurité + plus de 15 ans -> contradiction R2
radio("0_q_a3", "Avoir un coussin de sécurité pour les imprévus"); radio("0_q_a2", "Plus de 15 ans")
radio("0_q_a9", "Non, je n'y toucherai pas"); radio("0_q_a10", "Non")
suivant()
assert at.session_state.section == 1 and at.session_state.profil["A3"]["valeurs"] == ["coussin_securite"]

# Page 2 : question oubliée -> message, puis « Je ne sais pas » + réponse libre floue
radio("1_q_a4", "Moins du quart")
suivant()
assert at.session_state.section == 1 and len(at.warning) >= 1  # A5 manquant : on reste sur la page
radio("1_q_a5", "Je ne sais pas")
at.text_area(key="1_q_situation").input("c'est flou")
suivant()
assert at.session_state.profil["A5"]["statut"] == "à préciser"

# Page 3 : « je vends tout » mais curseur à 40 % -> contradiction R1
radio("2_q_b1r", "Je vends tout pour arrêter les pertes"); at.slider(key="2_q_b1").set_value(40)
radio("2_q_b5", "800 à 1 500 $ (modérée, 8 à 15 %)"); radio("2_q_b7", "Un à deux ans")
radio("2_q_b3", "Jamais"); radio("2_q_b4", "Chaque mois")
suivant()
assert at.session_state.profil["B1"]["valeurs"] == ["40"]

# Page 4 : quiz 2/3 -> intermédiaire
radio("3_q_c1_0", "Plus de 1 100 $"); radio("3_q_c1_1", "plus"); radio("3_q_c1_2", "monter")
at.multiselect(key="3_q_c2").set_value(["FNB (fonds indiciels)"])
suivant()
assert at.session_state.profil["C1"]["valeurs"] == ["intermediaire"]

# Page 5 : cryptos non cochées mais 10 % acceptés -> contradiction R3
at.multiselect(key="4_q_d1").set_value(["FNB d'actions", "Obligations"])
radio("4_q_d2", "Jusqu'à 10 %"); at.multiselect(key="4_q_d3").set_value(["Canada"])
radio("4_q_d12", "Au plus 10 % du portefeuille"); radio("4_q_d4", "Limiter la part en devises étrangères")
radio("4_q_d7", "Établies et stables"); radio("4_q_d8", "Non")
at.text_area(key="4_q_themes").input("L'IA et la santé m'intéressent, je refuse le tabac.")
suivant()

# Page 6 -> fin du questionnaire fixe
radio("5_q_e1", "Ce n'est pas un critère pour moi"); radio("5_q_e2", "Je refuse seulement les cas graves")
radio("5_q_g2", "CELI"); radio("5_q_e4", "Une préférence, sans obligation")
at.multiselect(key="5_q_e5").set_value(["Aucune exclusion", "Tabac"])  # « Aucune » + Tabac : on garde Tabac
at.multiselect(key="5_q_f2").set_value(["Aucune exclusion"])
suivant()
assert at.session_state.profil["E5"]["valeurs"] == ["tabac"], at.session_state.profil["E5"]
assert at.session_state.phase == "simulations"


def choisir(label_radio, valeur, bouton):
    [r for r in at.radio if r.label == label_radio][0].set_value(valeur)
    [b for b in at.button if b.label == bouton][0].click()
    at.run()
    assert not at.exception, at.exception


# Mise en situation 1 : replay, l'utilisateur garde tout aux 4 arrêts -> rupture observée « non atteinte »
for _ in range(4):
    choisir("Que faites-vous ?", "Garder", "Décider")
assert at.session_state.rp["fini"] and len(at.session_state.rp["decisions"]) == 4
[b for b in at.button if b.label == "Continuer"][0].click(); at.run()
assert at.session_state.profil["B2"]["valeurs"] == ["non_atteint"]
# Mise en situation 2 : fourchettes, choix du plus dynamique
choisir("Votre choix", [o for o in [r for r in at.radio if r.label == "Votre choix"][0].options if o.startswith("N° 5")][0], "Choisir")
assert at.session_state.profil["B6"]["valeurs"] == ["dynamique"]
# Mise en situation 3 : effet de mode, choix du titre A (très médiatisé) alors que D8 déclaré = « Non » -> R9
choisir("Votre choix", "Titre A", "Choisir")
assert at.session_state.profil["D8O"]["valeurs"] == ["oui"]
assert at.session_state.phase == "precisions" and at.session_state.profil["H1"]["valeurs"] == ["aucun"]
assert ["A6", "A12", "A8", "A7"] in APPELS and ["D5", "D6"] in APPELS  # analysés en arrière-plan

# Précisions : A5 (« je ne sais pas »), puis la réponse floue (relancée 2 fois puis incertaine)
file = at.session_state.file
assert [f["criteres"] for f in file] == [["A5"], ["A6", "A12", "A8", "A7"]], file
at.chat_input[0].set_value("environ 4 mois de dépenses").run()
assert at.session_state.profil["A5"]["statut"] == "validé"
at.chat_input[0].set_value("toujours flou").run()
assert at.session_state.file[0]["essai"] == 1
at.chat_input[0].set_value("encore flou").run()
assert at.session_state.profil["A6"]["statut"] == "incertain"

# Cohérence : R1, R2, R3 et R9 (déclaré « pas tenté » mais titre médiatisé choisi) posées une à une
vus = []
for _ in range(4):
    item = at.session_state.file[0]
    assert item["kind"] == "coherence", item
    vus.append(item["id"])
    [r for r in at.radio if r.label == "Votre réponse"][0].set_value(item["options"][0][0])
    [b for b in at.button if b.label == "Valider"][0].click()
    at.run()
    assert not at.exception, at.exception
assert sorted(vus) == ["R1", "R2", "R3", "R9"], vus
assert at.session_state.phase == "termine"
assert at.session_state.profil["B1"]["valeurs"] == ["20"] and at.session_state.profil["D2"]["valeurs"] == ["0"]
p = at.session_state.profil
print(f"Parcours OK : {len(p)} critères, {sum(v['statut'] == 'validé' for v in p.values())} validés, "
      f"{sum(v['statut'] != 'validé' for v in p.values())} incertains, contradictions résolues : {', '.join(sorted(vus))}")

# Second scénario : l'utilisateur déclare −40 % mais vend dès le 2e arrêt du replay -> on retient l'observé
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
at.session_state.phase = "simulations"
at.session_state.profil = {"B1": {"valeurs": ["40"], "source": "curseur", "citation": "40 %", "confiance": 1.0,
                                  "statut": "validé", "motif": ""},
                           "B5": {"valeurs": ["moderee_8_15"], "source": "QCM", "citation": "", "confiance": 1.0,
                                  "statut": "validé", "motif": ""}}
at.run()
choisir("Que faites-vous ?", "Garder", "Décider")
choisir("Que faites-vous ?", "Tout vendre", "Décider")
assert at.session_state.rp["fini"] and at.session_state.rp["cle"] == "equilibre"
[b for b in at.button if b.label == "Continuer"][0].click(); at.run()
b2 = at.session_state.profil["B2"]["valeurs"][0]
choisir("Votre choix", [o for o in [r for r in at.radio if r.label == "Votre choix"][0].options if o.startswith("N° 3")][0], "Choisir")
choisir("Votre choix", "Aucun, je préférerais un fonds diversifié", "Choisir")
p = at.session_state.profil
assert p["B1"]["valeurs"] == [b2] and p["B1"]["source"].startswith("replay") and p["H1"]["valeurs"] == ["grand"], (b2, p["B1"])
assert any("retient le plus prudent" in w.value for w in at.warning)
print(f"Replay avec vente OK : déclaré −40 %, vendu au 2e arrêt -> rupture retenue −{b2} % (écart grand)")
