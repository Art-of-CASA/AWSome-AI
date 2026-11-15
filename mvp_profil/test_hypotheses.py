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
    from criteres import CRITERES
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(Path(__file__).with_name("demo_hypotheses.py"))).run()
    assert not app.exception
    assert len(app.expander) == len(CRITERES) + 1
    assert "Stabilité des revenus" in app.expander[0].label
    assert all("%" not in e.label.rsplit(" · ", 1)[-1] for e in app.expander)
    assert not app.checkbox
    assert not app.selectbox
    assert not app.button


def test_personas_questionnaires_complets():
    import json
    from pathlib import Path
    from unittest.mock import patch

    from criteres import CRITERES
    from profil import incoherences
    from streamlit.testing.v1 import AppTest

    racine = Path(__file__).parent
    # Charger les démonstrations doit fonctionner sans appeler un modèle ou un service réseau.
    with patch("socket.create_connection", side_effect=AssertionError("Appel réseau inattendu")):
        for nom in ("amira", "mateo", "robert"):
            persona = json.loads((racine / "personas" / f"{nom}.json").read_text(encoding="utf-8"))
            profil = persona["profil"]
            assert set(profil) == set(CRITERES)
            assert not incoherences(profil)
            assert all(e["citation"] and e["motif"] for e in profil.values())
            app = AppTest.from_file(str(racine / "app.py"), default_timeout=30).run()
            assert not app.exception
            assert {b.key for b in app.button if b.key and b.key.startswith("persona_")} == {
                "persona_amira", "persona_mateo", "persona_robert"}
            app.button(key=f"persona_{nom}").click().run()
            assert not app.exception
            assert app.session_state["profil"] == profil
            assert app.session_state["replay_trace"] == persona["replay"]
            assert "Hypothèses du profil" in [t.label for t in app.tabs]
            hypotheses = [e for e in app.expander if e.label.endswith(" · Validé")]
            assert len(hypotheses) == len(CRITERES)
            texte = "\n".join(m.value for m in app.markdown)
            assert all(e["citation"] in texte and e["motif"] in texte for e in profil.values())
            assert "Aucune citation disponible." not in texte
            assert "Aucune hypothèse disponible pour le moment." not in texte


if __name__ == "__main__":
    test_statut_prime_sur_confiance()
    test_seuils_et_recherche()
    test_tous_criteres_et_tri_global()
    test_demo_n_affiche_pas_de_correction()
    test_personas_questionnaires_complets()
    print("Hypothèses du profil : statuts, tri et démonstration OK")
