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
            {"ticker": "1211.HK", "valeur": "partiel", "preuve": "constructeur de véhicules électriques", "source": "web:fr:Elon Musk", "confiance": 0.5},
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

assert res["mot_cle"] == "kw_dyn_entreprises_liees_a_elon_musk" and not res["depuis_cache"], res["mot_cle"]
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
assert c["regle"].startswith("Exclure : kw_dyn_entreprises_liees_a_elon_musk = oui (TSLA) ; FNB qui en détiennent : QQQ (3,4 %)"), c["regle"]
print(f"Chercheur OK : 3 outils, TSLA retenu sur preuve vérifiée, 4 verdicts écartés, "
      f"{len(res['fnb_exposes'])} FNB exposés ({', '.join(res['fnb_exposes'])}), cache réutilisé")
print("Règle :", c["regle"])
