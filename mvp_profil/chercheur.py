"""Agent CHERCHEUR : relie aux actifs un critère dynamique que le vocabulaire des actifs ne sait pas exprimer.

Exemple : « je ne veux rien qui touche à Elon Musk ». Aucune colonne de asset_criteria.csv ne dit quels actifs
« touchent à Elon Musk ». Le découvreur (criteres_dynamiques.py) crée alors le critère avec un CONCEPT à
rechercher, et ce module :
  1. donne à un agent Claude Haiku 5.5 le tableau des 66 actifs et des OUTILS pour chercher :
       chercher_dans_donnees  nos fichiers : noms, secteurs, thèmes, controverses, actualités, positions des FNB
       fiche_actif            la fiche complète d'un actif (dont ses actualités et, pour un FNB, ses positions)
       recherche_web          recherche Wikipédia (fr ou en)
       lire_page_web          texte d'une page Wikipédia
     L'agent rend « oui », « partiel » ou « non_concerne », avec une PREUVE : un passage recopié d'un résultat
     d'outil et l'identifiant de ce résultat. Un actif sans conclusion étayée reste « inconnu ».
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
import hashlib
import json
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from agents import SYSTEM_CRITIQUE, AgentError, Backend, Critique, _ask, _norm, appeler

DONNEES = json.loads(Path(__file__).with_name("donnees_chercheur.json").read_text(encoding="utf-8"))
ACTIFS: dict[str, dict] = DONNEES["actifs"]
FNB: dict[str, list[dict]] = DONNEES["fnb"]
MAX_ETAPES = 5                 # allers-retours d'outils au plus, puis réponse obligatoire
MOTS_MIN_PREUVE = 3            # une preuve d'un ou deux mots n'explique rien
SEUIL_PREUVE = 0.80           # accord ET confiance des deux agents, y compris pour un verdict négatif
VERSION_CACHE = 2            # les anciennes absences de verdict ne valent pas un « non » vérifié
DUREE_CACHE_JOURS = 7         # hypothèse de fraîcheur ; un changement des données invalide immédiatement
WIKI_LANGUES = ("fr", "en")
USER_AGENT = "AlphaForge-datathon/1.0 (prototype etudiant de recherche de faits publics)"
CACHE = Path(os.environ.get("ALPHAFORGE_CACHE", Path(__file__).with_name("cache"))) / "mots_cles_dynamiques.json"
_verrou = threading.Lock()


# ---------- Sortie imposée ----------
class Verdict(BaseModel):
    ticker: str
    valeur: Literal["oui", "partiel", "non_concerne"]
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
            "properties": {"ticker": {"type": "string"}, "valeur": {"type": "string", "enum": ["oui", "partiel", "non_concerne"]},
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
- non_concerne : une source explicite et suffisamment complète établit que l'actif ne relève pas du concept.
  L'absence d'un mot dans une fiche, une recherche sans résultat ou des positions partielles d'un FNB ne sont JAMAIS
  des preuves de non-implication. Une activité principale différente ne prouve pas l'absence d'activité secondaire.
- Un actif non étudié, une preuve insuffisante ou une information manquante ne donnent aucun verdict : il reste INCONNU.
  Ne cherche pas à remplir toute la liste à tout prix et ne transforme jamais « non trouvé » en « non concerné ».
Méthode : commence par le tableau fourni et par chercher_dans_donnees ; utilise recherche_web puis lire_page_web pour
vérifier un lien que nos données ne montrent pas. Quelques appels suffisent ; n'en fais pas plus que nécessaire.
Chaque verdict doit avoir une PREUVE : un passage recopié MOT POUR MOT d'un résultat d'outil (au moins quelques mots, sans
paraphrase), et la source exacte indiquée par [source: …] devant ce résultat (par exemple fiche:TSLA ou web:fr:Elon Musk, sans
crochets). Le code vérifie : une preuve introuvable est écartée. Préfère un passage qui DÉCRIT le lien (une phrase d'une page
ou d'une actualité) ; si seul un titre d'actualité ou un thème le montre, lis la page Wikipédia de l'entreprise pour confirmer.
Ne recherche que des entreprises, des personnes publiques ou des notions ; n'envoie jamais d'information sur l'utilisateur.
confiance : entre 0 et 1. Si tu n'as aucune conclusion étayée, renvoie une liste de verdicts vide. Le code signalera
alors une recherche non concluante, pas une absence d'exposition."""


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
                extraits = [l for l in texte.split("\n") if any(k in _norm(l) for k in cles)]
                lu = "\n".join(extraits[:4])
                # Le journal contient uniquement ce qui est réellement renvoyé à l'agent, pas la fiche entière.
                # Les passages déjà lus restent disponibles lorsqu'une autre recherche vise le même actif.
                source = f"fiche:{tk}"
                deja = self.journal.get(source, "")
                self.journal[source] = deja + ("\n" if deja and lu not in deja else "") + (lu if lu not in deja else "")
                trouves.append(f"[source: {source}]\n{lu}")
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
        lu = json.loads(CACHE.read_text(encoding="utf-8"))
        return lu if isinstance(lu, dict) else {}
    except (OSError, ValueError):
        return {}


def _empreinte(concept: str, effet: str, modele: str) -> str:
    """Identité complète : aucune collision de concepts au-delà des 40 caractères du libellé lisible.

    L'univers, les positions, le modèle et les consignes font partie de la clé. Un résultat qualifie une
    version des données, jamais tous les futurs états du même concept.
    """
    contenu = {
        "version": VERSION_CACHE,
        "concept": " ".join(unicodedata.normalize("NFKC", concept).casefold().split()),
        "effet": effet, "modele": modele,
        "donnees": DONNEES, "actifs": ACTIFS, "fnb": FNB,
        "consignes": [SYSTEM_CHERCHEUR, SYSTEM_CRITIQUE], "schema": SCHEMA, "outils": OUTILS,
        "seuil_preuve": SEUIL_PREUVE, "max_etapes": MAX_ETAPES,
    }
    return hashlib.sha256(json.dumps(contenu, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _cache_valide(resultat: dict | None, empreinte: str) -> bool:
    if not isinstance(resultat, dict) or resultat.get("version_cache") != VERSION_CACHE:
        return False
    if resultat.get("empreinte") != empreinte or not isinstance(resultat.get("etats_actifs"), dict):
        return False
    try:
        expiration = datetime.fromisoformat(resultat["expire_le"])
        return expiration.tzinfo is not None and datetime.now(timezone.utc) < expiration
    except (KeyError, TypeError, ValueError):
        return False


def _couverture(verdicts: list[dict], fnb_exposes: dict[str, float]) -> tuple[dict, dict[str, str]]:
    """État explicite de chaque actif. Une exposition FNB calculée est un minimum connu, pas un audit complet."""
    etats = {tk: "inconnu" for tk in ACTIFS}
    for v in verdicts:
        if v["valeur"] == "oui" or etats[v["ticker"]] != "oui":
            etats[v["ticker"]] = v["valeur"]
    for tk in fnb_exposes:
        if tk in etats and etats[tk] != "oui":
            etats[tk] = "partiel"
    qualifies = sum(etat != "inconnu" for etat in etats.values())
    verifies = len({v["ticker"] for v in verdicts})
    couverture = {
        "total": len(ACTIFS), "avec_verdict": verifies,
        "avec_exposition_fnb_calculee": len(fnb_exposes), "inconnus": len(ACTIFS) - qualifies,
        "pct_verifie": round(100 * verifies / max(1, len(ACTIFS)), 1),
        "fnb_positions_partielles": sorted(FNB),
        "limite": "Recherche bornée aux sources lues ; positions principales des FNB seulement. "
                  "Un actif inconnu n'est ni innocenté ni déclaré concerné.",
    }
    return couverture, etats


def etiqueter(backend: Backend, concept: str, effet: str = "exclure") -> dict:
    """Concept -> mot-clé d'actif avec preuves et couverture. Le cache respecte version, données et fraîcheur."""
    empreinte = _empreinte(concept, effet, backend.model)
    cle = f"kw_dyn_{slug(concept)}_{empreinte[:12]}"
    with _verrou:
        deja = _lire_cache().get(cle)
    if _cache_valide(deja, empreinte):
        return {**deja, "depuis_cache": True}
    t0 = time.time()
    rech = Recherche()
    etiq = _boucle(backend, concept, effet, rech)

    retenus, rejetes = [], []
    for v in etiq.verdicts:
        motif = _preuve_valide(v, rech.journal)
        if not motif and not (SEUIL_PREUVE <= v.confiance <= 1):
            motif = f"confiance du chercheur sous le seuil de {SEUIL_PREUVE:.0%} ou invalide"
        (rejetes.append({**v.model_dump(), "motif": motif}) if motif else retenus.append(v))
    if retenus:  # le critique vérifie que chaque preuve justifie le verdict
        prompt = (f"Concept : {concept}\nDéfinition retenue : {etiq.definition}\n"
                  "Pour chaque actif, la preuve (passage d'une source lue par le chercheur) justifie-t-elle le verdict ? "
                  "Ici, la « citation » est ce passage de source. critere_id = le ticker. Un thème de nos fiches qui nomme "
                  "exactement le concept (par exemple « reseaux_sociaux » pour les réseaux sociaux) est une preuve suffisante : "
                  "ces thèmes sont établis par l'équipe à partir des activités de l'entreprise.\n"
                  "IMPORTANT : non_concerne exige une preuve explicite qui écarte le concept. Une recherche sans résultat, "
                  "une fiche qui ne mentionne pas le concept, une activité principale différente ou une liste partielle de "
                  "positions FNB ne prouvent pas l'absence d'exposition : refuse ces verdicts négatifs. Ne complète aucune "
                  "information absente. Une confiance sous le seuil ne suffit pas, même si accord=true.\n"
                  + "\n".join(f"- {v.ticker} ({ACTIFS[v.ticker]['nom']}) : {v.valeur}. Preuve « {v.preuve} » "
                              f"[{v.source}]" for v in retenus))
        crit: Critique = _ask(backend, SYSTEM_CRITIQUE, prompt, Critique)
        avis = {a.critere_id: a for a in crit.avis}
        gardes = []
        for v in retenus:
            a = avis.get(v.ticker)
            if a and a.accord and SEUIL_PREUVE <= a.confiance <= 1:
                gardes.append({**v.model_dump(), "confiance": round(min(v.confiance, a.confiance), 2),
                               "url": rech.urls.get(v.source, "")})
            else:
                motif = (a.objection if a and not a.accord else
                         f"confiance sous le seuil de {SEUIL_PREUVE:.0%} ou invalide" if a else "pas d avis")
                rejetes.append({**v.model_dump(), "motif": f"critique : {motif}"})
        retenus = gardes
    # Deux preuves acceptées mais contradictoires ne permettent aucune conclusion automatique.
    contradictions = {v["ticker"] for v in retenus if v["valeur"] == "non_concerne"} & {
        v["ticker"] for v in retenus if v["valeur"] in ("oui", "partiel")}
    if contradictions:
        rejetes.extend({**v, "motif": "preuves contradictoires pour le même actif"}
                       for v in retenus if v["ticker"] in contradictions)
        retenus = [v for v in retenus if v["ticker"] not in contradictions]
    oui = sorted({v["ticker"] for v in retenus if v["valeur"] == "oui"})
    partiels = sorted({v["ticker"] for v in retenus if v["valeur"] == "partiel"} - set(oui))
    fnb_exposes = expositions_fnb(oui + partiels)
    # Les positions connues d'un fonds peuvent contredire une affirmation négative ; cette preuve est écartée.
    negatifs_fnb = [v for v in retenus if v["valeur"] == "non_concerne" and v["ticker"] in fnb_exposes]
    rejetes.extend({**v, "motif": "exposition identifiée dans les positions connues du FNB"} for v in negatifs_fnb)
    retenus = [v for v in retenus if v not in negatifs_fnb]
    couverture, etats = _couverture(retenus, fnb_exposes)
    maintenant = datetime.now(timezone.utc)
    resultat = {
        "mot_cle": cle, "concept": concept, "definition": etiq.definition, "oui": oui, "partiel": partiels,
        "non_concernes": sorted(tk for tk, etat in etats.items() if etat == "non_concerne"),
        "inconnus": sorted(tk for tk, etat in etats.items() if etat == "inconnu"),
        "etats_actifs": etats, "couverture": couverture,
        "fnb_exposes": fnb_exposes, "verdicts": retenus, "rejetes": rejetes,
        "appels_outils": rech.appels, "cree_le": maintenant.isoformat(timespec="seconds"),
        "expire_le": (maintenant + timedelta(days=DUREE_CACHE_JOURS)).isoformat(timespec="seconds"),
        "version_cache": VERSION_CACHE, "empreinte": empreinte,
        "modele": backend.model, "duree_s": round(time.time() - t0, 1),
    }
    with _verrou:
        cache = _lire_cache()
        cache[cle] = resultat
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    return {**resultat, "depuis_cache": False}
