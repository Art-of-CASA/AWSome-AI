"""Les deux agents à modèle de la recommandation. Le code décide ; les modèles orchestrent, expliquent et refusent.

  Conseiller   pourquoi il existe : une demande en langage courant doit être traduite en une SUITE d'outils
               (lire le profil, construire le portefeuille, tester un « et si »), puis résumée.
  Explicateur  pourquoi il existe : répondre à « pourquoi ? » sur un actif, une comparaison ou une demande,
               à partir d'un verdict DÉJÀ figé, et refuser ce que les données ne soutiennent pas.

Ce que les agents ne font jamais : calculer un score, un poids, un verdict ou un chiffre. Tout texte passe par
  1. le vérificateur de fidélité (chaque chiffre doit exister dans une sortie d'outil de l'échange) ;
  2. le contrôle de gouvernance (ni conseil personnalisé, ni promesse, ni prédiction) ;
  3. le Guardrail Amazon Bedrock, s'il est configuré.
Un texte rejeté est redemandé une fois, puis remplacé par un texte de gabarit construit par le code.
On affiche les ACTIONS observables (outils appelés, entrées, sorties, preuves), pas de raisonnement interne.
"""
from __future__ import annotations

import json
import os

from . import fidelite, gabarits, gouvernance, incoherence, outils
from .analyse import Analyse
from .traces import Journal

MODELE = os.environ.get("ALPHAFORGE_MODELE_RECOMMANDATION", "us.anthropic.claude-sonnet-5-5")
TOURS_MAX = 6
# Vérifié sur Bedrock le 2026-11-15 : Sonnet 5.5 renvoie aussi des blocs de raisonnement (reasoningContent), qui
# comptent dans la limite de sortie. La limite est donc large ; ces blocs ne sont jamais affichés ni journalisés,
# ils sont seulement renvoyés tels quels au modèle pendant la boucle d'outils, comme l'API le demande.
JETONS_MAX = 4000

REGLES_COMMUNES = """Règles absolues :
- Tu ne calcules RIEN. Chaque chiffre que tu écris doit être recopié tel quel d'une sortie d'outil de cet échange. Sinon, n'écris pas de chiffre.
- Tu ne décides rien : verdicts, scores, poids et plafonds viennent des outils. Tu ne les contestes pas et tu ne les adoucis pas.
- Simulation éducative : jamais de conseil financier personnalisé (« je vous conseille », « achetez », « vous devriez »), jamais de promesse, jamais de prédiction de rendement à partir du passé. Dis « cohérent avec le profil saisi », « plafonné à », « exclu parce que ».
- Si une information manque (actif absent de l'univers, donnée manquante, critère sans réponse), dis-le clairement. N'invente jamais une valeur.
- Distingue les faits (données datées), les hypothèses (seuils de l'équipe, ajustables) et les scénarios fictifs.
- Cite les preuves entre crochets avec leur identifiant exact, par exemple [actif:NVDA:max_drawdown] ou [profil:D12].
- Dis « traçable », jamais « 100 % explicable ».
- Réponds en français, en moins de 180 mots, sans titre, sans tableau, sans moraliser.
- N'expose pas ton raisonnement : donne la conclusion, les raisons observables et les preuves."""

SYSTEMES = {
    "conseiller": """Tu es l'agent CONSEILLER-PORTEFEUILLE d'AlphaForge, un outil de simulation éducative.
Ton rôle : comprendre la demande, appeler les outils utiles dans le bon ordre, puis résumer le résultat pour la personne.
Commence par lire_contraintes si tu ne connais pas encore le profil. Pour une demande d'ajout d'un titre, appelle evaluer_demande : le verdict qu'il renvoie est définitif.
""" + REGLES_COMMUNES,
    "explicateur": """Tu es l'agent EXPLICATEUR d'AlphaForge, un outil de simulation éducative.
Ton rôle : expliquer un verdict déjà calculé (actif, comparaison ou demande), avec ses preuves, ses hypothèses et ses limites.
Quand la personne donne une justification pour contester un verdict, tu l'écoutes, tu reconnais ce qu'elle dit, mais tu ne changes PAS le verdict : il a été figé avant que tu lises sa justification. Explique ce qui devrait changer dans le profil pour que le verdict change (écran « Et si… ? »).
Refuse poliment toute question que les données ne permettent pas de trancher (avenir d'un cours, meilleur titre à acheter).
""" + REGLES_COMMUNES,
}


class ModeleBedrock:
    """Appel d'Amazon Bedrock par l'API Converse, avec outils et Guardrail facultatif."""

    def __init__(self, modele: str = MODELE, region: str | None = None):
        import boto3
        from botocore.config import Config

        self.modele = modele
        self.client = boto3.client("bedrock-runtime", region_name=region or os.environ.get("AWS_REGION", "us-east-1"),
                                   config=Config(read_timeout=60, connect_timeout=5, retries={"max_attempts": 2}))
        self.guardrail = os.environ.get("ALPHAFORGE_GUARDRAIL_ID")
        self.guardrail_version = os.environ.get("ALPHAFORGE_GUARDRAIL_VERSION", "DRAFT")

    def converser(self, systeme: str, messages: list[dict], specs: list[dict]) -> dict:
        params = {"modelId": self.modele, "system": [{"text": systeme}], "messages": messages,
                  "inferenceConfig": {"maxTokens": JETONS_MAX}}
        if specs:
            params["toolConfig"] = {"tools": specs}
        if self.guardrail:
            params["guardrailConfig"] = {"guardrailIdentifier": self.guardrail, "guardrailVersion": self.guardrail_version}
        r = self.client.converse(**params)
        return {"message": r["output"]["message"], "arret": r.get("stopReason"), "usage": r.get("usage", {})}


def modele_par_defaut():
    """Modèle Bedrock si des identifiants AWS sont disponibles et si le mode « sans modèle » n'est pas demandé."""
    if os.environ.get("ALPHAFORGE_SANS_MODELE") == "1":
        return None
    try:
        import boto3
        if boto3.Session().get_credentials() is None:
            return None
        return ModeleBedrock()
    except Exception:
        return None


def _texte(message: dict) -> str:
    return "\n".join(b["text"] for b in message.get("content", []) if "text" in b).strip()


def dialoguer(role: str, question: str, analyse: Analyse, journal: Journal | None = None, modele=None,
              contexte: list[dict] | None = None, systeme: str | None = None, specs: list | None = None,
              executer=None, historique: list[dict] | None = None, texte_secours=None, mention: bool = True) -> dict:
    """Une question, une suite d'appels d'outils, un texte vérifié.

    contexte : sorties d'outils déjà calculées par le code et transmises à l'agent (par exemple le verdict figé
    d'une demande). Elles comptent comme sources pour le vérificateur de fidélité.
    systeme, specs, executer : consignes, outils et routeur propres à un usage (la conversation d'ajustement) ; par
    défaut ceux du rôle. historique : tours précédents [{role, texte}]. texte_secours(appels) : texte du code si le
    modèle est absent ou rejeté.
    """
    executer = executer or (lambda nom, entree: outils.executer(analyse, nom, entree))
    fin = gouvernance.finaliser if mention else (lambda t: t)
    journal = journal or Journal(persister=False)
    appels: list[dict] = [dict(c) for c in (contexte or [])]
    journal.noter("question", role=role, question=question)
    tickers = analyse.uni.tickers()

    def secours(motif: str) -> dict:
        if not appels and texte_secours is None:  # aucun outil appelé : le code choisit l'outil par défaut du rôle
            nom = "construire_portefeuille" if role == "conseiller" else "lire_contraintes"
            appels.append({"outil": nom, "entree": {}, "sortie": outils.executer(analyse, nom, {})})
        texte = texte_secours(appels) if texte_secours else gabarits.depuis_appels(appels)
        journal.noter("texte_de_secours", role=role, motif=motif)
        return {"texte": fin(texte), "source": "gabarit (code)", "motif_secours": motif, "appels": appels,
                "fidelite": fidelite.verifier(texte, [a["sortie"] for a in appels], question, tickers),
                "gouvernance": gouvernance.controler_texte(texte), "role": role}

    if modele is None:
        return secours("mode sans modèle")
    invite = question
    if contexte:
        invite += "\n\nRésultats déjà calculés par le code (définitifs, à expliquer sans les modifier) :\n" + \
                  json.dumps([{"outil": c["outil"], "sortie": c["sortie"]} for c in contexte], ensure_ascii=False, default=str)
    messages = [{"role": "assistant" if h["role"] == "assistant" else "user", "content": [{"text": h["texte"]}]}
                for h in (historique or []) if h.get("texte")]
    while messages and messages[0]["role"] != "user":   # l'API exige de commencer par un tour de l'utilisateur
        messages.pop(0)
    if messages and messages[-1]["role"] == "user":
        messages.pop()
    messages.append({"role": "user", "content": [{"text": invite}]})
    specs = specs if specs is not None else outils.specifications(role)
    consignes = systeme or SYSTEMES[role]
    rejets = 0
    try:
        for _ in range(TOURS_MAX + 2):
            rep = modele.converser(consignes, messages, specs)
            msg = rep["message"]
            messages.append(msg)
            if rep["arret"] == "guardrail_intervened":
                journal.noter("guardrail", role=role, action="intervention")
                return secours("texte bloqué par le Guardrail Bedrock")
            demandes = [b["toolUse"] for b in msg.get("content", []) if "toolUse" in b]
            if demandes and len([a for a in appels if a.get("par") == "agent"]) < TOURS_MAX * 2:
                resultats = []
                for d in demandes:
                    sortie = executer(d["name"], d.get("input") or {})
                    appels.append({"outil": d["name"], "entree": d.get("input") or {}, "sortie": sortie, "par": "agent"})
                    journal.noter("appel_outil", role=role, outil=d["name"], entree=d.get("input") or {},
                                  resume={k: sortie.get(k) for k in ("verdict", "libelle_verdict", "score", "ratio_tension",
                                                                    "etat_tension", "empreinte", "erreur", "decision", "ticker") if k in sortie})
                    resultats.append({"toolResult": {"toolUseId": d["toolUseId"],
                                                     "content": [{"text": json.dumps(sortie, ensure_ascii=False, default=str)[:60000]}]}})
                messages.append({"role": "user", "content": resultats})
                continue
            if rep["arret"] == "max_tokens":
                return secours("réponse du modèle tronquée")
            texte = _texte(msg)
            fid = fidelite.verifier(texte, [a["sortie"] for a in appels], question, tickers)
            gouv = gouvernance.controler_texte(texte)
            journal.noter("controle_texte", role=role, fidele=fid["fidele"], sans_origine=fid["sans_origine"],
                          conforme=gouv["conforme"], infractions=gouv["infractions"])
            if texte and fid["fidele"] and gouv["conforme"]:
                return {"texte": fin(texte), "source": f"modèle ({getattr(modele, 'modele', 'simulé')})",
                        "appels": appels, "fidelite": fid, "gouvernance": gouv, "role": role, "rejets": rejets}
            rejets += 1
            if rejets > 1:
                return secours("texte du modèle rejeté deux fois par les contrôles")
            reproche = []
            if fid["sans_origine"]:
                reproche.append("Ces nombres n'existent dans aucune sortie d'outil : " + ", ".join(fid["sans_origine"]) +
                                ". Retire-les ou remplace-les par les valeurs exactes des outils.")
            if gouv["infractions"]:
                reproche.append("Formulations interdites : " + ", ".join(i["extrait"] for i in gouv["infractions"]) + ".")
            if not texte:
                reproche.append("Ta réponse était vide.")
            messages.append({"role": "user", "content": [{"text": "Texte rejeté par les contrôles. " + " ".join(reproche) +
                                                         " Réécris la réponse en respectant les règles."}]})
        return secours("nombre de tours dépassé")
    except Exception as e:  # réseau, droits, quota : la démonstration continue sans modèle
        journal.noter("erreur_modele", role=role, erreur=f"{type(e).__name__}: {str(e)[:200]}")
        return secours(f"modèle indisponible ({type(e).__name__})")


def traiter_demande(analyse: Analyse, actif: str, part_pct: float, justification: str = "", journal: Journal | None = None,
                    modele=None) -> dict:
    """Parcours « demande d'un titre » (cas Robert), dans un ordre que la trace permet de vérifier :

      1. le code calcule et FIGE le verdict (horodatage, empreinte) ;
      2. le code détecte les incohérences entre la demande et le profil ;
      3. seulement ensuite, la justification de la personne est lue, et transmise à l'Explicateur ;
      4. après la rédaction, le code revérifie que le verdict n'a pas bougé.
    """
    journal = journal or Journal(persister=False)
    verdict = analyse.demande(actif, part_pct)
    journal.noter("verdict_fige", ticker=verdict["ticker"], part_pct=part_pct, verdict=verdict["verdict"],
                  empreinte=verdict["empreinte"], fige_le=verdict["fige_le"])
    incoh = incoherence.detecter(analyse, verdict)
    journal.noter("incoherence", incoherent=incoh["incoherent"], tensions=[t["critere"] for t in incoh["tensions"]])
    journal.noter("justification_recue", longueur=len(justification), texte=justification[:500])
    sortie = {k: v for k, v in verdict.items() if k not in ("controles", "preuves")}
    sortie["preuves"] = [p["id"] for p in verdict.get("preuves", [])]
    sortie["incoherence"] = incoh
    question = (f"La personne demande d'ajouter {verdict['ticker']} pour {part_pct:g} % de son portefeuille fictif. "
                + (f"Sa justification : « {justification.strip()} ». " if justification.strip() else "") +
                "Explique le verdict, les raisons et les preuves, puis ce qui resterait compatible.")
    reponse = dialoguer("explicateur", question, analyse, journal, modele,
                        contexte=[{"outil": "evaluer_demande", "entree": {"actif": verdict["ticker"], "part_pct": part_pct},
                                   "sortie": sortie, "par": "code"}])
    apres = analyse.demande(actif, part_pct)
    inchange = apres["verdict"] == verdict["verdict"] and apres["empreinte"] == verdict["empreinte"]
    journal.noter("verdict_reverifie", inchange=inchange, empreinte=apres["empreinte"])
    return {"verdict": verdict, "incoherence": incoh, "reponse": reponse, "verdict_inchange": inchange,
            "ordre": [e["type"] for e in journal.evenements]}
