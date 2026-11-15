"""Critères DYNAMIQUES : propres à chaque personne, créés à partir d'une dernière question ouverte.

Les 37 critères fixes (criteres.py) couvrent les cas prévus. Mais chaque personne a ses particularités :
« je travaille chez Shopify et j'ai déjà beaucoup d'actions de mon employeur », « je déménage en Europe dans
5 ans », « je ne veux rien qui touche à Elon Musk », « finance islamique : pas d'intérêts »… À la toute fin
du parcours, une question ouverte demande à la personne ce qu'elle aimerait encore préciser, et l'IA en tire
des critères nouveaux, créés pour elle.

Pour rester reproductible et comparable aux actifs comme les critères fixes, un critère dynamique n'est
PAS du texte libre : c'est une règle (effet, dimension, valeurs) exprimée avec le vocabulaire RÉEL des actifs
(vocabulaire_actifs.json, tiré de data_extended/asset_criteria.csv par scripts/build_vocabulaire.py) :
  effet      exclure | privilegier | plafonner (avec un % maximal) | note
  dimension  titre, classe, region, pays, devise, secteur, theme, exclusion, risque_pays, … (17 dimensions)
  valeurs    valeurs existantes de cette dimension, recopiées exactement
Le code vérifie tout (dimension connue, valeurs existantes, citation exacte, accord du critique) et calcule
les actifs concernés. Ce qui ne peut pas s'exprimer avec ce vocabulaire n'est pas perdu : il devient une
« note » (contexte pour le conseiller, citée mot pour mot, non utilisée pour filtrer).
Décision : validé si le critique est d'accord et si les deux confiances >= seuil ; « retenu » (confiance plus
basse, signalée) si la confiance atteint le plancher de 50 % ; sinon le critère n'est pas créé.

Quand l'idée vise des actifs mais qu'aucune valeur existante ne la traduit (« rien qui touche à Elon Musk »), le
critère est créé « à étiqueter » avec un CONCEPT : l'agent chercheur (chercheur.py) parcourt nos données et
Wikipédia, preuves à l'appui, et en fait un nouveau mot-clé d'actif kw_dyn_<concept> (appliquer_etiquetage).
Exclure ou plafonner un titre signale aussi les FNB qui le détiennent parmi leurs principales positions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from agents import (SEUIL_PLANCHER, SYSTEM_CRITIQUE, Backend, Critique, _ask, _citation_presente, _transcript)
from chercheur import expositions_fnb
from criteres import CRITERES

VOCAB = json.loads((Path(__file__).with_name("vocabulaire_actifs.json")).read_text(encoding="utf-8"))
DIMENSIONS = VOCAB["dimensions"]
EFFETS = {"exclure": "Exclure", "privilegier": "Privilégier", "plafonner": "Plafonner", "note": "Note"}
# Même typologie que les règles des critères fixes (config/criteres_appariement.csv, colonne type_regle)
TYPE_REGLE = {"exclure": "exclusion", "plafonner": "plafond", "privilegier": "preference", "note": "information"}

QUESTION_OUVERTE = ("Dernière question : y a-t-il quelque chose de particulier à votre situation ou à vos envies que nous "
                    "n'avons pas abordé et que vous aimeriez préciser ? Une entreprise, un pays, une valeur, un projet…")
AIDE_OUVERTE = ("Exemples : « Je travaille chez Shopify et j'ai déjà beaucoup d'actions de mon employeur. » · "
                "« Je vais m'installer en Europe dans cinq ans. » · « Je ne veux rien qui touche aux réseaux sociaux. »")


class CritereIA(BaseModel):
    nom: str                 # intitulé court, à la troisième personne (« Pas d'actions de son employeur, Shopify »)
    citation: str            # mots exacts de l'utilisateur
    effet: Literal["exclure", "privilegier", "plafonner", "note"]
    dimension: str           # une des dimensions du vocabulaire, ou « aucune » pour une note
    valeurs: list[str]       # valeurs existantes de cette dimension (vide pour une note)
    plafond_pct: int         # pour « plafonner » : part maximale du portefeuille en %, sinon 0
    concept: str             # idée qui vise des actifs sans valeur existante pour la traduire (« Elon Musk ») ; sinon vide
    confiance: float
    justification: str


class Decouverte(BaseModel):
    criteres: list[CritereIA]


def _vocabulaire() -> str:
    lignes = []
    for dim, d in DIMENSIONS.items():
        if dim == "titre":
            vals = ", ".join(f"{tk} ({VOCAB['noms'][tk]})" for tk in d["valeurs"])
        else:
            vals = ", ".join(d["valeurs"])
        lignes.append(f"- {dim} : {d['description']}. Valeurs : {vals}")
    return "\n".join(lignes)


def _fixes() -> str:
    return "\n".join(f"- {c['nom']}" for c in CRITERES.values())


SYSTEM_DECOUVREUR = """Tu es l'agent DÉCOUVREUR d'un outil de profil d'investisseur (simulation éducative, aucun conseil financier).
L'utilisateur a déjà répondu à un questionnaire complet. On lui a posé une dernière question ouverte : y a-t-il autre chose à préciser ?
Ta tâche : transformer sa réponse en CRITÈRES NOUVEAUX, propres à cette personne, que le questionnaire ne couvre pas déjà.
Pour chaque idée distincte de sa réponse, crée un critère :
- effet : exclure (il refuse), privilegier (il préfère, sans exclure le reste), plafonner (il accepte mais en quantité limitée,
  plafond_pct = part maximale en %), note (contexte utile qui ne s'exprime pas avec le vocabulaire des actifs).
  plafonner seulement si l'utilisateur donne LUI-MÊME un chiffre pour CETTE idée, présent dans la citation ; ne reprends
  jamais un chiffre dit à propos d'autre chose. Sans chiffre, choisis exclure ou privilegier.
- dimension et valeurs : choisis la dimension la plus PRÉCISE du vocabulaire des actifs et recopie EXACTEMENT des valeurs
  existantes. Un thème précis passe avant un secteur large (les banques -> theme banque, pas secteur Financials qui inclut
  les assureurs). Exemples : son employeur figure dans l'univers -> dimension titre, valeur son ticker ; il déménage en
  Europe -> privilegier devise EUR. N'invente aucune valeur.
- Si l'idée vise des entreprises ou des activités mais qu'aucune valeur existante ne la traduit exactement (« rien qui touche
  à Elon Musk », « pas de réseaux sociaux », « les entreprises qui recyclent »), garde l'effet voulu, mets dimension « aucune »,
  valeurs vides, et remplis concept : quelques mots, sans rien de personnel sur l'utilisateur (« entreprises liées à Elon Musk »).
  Un agent chercheur trouvera ensuite, preuves à l'appui, les actifs concernés.
- Si l'idée ne vise pas d'actif (situation de vie, contrainte de calendrier…), crée une note : dimension « aucune », valeurs
  vides, concept vide. Une note garde l'information sans filtrer les actifs.
- concept reste vide dès que des valeurs existantes traduisent l'idée.
- nom : intitulé court et clair, en français. citation : les mots exacts de l'utilisateur (copie fidèle). confiance entre 0 et 1.
- Ne recrée pas un critère que le questionnaire couvre déjà (liste fournie), sauf si la réponse le rend plus précis
  (exemple : « pas de banques » alors que le questionnaire ne demande que des thèmes généraux -> critère utile).
- Ne t'appuie que sur ce que l'utilisateur a dit. S'il n'a rien à ajouter (« non », « rien »), renvoie une liste vide."""


def decouvrir(backend: Backend, question: str, reponse: str) -> Decouverte:
    prompt = (f"Critères déjà couverts par le questionnaire :\n{_fixes()}\n\n"
              f"Vocabulaire des actifs (dimension : valeurs autorisées) :\n{_vocabulaire()}\n\n"
              f"Question : {question}\nRéponse de l'utilisateur : {reponse}")
    return _ask(backend, SYSTEM_DECOUVREUR, prompt, Decouverte)


A_ETIQUETER = "a_etiqueter"  # dimension d'attente : le chercheur crée le mot-clé (chercheur.py)


def _nettoyer(c: CritereIA) -> tuple[str, str, list[str], int]:
    """Contrôle déterministe : dimension connue et valeurs existantes. Sinon : à étiqueter par le chercheur si
    l'idée vise des actifs (concept rempli), ou note."""
    dim, effet = c.dimension.strip(), c.effet
    vals = []
    if effet != "note" and dim in DIMENSIONS:
        existantes = {v.lower(): v for v in DIMENSIONS[dim]["valeurs"]}
        vals = list(dict.fromkeys(existantes[v.strip().lower()] for v in c.valeurs if v.strip().lower() in existantes))
    if not vals:
        if effet == "note" or not c.concept.strip():
            return "note", "aucune", [], 0
        dim = A_ETIQUETER
    plafond = max(0, min(100, c.plafond_pct)) if effet == "plafonner" else 0
    if effet == "plafonner" and (plafond == 0 or not re.search(rf"(?<!\d){plafond}(?!\d)", c.citation)):
        # Plafond de 0 %, ou chiffre absent de la citation (emprunté à une autre phrase) : exclusion, plus prudente
        effet, plafond = "exclure", 0
    return effet, dim, vals, plafond


def actifs_concernes(dimension: str, valeurs: list[str]) -> list[str]:
    if dimension not in DIMENSIONS:
        return []
    d = DIMENSIONS[dimension]["valeurs"]
    return sorted({tk for v in valeurs for tk in d.get(v, [])})


def regle(c: dict) -> str:
    """Phrase lisible de la règle, affichée à l'utilisateur et exportée."""
    if c["effet"] == "note":
        return "Note pour le conseiller (aucun filtre automatique)"
    action = f"Plafonner à {c['plafond_pct']} %" if c["effet"] == "plafonner" else EFFETS[c["effet"]]
    if c["dimension"] == A_ETIQUETER:
        etat = {"echec": "recherche impossible, à revoir"}.get(c.get("etiquetage"), "recherche des actifs concernés en cours")
        return f"{action} : « {c['concept']} » ({etat})"
    if c["dimension"] == "mot_cle_dynamique":
        cible = f"{c['colonne']} = {', '.join(c['valeurs'])}"
        if not c["actifs"]:
            return f"{action} : {cible} (recherche faite : aucun actif de l'univers concerné)"
    else:
        cible = f"{c['dimension']} = {', '.join(c['valeurs'])}"
    n = len(c["actifs"])
    liste = ", ".join(c["actifs"]) if n <= 4 else f"{n} actifs de l'univers"
    portee = f" ({liste})" if n and c["dimension"] != "titre" else ""  # un titre se nomme lui-même
    fnb = c.get("fnb_exposes") or {}
    pct = lambda p: f"{p * 100:.1f} %".replace(".", ",")  # noqa: E731
    expo = (" ; FNB qui en détiennent : " + ", ".join(f"{e} ({pct(p)})" for e, p in list(fnb.items())[:5])) if fnb else ""
    return f"{action} : {cible}{portee}{expo}"


def appliquer_etiquetage(c: dict, res: dict) -> dict:
    """Résultat du chercheur -> le critère devient une règle sur le nouveau mot-clé kw_dyn_<concept>."""
    vals = ["oui", "partiel"] if res["partiel"] else ["oui"]
    actifs = res["oui"] + res["partiel"]
    c.update(dimension="mot_cle_dynamique", colonne=res["mot_cle"], valeurs=vals, actifs=actifs,
             fnb_exposes=res["fnb_exposes"] if c["effet"] in ("exclure", "plafonner") else {},
             etiquetage="fait", preuves=res["verdicts"], definition_mot_cle=res["definition"],
             recherche={k: res[k] for k in ("cree_le", "duree_s", "depuis_cache", "appels_outils", "rejetes") if k in res})
    c["regle"] = regle(c)
    return c


def _decrire(proposes: dict[str, dict]) -> str:
    return "\n".join(f"- {k} « {c['nom']} » : {regle(c)}. Citation : « {c['citation']} »" for k, c in proposes.items())


def creer(backend: Backend, question: str, reponse: str, seuil: float, deja: int = 0) -> list[dict]:
    """Question ouverte -> critères dynamiques vérifiés. deja = nombre de critères dynamiques existants (numérotation X1, X2…)."""
    echanges = [(question, reponse)]
    decouverte = decouvrir(backend, question, reponse)
    proposes: dict[str, dict] = {}
    for c in decouverte.criteres:
        if not c.nom.strip() or not _citation_presente(c.citation, echanges):  # citation inventée : écartée
            continue
        effet, dim, vals, plafond = _nettoyer(c)
        cid = f"X{deja + len(proposes) + 1}"
        actifs = actifs_concernes(dim, vals)
        proposes[cid] = {"id": cid, "nom": c.nom.strip(), "effet": effet, "type_regle": TYPE_REGLE[effet],
                         "dimension": dim, "colonne": DIMENSIONS[dim]["colonne"] if dim in DIMENSIONS else "", "valeurs": vals,
                         "plafond_pct": plafond, "actifs": actifs, "citation": c.citation.strip(),
                         "concept": c.concept.strip() if dim == A_ETIQUETER else "",
                         "etiquetage": "en_attente" if dim == A_ETIQUETER else "",
                         # Transparence des FNB : exclure ou plafonner un titre concerne aussi les FNB qui le détiennent
                         "fnb_exposes": expositions_fnb(actifs) if effet in ("exclure", "plafonner") else {},
                         "confiance_classificateur": max(0.0, min(1.0, c.confiance)), "justification": c.justification}
    if not proposes:
        return []
    prompt = (f"Critères NOUVEAUX proposés à partir de la réponse à une question ouverte (vérifie que chacun traduit "
              f"fidèlement ce que l'utilisateur a dit, et que la règle n'est ni trop large ni trop étroite) :\n"
              f"{_decrire(proposes)}\n\nConversation :\n{_transcript(echanges)}")
    crit: Critique = _ask(backend, SYSTEM_CRITIQUE, prompt, Critique)
    avis = {a.critere_id: a for a in crit.avis}
    out = []
    for cid, c in proposes.items():
        a = avis.get(cid)
        conf = min(c["confiance_classificateur"], max(0.0, min(1.0, a.confiance)) if a else 0.0)
        if a and a.accord and conf >= seuil:
            statut, motif = "validé", c["justification"]
        elif conf >= SEUIL_PLANCHER:
            statut = "retenu"
            motif = (f"Confiance {conf:.0%} sous le seuil de {seuil:.0%}" if not a or a.accord
                     else f"Réserve du critique : {a.objection}")
        else:
            continue  # trop incertain : on ne crée pas de règle sur une devinette
        out.append({**c, "confiance": round(conf, 2), "statut": statut, "motif": motif, "regle": regle(c),
                    "source": "question ouverte (IA)"})
    return out
