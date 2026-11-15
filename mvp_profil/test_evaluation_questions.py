"""Tests hors ligne des mesures d'exactitude, relance et effectifs de parcours."""
from __future__ import annotations

from evaluation_questions import proportion, resumer_questions


assert proportion(0, 0)["taux"] is None and proportion(0, 0)["wilson_95"] is None
assert proportion(0, 1)["wilson_95"] == [0, 0.793451]
assert proportion(1, 1)["wilson_95"] == [0.206549, 1]
assert proportion(0, 100)["wilson_95"] == [0, 0.036993]
for s, n in ((2, 1), (-1, 10), (0, -1), (True, 1)):
    try:
        proportion(s, n)
        raise AssertionError("Effectifs invalides acceptés")
    except ValueError:
        pass

vide = resumer_questions([])
assert vide["erreur_parmi_reponses_utilisables"]["taux"] is None
assert vide["sessions"]["completion_sessions_closes"]["taux"] is None


def reponse(cid, tour, attendu, obtenu, utilisable, clarte="claire"):
    return {"type": "reponse", "conversation": "C1", "critere": cid, "tour": tour,
            "attendu": attendu, "obtenu": obtenu, "utilisable": utilisable, "clarte": clarte}


evenements = [
    reponse("A2", 1, ["10_15_ans"], ["10_15_ans"], True),
    reponse("A5", 2, ["3_6_mois"], [], False),
    {"type": "question", "conversation": "C1", "critere": "A5", "tour": 3,
     "nature": "clarification", "justifiee": False, "raison": "analyse_en_cours"},
    reponse("A5", 4, ["3_6_mois"], ["plus_6_mois"], True),
    {"type": "question", "conversation": "C1", "critere": "A5", "tour": 5,
     "nature": "clarification", "justifiee": False, "raison": "borne_non_definie"},
    reponse("A7", 6, [], [], False, "ambigue"),
    {"type": "question", "conversation": "C1", "critere": "A7", "tour": 7,
     "nature": "clarification", "justifiee": True},
    {"type": "question", "conversation": "C1", "critere": "A8", "tour": 8, "nature": "initiale"},
    {"type": "reponse", "conversation": "C2", "critere": "A2", "tour": 1},
    {"type": "session", "conversation": "C1", "etat": "terminee", "duree_s": 60},
    {"type": "session", "conversation": "C2", "etat": "abandonnee", "duree_s": 30},
    {"type": "session", "conversation": "C3", "etat": "en_cours"},
]
rapport = resumer_questions(evenements)
assert rapport["acceptation_correcte_premiere_reponse_claire"]["denominateur"] == 2
assert rapport["acceptation_correcte_premiere_reponse_claire"]["taux"] == 0.5
assert rapport["erreur_parmi_reponses_utilisables"]["taux"] == 0.5
assert rapport["clarifications_injustifiees"]["nombre"] == 2
assert rapport["clarifications_injustifiees"]["denominateur"] == 3
assert rapport["questions_injustifiees"]["denominateur"] == 3  # A8 non annoté ne devient pas un bon cas.
assert rapport["effectifs"]["reponses_non_annotees"] == 1
assert rapport["bons_refus"]["taux"] == 1
assert rapport["exces_questions_par_critere"] == [{"conversation": "C1", "critere": "A5", "clarification": 2}]
assert {q["critere"]: q["clarifications"] for q in rapport["questions_par_critere"]} == {"A5": 2, "A7": 1, "A8": 0}
assert rapport["sessions"]["completion_sessions_closes"]["denominateur"] == 2
assert rapport["sessions"]["completion_sessions_closes"]["taux"] == 0.5
assert rapport["sessions"]["en_cours"] == 1
assert rapport["sessions"]["duree_mediane_s"] == 45

# Réordonner les événements ne change pas le choix de la première réponse annotée.
autre = resumer_questions(list(reversed(evenements)))
assert autre["acceptation_correcte_premiere_reponse_claire"] == rapport["acceptation_correcte_premiere_reponse_claire"]

# Une première réponse non annotée ne devient pas une réussite au premier essai par sa répétition annotée.
non_annotee = {"type": "reponse", "conversation": "C1", "critere": "A2", "tour": 0}
premier_inconnu = resumer_questions([non_annotee, evenements[0]])
assert premier_inconnu["acceptation_correcte_premiere_reponse_claire"]["denominateur"] == 0
assert premier_inconnu["effectifs"]["premieres_reponses_non_annotees"] == 1

# Plusieurs instantanés de la même session ne comptent pas plusieurs participants.
une = resumer_questions([{"type": "session", "conversation": "C", "etat": "en_cours"},
                        {"type": "session", "conversation": "C", "etat": "terminee", "duree_s": 10}])
assert une["sessions"]["observees"] == 1 and une["sessions"]["completion_sessions_closes"]["taux"] == 1

for champ, valeur in (("justifiee", "oui"),):
    invalide = {"type": "question", "conversation": "C", "critere": "A2", "tour": 1,
                "nature": "clarification", champ: valeur}
    try:
        resumer_questions([invalide])
        raise AssertionError("Annotation invalide acceptée")
    except ValueError:
        pass

print("Mesures questions OK : effectifs explicites, zéro cas non mesuré, Wilson, erreurs et relances distinctes, sessions sans doublon")
