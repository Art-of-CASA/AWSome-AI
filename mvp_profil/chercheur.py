"""Agent CHERCHEUR : relie aux actifs un critère dynamique que le vocabulaire des actifs ne sait pas exprimer.

Exemple : « je ne veux rien qui touche à Elon Musk ». Aucune colonne de asset_criteria.csv ne dit quels actifs
« touchent à Elon Musk ». Le découvreur (criteres_dynamiques.py) crée alors le critère avec un CONCEPT à
rechercher, et ce module :
  1. donne à un agent Claude Haiku 5.5 le tableau des 66 actifs et des OUTILS pour chercher :
       chercher_dans_donnees  nos fichiers : noms, secteurs, thèmes, controverses, actualités, positions des FNB
       fiche_actif            la fiche complète d'un actif (dont ses actualités et, pour un FNB, ses positions)
       recherche_web          recherche Wikipédia (fr ou en)
       lire_page_web          texte d'une page Wikipédia
     L'agent rend, pour chaque actif concerné, « oui » ou « partiel », avec une PREUVE : un passage recopié d'un
     résultat d'outil et l'identifiant de ce résultat.
  2. CONTRÔLE par le code : le ticker existe, la source a vraiment été lue pendant la recherche, et le passage
     s'y trouve mot pour mot (même principe que la citation exacte de l'utilisateur). Sinon le verdict est écarté.
  3. CRITIQUE : l'agent critique vérifie que chaque preuve justifie le verdict ; un désaccord écarte le verdict.
  4. FNB, par le code : un FNB qui détient un actif « oui » parmi ses principales positions devient « partiel »,
     avec le poids de cette position (exemple : SPY détient TSLA à 2 %).
  5. Le résultat devient un nouveau MOT-CLÉ (kw_dyn_<concept>), enregistré avec ses preuves, ses sources et sa
     date dans un cache (mots_cles_dynamiques.json). Le même concept, demandé par un autre utilisateur, est
     repris du cache sans nouvelle recherche : le vocabulaire s'enrichit avec l'usage et reste reproductible.

Recherche web : l'outil web_search intégré d'Anthropic n'est pas offert sur Amazon Bedrock ; la recherche est
donc un outil à nous, limité à Wikipédia (fr, en). Seul le concept est envoyé (« Elon Musk »), jamais une
information sur l'utilisateur.
"""
from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from agents import SYSTEM_CRITIQUE, AgentError, Backend, Critique, _ask, _norm, appeler

DONNEES = json.loads(Path(__file__).with_name("donnees_chercheur.json").read_text(encoding="utf-8"))
ACTIFS: dict[str, dict] = DONNEES["actifs"]
FNB: dict[str, list[dict]] = DONNEES["fnb"]
MAX_ETAPES = 5                 # allers-retours d'outils au plus, puis réponse obligatoire
MOTS_MIN_PREUVE = 3            # une preuve d'un ou deux mots n'explique rien
WIKI_LANGUES = ("fr", "en")
USER_AGENT = "AlphaForge-datathon/1.0 (prototype etudiant de recherche de faits publics)"
CACHE = Path(os.environ.get("ALPHAFORGE_CACHE", Path(__file__).with_name("cache"))) / "mots_cles_dynamiques.json"
_verrou = threading.Lock()


# ---------- Sortie imposée ----------
class Verdict(BaseModel):
    ticker: str
    valeur: Literal["oui", "partiel"]
    preuve: str          # passage recopié mot pour mot d'un résultat d'outil
    source: str          # identifiant [source: …] de ce résultat
    confiance: float


class Etiquetage(BaseModel):
    definition: str      # ce que veut dire « concerné » pour ce concept, en une phrase
    verdicts: list[Verdict]


SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["definition", "verdicts"],
    "properties": {
        "definition": {"type": "string"},
        "verdicts": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["ticker", "valeur", "preuve", "source", "confiance"],
            "properties": {"ticker": {"type": "string"}, "valeur": {"type": "string", "enum": ["oui", "partiel"]},
                           "preuve": {"type": "string"}, "source": {"type": "string"},
                           "confiance": {"type": "number"}}}},
    },
}


def _outil(nom, description, proprietes):
    return {"name": nom, "description": description, "strict": True,
            "input_schema": {"type": "object", "properties": proprietes, "required": list(proprietes),
                             "additionalProperties": False}}


LANGUE = {"type": "string", "enum": list(WIKI_LANGUES)}
OUTILS = [
    _outil("chercher_dans_donnees", "Cherche des mots dans nos données sur les 66 actifs : noms, secteurs, thèmes, "
           "controverses, titres d'actualité récents, positions des FNB. Renvoie les actifs où ils apparaissent.",
           {"mots": {"type": "string", "description": "un ou quelques mots, par exemple « Musk »"}}),
    _outil("fiche_actif", "Fiche complète d'un actif de l'univers : description, thèmes, controverses, actualités "
           "récentes et, pour un FNB, principales positions.", {"ticker": {"type": "string"}}),
    _outil("recherche_web", "Recherche sur Wikipédia. Renvoie les titres et extraits des pages trouvées.",
           {"requete": {"type": "string"}, "langue": LANGUE}),
    _outil("lire_page_web", "Texte d'une page Wikipédia (titre exact, tel que renvoyé par recherche_web).",
           {"titre": {"type": "string"}, "langue": LANGUE}),
]

SYSTEM_CHERCHEUR = """Tu es l'agent CHERCHEUR d'un outil de profil d'investisseur (simulation éducative, aucun conseil financier).
Un utilisateur a exprimé une préférence qui porte sur un CONCEPT (par exemple « entreprises liées à Elon Musk »).
Ta tâche : trouver, parmi les 66 actifs de l'univers (et seulement eux), ceux que ce concept concerne, preuves à l'appui.
- oui : l'actif est directement concerné (l'entreprise elle-même, ou une activité principale de l'entreprise).
- partiel : l'actif est concerné en partie seulement (activité secondaire, participation, filiale).
  Ne t'occupe pas des FNB qui détiennent un actif concerné : le code les calcule à partir de leurs positions.
- N'inscris pas les actifs non concernés : l'absence de verdict veut dire « non ».
Méthode : commence par le tableau fourni et par chercher_dans_donnees ; utilise recherche_web puis lire_page_web pour
vérifier un lien que nos données ne montrent pas. Quelques appels suffisent ; n'en fais pas plus que nécessaire.
Chaque verdict doit avoir une PREUVE : un passage recopié MOT POUR MOT d'un résultat d'outil (au moins quelques mots, sans
paraphrase), et la source exacte indiquée par [source: …] devant ce résultat (par exemple fiche:TSLA ou web:fr:Elon Musk, sans
crochets). Le code vérifie : une preuve introuvable est écartée. Préfère un passage qui DÉCRIT le lien (une phrase d'une page
ou d'une actualité) ; si seul un titre d'actualité ou un thème le montre, lis la page Wikipédia de l'entreprise pour confirmer.
Ne recherche que des entreprises, des personnes publiques ou des notions ; n'envoie jamais d'information sur l'utilisateur.
confiance : entre 0 et 1. Si rien ne relie le concept à un actif, renvoie une liste de verdicts vide."""


# ---------- Outils ----------
def _fiche(tk: str) -> str:
    a = ACTIFS[tk]
    lignes = [f"{tk} : {a['nom']} ; classe {a['classe']} ; secteur {a['secteur']} ; pays {a['pays']} ; "
              f"région {a['region']} ; devise {a['devise']} ; thèmes {a['themes'] or '-'} ; "
              f"exclusions détectées {a['exclusions'] or '-'} ; implication fossile {a['fossile'] or '-'} ; "
              f"controverses {a['controverses'] or '-'}"]
    for c in DONNEES["controverses"].get(tk, []):
        lignes.append(f"Controverse ({c['date']}) {c['sujet']} : {c['resume']} (source : {c['source']})")
    for n in DONNEES["actualites"].get(tk, []):
        lignes.append(f"Actualité ({n['date']}) : {n['titre']}")
    for p in FNB.get(tk, []):
        lignes.append(f"Position du FNB : {p['nom']} ({p['symbole']}) {p['poids']:.1%}")
    return "\n".join(lignes)


def _tableau() -> str:
    return "\n".join(f"{tk} | {a['nom']} | {a['classe']} | {a['secteur']} | {a['pays']} | {a['themes']}"
                     for tk, a in ACTIFS.items())


def _http_get(url: str, params: dict) -> dict:
    """GET JSON (remplacé dans les tests). Seul Wikipédia est appelé."""
    import httpx2 as httpx
    r = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _sans_balises(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s))


class Recherche:
    """Exécute les outils et garde un JOURNAL {source: texte lu}, qui sert à vérifier les preuves."""

    def __init__(self):
        self.journal: dict[str, str] = {"tableau": _tableau()}
        self.urls: dict[str, str] = {}
        self.appels: list[dict] = []

    def executer(self, nom: str, entree: dict) -> str:
        self.appels.append({"outil": nom, "entree": entree})
        try:
            return getattr(self, nom)(**entree)
        except AgentError:
            raise
        except Exception as e:  # noqa: BLE001  (une page absente ou le réseau ne doivent pas arrêter la recherche)
            return f"Erreur de l'outil : {e}"

    def chercher_dans_donnees(self, mots: str) -> str:
        cles = [_norm(m) for m in mots.split() if len(m) > 2] or [_norm(mots)]
        trouves = []
        for tk in ACTIFS:
            texte = _fiche(tk)
            n = _norm(texte)
            if all(k in n for k in cles):
                self.journal[f"fiche:{tk}"] = texte
                extraits = [l for l in texte.split("\n") if any(k in _norm(l) for k in cles)]
                trouves.append(f"[source: fiche:{tk}]\n" + "\n".join(extraits[:4]))
        return "\n\n".join(trouves) if trouves else f"Aucun actif ne mentionne « {mots} » dans nos données."

    def fiche_actif(self, ticker: str) -> str:
        tk = next((t for t in ACTIFS if t.lower() == ticker.strip().lower()), None)
        if tk is None:
            return f"Ticker inconnu : {ticker}. Les tickers valides sont ceux du tableau."
        self.journal[f"fiche:{tk}"] = _fiche(tk)
        return f"[source: fiche:{tk}]\n{self.journal[f'fiche:{tk}']}"

    def recherche_web(self, requete: str, langue: str) -> str:
        d = _http_get(f"https://{langue}.wikipedia.org/w/api.php",
                      {"action": "query", "list": "search", "srsearch": requete, "srlimit": 5, "format": "json"})
        res = d.get("query", {}).get("search", [])
        if not res:
            return f"Aucun résultat pour « {requete} »."
        src = f"web:{langue}:recherche:{requete}"
        self.journal[src] = "\n".join(f"{r['title']} : {_sans_balises(r.get('snippet', ''))}" for r in res)
        self.urls[src] = f"https://{langue}.wikipedia.org/w/index.php?search={requete}"
        return f"[source: {src}]\n{self.journal[src]}"

    def lire_page_web(self, titre: str, langue: str) -> str:
        d = _http_get(f"https://{langue}.wikipedia.org/w/api.php",
                      {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": titre,
                       "format": "json"})
        pages = list(d.get("query", {}).get("pages", {}).values())
        if not pages or "extract" not in pages[0]:
            return f"Page introuvable : {titre}."
        vrai_titre = pages[0].get("title", titre)
        src = f"web:{langue}:{vrai_titre}"
        self.journal[src] = pages[0]["extract"][:8000]
        self.urls[src] = f"https://{langue}.wikipedia.org/wiki/{vrai_titre.replace(' ', '_')}"
        return f"[source: {src}]\n{self.journal[src]}"


# ---------- Boucle de l'agent ----------
def _boucle(backend: Backend, concept: str, effet: str, rech: Recherche) -> Etiquetage:
    messages = [{"role": "user", "content":
                 f"Concept : {concept}\nCe que l'utilisateur veut en faire : {effet}\n\n"
                 f"[source: tableau] Les 66 actifs (ticker | nom | classe | secteur | pays | thèmes) :\n{rech.journal['tableau']}"}]
    for etape in range(MAX_ETAPES + 1):
        resp = appeler(backend, backend.client.messages.create,
                       model=backend.model, max_tokens=4000, system=SYSTEM_CHERCHEUR, messages=messages,
                       tools=OUTILS, tool_choice={"type": "auto" if etape < MAX_ETAPES else "none"},
                       output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}})
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": b.id, "content": rech.executer(b.name, b.input)}
                for b in resp.content if b.type == "tool_use"]})
            continue
        texte = next((b.text for b in resp.content if b.type == "text"), "")
        try:
            return Etiquetage.model_validate_json(texte)
        except ValueError as e:
            raise AgentError("Réponse du chercheur illisible.") from e
    raise AgentError("Le chercheur n'a pas conclu.")


def _preuve_valide(v: Verdict, journal: dict[str, str]) -> str:
    """'' si la preuve est vérifiée, sinon le motif du rejet. Corrige v.source si le passage vient d'une autre source lue
    (le modèle recopie parfois mal l'identifiant) : seul compte que le passage ait vraiment été lu, mot pour mot."""
    if v.ticker not in ACTIFS:
        return "ticker hors univers"
    p = _norm(v.preuve)
    if len(p.split()) < MOTS_MIN_PREUVE:
        return "preuve trop courte"
    source = re.sub(r"^\[?\s*source\s*:\s*|\]$", "", v.source.strip()).strip()
    lues = [source] + [s for s in journal if s != source] if source in journal else list(journal)
    for s in lues:
        if f" {p} " in f" {_norm(journal[s])} ":
            v.source = s
            return ""
    return "passage introuvable dans les sources lues" if journal else "source jamais lue pendant la recherche"


def expositions_fnb(tickers: list[str]) -> dict[str, float]:
    """FNB qui détiennent ces actifs parmi leurs principales positions -> poids total (0 à 1)."""
    out = {}
    for etf, positions in FNB.items():
        poids = sum(p["poids"] for p in positions if p["ticker"] in tickers)
        if poids > 0 and etf not in tickers:
            out[etf] = round(poids, 6)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def slug(concept: str) -> str:
    s = unicodedata.normalize("NFKD", concept).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:40] or "concept"


def _lire_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def etiqueter(backend: Backend, concept: str, effet: str = "exclure") -> dict:
    """Concept -> nouveau mot-clé d'actif kw_dyn_<concept>, avec preuves vérifiées. Repris du cache s'il existe."""
    cle = f"kw_dyn_{slug(concept)}"
    with _verrou:
        deja = _lire_cache().get(cle)
    if deja:
        return {**deja, "depuis_cache": True}
    t0 = time.time()
    rech = Recherche()
    etiq = _boucle(backend, concept, effet, rech)

    retenus, rejetes = [], []
    for v in etiq.verdicts:
        motif = _preuve_valide(v, rech.journal)
        (rejetes.append({**v.model_dump(), "motif": motif}) if motif else retenus.append(v))
    if retenus:  # le critique vérifie que chaque preuve justifie le verdict
        prompt = (f"Concept : {concept}\nDéfinition retenue : {etiq.definition}\n"
                  "Pour chaque actif, la preuve (passage d'une source lue par le chercheur) justifie-t-elle le verdict ? "
                  "Ici, la « citation » est ce passage de source. critere_id = le ticker. Un thème de nos fiches qui nomme "
                  "exactement le concept (par exemple « reseaux_sociaux » pour les réseaux sociaux) est une preuve suffisante : "
                  "ces thèmes sont établis par l'équipe à partir des activités de l'entreprise.\n"
                  + "\n".join(f"- {v.ticker} ({ACTIFS[v.ticker]['nom']}) : {v.valeur}. Preuve « {v.preuve} » "
                              f"[{v.source}]" for v in retenus))
        crit: Critique = _ask(backend, SYSTEM_CRITIQUE, prompt, Critique)
        avis = {a.critere_id: a for a in crit.avis}
        gardes = []
        for v in retenus:
            a = avis.get(v.ticker)
            if a and a.accord:
                gardes.append({**v.model_dump(), "confiance": round(min(v.confiance, a.confiance), 2),
                               "url": rech.urls.get(v.source, "")})
            else:
                rejetes.append({**v.model_dump(), "motif": f"critique : {a.objection if a else 'pas d avis'}"})
        retenus = gardes
    oui = sorted({v["ticker"] for v in retenus if v["valeur"] == "oui"})
    partiels = sorted({v["ticker"] for v in retenus if v["valeur"] == "partiel"} - set(oui))
    resultat = {
        "mot_cle": cle, "concept": concept, "definition": etiq.definition, "oui": oui, "partiel": partiels,
        "fnb_exposes": expositions_fnb(oui + partiels), "verdicts": retenus, "rejetes": rejetes,
        "appels_outils": rech.appels, "cree_le": datetime.now().isoformat(timespec="seconds"),
        "modele": backend.model, "duree_s": round(time.time() - t0, 1),
    }
    with _verrou:
        cache = _lire_cache()
        cache[cle] = resultat
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**resultat, "depuis_cache": False}
