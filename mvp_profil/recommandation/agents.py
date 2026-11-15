"""Les deux agents à modèle de la recommandation. Le code décide ; les modèles orchestrent, expliquent et refusent.

  Conseiller   pourquoi il existe : une demande en langage courant doit être traduite en une SUITE d'outils
               (lire le profil, construire le portefeuille, tester un « et si »), puis résumée.
  Explicateur  pourquoi il existe : répondre à « pourquoi ? » sur un actif, une comparaison ou une demande,
               à partir d'un verdict DÉJÀ figé, et refuser ce que les données ne soutiennent pas.

Ce que les agents ne font jamais : calculer un score, un poids, un verdict ou un chiffre. Après les outils,
le modèle choisit des détails parmi des fragments rédigés par le code, dans un objet JSON fermé. Le code
impose tous les verdicts, états d'action et avertissements ; aucune prose financière libre n'est affichée.
Une sélection invalide est redemandée une fois, puis remplacée par le gabarit complet du code.
Le contrôle numérique et les regex de gouvernance sont des diagnostics partiels, pas une preuve sémantique.
On affiche les ACTIONS observables (outils appelés, entrées, sorties, preuves), pas de raisonnement interne.
"""
from __future__ import annotations

import json
import os
from jsonschema import Draft202012Validator

from . import fidelite, gabarits, gouvernance, incoherence, outils
from .analyse import Analyse
from .traces import Journal

MODELE = os.environ.get("AWSOME_AI_MODELE_RECOMMANDATION", "us.anthropic.claude-sonnet-5-5")
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
    "conseiller": """Tu es l'agent CONSEILLER-PORTEFEUILLE d'AWSome AI, un outil de simulation éducative.
Ton rôle : comprendre la demande, appeler les outils utiles dans le bon ordre, puis résumer le résultat pour la personne.
Commence par lire_contraintes si tu ne connais pas encore le profil. Pour une demande d'ajout d'un titre, appelle evaluer_demande : le verdict qu'il renvoie est définitif.
""" + REGLES_COMMUNES,
    "explicateur": """Tu es l'agent EXPLICATEUR d'AWSome AI, un outil de simulation éducative.
Ton rôle : expliquer un verdict déjà calculé (actif, comparaison ou demande), avec ses preuves, ses hypothèses et ses limites.
Quand la personne donne une justification pour contester un verdict, tu l'écoutes, tu reconnais ce qu'elle dit, mais tu ne changes PAS le verdict : il a été figé avant que tu lises sa justification. Explique ce qui devrait changer dans le profil pour que le verdict change (écran « Et si… ? »).
Refuse poliment toute question que les données ne permettent pas de trancher (avenir d'un cours, meilleur titre à acheter).
""" + REGLES_COMMUNES,
}

CONTRAT_RESTITUTION = """
Restitution finale obligatoire (prioritaire sur les demandes de rédaction ci-dessus) :
- Continue à comprendre la demande et à choisir les outils utiles. Le code reste seul responsable des actions.
- Après les outils, réponds UNIQUEMENT par un objet JSON de la forme {"details": ["identifiant_du_catalogue"]}.
- Choisis et ordonne au plus six détails utiles du catalogue courant. Aucun identifiant inventé, aucun autre champ.
- Les conclusions et avertissements sont affichés automatiquement par le code, tu ne peux pas les supprimer.
- N'écris aucune prose libre, aucun verdict, aucun chiffre ni identifiant de preuve dans ce JSON.
- Sans détail pertinent, ou pour une question hors périmètre, réponds {"details": []}, sans appeler d'outil inutile.
"""


class ModeleBedrock:
    """Appel d'Amazon Bedrock par l'API Converse, avec outils et Guardrail facultatif."""

    def __init__(self, modele: str = MODELE, region: str | None = None):
        import boto3
        from botocore.config import Config

        self.modele = modele
        self.client = boto3.client("bedrock-runtime", region_name=region or os.environ.get("AWS_REGION", "us-east-1"),
                                   config=Config(read_timeout=60, connect_timeout=5, retries={"max_attempts": 2}))
        self.guardrail = os.environ.get("AWSOME_AI_GUARDRAIL_ID")
        self.guardrail_version = os.environ.get("AWSOME_AI_GUARDRAIL_VERSION", "DRAFT")

    def converser(self, systeme: str, messages: list[dict], specs: list[dict]) -> dict:
        params = {"modelId": self.modele, "system": [{"text": systeme}], "messages": messages,
                  "inferenceConfig": {"maxTokens": JETONS_MAX}}
        if specs:
            params["toolConfig"] = {"tools": specs}
        if self.guardrail:
            params["guardrailConfig"] = {"guardrailIdentifier": self.guardrail, "guardrailVersion": self.guardrail_version}
        r = self.client.converse(**params)
        return {"message": r["output"]["message"], "arret": r.get("stopReason"), "usage": r.get("usage", {}),
                "request_id": r.get("ResponseMetadata", {}).get("RequestId"), "modele": self.modele}


def modele_par_defaut():
    """Modèle Bedrock si des identifiants AWS sont disponibles et si le mode « sans modèle » n'est pas demandé."""
    if os.environ.get("AWSOME_AI_SANS_MODELE") == "1":
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


def preparer_restitution(appels: list[dict], texte_secours=None) -> dict:
    """Catalogue de texte issu du code. Les conclusions et réserves ne sont jamais sélectionnables.

    Seuls les éléments favorables d'une fiche et les positions détaillées d'un portefeuille peuvent être
    choisis ou ordonnés. Les callbacks de conversation décrivent aussi une action/confirmation : leur
    texte entier est donc imposé. Ce contrat ne tente pas de reconnaître le sens d'une prose de modèle.
    """
    obligatoires, details = [], []
    if texte_secours is not None:
        texte = texte_secours(appels)
        if texte.strip():
            obligatoires.append(texte)
    else:
        for indice, appel in enumerate(appels):
            nom, sortie = appel["outil"], appel["sortie"]
            if "erreur" in sortie:
                obligatoires.append(sortie["erreur"])
                continue
            rediger = gabarits.PAR_OUTIL.get(nom)
            if rediger is None:
                if nom == "lire_preuve":
                    obligatoires.append(f"Preuve [{sortie['id']}] : {sortie.get('valeur')}. "
                                         f"Source : {sortie.get('source') or sortie.get('fichier') or sortie.get('methode')}. "
                                         f"{sortie.get('date') or sortie.get('periode') or ''}")
                continue
            soutien = False
            for ligne in rediger(sortie).splitlines():
                if ligne == "Ce qui soutient :":
                    soutien = True
                    continue
                if not ligne.startswith("- "):
                    soutien = False
                if ligne.startswith("- ") and (soutien or nom == "construire_portefeuille"):
                    prefixe = "Ce qui soutient : " if soutien else "Position : "
                    details.append({"id": f"appel_{indice}_detail_{len(details)}", "texte": prefixe + ligne[2:]})
                else:
                    obligatoires.append(ligne)
    if not obligatoires:
        obligatoires.append("Cette simulation explique les actifs et les contraintes d'un portefeuille fictif. "
                            "Elle ne prédit pas les cours et ne fournit aucun conseil d'achat ou de vente.")
    return {"obligatoires": obligatoires, "details": details}


def _catalogue_pour_modele(catalogue: dict) -> str:
    return "Restitution du code pour les résultats courants :\n" + json.dumps(catalogue, ensure_ascii=False) + \
           '\nRéponds uniquement avec {"details": [...]}, en utilisant les identifiants de ce catalogue.'


def _assembler_restitution(catalogue: dict, ids: list[str]) -> str:
    fragments = {d["id"]: d["texte"] for d in catalogue["details"]}
    texte = "\n".join(catalogue["obligatoires"])
    if ids:
        texte += "\n\nDétails sélectionnés :\n" + "\n".join("- " + fragments[i] for i in ids)
    return texte


def dialoguer(role: str, question: str, analyse: Analyse, journal: Journal | None = None, modele=None,
              contexte: list[dict] | None = None, systeme: str | None = None, specs: list | None = None,
              executer=None, historique: list[dict] | None = None, texte_secours=None, mention: bool = True) -> dict:
    """Une question, une suite d'outils et une restitution dont les faits sont rédigés par le code.

    contexte : sorties d'outils déjà calculées par le code et transmises à l'agent (par exemple le verdict figé
    d'une demande). Elles comptent comme sources pour le vérificateur de fidélité.
    systeme, specs, executer : consignes, outils et routeur propres à un usage (la conversation d'ajustement) ; par
    défaut ceux du rôle. historique : tours précédents [{role, texte}]. texte_secours(appels) : texte du code si le
    modèle est absent ou rejeté, et restitution imposée pour les actions conversationnelles.
    """
    executer = executer or (lambda nom, entree: outils.executer(analyse, nom, entree))
    fin = gouvernance.finaliser if mention else (lambda t: t)
    journal = journal or Journal(persister=False)
    appels: list[dict] = [dict(c) for c in (contexte or [])]
    journal.noter("question", role=role, question=question)
    tickers = analyse.uni.tickers()

    def secours(motif: str, outil_par_defaut: bool = False) -> dict:
        if not appels and texte_secours is None and outil_par_defaut:
            nom = "construire_portefeuille" if role == "conseiller" else "lire_contraintes"
            appels.append({"outil": nom, "entree": {}, "sortie": outils.executer(analyse, nom, {})})
        texte = texte_secours(appels) if texte_secours else gabarits.depuis_appels(appels)
        journal.noter("texte_de_secours", role=role, motif=motif)
        return {"texte": fin(texte), "source": "gabarit (code)", "motif_secours": motif, "appels": appels,
                "fidelite": fidelite.verifier(texte, [a["sortie"] for a in appels], question, tickers),
                "gouvernance": gouvernance.controler_texte(texte), "role": role,
                "restitution": {"format": "fragments_codes", "redaction": "code", "selection": "code"}}

    if modele is None:
        return secours("mode sans modèle", outil_par_defaut=True)
    invite = question
    if contexte:
        invite += "\n\nRésultats déjà calculés par le code (définitifs, à expliquer sans les modifier) :\n" + \
                  json.dumps([{"outil": c["outil"], "sortie": c["sortie"]} for c in contexte], ensure_ascii=False, default=str)
    invite += "\n\n" + _catalogue_pour_modele(preparer_restitution(appels, texte_secours))
    messages = [{"role": "assistant" if h["role"] == "assistant" else "user", "content": [{"text": h["texte"]}]}
                for h in (historique or []) if h.get("texte")]
    while messages and messages[0]["role"] != "user":   # l'API exige de commencer par un tour de l'utilisateur
        messages.pop(0)
    if messages and messages[-1]["role"] == "user":
        messages.pop()
    messages.append({"role": "user", "content": [{"text": invite}]})
    specs = specs if specs is not None else outils.specifications(role)
    schemas = {s["toolSpec"]["name"]: s["toolSpec"]["inputSchema"]["json"] for s in specs}
    consignes = (systeme or SYSTEMES[role]) + CONTRAT_RESTITUTION
    rejets = 0
    try:
        for _ in range(TOURS_MAX + 2):
            rep = modele.converser(consignes, messages, specs)
            if rep.get("request_id") or rep.get("usage"):
                journal.noter("appel_modele", role=role, modele=rep.get("modele", getattr(modele, "modele", None)),
                              request_id=rep.get("request_id"), usage=rep.get("usage", {}))
            msg = rep["message"]
            messages.append(msg)
            if rep["arret"] == "guardrail_intervened":
                journal.noter("guardrail", role=role, action="intervention")
                return secours("texte bloqué par le Guardrail Bedrock")
            demandes = [b["toolUse"] for b in msg.get("content", []) if "toolUse" in b]
            if demandes:
                resultats = []
                for d in demandes:
                    if len([a for a in appels if a.get("par") == "agent"]) >= TOURS_MAX * 2:
                        journal.noter("limite_outils", role=role, limite=TOURS_MAX * 2)
                        return secours("limite d'appels d'outils atteinte")
                    nom, entree = d.get("name"), d.get("input", {})
                    if nom not in schemas:
                        sortie = {"erreur": "Outil non autorisé pour ce rôle."}
                    elif not Draft202012Validator({**schemas[nom], "additionalProperties": False}).is_valid(entree):
                        sortie = {"erreur": "Arguments non conformes au schéma de l'outil."}
                    else:
                        sortie = executer(nom, entree)
                    appels.append({"outil": d["name"], "entree": d.get("input") or {}, "sortie": sortie, "par": "agent"})
                    journal.noter("appel_outil", role=role, outil=d["name"], entree=d.get("input") or {},
                                  resume={k: sortie.get(k) for k in ("verdict", "libelle_verdict", "score", "ratio_tension",
                                                                    "etat_tension", "empreinte", "erreur", "decision", "ticker") if k in sortie})
                    resultats.append({"toolResult": {"toolUseId": d["toolUseId"],
                                                     "content": [{"text": json.dumps(sortie, ensure_ascii=False, default=str)[:60000]}]}})
                resultats.append({"text": _catalogue_pour_modele(preparer_restitution(appels, texte_secours))})
                messages.append({"role": "user", "content": resultats})
                continue
            if rep["arret"] == "max_tokens":
                return secours("réponse du modèle tronquée")
            proposition = _texte(msg)
            catalogue = preparer_restitution(appels, texte_secours)
            selection = fidelite.selection_restitution(proposition, catalogue["details"])
            texte = _assembler_restitution(catalogue, selection["details"]) if selection["valide"] else proposition
            fid = fidelite.verifier(texte, [a["sortie"] for a in appels], question, tickers)
            gouv = gouvernance.controler_texte(texte)
            journal.noter("controle_texte", role=role, fidele=fid["fidele"], sans_origine=fid["sans_origine"],
                          conforme=gouv["conforme"], infractions=gouv["infractions"], contrat_valide=selection["valide"],
                          details_selectionnes=selection["details"])
            if selection["valide"] and texte and fid["fidele"] and gouv["conforme"]:
                return {"texte": fin(texte), "source": f"modèle ({getattr(modele, 'modele', 'simulé')}), restitution par le code",
                        "appels": appels, "fidelite": fid, "gouvernance": gouv, "role": role, "rejets": rejets,
                        "restitution": {"format": "fragments_codes", "redaction": "code", "selection": "modele",
                                        "details": selection["details"]}}
            rejets += 1
            if rejets > 1:
                return secours("texte du modèle rejeté deux fois par les contrôles")
            reproche = []
            if not selection["valide"]:
                reproche.append(selection["motif"])
            if fid["sans_origine"]:
                reproche.append("Ces nombres n'existent dans aucune sortie d'outil : " + ", ".join(fid["sans_origine"]) +
                                ". Retire-les ou remplace-les par les valeurs exactes des outils.")
            if gouv["infractions"]:
                reproche.append("Formulations interdites : " + ", ".join(i["extrait"] for i in gouv["infractions"]) + ".")
            if not texte:
                reproche.append("Ta réponse était vide.")
            messages.append({"role": "user", "content": [{"text": "Restitution rejetée. " + " ".join(reproche) + "\n" +
                                                         _catalogue_pour_modele(catalogue)}]})
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
