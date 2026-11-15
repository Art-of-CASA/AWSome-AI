"""Test hors ligne de l'agent CHERCHEUR (faux serveur : vrai SDK et vrais outils, Wikipédia simulé, aucun coût).

Scénario « rien qui touche à Elon Musk » : l'agent appelle trois outils (nos données, recherche Wikipédia, page
Wikipédia), puis rend 6 verdicts. Le code doit garder les 2 preuves réelles de Tesla, écarter un ticker hors univers, une preuve
inventée et une source jamais lue ; le critique en refuse un autre ; les FNB qui détiennent Tesla deviennent exposés ;
le mot-clé est mis en cache et repris sans nouvel appel.
Lancer : python mvp_profil/test_chercheur.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
os.environ["ALPHAFORGE_CACHE"] = tempfile.mkdtemp()

import anthropic  # noqa: E402
import httpx2 as httpx  # noqa: E402

import chercheur  # noqa: E402
import criteres_dynamiques as cd  # noqa: E402
from agents import MODELES, Backend  # noqa: E402

ENVOIS, WEB = [], []
PAGE = ("Elon Musk est un entrepreneur. Il est le directeur général de Tesla, constructeur de véhicules électriques, "
        "et le fondateur de SpaceX.")


def faux_wikipedia(url, params):
    WEB.append((url, dict(params)))
    if params.get("list") == "search":
        return {"query": {"search": [{"title": "Elon Musk", "snippet": "entrepreneur, <span>directeur</span> de Tesla"}]}}
    return {"query": {"pages": {"1": {"title": "Elon Musk", "extract": PAGE}}}}


chercheur._http_get = faux_wikipedia

ETAPES = [
    {"stop_reason": "tool_use", "content": [
        {"type": "tool_use", "id": "t1", "name": "chercher_dans_donnees", "input": {"mots": "Tesla"}},
        {"type": "tool_use", "id": "t2", "name": "recherche_web", "input": {"requete": "Elon Musk", "langue": "fr"}}]},
    {"stop_reason": "tool_use", "content": [
        {"type": "tool_use", "id": "t3", "name": "lire_page_web", "input": {"titre": "Elon Musk", "langue": "fr"}}]},
    {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps({
        "definition": "Entreprise dirigée, fondée ou contrôlée par Elon Musk.",
        "verdicts": [
            {"ticker": "TSLA", "valeur": "oui", "preuve": "Il est le directeur général de Tesla", "source": "web:fr:Elon Musk", "confiance": 0.95},
            {"ticker": "TSLA", "valeur": "oui", "preuve": "TSLA : Tesla ; classe equity", "source": "[source: web:en:Tesla]", "confiance": 0.9},
            {"ticker": "SPCX", "valeur": "oui", "preuve": "et le fondateur de SpaceX", "source": "web:fr:Elon Musk", "confiance": 0.9},
            {"ticker": "NVDA", "valeur": "partiel", "preuve": "Nvidia fournit les puces de Tesla", "source": "web:fr:Elon Musk", "confiance": 0.6},
            {"ticker": "AAPL", "valeur": "partiel", "preuve": "Apple collabore avec Elon Musk depuis", "source": "web:en:Apple", "confiance": 0.5},
            {"ticker": "1211.HK", "valeur": "partiel", "preuve": "constructeur de véhicules électriques", "source": "web:fr:Elon Musk", "confiance": 0.9},
        ]})}]},
]
CRITIQUE = {"avis": [{"critere_id": "TSLA", "accord": True, "confiance": 0.9, "objection": "", "valeurs_suggerees": []}],
            "question_relance": ""}  # 1211.HK (BYD) : pas d accord (aucun avis) -> écarté


def handler(request):
    body = json.loads(request.content)
    ENVOIS.append(body)
    if "CRITIQUE" in body["system"]:
        payload = {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(CRITIQUE)}]}
    else:
        payload = ETAPES[sum(1 for b in ENVOIS if "CHERCHEUR" in b["system"]) - 1]
    return httpx.Response(200, json={"id": "msg", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
                                     "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}, **payload})


client = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
b = Backend(client, MODELES["anthropic"], "test")
res = chercheur.etiqueter(b, "entreprises liées à Elon Musk", "exclure")

assert res["mot_cle"].startswith("kw_dyn_entreprises_liees_a_elon_musk_") and not res["depuis_cache"], res["mot_cle"]
assert res["oui"] == ["TSLA"] and res["partiel"] == [], (res["oui"], res["partiel"])
motifs = {(r["ticker"], r["motif"]) for r in res["rejetes"]}
assert ("SPCX", "ticker hors univers") in motifs
assert ("NVDA", "passage introuvable dans les sources lues") in motifs       # preuve inventée
assert ("AAPL", "passage introuvable dans les sources lues") in motifs
assert any(t == "1211.HK" and m.startswith("critique") for t, m in motifs)  # refusé par le critique
assert set(res["fnb_exposes"]) >= {"SPY", "QQQ", "ESGV"} and "XIU.TO" not in res["fnb_exposes"], res["fnb_exposes"]
assert any(v["url"] == "https://fr.wikipedia.org/wiki/Elon_Musk" for v in res["verdicts"])
assert any(v["source"] == "fiche:TSLA" for v in res["verdicts"])  # identifiant mal recopié : corrigé vers la source réellement lue
assert [a["outil"] for a in res["appels_outils"]] == ["chercher_dans_donnees", "recherche_web", "lire_page_web"]
assert res["etats_actifs"]["TSLA"] == "oui" and res["etats_actifs"]["SPY"] == "partiel"
assert res["etats_actifs"]["NVDA"] == "inconnu" and "NVDA" in res["inconnus"]
assert set(res["etats_actifs"]) == set(chercheur.ACTIFS) and not res["non_concernes"]
assert res["couverture"]["avec_verdict"] == 1  # deux preuves, un seul actif explicitement vérifié
assert res["couverture"]["inconnus"] == len(chercheur.ACTIFS) - 1 - len(res["fnb_exposes"])

# Ce qui part au modèle : outils stricts, sortie JSON imposée, tableau des 66 actifs, résultats d'outils renvoyés
premier = [e for e in ENVOIS if "CHERCHEUR" in e["system"]][0]
assert {t["name"] for t in premier["tools"]} == {"chercher_dans_donnees", "fiche_actif", "recherche_web", "lire_page_web"}
assert all(t["strict"] for t in premier["tools"]) and premier["output_config"]["format"]["type"] == "json_schema"
assert "TSLA | Tesla" in premier["messages"][0]["content"]
deuxieme = [e for e in ENVOIS if "CHERCHEUR" in e["system"]][1]
resultats = deuxieme["messages"][-1]["content"]
assert [r["tool_use_id"] for r in resultats] == ["t1", "t2"] and "[source: fiche:TSLA]" in resultats[0]["content"]
# Seul le concept part sur Wikipédia
assert WEB[0][0] == "https://fr.wikipedia.org/w/api.php" and WEB[0][1]["srsearch"] == "Elon Musk"

# Cache : même concept -> aucun nouvel appel au modèle ni au web
n, w = len(ENVOIS), len(WEB)
res2 = chercheur.etiqueter(b, "Entreprises liées à Elon Musk", "exclure")
assert res2["depuis_cache"] and res2["oui"] == ["TSLA"] and len(ENVOIS) == n and len(WEB) == w

# Le critère dynamique devient une règle sur le nouveau mot-clé
c = {"id": "X1", "nom": "Rien de lié à Elon Musk", "effet": "exclure", "dimension": cd.A_ETIQUETER, "colonne": "",
     "valeurs": [], "actifs": [], "plafond_pct": 0, "concept": "entreprises liées à Elon Musk", "etiquetage": "en_attente"}
assert "recherche des actifs concernés en cours" in cd.regle(c)
cd.appliquer_etiquetage(c, res)
assert c["etiquetage"] == "fait" and c["actifs"] == ["TSLA"] and c["colonne"] == res["mot_cle"]
assert c["regle"].startswith(f"Exclure : {res['mot_cle']} = oui (TSLA) ; FNB qui en détiennent : QQQ (3,4 %)"), c["regle"]
print(f"Chercheur OK : 3 outils, TSLA retenu sur preuve vérifiée, 4 verdicts écartés, "
      f"{len(res['fnb_exposes'])} FNB exposés ({', '.join(res['fnb_exposes'])}), cache réutilisé")
print("Règle :", c["regle"])


def recherche_simulee(concept, verdicts, avis, texte, cache):
    """Les outils du faux chercheur ont lu cette source ; aucun appel réseau ni modèle réel."""
    def boucle(backend, concept, effet, rech):
        rech.journal["test:source"] = texte
        return chercheur.Etiquetage(definition=concept, verdicts=verdicts)

    critique = chercheur.Critique(avis=avis, question_relance="")
    with patch.object(chercheur, "CACHE", cache), patch.object(chercheur, "_boucle", side_effect=boucle), \
            patch.object(chercheur, "_ask", return_value=critique):
        return chercheur.etiqueter(b, concept)


def verdict(ticker, valeur, preuve, confiance=0.95):
    return {"ticker": ticker, "valeur": valeur, "preuve": preuve, "source": "test:source", "confiance": confiance}


def accord(ticker, confiance=0.95):
    return {"critere_id": ticker, "accord": True, "confiance": confiance, "objection": "", "valeurs_suggerees": []}


with tempfile.TemporaryDirectory() as dossier:
    cache = Path(dossier) / "recherches.json"

    # Une recherche locale n'envoie que quatre extraits : une preuve dans le reste de la fiche n'a pas encore été lue.
    fiche = "\n".join(["Tesla extrait numéro " + str(i) for i in range(5)] + ["Tesla passage détaillé encore non lu"])
    with patch.object(chercheur, "_fiche", side_effect=lambda tk: fiche if tk == "TSLA" else "Autre entreprise"):
        rech = chercheur.Recherche()
        extraits = rech.chercher_dans_donnees("Tesla")
        preuve_cachee = chercheur.Verdict(**verdict("TSLA", "oui", "Tesla passage détaillé encore non lu"))
        assert "encore non lu" not in extraits
        assert chercheur._preuve_valide(preuve_cachee, rech.journal) == "passage introuvable dans les sources lues"
        rech.fiche_actif("TSLA")
        assert not chercheur._preuve_valide(preuve_cachee, rech.journal)

    # Une recherche vide ne prouve rien sur aucun actif, même si elle a parcouru le tableau.
    vide = recherche_simulee("activité non documentée", [], [], "Aucune information disponible dans ces sources.", cache)
    assert set(vide["inconnus"]) == set(chercheur.ACTIFS) and not vide["non_concernes"]
    assert vide["couverture"]["pct_verifie"] == 0 and not vide["oui"] and not vide["partiel"]
    critere_vide = {"id": "X1", "nom": "Concept non établi", "effet": "exclure", "dimension": cd.A_ETIQUETER,
                   "colonne": "", "valeurs": [], "actifs": [], "plafond_pct": 0, "concept": "activité non documentée"}
    cd.appliquer_etiquetage(critere_vide, vide)
    assert "aucun lien établi" in critere_vide["regle"] and "recherche incomplète" in critere_vide["regle"]
    assert critere_vide["recherche"]["inconnus"] == vide["inconnus"]

    # Un négatif explicite suit exactement les mêmes contrôles de preuve et d'accord qu'un positif.
    texte = "Apple ne fabrique ni ne commercialise aucun produit du concept étudié."
    negatif = recherche_simulee("produit précis", [verdict("AAPL", "non_concerne", texte)], [accord("AAPL")], texte, cache)
    assert negatif["non_concernes"] == ["AAPL"] and negatif["etats_actifs"]["AAPL"] == "non_concerne"
    assert not negatif["oui"] and not negatif["partiel"] and len(negatif["inconnus"]) == len(chercheur.ACTIFS) - 1
    invente = recherche_simulee("produit sans preuve", [verdict("AAPL", "non_concerne", "Cette phrase ne figure pas dans la source")],
                               [accord("AAPL")], texte, cache)
    assert not invente["non_concernes"] and invente["etats_actifs"]["AAPL"] == "inconnu"

    # Accord sans confiance suffisante ne suffit pas à produire une exclusion ni un négatif rassurant.
    faible = recherche_simulee("confiance critique faible", [verdict("AAPL", "non_concerne", texte)],
                              [accord("AAPL", 0.4)], texte, cache)
    assert faible["etats_actifs"]["AAPL"] == "inconnu" and not faible["verdicts"]
    faible_chercheur = recherche_simulee("confiance chercheur faible", [verdict("AAPL", "oui", texte, 0.4)],
                                        [accord("AAPL")], texte, cache)
    assert faible_chercheur["etats_actifs"]["AAPL"] == "inconnu" and not faible_chercheur["verdicts"]

    # Des conclusions contradictoires sur le même actif ne sont pas arbitrées silencieusement.
    contradiction = recherche_simulee("preuves contradictoires", [verdict("AAPL", "oui", texte),
        verdict("AAPL", "non_concerne", texte)], [accord("AAPL")], texte, cache)
    assert contradiction["etats_actifs"]["AAPL"] == "inconnu" and len(contradiction["rejetes"]) == 2

    # Même préfixe lisible, concepts complets différents : les nouvelles clés sont distinctes.
    c1 = "entreprises présentes dans le secteur des armes nucléaires"
    c2 = "entreprises présentes dans le secteur des armes conventionnelles"
    assert chercheur.slug(c1) == chercheur.slug(c2)
    r1 = recherche_simulee(c1, [], [], "Source sans conclusion.", cache)
    r2 = recherche_simulee(c2, [], [], "Source sans conclusion.", cache)
    assert r1["mot_cle"] != r2["mot_cle"] and not r2["depuis_cache"]

    # Un cache ancien, périmé ou construit sur d'autres données/consignes ne contourne pas les contrôles.
    assert not chercheur._cache_valide({"oui": ["AAPL"]}, r1["empreinte"])
    perime = {**r1, "expire_le": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()}
    assert not chercheur._cache_valide(perime, r1["empreinte"])
    avec_cache = json.loads(cache.read_text(encoding="utf-8"))
    avec_cache[r1["mot_cle"]] = perime
    cache.write_text(json.dumps(avec_cache), encoding="utf-8")
    assert not recherche_simulee(c1, [], [], "Source sans conclusion.", cache)["depuis_cache"]
    avant = chercheur._empreinte(c1, "exclure", b.model)
    with patch.dict(chercheur.ACTIFS, {"AAPL": {**chercheur.ACTIFS["AAPL"], "nom": "nom actualisé"}}):
        assert chercheur._empreinte(c1, "exclure", b.model) != avant
    with patch.object(chercheur, "SYSTEM_CHERCHEUR", chercheur.SYSTEM_CHERCHEUR + " Nouvelle consigne."):
        assert chercheur._empreinte(c1, "exclure", b.model) != avant

print("Incertitude OK : actifs inconnus explicites, négatifs prouvés, seuils et contradictions contrôlés, cache versionné sans collision")
