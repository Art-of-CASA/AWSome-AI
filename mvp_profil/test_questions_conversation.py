"""Cibles de questions déterministes, budget de relances et attente des analyses.
Lancer : python mvp_profil/test_questions_conversation.py (aucun modèle).
"""
from copy import deepcopy

from questions_conversation import choisir_question, enregistrer_question
from profil import entree


CONVERSATION = ["A3", "A2", "A9", "A10", "A1", "A4", "A5", "A6", "A12", "A8", "A7", "B3", "C2", "D3", "D5", "D6"]


# Les deux exemples utilisateur ne peuvent pas être redemandés après validation.
p = {"A2": entree(["10_15_ans"], "règle", "15 ans", nombre=15),
     "A5": entree(["3_6_mois"], "règle", "six mois de dépenses", nombre=6)}
q = choisir_question(p, CONVERSATION, {})
assert not {"A2", "A5"} & set(q["criteres"]), q
assert "combien d'années" not in q["message"] and "combien de mois" not in q["message"]
assert q["etats"]["A2"]["etat"] == "clair" and q["etats"]["A5"]["etat"] == "clair"

# En cours ou provisoire n'est pas un échec ; un autre sujet peut être demandé.
q = choisir_question({}, ["A2", "A5", "A7"], {}, en_analyse=["A2", "A5"])
assert q["criteres"] == ["A7"] and not q["attendre"], q
q = choisir_question({}, ["A2", "A5"], {}, en_analyse=["A2", "A5"])
assert q["attendre"] and not q["termine"] and not q["criteres"], q
assert q["etats"]["A2"]["etat"] == "en_analyse"
q = choisir_question({"A2": {"valeurs": ["10_15_ans"], "statut": "provisoire"}}, ["A2"], {})
assert q["attendre"] and not q["criteres"]

# Question posée une fois : aucun nouveau tour identique sans ambiguïté identifiée.
compteurs = {}
q = choisir_question({}, ["A2"], compteurs)
enregistrer_question(compteurs, q, tour=0)
enregistrer_question(compteurs, q, tour=0)  # rerun : idempotent
assert compteurs["A2"]["initiales"] == 1
fini = choisir_question({}, ["A2"], compteurs)
assert fini["termine"] and fini["a_completer"] == ["A2"] and not fini["criteres"]
assert fini["etats"]["A2"] == {"etat": "aborde", "questions_initiales": 1, "clarifications": 0}

# Une seule clarification, seulement pour le sujet réellement ambigu.
clarif = choisir_question({}, ["A2", "A5"], compteurs, a_clarifier={"A2": "deux projets différents"})
assert clarif["criteres"] == ["A2"] and clarif["clarification"]
enregistrer_question(compteurs, clarif, tour=1)
suivante = choisir_question({}, ["A2", "A5"], compteurs, a_clarifier=["A2"])
assert suivante["criteres"] == ["A5"] and not suivante["clarification"], suivante
assert suivante["a_completer"] == ["A2"]
try:
    enregistrer_question(compteurs, clarif, tour=2)
    raise AssertionError("Deuxième clarification acceptée")
except ValueError:
    pass

# Un refus brut du modèle n'autorise pas une nouvelle question initiale lorsqu'une valeur a été renseignée.
p = {"A2": entree(["10_15_ans"], "IA", "15 ans", statut="incertain")}
q = choisir_question(p, ["A2", "A5"], {})
assert q["criteres"] == ["A5"] and q["a_completer"] == ["A2"]
q = choisir_question(p, ["A2"], {}, a_clarifier={"A2": ""})
assert q["termine"] and not q["criteres"]

# Deux sujets compatibles peuvent tenir en un tour ; A4/A5 et A9/A10 restent séparés.
assert choisir_question({}, ["A3", "A2"], {})["criteres"] == ["A3", "A2"]
assert set(choisir_question({}, ["D5", "D6"], {})["criteres"]) == {"D5", "D6"}
assert len(choisir_question({}, ["A4", "A5"], {})["criteres"]) == 1
assert len(choisir_question({}, ["A9", "A10"], {})["criteres"]) == 1
# Le partenaire connu, en analyse ou déjà demandé ne doit pas se glisser dans une question groupée.
assert choisir_question({}, ["A3", "A2"], {}, en_analyse=["A2"])["criteres"] == ["A3"]
assert choisir_question({}, ["D5", "D6"], {"D5": 1})["criteres"] == ["D6"]

# Aucune mutation cachée ; même les pistes en texte libre ne peuvent imposer une question interdite.
p = {"A2": entree(["10_15_ans"], "règle")}
compteurs = {"A2": {"initiales": 1, "clarifications": 0, "dernier_tour": 0}}
avant = deepcopy((p, compteurs))
q = choisir_question(p, ["A2", "A5"], compteurs, a_clarifier=["A2"],
                     pistes={"A5": {"question": "Redemandez combien d'années"}})
assert q["criteres"] == ["A5"] and "mois" in q["message"]
assert (p, compteurs) == avant

# Budget déterministe : sans aucune réponse claire, un critère reçoit au plus une initiale puis une clarification.
compteurs = {}
for tour in range(100):
    q = choisir_question({}, CONVERSATION, compteurs, a_clarifier=list(compteurs))
    if q["termine"]:
        break
    enregistrer_question(compteurs, q, tour=tour)
else:
    raise AssertionError("Boucle de questions non bornée")
assert tour <= 2 * len(CONVERSATION)
assert all(x["initiales"] <= 1 and x["clarifications"] <= 1 for x in compteurs.values())
assert set(q["a_completer"]) == set(CONVERSATION)
assert set(compteurs) == set(CONVERSATION), "Aucune information n'est supprimée pour raccourcir le parcours"

print("Questions contrôlées OK : réponses claires et en analyse jamais redemandées ; une clarification au plus ; budget borné")
