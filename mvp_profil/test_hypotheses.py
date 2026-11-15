from hypotheses import etat, lignes


def test_statut_prime_sur_confiance():
    assert etat({"statut": "incertain", "valeurs": ["x"], "confiance": .95}, .8)[0] == "rouge"
    assert etat({"statut": "retenu", "valeurs": ["x"], "confiance": .9}, .8)[0] == "jaune"


def test_seuils_et_recherche():
    c = {"statut": "validé", "valeurs": ["x"]}
    for confiance, couleur in [(.49, "rouge"), (.5, "jaune"), (.79, "jaune"), (.8, "vert")]:
        assert etat({**c, "confiance": confiance}, .8)[0] == couleur
    assert etat({**c, "confiance": 1, "etiquetage": "en_attente"}, .8)[0] == "attente"
    assert etat({**c, "confiance": 1, "etiquetage": "echec"}, .8)[0] == "rouge"
    assert etat({}, .8)[0] == "rouge"


def test_tous_criteres_et_tri_global():
    from criteres import CRITERES
    resultat = lignes({"A2": {"confiance": .9}}, [{"id": "X1", "confiance": .6}])
    assert len(resultat) == len(CRITERES) + 1
    assert resultat[-1]["id"] == "A2"
    assert resultat[-2]["id"] == "X1"


def test_demo_n_affiche_pas_de_correction():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).with_name("demo_hypotheses.py"))).run()
    assert not app.exception
    assert len(app.expander) == 38
    assert "Stabilité des revenus" in app.expander[0].label
    assert all("%" not in e.label.rsplit(" · ", 1)[-1] for e in app.expander)
    assert not app.checkbox
    assert not app.selectbox
    assert not app.button
