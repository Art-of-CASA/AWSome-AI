"""Régressions sans modèle : une réponse nette suffit, une ambiguïté n'est pas devinée."""
from __future__ import annotations

import sys

from reponses_directes import analyser_reponses, extraire_reponses


HORIZON = "Dans combien d'années aurez-vous besoin de la majeure partie de cet argent ?"
RESERVE = "Sans toucher à ce placement, combien de mois de dépenses pourriez-vous couvrir ?"
DETTES = "Avez-vous en ce moment un solde de carte de crédit ou un prêt personnel à taux élevé ?"
cas = 0


def attendu(question, reponse, cid, valeur, **extras):
    global cas
    cas += 1
    resultat = extraire_reponses(question, reponse)
    assert cid in resultat, (question, reponse, analyser_reponses(question, reponse))
    r = resultat[cid]
    assert r["valeurs"] == [valeur], (reponse, r)
    assert r["statut"] == "validé" and r["citation"] == reponse and r["source"] == "réponse explicite (règle)"
    assert r["regle"].endswith(":" + cid)
    for cle, val in extras.items():
        assert r[cle] == val, (reponse, cle, r[cle], val)


def refuse(question, reponse, cid, precision=False):
    global cas
    cas += 1
    r = analyser_reponses(question, reponse)
    assert cid not in r["reponses"], (question, reponse, r)
    if precision:
        assert r["a_preciser"].get(cid, {}).get("motif"), r


# Frontières exactes : jamais une raison de redemander quinze ans ou six mois.
for reponse in ("15 ans", "quinze ans", "15ans", "quinzeans", "exactement quinze ans", "dans 15 ans", "c'est quinze ans", "euh, quinze ans"):
    attendu(HORIZON, reponse, "A2", "10_15_ans", nombre=15, unite="ans", duree_mois=180)
for n, valeur in ((0, "moins_3_ans"), (2, "moins_3_ans"), (3, "3_5_ans"), (5, "5_10_ans"),
                  (10, "10_15_ans"), (15, "10_15_ans"), (16, "plus_15_ans")):
    attendu(HORIZON, f"{n} ans", "A2", valeur, nombre=n)
for reponse in ("six mois", "6mois", "sixmois", "six mois de dépenses", "j'ai six mois de dépenses",
                "je peux couvrir six mois de dépenses", "j'en ai pour six mois", "exactement six mois"):
    attendu(RESERVE, reponse, "A5", "3_6_mois", nombre=6, duree_mois=6)
for n, valeur in ((0, "aucun"), (1, "moins_3_mois"), (2, "moins_3_mois"), (3, "3_6_mois"),
                  (6, "3_6_mois"), (7, "plus_6_mois")):
    attendu(RESERVE, f"{n} mois", "A5", valeur, nombre=n)
attendu(HORIZON, "quinze", "A2", "10_15_ans", nombre=15)
attendu("À quoi servira cet argent et dans combien d'années devrez-vous le récupérer ?",
        "C'est pour ma retraite, dans quinze ans.", "A2", "10_15_ans", nombre=15)
attendu(RESERVE, "six", "A5", "3_6_mois", nombre=6)
attendu(HORIZON, "six mois", "A2", "moins_3_ans", duree_mois=6)
attendu(RESERVE, "un an", "A5", "plus_6_mois", duree_mois=12)
attendu(HORIZON, "un an et demi", "A2", "moins_3_ans", nombre=1.5, duree_mois=18)
attendu(HORIZON, "dix-huit ans", "A2", "plus_15_ans", nombre=18)
attendu(HORIZON, "vingt et un ans", "A2", "plus_15_ans", nombre=21)
attendu(HORIZON, "quatre-vingt-un ans", "A2", "plus_15_ans", nombre=81)
attendu(HORIZON, "1,5 an", "A2", "moins_3_ans", nombre=1.5)

# Les bornes sont conservées comme bornes ; elles ne deviennent pas des mesures exactes.
attendu(HORIZON, "au moins quinze ans", "A2", "10_15_ans", nombre=None, nombre_min=15,
        nature="borne inférieure", borne_incluse=True)
attendu(HORIZON, "pas avant quinze ans au moins", "A2", "10_15_ans", nombre=None, nombre_min=15)
attendu(HORIZON, "plus de quinze ans", "A2", "plus_15_ans", nombre_min=15, borne_incluse=False)
attendu(RESERVE, "au moins six mois", "A5", "3_6_mois", nombre_min=6, nombre=None)
attendu(RESERVE, "plus de six mois", "A5", "plus_6_mois", nombre_min=6, borne_incluse=False)
attendu(HORIZON, "entre dix et douze ans", "A2", "10_15_ans", nombre=None, intervalle=[10, 12])
attendu(RESERVE, "entre quatre et six mois", "A5", "3_6_mois", intervalle=[4, 6])
refuse(HORIZON, "entre huit et douze ans", "A2", precision=True)
refuse(RESERVE, "entre deux et quatre mois", "A5", precision=True)
refuse(HORIZON, "entre douze et dix ans", "A2", precision=True)
refuse(HORIZON, "moins de quinze ans", "A2", precision=True)

# Les durées ne sont pas interchangeables entre horizon et réserve hors placement.
attendu("Quel est votre projet ?", "Mon horizon est de quinze ans", "A2", "10_15_ans")
attendu("Quelle est votre situation ?", "J'ai une réserve de six mois de dépenses de côté", "A5", "3_6_mois")
texte = "Mon horizon est quinze ans et j'ai une réserve de six mois de dépenses."
r = extraire_reponses("Quelle est votre situation ?", texte)
assert r["A2"]["valeurs"] == ["10_15_ans"] and r["A5"]["valeurs"] == ["3_6_mois"], r
assert all(v["citation"] == texte for v in r.values())
refuse(RESERVE, "mon placement couvre six mois de dépenses", "A5", precision=True)
refuse(RESERVE, "Je peux vivre six mois avec mon placement", "A5", precision=True)
refuse(RESERVE, "j'ai six mois de salaire", "A5", precision=True)
refuse(HORIZON, "j'ai quinze ans", "A2", precision=True)
refuse("Dans combien de temps aurez-vous besoin de cet argent ?", "j'aurai besoin de mon argent dans six mois", "A5")
refuse("Quel est votre horizon ?", "J'ai une réserve de six mois de dépenses", "A2")
refuse("Quelle est votre situation ?", "j'ai six mois de dépenses", "A5", precision=True)
refuse(HORIZON, "j'ai investi quinze ans", "A2", precision=True)
refuse(HORIZON, "Mon horizon est quinze ans ou un", "A2", precision=True)
refuse("Quel est votre horizon et combien de mois de réserve avez-vous ?", "six mois", "A5")
refuse("Quel est votre horizon et combien de mois de réserve avez-vous ?", "quinze ans", "A2")

# Négation, hésitation, historique et corrections : le parseur ne remplace pas le jugement contextuel.
for phrase in ("pas quinze ans", "15 ans pas 5", "quinze ans ou cinq", "depuis quinze ans", "j'avais quinze ans", "plus de quinze et moins de dix-huit ans"):
    refuse(HORIZON, phrase, "A2", precision=True)
for phrase in ("pas six mois", "six mois ou deux", "depuis six mois"):
    refuse(RESERVE, phrase, "A5", precision=True)
for question, texte, cid in ((HORIZON, "peut-être quinze ans", "A2"), (HORIZON, "environ quinze ans", "A2"),
                             (HORIZON, "je crois quinze ans", "A2"), (RESERVE, "peut-être six mois", "A5")):
    resultat = analyser_reponses(question, texte)
    assert cid not in resultat["reponses"] and cid not in resultat["a_preciser"], resultat
    cas += 1  # la nuance passe à l'IA, elle n'impose pas une nouvelle question
refuse(HORIZON, "mon horizon est quinze ans ; mon horizon est vingt ans", "A2", precision=True)
refuse(RESERVE, "", "A5")
refuse(RESERVE, "je ne sais pas", "A5")
refuse(HORIZON, "1500 ans", "A2", precision=True)
refuse(HORIZON, "-15 ans", "A2", precision=True)
refuse(RESERVE, "-6 mois", "A5", precision=True)
refuse(RESERVE, "Ma réserve couvre six mois mais elle est bloquée", "A5", precision=True)
refuse("Quelle est votre situation ?", "Cet argent est réservé pour quinze ans", "A5")
refuse("Quelle est votre situation ?", "Je réserve de l'argent pour quinze ans", "A5")
assert extraire_reponses(HORIZON, "15 ans", ("A5",)) == {}
assert extraire_reponses(HORIZON, "15 ans", ("inconnu",)) == {}

# Un oui/non n'est immédiat que pour une question de dette univoque.
attendu(DETTES, "oui", "A7", "oui")
attendu(DETTES, "non", "A7", "non")
refuse("Avez-vous des dettes à taux élevé et une réserve ?", "oui", "A7")
refuse(DETTES, "oui mais je ne sais pas si le taux est élevé", "A7")
refuse("Avez-vous des enfants ?", "non", "A7")
assert "agents" not in sys.modules and "anthropic" not in sys.modules
print(f"Réponses directes OK : {cas} cas, frontières exactes, contexte, bornes conservées, ambiguïtés et absence de modèle.")
