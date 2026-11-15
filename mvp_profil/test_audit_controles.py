"""Régressions des frontières d'agents : modèles simulés, aucun service distant."""
from reco_tests_commun import ch, verifier
from recommandation import agents, conversation as K


class Modele:
    modele = "audit-simule"

    def __init__(self, appels):
        self.appels = appels

    def converser(self, systeme, messages, specs):
        if self.appels is not None:
            appels, self.appels = self.appels, None
            return {"arret": "tool_use", "message": {"role": "assistant", "content": [
                {"toolUse": {"toolUseId": str(i), "name": n, "input": e}} for i, (n, e) in enumerate(appels)]}}
        return {"arret": "end_turn", "message": {"role": "assistant", "content": [{"text": '{"details": []}'}]}}


def contexte():
    return K.Contexte(ch.charger_persona("robert")["profil"], [], K.etat_initial())


a = contexte().analyse
for nom, entree, autorise in [("chercher_actif", {"actif": "NVDA"}, True),
                              ("construire_portefeuille", {}, False),
                              ("chercher_actif", {"actif": []}, False),
                              ("chercher_actif", {"actif": "NVDA", "extra": True}, False)]:
    r = agents.dialoguer("explicateur", "Pourquoi NVDA ?", a, modele=Modele([(nom, entree)]))
    verifier(("erreur" not in r["appels"][0]["sortie"]) == autorise, f"Frontière outil : {nom} {entree}")

r = agents.dialoguer("explicateur", "Profil", a, modele=Modele([("lire_contraintes", {})] * 13))
verifier(len(r["appels"]) == 12 and "limite" in r["motif_secours"], "budget par appel, même dans un lot")

c = contexte()
K.proposer_mise_a_jour(c, "D9", "20")
K.tour(c, "oui", Modele([("proposer_mise_a_jour_du_profil", {"critere": "A2", "valeur": "10_15_ans"}), ("confirmer", {})]))
verifier("A2" not in c.etat["maj"], "un oui ne valide pas une nouvelle proposition")
verifier(c.etat["maj"]["D9"]["valeurs"] == ["20"], "le oui reste utilisable pour la proposition affichée")
for phrase in ("Bonjour", "non", "Pourquoi NVDA ?"):
    c = contexte()
    K.tour(c, phrase, Modele([("ajouter_au_portefeuille", {"actif": "NVDA", "part_pct": 5})]))
    verifier(not c.etat["ajouts"], "pas d'ajout sans demande : " + phrase)
c = contexte()
K.tour(c, "ajoute Nvidia pour 3 %", Modele([("ajouter_au_portefeuille", {"actif": "NVDA", "part_pct": 5})]))
verifier(c.etat["ajouts"] == {"NVDA": 3.0}, "la part vient de la demande, jamais du modèle")
c = contexte()
K.tour(c, "ajoute Nvidia", Modele([("ajouter_au_portefeuille", {"actif": "RY.TO", "part_pct": 5})]))
verifier(not c.etat["ajouts"], "le modèle ne peut pas changer le titre demandé")
print("Frontières audit OK : permissions, schémas, budget, consentement et arguments liés à la demande")

# Le contenu privé reste dans la session ; les copies disque/table sont minimisées.
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from recommandation import traces
with tempfile.TemporaryDirectory() as d, patch.object(traces, "DOSSIER", Path(d)):
    j = traces.Journal()
    j.noter("question", question="private@example.invalid", entree={"actif": "private@example.invalid"})
    contenu = (Path(d) / f"{j.session}.jsonl").read_text()
    verifier("private@example.invalid" not in contenu, "pas de texte utilisateur dans le journal persistant")
    verifier(json.loads(contenu)["version_code"].startswith("profil-"), "version vérifiable dans chaque événement")

class AvecUsage(Modele):
    def converser(self, *args):
        r = super().converser(*args)
        r.update(request_id="audit-request", usage={"inputTokens": 10, "outputTokens": 2})
        return r
j = traces.Journal(persister=False)
agents.dialoguer("explicateur", "Profil", a, journal=j, modele=AvecUsage([]))
verifier(j.de_type("appel_modele")[0]["request_id"] == "audit-request", "identifiant d'appel conservé")
verifier(j.de_type("appel_modele")[0]["usage"]["inputTokens"] == 10, "consommation conservée")
