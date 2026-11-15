"""Tests hors ligne du débat : un faux serveur remplace l'API Anthropic (aucune clé, aucun coût).

Le vrai SDK `anthropic` construit les requêtes ; on vérifie ce qu'il envoie et la logique de validation.
Lancer : python mvp_profil/test_debat.py
"""
from __future__ import annotations

import json

import anthropic
import httpx2 as httpx  # le SDK anthropic utilise httpx2 (fork de httpx)

from agents import MODELES, Backend, debattre

ENVOIS: list[dict] = []
URLS: list[str] = []


def serveur(scenario):
    """Renvoie un transport httpx qui répond comme l'API Messages, selon le scénario."""
    compteur = {"classif": 0, "critique": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        ENVOIS.append(body)
        URLS.append(str(request.url))
        role = "critique" if "CRITIQUE" in body["system"] else "classif"
        compteur[role] += 1
        payload = scenario[role][min(compteur[role], len(scenario[role])) - 1]
        return httpx.Response(200, json={
            "id": f"msg_{len(ENVOIS)}", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 10},
        })
    return httpx.MockTransport(handler)


def client(scenario):
    c = anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=serveur(scenario)))
    return Backend(c, MODELES["anthropic"], "test")


def client_bedrock(scenario):
    # Faux identifiants AWS : le SDK signe la requête (SigV4) mais elle n'atteint jamais AWS.
    c = anthropic.AnthropicBedrock(aws_region="us-east-1", aws_access_key="AKIATEST", aws_secret_key="test",
                                   http_client=httpx.Client(transport=serveur(scenario)))
    return Backend(c, MODELES["bedrock"], "test bedrock")


def prop(cid, vals, cit, conf):
    return {"critere_id": cid, "valeurs": vals, "citation": cit, "confiance": conf, "justification": "test"}


def avis(cid, ok, conf, obj="", sugg=None):
    return {"critere_id": cid, "accord": ok, "confiance": conf, "objection": obj, "valeurs_suggerees": sugg or []}


ECH = [("À quoi servira cet argent ?", "C'est pour ma retraite, dans environ 12 ans.")]

# 1) Accord immédiat au-dessus du seuil
s1 = {"classif": [{"propositions": [prop("A3", ["retraite"], "pour ma retraite", 0.95),
                                     prop("A2", ["10_15_ans"], "dans environ 12 ans", 0.9)]}],
      "critique": [{"avis": [avis("A3", True, 0.92), avis("A2", True, 0.88)], "question_relance": ""}]}
d = debattre(client(s1), ECH, ["A3", "A2"])
assert not d.non_valides and len(d.tours) == 1, d
assert d.resultats["A2"].confiance == 0.88  # min des deux confiances

# Ce que le SDK a réellement envoyé
b = ENVOIS[0]
assert b["model"] == "claude-haiku-5-5"
assert b["output_config"]["effort"] == "low"
assert b["thinking"] == {"type": "disabled"} and b["max_tokens"] == 3000  # réglages de rapidité
assert b["output_config"]["format"]["type"] == "json_schema"
assert "propositions" in json.dumps(b["output_config"]["format"]["schema"])

# 2) Désaccord au tour 1, le classificateur corrige, accord au tour 2
s2 = {"classif": [{"propositions": [prop("A3", ["croissance"], "pour ma retraite", 0.9),
                                     prop("A2", ["10_15_ans"], "dans environ 12 ans", 0.9)]},
                  {"propositions": [prop("A3", ["retraite"], "pour ma retraite", 0.93),
                                    prop("A2", ["10_15_ans"], "dans environ 12 ans", 0.9)]}],
      "critique": [{"avis": [avis("A3", False, 0.3, "Il parle de retraite", ["retraite"]), avis("A2", True, 0.9)],
                    "question_relance": ""},
                   {"avis": [avis("A3", True, 0.9), avis("A2", True, 0.9)], "question_relance": ""}]}
d = debattre(client(s2), ECH, ["A3", "A2"])
assert not d.non_valides and len(d.tours) == 2, d

# 3) Réponse vague : confiance sous 80 % -> relance demandée
ECH3 = [("Votre portefeuille perd 20 % : que faites-vous ?", "Bof, je ne sais pas trop, ça dépend.")]
s3 = {"classif": [{"propositions": [prop("B1", ["20"], "ça dépend", 0.4)]}],
      "critique": [{"avis": [avis("B1", False, 0.3, "Réponse trop vague")],
                    "question_relance": "Et si vos 10 000 $ devenaient 7 000 $, vendriez-vous ?"}]}
n = len(ENVOIS)
d = debattre(client(s3), ECH3, ["B1"], max_tours=2)
assert d.non_valides == ["B1"] and d.question_relance == "", d
assert len(ENVOIS) - n == 1  # classificateur peu sûr : le critique n'est pas appelé (gain de temps)

# 4) Citation inventée : refusée même si les deux agents sont d'accord
s4 = {"classif": [{"propositions": [prop("B1", ["30"], "je garderais jusqu'à -30 %", 0.95)]}],
      "critique": [{"avis": [avis("B1", True, 0.95)], "question_relance": ""}]}
d = debattre(client(s4), ECH3, ["B1"], max_tours=1)
assert d.non_valides == ["B1"] and "Citation introuvable" in d.resultats["B1"].motif, d

# 5) Valeur hors liste fermée : rejetée
s5 = {"classif": [{"propositions": [prop("A3", ["vacances"], "pour ma retraite", 0.95)]}],
      "critique": [{"avis": [avis("A3", True, 0.95)], "question_relance": "Précisez ?"}]}
d = debattre(client(s5), ECH, ["A3"], max_tours=1)
assert d.non_valides == ["A3"], d

# 6) Même débat via Amazon Bedrock : bonne URL (profil d'inférence), requête signée, même format
n = len(ENVOIS)
d = debattre(client_bedrock(s1), ECH, ["A3", "A2"])
assert not d.non_valides, d
assert "bedrock-runtime.us-east-1.amazonaws.com/model/us.anthropic.claude-haiku-5-5/invoke" in URLS[n], URLS[n]
assert ENVOIS[n]["anthropic_version"] and "model" not in ENVOIS[n]  # sur Bedrock, le modèle est dans l'URL
assert ENVOIS[n]["output_config"]["effort"] == "low" and ENVOIS[n]["output_config"]["format"]["type"] == "json_schema"
assert ENVOIS[n]["thinking"] == {"type": "disabled"}

# 7) Le critique ne reçoit que les critères sûrs ; le critère incertain part en précision sans débat
ECH7 = [("Situation ?", "Je travaille dans la santé, pour le reste je ne sais pas.")]
s7 = {"classif": [{"propositions": [prop("A12", ["sante"], "je travaille dans la santé", 0.95),
                                     prop("A8", ["0"], "", 0.2)]}],
      "critique": [{"avis": [avis("A12", True, 0.9)], "question_relance": ""}]}
n = len(ENVOIS)
d = debattre(client(s7), ECH7, ["A12", "A8"])
assert d.resultats["A12"].valide and d.non_valides == ["A8"], d
assert "A8" not in json.dumps(ENVOIS[n + 1]["messages"][0]["content"].split("Classification proposée")[1])

print("7 scénarios OK (dont Bedrock) :", len(ENVOIS), "requêtes simulées, format envoyé conforme")
