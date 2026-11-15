"""Test hors ligne du parcours complet dans l'interface (Streamlit AppTest), agents simulés.

Scénario : 6 pages fixes avec un « Je ne sais pas », une réponse libre floue et trois contradictions
volontaires ; une question déjà connue retirée de sa page ; réponses libres et précisions À LA VOIX,
demande de répétition, possibilité choisie à l'oral et question ouverte jusqu'au profil final.
Lancer : python mvp_profil/test_app.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.environ["AWS_ACCESS_KEY_ID"] = "AKIATEST"      # identifiants factices : les agents sont simulés,
os.environ["AWS_SECRET_ACCESS_KEY"] = "test"        # aucun appel ne part vers AWS

import agents  # noqa: E402
import chercheur  # noqa: E402
import entretien  # noqa: E402
import voix_composant  # noqa: E402
import replay_composant  # noqa: E402
import criteres_dynamiques  # noqa: E402
from agents import Debat, Resultat  # noqa: E402
from criteres import CRITERES  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APPELS = []


SEUILS, OUVERTES, FACULTATIFS = [], [], []
VOIX = {"n": 0, "texte": None}  # micro simulé : chaque appel à parler() envoie un nouvel énoncé
REPLAY = {"args": None, "payload": None}


def faux_replay(**kw):
    REPLAY["args"] = kw
    return REPLAY["payload"]


def terminer_replay(actions=None, cursor=None):
    """Le navigateur transmet une fin naturelle, ou une vente choisie entre deux séances."""
    args = REPLAY["args"]
    REPLAY["payload"] = {"session_id": args["session_id"], "seq": args["ack"] + 1,
                         "cursor": len(args["values"]) - 1 if cursor is None else cursor,
                         "actions": actions or [], "complete": True}
    at.run()
    REPLAY["payload"] = None
    assert not at.exception, at.exception


def fausse_voix(**kw):
    return {"kind": "audio", "n": VOIX["n"], "wav": "", "instance_id": "micro-test",
            "session_id": kw["session_id"], "question_id": kw["question_id"], "playback_id": kw["n"]} if VOIX["texte"] is not None else None


def pas_de_voix(texte):
    raise RuntimeError("Polly indisponible en test")


def faux_choix(backend, question, options, reponse):
    return 0 if "première" in reponse else -1


def parler(texte):
    VOIX["n"] += 1
    VOIX["texte"] = texte
    at.run()
    assert not at.exception, at.exception
    assert not at.chat_input and not at.text_area, "La réponse libre doit être orale."


def faux_debat(backend, echanges, criteres_ids, seuil=0.8, max_tours=2, facultatifs=()):
    APPELS.append(list(criteres_ids))
    SEUILS.append(seuil)
    FACULTATIFS.append(list(facultatifs))
    flou = "flou" in echanges[-1][1]
    res = {c: Resultat(c, [] if flou else [CRITERES[c]["valeurs"][0]], echanges[-1][1], 0.3 if flou else 0.9,
                       not flou, "Réponse réellement ambiguë" if flou else "ok", accord_critique=not flou,
                       precision_necessaire=flou, motif_precision="Situation non renseignée" if flou else "")
           for c in criteres_ids}
    return Debat(res, [{"tour": 1, "classificateur": {"propositions": []}, "critique": None, "valides": []}],
                 "Pouvez-vous préciser ?" if flou else "")


def faux_creer(backend, question, reponse, seuil, deja=0):
    OUVERTES.append(reponse)
    return [{"id": f"X{deja + 1}", "nom": "Pas d'actions de son employeur (Shopify)", "effet": "exclure",
             "dimension": "titre", "valeurs": ["SHOP.TO"], "plafond_pct": 0, "actifs": ["SHOP.TO"],
             "citation": "je ne veux pas plus d'actions de mon employeur", "confiance": 0.9, "statut": "validé",
             "motif": "ok", "regle": "Exclure : titre = SHOP.TO (1 actif de l'univers)", "source": "question ouverte (IA)",
             "applicable": True},
            {"id": f"X{deja + 2}", "nom": "Rien de lié à Elon Musk", "effet": "exclure", "dimension": "a_etiqueter",
             "colonne": "", "valeurs": [], "plafond_pct": 0, "actifs": [], "concept": "entreprises liées à Elon Musk",
             "etiquetage": "en_attente", "citation": "rien qui touche à Elon Musk", "confiance": 0.85, "statut": "validé",
             "motif": "ok", "regle": "Exclure : « entreprises liées à Elon Musk » (recherche des actifs concernés en cours)",
             "source": "question ouverte (IA)"}]


def faux_etiqueter(backend, concept, effet="exclure"):
    import time
    time.sleep(0.3)
    return {"mot_cle": "kw_dyn_entreprises_liees_a_elon_musk", "concept": concept, "definition": "Lié à Elon Musk.",
            "oui": ["TSLA"], "partiel": [], "fnb_exposes": {"QQQ": 0.034}, "rejetes": [], "appels_outils": [{}],
            "verdicts": [{"ticker": "TSLA", "valeur": "oui", "preuve": "Il est le directeur général de Tesla",
                          "source": "web:fr:Elon Musk", "confiance": 0.9, "url": "https://fr.wikipedia.org/wiki/Elon_Musk"}],
            "cree_le": "2026-11-14T19:30:00", "duree_s": 0.3, "depuis_cache": False}


agents.debattre = faux_debat
agents.aws_identifiants_presents = lambda: True
agents.backend_bedrock = lambda: agents.Backend(None, agents.MODELES["bedrock"], "test hors ligne")
criteres_dynamiques.creer = faux_creer
voix_composant.conversation_vocale = fausse_voix
replay_composant.replay_marche = faux_replay
entretien.transcrire = lambda wav: VOIX["texte"]
entretien.synthese_vocale = pas_de_voix
entretien.choisir_option = faux_choix
chercheur.etiqueter = faux_etiqueter
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
    assert not at.chat_input and not at.text_area


# Page 1 : coussin de sécurité + plus de 15 ans -> contradiction R2
radio("0_q_a3", "Avoir un coussin de sécurité pour les imprévus"); radio("0_q_a2", "Plus de 15 ans")
radio("0_q_a9", "Non, je n'y toucherai pas"); radio("0_q_a10", "Non")
suivant()
assert at.session_state.section == 1 and at.session_state.profil["A3"]["valeurs"] == ["coussin_securite"]

# Page 2 : question oubliée -> message, puis « Je ne sais pas » + réponse libre floue
radio("1_q_a4", "Moins du quart"); radio("1_q_a1", "En milieu de carrière")
suivant()
assert at.session_state.section == 1 and len(at.warning) >= 1  # A5 manquant : on reste sur la page
radio("1_q_a5", "Je ne sais pas")
suivant()
assert at.session_state.phase == "libre_oral"
parler("c'est flou")
assert at.session_state.phase == "questionnaire"
assert at.session_state.profil["A5"]["statut"] == "à préciser"

# Page 3 : « je vends tout » mais curseur à 40 % -> contradiction R1
radio("2_q_b1r", "Je vends tout pour arrêter les pertes"); at.selectbox(key="2_q_b1").select(40)
radio("2_q_b5", "800 à 1 500 $ (modérée, 8 à 15 %)"); radio("2_q_b7", "Un à deux ans")
radio("2_q_b3", "Jamais"); radio("2_q_b4", "Chaque mois")
suivant()
assert at.session_state.profil["B1"]["valeurs"] == ["40"]

# Page 4 : quiz 2/3 -> intermédiaire
radio("3_q_c1_0", "Plus de 1 100 $"); radio("3_q_c1_1", "plus"); radio("3_q_c1_2", "monter")
at.multiselect(key="3_q_c2").set_value(["FNB (fonds indiciels)"])
suivant()
assert at.session_state.profil["C1"]["valeurs"] == ["intermediaire"]

# Page 5 : les exclusions et l'accès passent avant les préférences.
radio("4_q_e1", "Ce n'est pas un critère pour moi"); radio("4_q_e2", "Je refuse seulement les cas graves")
radio("4_q_g2", "CELI"); radio("4_q_g3", "Non, Canada et États-Unis seulement"); radio("4_q_e4", "Une préférence, sans obligation")
at.multiselect(key="4_q_e5").set_value(["Aucune exclusion", "Tabac"])
at.multiselect(key="4_q_f2").set_value(["Aucune exclusion"])
suivant()
assert at.session_state.profil["E5"]["valeurs"] == ["tabac"], at.session_state.profil["E5"]

# Page 6 : le style déjà connu ne doit pas être redemandé.
from profil import entree  # noqa: E402
at.session_state.profil["D7"] = entree(["etablie"], "réponse libre (IA)", "des entreprises solides", 0.9)
at.run()
assert not [r for r in at.radio if r.key == "5_q_d7"] and any("1 question(s) retirée(s)" in c.value for c in at.caption)
# Cryptos non cochées mais 10 % acceptés -> contradiction R3
at.multiselect(key="5_q_d1").set_value(["FNB d'actions", "Obligations"])
radio("5_q_d2", "Jusqu'à 10 %"); at.multiselect(key="5_q_d3").set_value(["Canada"])
radio("5_q_d12", "Au plus 10 % du portefeuille"); radio("5_q_d4", "Limiter la part en devises étrangères")
radio("5_q_d8", "Non"); radio("5_q_d11", "Un mélange des deux"); radio("5_q_d9", "10 % au plus")
suivant()
assert at.session_state.phase == "libre_oral"
parler("L'IA et la santé m'intéressent, je refuse le tabac.")

assert at.session_state.phase == "simulations"


def choisir(label_radio, valeur, bouton):
    [r for r in at.radio if r.label == label_radio][0].set_value(valeur)
    [b for b in at.button if b.label == bouton][0].click()
    at.run()
    assert not at.exception, at.exception


# Mise en situation 1 : le marché défile sans intervention ni question imposée.
terminer_replay()
assert at.session_state.rp["fini"] and not at.session_state.rp["actions"]
[b for b in at.button if b.label == "Continuer"][0].click(); at.run()
assert at.session_state.profil["B2"]["valeurs"] == ["non_atteint"]
# Mise en situation 2 : fourchettes, choix du plus dynamique
choisir("Votre choix", [o for o in [r for r in at.radio if r.label == "Votre choix"][0].options if o.startswith("N° 5")][0], "Choisir")
assert at.session_state.profil["B6"]["valeurs"] == ["dynamique"]
# Mise en situation 3 : titre médiatisé choisi, conservé comme signal sans question ni correction de D8/D12.
choisir("Votre choix", "Titre A", "Choisir")
assert at.session_state.profil["D8O"]["valeurs"] == ["oui"]
# Déclaré −40 %, tout gardé, mais le replay n'a montré qu'environ −15 % : la tolérance n'a PAS été testée
assert at.session_state.phase == "precisions" and at.session_state.profil["H1"]["valeurs"] == ["non_teste"]
assert ["A6", "A12", "A8", "A7"] in APPELS and ["D5", "D6"] in APPELS  # analysés en arrière-plan
# Chaque réponse libre est aussi lue pour les autres critères encore inconnus (facultatifs), sauf ceux déjà connus
fac_situation = FACULTATIFS[APPELS.index(["A6", "A12", "A8", "A7"])]
assert "D7" in fac_situation and "A3" not in fac_situation and "C1" not in fac_situation, fac_situation

# Précisions : le groupe comportant les dettes passe d'abord, puis la réserve d'urgence.
file = at.session_state.file
assert [f["criteres"] for f in file] == [["A6", "A12", "A8", "A7"], ["A5"]], file
assert at.session_state.vocal["etape"].startswith("prec:")  # identifiant propre à la précision lue
parler("toujours flou")
assert at.session_state.profil["A6"]["statut"] == "incertain"  # pas de 3e question
assert APPELS[-1] == ["A6", "A12", "A8", "A7"] and SEUILS[-1] == 0.8
nb_appels = len(APPELS)
parler("J'ai 4 mois de dépenses de côté, en dehors de ce placement.")
assert at.session_state.profil["A5"]["statut"] == "validé"
assert at.session_state.profil["A5"]["valeurs"] == ["3_6_mois"]
assert len(APPELS) == nb_appels, "Une réponse numérique explicite ne nécessite aucun modèle."

# Cohérence : seules les contradictions établies R1, R2 et R3 donnent une question.
vus = []
# La 1re contradiction se règle à l'oral : demande de répétition (relue, rien d'enregistré), puis « la première »
premiere = at.session_state.file[0]
n_avant = at.session_state.vocal["n"]
parler("Pardon, pouvez-vous répéter ?")
assert at.session_state.file[0] is not None and at.session_state.file[0]["id"] == premiere["id"]
assert at.session_state.vocal["n"] == n_avant + 1  # relue
parler("euh, la première")
vus.append(premiere["id"])
assert premiere["id"] in at.session_state.coherences_posees
for _ in range(2):
    item = at.session_state.file[0]
    assert item["kind"] == "coherence", item
    vus.append(item["id"])
    [r for r in at.radio if r.label == "Votre réponse"][0].set_value(item["options"][0][0])
    [b for b in at.button if b.label == "Valider"][0].click()
    at.run()
    assert not at.exception, at.exception
assert sorted(vus) == ["R1", "R2", "R3"], vus
assert at.session_state.profil["D8"]["valeurs"] == ["non"]
assert at.session_state.profil["D12"]["valeurs"] == ["plafonne_10"]

# Question ouverte finale -> critère dynamique
assert at.session_state.phase == "ouverte" and at.session_state.vocal["etape"] == "ouverte"
parler("Je travaille chez Shopify, je ne veux pas plus d'actions de mon employeur.")  # réponse à l'oral
assert at.session_state.phase == "termine" and OUVERTES == ["Je travaille chez Shopify, je ne veux pas plus d'actions de mon employeur."]
assert at.session_state.dynamiques[0]["id"] == "X1" and any("X1 · Pas d'actions de son employeur" in m.value for m in at.markdown)
# X2 : le chercheur travaille en arrière-plan, puis le critère devient une règle sur le nouveau mot-clé
assert at.session_state.dynamiques[1]["etiquetage"] == "en_attente" and len(at.session_state.recherches) == 1
import time; time.sleep(0.6); at.run()
x2 = at.session_state.dynamiques[1]
assert x2["etiquetage"] == "fait" and x2["actifs"] == ["TSLA"] and not at.session_state.recherches, x2
assert x2["regle"] == "Exclure : kw_dyn_entreprises_liees_a_elon_musk = oui (TSLA) ; FNB qui en détiennent : QQQ (3,4 %)", x2["regle"]
assert any("Preuves de X2" in e.label for e in at.expander)
assert at.session_state.profil["B1"]["valeurs"] == ["20"] and at.session_state.profil["D2"]["valeurs"] == ["0"]
p = at.session_state.profil
print(f"Parcours OK : {len(p)} critères, {sum(v['statut'] == 'validé' for v in p.values())} validés, "
      f"{sum(v['statut'] != 'validé' for v in p.values())} incertains, contradictions résolues : {', '.join(sorted(vus))}")

# Second scénario : l'utilisateur déclare −40 %, puis vend librement pendant la baisse.
VOIX["texte"] = None
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
at.session_state.phase = "simulations"
at.session_state.profil = {"B1": {"valeurs": ["40"], "source": "curseur", "citation": "40 %", "confiance": 1.0,
                                  "statut": "validé", "motif": ""},
                           "B5": {"valeurs": ["moderee_8_15"], "source": "QCM", "citation": "", "confiance": 1.0,
                                  "statut": "validé", "motif": ""}}
at.run()
indice_vente = next(i for i, valeur in enumerate(REPLAY["args"]["values"]) if valeur <= 9000)
terminer_replay([{"index": indice_vente, "action": "vendre"}], cursor=indice_vente)
assert at.session_state.rp["fini"] and at.session_state.rp["cle"] == "equilibre"
[b for b in at.button if b.label == "Continuer"][0].click(); at.run()
b2 = at.session_state.profil["B2"]["valeurs"][0]
choisir("Votre choix", [o for o in [r for r in at.radio if r.label == "Votre choix"][0].options if o.startswith("N° 3")][0], "Choisir")
choisir("Votre choix", "Aucun, je préférerais un fonds diversifié", "Choisir")
p = at.session_state.profil
assert p["B1"]["valeurs"] == [b2] and p["B1"]["source"].startswith("replay") and p["H1"]["valeurs"] == ["grand"], (b2, p["B1"])
assert any("retient le plus prudent" in w.value for w in at.warning)
print(f"Replay avec vente libre OK : déclaré −40 %, vente pendant la baisse -> rupture retenue −{b2} % (écart grand)")

# Mode démonstration : un persona de l'énoncé se charge en un clic et sa synthèse s'affiche
VOIX["texte"] = None
at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30)
at.run()
[b for b in at.button if b.label == "Charger Robert"][0].click(); at.run()
assert not at.exception, at.exception
assert at.session_state.phase == "termine" and at.session_state.persona["nom"] == "Robert"
assert [tab.label for tab in at.tabs] == ["Synthèse", "Hypothèses du profil"]
assert any(m.label == "Budget de perte du portefeuille" and m.value == "15 %" for m in at.metric), [(m.label, m.value) for m in at.metric]
assert any("Simulation éducative" in i.value for i in at.info)
print("Mode démonstration OK : Robert chargé, budget de perte 15 %, bandeau de simulation affiché")

# Les explications et la sensibilité sont visibles, et un plafond qualitatif se confirme sans exclusion.
assert any("réponses qui déterminent" in m.value for m in at.markdown)
assert any("Détail des variations" in e.label for e in at.expander)
limite = {"id": "X1", "nom": "Limiter les banques", "effet": "plafonner", "dimension": "theme",
          "valeurs": ["banque"], "plafond_pct": None, "actifs": ["RY.TO"], "citation": "Limiter les banques",
          "confiance": 0.9, "statut": "à préciser", "applicable": False, "motif": "Pourcentage maximal à préciser",
          "regle": "Limiter (plafond à préciser) : theme = banque", "source": "question ouverte (IA)"}
at.session_state.dynamiques = [limite]
at.run()
assert not at.exception, at.exception
assert at.session_state.dynamiques[0]["plafond_pct"] is None
at.number_input[0].set_value(7)
[c for c in at.checkbox if c.label.startswith("Je confirme cette règle")][0].check()
[b for b in at.button if b.label == "Confirmer cette précision"][0].click()
at.run()
assert not at.exception, at.exception
limite = at.session_state.dynamiques[0]
assert limite["effet"] == "plafonner" and limite["plafond_pct"] == 7 and limite["applicable"], limite
assert limite["statut"] == "validé" and "Plafonner à 7 %" in limite["regle"]
print("Synthèse explicable, robustesse et confirmation d'un plafond sans exclusion : OK")

# Part minimale à confirmer ; une règle validée sans cible n'affiche pas ✅ ; la parole n'est jamais du HTML.
minimum = {"id": "X2", "nom": "Obligations minimum", "effet": "minimum", "dimension": "classe", "valeurs": ["etf_bond"],
           "plafond_pct": 0, "minimum_pct": None, "actifs": ["XBB.TO"], "citation": "une part minimale en obligations",
           "confiance": 0.9, "statut": "à préciser", "applicable": False, "motif": "Pourcentage minimal à préciser",
           "regle": "Garder une part minimale (pourcentage à préciser) : classe = etf_bond", "source": "question ouverte (IA)"}
sans_cible = {"id": "X3", "nom": "Tabac <b>gras</b>", "effet": "exclure", "dimension": "mot_cle_dynamique",
              "colonne": "kw_dyn_tabac", "valeurs": ["oui"], "plafond_pct": 0, "actifs": [], "etiquetage": "fait",
              "citation": "<img src=x onerror=alert(1)> pas de tabac", "confiance": 0.9, "statut": "validé",
              "applicable": False, "motif": "ok", "regle": "Exclure : kw_dyn_tabac = oui (aucun lien établi)",
              "source": "question ouverte (IA)", "preuves": [], "recherche": {}}
at.session_state.dynamiques = [limite, minimum, sans_cible]
at.run()
assert not at.exception, at.exception
textes = [m.value for m in at.markdown if "X3 ·" in m.value]
assert textes and "⚠️ Aucun filtre applicable" in textes[0] and "✅" not in textes[0], textes
assert "<img" not in textes[0] and "&lt;img" in textes[0] and "<b>" not in textes[0], textes
assert any("Part minimale du portefeuille" in n.label for n in at.number_input), [n.label for n in at.number_input]
champ = [n for n in at.number_input if "Part minimale" in n.label][0]
champ.set_value(12)
[c for c in at.checkbox if c.label.startswith("Je confirme cette règle")][0].check()
[b for b in at.button if b.label == "Confirmer cette précision"][0].click()
at.run()
assert not at.exception, at.exception
minimum = at.session_state.dynamiques[1]
assert minimum["minimum_pct"] == 12 and minimum["applicable"] and minimum["regle"].startswith("Garder au moins 12 %"), minimum
print("Critères personnels : part minimale confirmée, ✅ réservé aux règles applicables, texte échappé : OK")

# L'aperçu est utilisable sans accès au modèle et n'enregistre aucun profil d'investisseur.
from unittest.mock import patch  # noqa: E402

VOIX["texte"] = None
with patch("agents.aws_identifiants_presents", return_value=False), \
     patch("agents.backend_bedrock", side_effect=AssertionError("L'aperçu ne doit pas appeler le modèle")):
    at = AppTest.from_file(os.path.join(os.path.dirname(__file__), "app.py"), default_timeout=30).run()
    assert not at.exception, at.exception
    assert next(b for b in at.button if b.label == "Commencer en conversation").disabled
    assert next(b for b in at.button if b.label == "Questionnaire classique").disabled
    assert not at.button(key="decouvrir_replay").disabled
    at.button(key="decouvrir_replay").click().run()
    assert not at.exception, at.exception
    assert at.session_state.phase == "simulations" and at.session_state.demo_replay
    assert not at.session_state.profil
    terminer_replay()
    assert at.session_state.rp["fini"] and not at.session_state.profil
    at.button(key="replay_suite").click().run()
    assert not at.exception, at.exception
    assert at.session_state.phase == "accueil" and not at.session_state.profil
    assert "demo_replay" not in at.session_state and "rp" not in at.session_state
print("Aperçu sans identifiants : lancement, replay complet et retour à l'accueil sans création de profil OK")
