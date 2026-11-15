"""Tests hors ligne des critères dynamiques et des nouvelles règles de relance (faux serveur, vrai SDK, aucun coût).

Vérifie : un titre de l'univers devient une exclusion avec ses actifs concernés ; une valeur inventée devient une
« note » (rien n'est filtré sur une valeur qui n'existe pas) ; une citation inventée est écartée ; un critère contesté
mais au-dessus du plancher est « retenu » ; un critère trop incertain n'est pas créé ; et les fonctions de relance
(seuil abaissé à la 2e tentative, meilleure réponse, comparaison de citation tolérante à la ponctuation).
Lancer : python mvp_profil/test_dynamiques.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import anthropic  # noqa: E402
import httpx2 as httpx  # noqa: E402

import criteres_dynamiques as cd  # noqa: E402
from agents import MODELES, Backend, Resultat, _citation_presente, meilleur, retenable, seuil_essai  # noqa: E402

ENVOIS = []


def backend(decouverte, critique):
    def handler(request):
        body = json.loads(request.content)
        ENVOIS.append(body)
        payload = critique if "CRITIQUE" in body["system"] else decouverte
        return httpx.Response(200, json={
            "id": "msg", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "stop_reason": "end_turn", "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1}})
    c = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    return Backend(c, MODELES["anthropic"], "test")


def crit(nom, cit, effet, dim, vals, conf, plafond=0, concept=""):
    return {"nom": nom, "citation": cit, "effet": effet, "dimension": dim, "valeurs": vals, "plafond_pct": plafond,
            "concept": concept, "confiance": conf, "justification": "test"}


def avis(cid, ok, conf, obj=""):
    return {"critere_id": cid, "accord": ok, "confiance": conf, "objection": obj, "valeurs_suggerees": []}


REPONSE = ("Je travaille chez Shopify et j'ai déjà plein d'actions de mon employeur. Je déménage en Europe dans 5 ans. "
           "Pas trop de banques, 10 % max. Et rien qui touche à Elon Musk.")
dec = {"criteres": [
    crit("Pas d'actions de son employeur (Shopify)", "j'ai déjà plein d'actions de mon employeur", "exclure", "titre", ["shop.to"], 0.95),
    crit("Préférence pour l'euro", "Je déménage en Europe dans 5 ans", "privilegier", "devise", ["EUR"], 0.85),
    crit("Banques plafonnées à 10 %", "Pas trop de banques, 10 % max", "plafonner", "theme", ["banque"], 0.9, 10),
    crit("Rien lié à Elon Musk", "rien qui touche à Elon Musk", "exclure", "theme", ["elon_musk"], 0.9),  # valeur inexistante
    crit("Aime le golf", "j'adore le golf", "note", "aucune", [], 0.9),                                    # citation inventée
    crit("Pas de réseaux sociaux", "Et rien qui touche à Elon Musk", "exclure", "aucune", [], 0.85,
         concept="entreprises liées à Elon Musk"),                                                      # -> chercheur
]}
# Plafond emprunté à une autre phrase : reste une limite non chiffrée, jamais une exclusion.
dec["criteres"][0] = crit("Pas d'actions de son employeur (Shopify)", "j'ai déjà plein d'actions de mon employeur",
                          "plafonner", "titre", ["shop.to"], 0.95, 10)
cri = {"avis": [avis("X1", True, 0.95), avis("X2", False, 0.6, "Préférence possible, pas certaine"),
                avis("X3", True, 0.9), avis("X4", True, 0.85), avis("X5", True, 0.85)], "question_relance": ""}
out = cd.creer(backend(dec, cri), cd.QUESTION_OUVERTE, REPONSE, 0.8)
par_nom = {c["nom"]: c for c in out}
assert [c["id"] for c in out] == ["X1", "X2", "X3", "X4", "X5"], [c["id"] for c in out]  # le golf (citation inventée) est écarté

x1 = par_nom["Pas d'actions de son employeur (Shopify)"]
assert x1["valeurs"] == ["SHOP.TO"] and x1["actifs"] == ["SHOP.TO"] and x1["statut"] == "à préciser", x1
assert x1["effet"] == "plafonner" and x1["plafond_pct"] is None and not x1["applicable"], x1
assert "plafond à préciser" in x1["regle"]
x2 = par_nom["Préférence pour l'euro"]
assert x2["statut"] == "à préciser" and x2["confiance"] == 0.6 and not x2["applicable"], x2
assert set(x2["actifs"]) == {"ASML.AS", "ENEL.MI", "IBE.MC", "MC.PA", "RHM.DE", "SAP.DE", "SIE.DE", "TTE.PA"}, x2["actifs"]  # 8 titres en euros depuis l'ajout du 15 novembre 2026
x3 = par_nom["Banques plafonnées à 10 %"]
assert x3["effet"] == "plafonner" and x3["plafond_pct"] == 10 and "RY.TO" in x3["actifs"] and x3["regle"].startswith("Plafonner à 10 %")
x4 = par_nom["Rien lié à Elon Musk"]
assert x4["effet"] == "note" and x4["actifs"] == [] and x4["statut"] == "validé", x4  # rien de filtré sur une valeur inventée
x5 = out[4]  # idée qui vise des actifs, sans valeur existante : à étiqueter par le chercheur
assert x5["dimension"] == cd.A_ETIQUETER and x5["etiquetage"] == "en_attente" and x5["concept"] == "entreprises liées à Elon Musk"
assert x5["regle"] == "Exclure : « entreprises liées à Elon Musk » (recherche des actifs concernés en cours)", x5["regle"]
assert list(x1["fnb_exposes"]) == ["XIU.TO"] and abs(x1["fnb_exposes"]["XIU.TO"] - 0.0645) < 1e-3, x1["fnb_exposes"]  # Shopify exclu : XIU.TO en détient 6,4 %
assert "FNB qui en détiennent : XIU.TO (6,4 %)" in x1["regle"], x1["regle"]
assert x2["fnb_exposes"] == {}  # une préférence ne touche pas les FNB

# Ce qui part au découvreur : le vocabulaire réel des actifs et la liste des critères fixes
prompt = ENVOIS[0]["messages"][0]["content"]
assert "SHOP.TO (Shopify)" in prompt and "Horizon de placement" in prompt and "kw_exclusions" in prompt
# Le critique reçoit les règles lisibles, avec leur portée
assert "Plafonner à 10 %" in ENVOIS[1]["messages"][0]["content"]

# Critère trop incertain (< 50 %) : non créé ; réponse « rien à ajouter » : aucun appel au critique
dec2 = {"criteres": [crit("Peut-être l'or", "peut-être l'or", "privilegier", "classe", ["etf_commodity"], 0.4)]}
assert cd.creer(backend(dec2, {"avis": [avis("X1", True, 0.9)], "question_relance": ""}), "?", "peut-être l'or", 0.8) == []
n = len(ENVOIS)
assert cd.creer(backend({"criteres": []}, {}), "?", "non rien", 0.8) == [] and len(ENVOIS) == n + 1
print(f"Critères dynamiques OK : {len(out)} créés (exclusion d'un titre et FNB exposé, préférence retenue, plafond, "
      "note, concept à étiqueter), citation inventée écartée")

# ---------- Relances : une reformulation, puis la meilleure réponse ----------
assert seuil_essai(0.8, 0) == 0.8 and seuil_essai(0.8, 1) == 0.65 and seuil_essai(0.6, 1) == 0.5
a = Resultat("A2", ["10_15_ans"], "x", 0.7, False, "Confiance 70 % sous le seuil de 80 %")
b = Resultat("A2", [], "", 0.0, False, "Information absente")
c = Resultat("A2", ["5_10_ans"], "y", 0.6, False, "Désaccord du critique")
assert meilleur(meilleur(a, b), c) is c and meilleur(None, b) is None
assert not retenable(c)
assert retenable(a) and not retenable(Resultat("A2", ["x"], "z", 0.45, False, "peu sûr"))
assert not retenable(Resultat("A2", ["x"], "z", 0.5, False, "Citation introuvable dans la réponse de l'utilisateur"))
# Citation tolérante : ponctuation ajoutée par la transcription ou par le modèle
ech = [("?", "Euh, c'est pour ma retraite... dans, genre, douze ans.")]
assert _citation_presente("pour ma retraite", ech) and _citation_presente("dans genre douze ans", ech)
assert _citation_presente("C'est pour ma retraite…dans, genre", ech) and not _citation_presente("dans dix ans", ech)
assert not _citation_presente("an", ech)  # un morceau de mot ne compte pas
print("Relances OK : seuil 80 % puis 65 %, meilleure réponse retenue (plancher 50 %), citations tolérantes")

# Limite qualitative ou nombre sans unité : à préciser. Un vrai 0 % reste un plafond.
for citation, nombre in [("Limiter les banques", None), ("banques dans 10 ans", 10),
                         ("banques à 150 %", 150), ("banques à 10,5 %", 5),
                         ("Je garde 10 % en crypto et je veux limiter les banques", 10)]:
    c_limite = cd.CritereIA(**crit("Banques", citation, "plafonner", "theme", ["banque"], 0.9, nombre))
    effet, _, _, pct = cd._nettoyer(c_limite)
    assert effet == "plafonner" and pct is None, (citation, pct)
for citation, nombre in [("banques à 0 %", 0), ("banques dix pour cent", 10), ("banques à 10 % maximum", 10),
                         ("Les banques, 10 % et pas plus", 10)]:
    assert cd.plafond_etaye(citation, nombre), citation
cd.confirmer(x1, 7)
assert x1["effet"] == "plafonner" and x1["plafond_pct"] == 7 and x1["applicable"]
assert x1["statut"] == "validé" and x1["confirmations"][-1]["plafond_pct"] == 7
for invalide in (None, -1, 101, True, 10.5):
    try:
        cd.confirmer(dict(x1), invalide)
        raise AssertionError(f"Plafond invalide accepté : {invalide}")
    except ValueError:
        pass
vide = dict(x5)
cd.appliquer_etiquetage(vide, {"oui": [], "partiel": [], "mot_cle": "kw_dyn_test", "fnb_exposes": {},
                             "verdicts": [], "definition": "test", "inconnus": ["TSLA"],
                             "non_concernes": [], "couverture": {"total": 66, "avec_verdict": 0}})
assert "aucun lien établi" in vide["regle"] and "aucun actif de l'univers concerné" not in vide["regle"]
assert vide["recherche"]["inconnus"] == ["TSLA"]
print("Limites à préciser, confirmation explicite et absence de preuve distincte d'un résultat négatif : OK")
