"""Tests hors ligne du débat : un faux serveur remplace l'API Anthropic (aucune clé, aucun coût).

Le vrai SDK `anthropic` construit les requêtes ; on vérifie ce qu'il envoie et la logique de validation.
Lancer : python mvp_profil/test_debat.py
"""
from __future__ import annotations

import json

import anthropic
import httpx2 as httpx  # le SDK anthropic utilise httpx2 (fork de httpx)

from agents import (MODELES, Avis, Backend, Proposition, Resultat, _definitions_questionnaire,
                    debattre, evaluer, meilleur, precontrole, retenable)

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

# 8) Une réponse courte doit être présentée avec sa question et la définition exacte de la valeur.
ech8 = [("Avez-vous des dettes à taux élevé ?", "Non.")]
s8 = {"classif": [{"propositions": [prop("A7", ["non"], "Non", 0.95)]}],
      "critique": [{"avis": [avis("A7", True, 0.94)], "question_relance": ""}]}
n = len(ENVOIS)
d = debattre(client(s8), ech8, ["A7"])
assert d.resultats["A7"].valide and d.resultats["A7"].accord_critique is True
for body in ENVOIS[n:]:
    prompt = body["messages"][0]["content"]
    assert "Avez-vous des dettes à taux élevé ?" in prompt and "Utilisateur : Non." in prompt
assert "aucune = Je les refuse toutes" in _definitions_questionnaire(["E2"])
assert "A2" not in _definitions_questionnaire(["E2"])  # pas de dictionnaire complet envoyé à chaque fois

# 9) Le contexte de correction et le sens des options parviennent aux deux agents sans accepter une citation inventée.
ech9 = [("Quand aurez-vous besoin de cet argent ?", "Dans douze ans."),
        ("Toujours douze ans ?", "Non, je corrige : dans quatre ans.")]
s9 = {"classif": [{"propositions": [prop("A2", ["3_5_ans"], "dans quatre ans", 0.94)]}],
      "critique": [{"avis": [avis("A2", True, 0.92)], "question_relance": ""}]}
n = len(ENVOIS)
d = debattre(client(s9), ech9, ["A2"])
assert d.resultats["A2"].valeurs == ["3_5_ans"] and d.resultats["A2"].valide
for body in ENVOIS[n:]:
    assert "dans quatre ans" in body["messages"][0]["content"]
    assert "3_5_ans = 3 à moins de 5 ans" in body["messages"][0]["content"]
    assert "correction" in body["system"].lower()

# 10) Un critique en désaccord à confiance élevée ne peut pas être contourné par le maintien « retenu ».
p10 = Proposition(critere_id="A2", valeurs=["10_15_ans"], citation="Dans douze ans", confiance=0.95,
                  justification="douze ans")
a10 = Avis(critere_id="A2", accord=False, confiance=0.95, objection="La réponse est corrigée ensuite",
           valeurs_suggerees=["3_5_ans"])
r10 = evaluer("A2", p10, a10, ech9, seuil=0.8)
assert not r10.valide and r10.accord_critique is False and not retenable(r10)
assert not retenable(Resultat("A2", ["10_15_ans"], "Dans douze ans", 0.9, False, "Désaccord du critique"))

# Un accord sous le seuil peut rester signalé « retenu » ; une classification non vérifiée ne le peut pas.
a10.accord, a10.confiance = True, 0.7
accord_faible = evaluer("A2", p10, a10, ech9[:1], seuil=0.8)
assert not accord_faible.valide and accord_faible.accord_critique is True and retenable(accord_faible)
p10.confiance = 0.7
sans_controle = precontrole("A2", p10, ech9[:1], seuil=0.8)
assert sans_controle and sans_controle.accord_critique is None and not retenable(sans_controle)

# 11) Une réponse corrigée moins confiante ne ressuscite pas la valeur précédente, même mieux notée.
ancien = Resultat("A2", ["10_15_ans"], "Dans douze ans", 0.96, True, "ok", True)
recent = Resultat("A2", ["3_5_ans"], "dans quatre ans", 0.7, False, "Confiance 70 % sous le seuil de 80 %", True)
assert meilleur(ancien, recent) is recent and retenable(recent)
conteste = Resultat("A2", ["3_5_ans"], "dans quatre ans", 0.6, False, "Désaccord du critique", False)
assert meilleur(recent, conteste) is conteste and not retenable(meilleur(recent, conteste))
assert meilleur(recent, Resultat("A2", [], "", 0.0, False, "Information absente")) is recent

# 12) Retraits de capital et besoin de revenus sont deux informations distinctes, même dans une même réponse.
ech12 = [("Prévoyez-vous des retraits et avez-vous besoin d'un revenu ?",
          "Aucun retrait de capital, mais les dividendes paient mes dépenses essentielles.")]
s12 = {"classif": [{"propositions": [prop("A9", ["aucun"], "Aucun retrait de capital", 0.94),
                                       prop("A10", ["essentiel"], "les dividendes paient mes dépenses essentielles", 0.93)]}],
       "critique": [{"avis": [avis("A9", True, 0.93), avis("A10", True, 0.92)], "question_relance": ""}]}
n = len(ENVOIS)
d = debattre(client(s12), ech12, ["A9", "A10"])
assert not d.non_valides and d.resultats["A9"].valeurs == ["aucun"] and d.resultats["A10"].valeurs == ["essentiel"]
for body in ENVOIS[n:]:
    assert "question composée ne renseigne pas tous les champs par défaut" in body["system"]
    assert "A9=aucun retrait ne prouve pas A10=non" in body["system"]
    assert "citation qui l'étaye" in body["system"] or "mots récents qui étayent" in body["system"]

print("12 scénarios OK (dont Bedrock) :", len(ENVOIS), "requêtes simulées, contexte et contrôles conformes")
print("Les réponses du modèle sont simulées : ces tests ne mesurent pas sa compréhension réelle.")

# Une demande de précision doit décrire une ambiguïté utile, pas une difficulté du modèle.
ech_precision = [("Dans combien d'années ?", "Entre huit et douze ans.")]
p_precision = Proposition(critere_id="A2", valeurs=["5_10_ans"], citation="Entre huit et douze ans",
                         confiance=0.65, justification="Fourchette chevauchante", precision_necessaire=True,
                         motif_precision="L'horizon annoncé traverse les classes 5-10 et 10-15 ans.")
r_precision = precontrole("A2", p_precision, ech_precision, 0.8)
assert r_precision.precision_necessaire and "traverse" in r_precision.motif_precision
p_precision.motif_precision = "Confiance sous le seuil de 80 %."
r_precision = precontrole("A2", p_precision, ech_precision, 0.8)
assert not r_precision.precision_necessaire and r_precision.motif_precision == ""

p_clair = Proposition(critere_id="A2", valeurs=["10_15_ans"], citation="Dans douze ans",
                      confiance=0.9, justification="Réponse claire")
ech_clair = [("Dans combien d'années ?", "Dans douze ans.")]
a_interne = Avis(critere_id="A2", accord=False, confiance=0.7, objection="Je préfère un autre code",
                 valeurs_suggerees=["plus_15_ans"])
r_interne = evaluer("A2", p_clair, a_interne, ech_clair, 0.8)
assert not r_interne.valide and not r_interne.precision_necessaire
a_interne.precision_necessaire, a_interne.motif_precision = True, "Pas clair"
assert not evaluer("A2", p_clair, a_interne, ech_clair, 0.8).precision_necessaire

p_precision.motif_precision = "La durée de huit à douze ans traverse deux classes."
a_precision = Avis(critere_id="A2", accord=False, confiance=0.7, objection="La durée traverse deux classes",
                   valeurs_suggerees=[], precision_necessaire=True,
                   motif_precision="La durée de huit à douze ans traverse deux classes.")
assert evaluer("A2", p_precision, a_precision, ech_precision, 0.8).precision_necessaire
p_precision.citation = "dans trente ans"
assert not evaluer("A2", p_precision, a_precision, ech_precision, 0.8).precision_necessaire
assert not evaluer("A2", p_clair, None, ech_clair, 0.8).precision_necessaire
p_clair.precision_necessaire, p_clair.motif_precision = True, "Une durée exacte serait plus confortable."
a_ok = Avis(critere_id="A2", accord=True, confiance=0.95, objection="", valeurs_suggerees=[])
r_ok = evaluer("A2", p_clair, a_ok, ech_clair, 0.8)
assert r_ok.valide and not r_ok.precision_necessaire and r_ok.motif_precision == ""

# Un critique trop zélé ne peut pas transformer son désaccord interne en question utilisateur.
s_interne = {"classif": [{"propositions": [prop("A2", ["10_15_ans"], "Dans douze ans", 0.9)]}],
             "critique": [{"avis": [avis("A2", False, 0.7, "Autre code possible")],
                            "question_relance": "Répétez votre horizon."}]}
d_interne = debattre(client(s_interne), ech_clair, ["A2"], max_tours=1)
assert not d_interne.resultats["A2"].precision_necessaire and d_interne.question_relance == ""

# La conversation dispose du même débat interne à deux tours que les réponses libres du questionnaire.
import entretien
n = len(ENVOIS)
conv = entretien.analyser(client(s2), ECH, ["A3", "A2"], seuil=0.8)
assert conv["A3"].valide and conv["A3"].valeurs == ["retraite"] and conv["A2"].valide
assert len(ENVOIS) - n == 4
print("Précisions justifiées uniquement et désaccord conversationnel résolu entre agents : OK")
