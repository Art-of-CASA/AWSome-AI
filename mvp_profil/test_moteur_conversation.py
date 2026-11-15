"""Régressions d'orchestration, sans serveur, sans Streamlit et sans modèle réel."""
from concurrent.futures import Future

from agents import Resultat
import moteur_conversation as m


class ExecuteurControle:
    def __init__(self):
        self.taches = []

    def submit(self, fonction, *args):
        f = Future()
        self.taches.append((f, args))
        return f


profil, c, ex = {}, m.creer(), ExecuteurControle()
m.recevoir(c, profil, "C'est pour ma retraite, dans quinze ans.")
assert profil["A2"]["valeurs"] == ["10_15_ans"] and profil["A2"]["nombre"] == 15
m.planifier(c, profil, ex, None, None, .8)
assert len(ex.taches) == 1
m.poser(c, m.suivante(c, profil, 10))
m.recevoir(c, profil, "En dehors du placement, ma réserve couvre six mois de dépenses.")
assert profil["A5"]["valeurs"] == ["3_6_mois"] and profil["A5"]["nombre"] == 6
ex.taches[0][0].set_result({
    "A3": Resultat("A3", ["retraite"], "ma retraite", .95, True, "clair", True),
    "A2": Resultat("A2", ["3_5_ans"], "quinze ans", .95, True, "modèle simulé erroné", True),
    "A5": Resultat("A5", ["moins_3_mois"], "six mois", .95, True, "modèle simulé erroné", True),
})
m.integrer(c, profil)
assert profil["A3"]["valeurs"] == ["retraite"], "Une autre réponse ne doit pas périmer l'objectif déjà exprimé."
assert profil["A2"]["nombre"] == 15 and profil["A5"]["nombre"] == 6
for _ in range(3):
    decision = m.suivante(c, profil, 10)
    assert not {"A2", "A5"} & set(decision["criteres"])
m.poser(c, decision)
m.recevoir(c, profil, "En fait, j'aurai besoin de cet argent dans deux ans.")
assert profil["A2"]["valeurs"] == ["moins_3_ans"] and profil["A2"]["nombre"] == 2

# Une panne de traitement conserve la réponse sans la présenter comme ambiguë.
p2, c2, ex2 = {}, m.creer(), ExecuteurControle()
m.recevoir(c2, p2, "Pour ma retraite.")
m.planifier(c2, p2, ex2, None, None, .8)
ex2.taches[0][0].set_exception(RuntimeError("service indisponible"))
m.integrer(c2, p2)
assert not c2["suivi"] and c2["echanges"][0][1] == "Pour ma retraite."
assert not {"A2", "A3"} & set(m.suivante(c2, p2, 10)["criteres"])

# Une frontière vraiment ambiguë reçoit au plus une clarification, jamais une troisième question.
p3, c3 = {}, m.creer()
m.recevoir(c3, p3, "J'aurai besoin de cet argent dans cinq à vingt ans.")
q = m.suivante(c3, p3, 10)
assert q["clarification"] and q["criteres"] == ["A2"], q
m.poser(c3, q)
m.recevoir(c3, p3, "Entre cinq et vingt ans.")
q = m.suivante(c3, p3, 10)
assert "A2" not in q["criteres"]
assert c3["questions_posees"]["A2"]["initiales"] == 1
assert c3["questions_posees"]["A2"]["clarifications"] == 1
assert "A2" not in p3 or p3["A2"]["statut"] not in ("validé", "retenu")
print("Moteur OK : chiffres immédiats, fraîcheur par critère, correction récente, panne sans relance et ambiguïté bornée.")
