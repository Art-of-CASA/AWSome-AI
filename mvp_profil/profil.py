"""Logique déterministe du profil : conversion des réponses fermées et règles de cohérence.

Aucune IA ici : même réponse, même valeur, pour tout le monde.
"""
from __future__ import annotations

from criteres import CRITERES

# « retenu » : meilleure réponse obtenue après une reformulation, sous le seuil mais au-dessus du plancher de 50 %.
UTILISABLES = ("validé", "retenu")

# ---------- Réponses fermées -> valeurs ----------

def valeur_curseur(item: dict, x: float) -> str:
    for borne, val in item["classes"]:
        if x <= borne:
            return val
    return item["classes"][-1][1]


def niveau_quiz(item: dict, reponses: list[int | None]) -> tuple[str, int]:
    score = sum(1 for q, r in zip(item["questions"], reponses) if r == q["bonne"])
    return item["niveaux"][score], score


def entree(valeurs: list[str], source: str, citation: str = "", confiance: float = 1.0,
           statut: str = "validé", motif: str = "", **extra) -> dict:
    """extra : mesures chiffrées gardées avec la valeur (perte observée au replay, valeur déclarée d'origine…)."""
    return {"valeurs": valeurs, "source": source, "citation": citation, "confiance": round(confiance, 2),
            "statut": statut, "motif": motif, **extra}


# ---------- Règles de cohérence ----------
# Chaque règle repère deux réponses qui se contredisent et propose une question de clarification (QCM).
# Une option applique un « correctif » : {critère: nouvelles valeurs}.
# RÈGLE : un correctif n'écrit jamais une valeur que la personne n'a pas choisie. Soit le texte de l'option énonce
# la valeur (« vers −20 % », « moins de 3 ans », « 5 % au plus »), soit le correctif vaut None : le critère est
# alors REDEMANDÉ (question de précision), au lieu d'être deviné.

def _v(profil: dict, cid: str) -> list[str]:
    e = profil.get(cid)
    return e["valeurs"] if e and e["statut"] in UTILISABLES else []


def incoherences(profil: dict) -> list[dict]:
    out = []
    b1, b1r = _v(profil, "B1"), _v(profil, "B1R")
    if b1 and b1r:
        if b1r[0] == "vendre_tout" and b1[0] in ("30", "40", "50_plus"):
            out.append({"id": "R1", "criteres": ["B1R", "B1"],
                        "texte": f"Vous avez dit que vous vendriez tout après une baisse de 20 %, mais aussi que vous ne vendriez "
                                 f"qu'à partir de −{b1[0].replace('_plus', '')} %. Qu'est-ce qui vous ressemble le plus ?",
                        "options": [("Je vendrais vers −20 %, quand ça commence à baisser", {"B1": ["20"]}),
                                    (f"Je tiendrais jusqu'à −{b1[0].replace('_plus', '')} % environ", {"B1R": ["attendre"]})]})
        if b1r[0] == "acheter_plus" and b1[0] in ("5", "10"):
            out.append({"id": "R1b", "criteres": ["B1R", "B1"],
                        "texte": f"Vous avez dit que vous rachèteriez après une baisse de 20 %, mais aussi que vous vendriez dès −{b1[0]} %. "
                                 "Qu'est-ce qui vous ressemble le plus ?",
                        "options": [(f"Je vendrais dès −{b1[0]} %", {"B1R": ["vendre_tout"]}),
                                    ("Je profiterais de la baisse pour racheter", {"B1": None})]})
    a3, a2 = _v(profil, "A3"), _v(profil, "A2")
    if a3 == ["coussin_securite"] and a2 and a2[0] in ("10_15_ans", "plus_15_ans"):
        out.append({"id": "R2", "criteres": ["A3", "A2"],
                    "texte": "Un coussin de sécurité sert d'habitude à faire face à un imprévu rapidement, mais vous prévoyez "
                             "de garder cet argent plus de 10 ans. Pour vous, il s'agit plutôt :",
                    "options": [("D'une réserve pour les imprévus, dont je pourrais avoir besoin d'ici moins de 3 ans", {"A2": ["moins_3_ans"]}),
                                ("D'une épargne de long terme à faire fructifier", {"A3": ["croissance"]})]})
    d1, d2 = _v(profil, "D1"), _v(profil, "D2")
    if d1 and "crypto" not in d1 and d2 and d2[0] != "0":
        out.append({"id": "R3", "criteres": ["D1", "D2"],
                    "texte": f"Vous n'avez pas coché les cryptoactifs parmi les placements acceptés, mais vous accepteriez "
                             f"d'en détenir jusqu'à {d2[0]} %. Qu'en est-il ?",
                    "options": [("Je ne veux pas de cryptoactifs", {"D2": ["0"]}),
                                ("J'accepte une petite part de cryptoactifs", {"D1": d1 + ["crypto"]})]})
    e1, d5 = _v(profil, "E1"), _v(profil, "D5")
    if e1 and e1[0].startswith("exclure") and "energie_fossile" in d5:
        out.append({"id": "R4", "criteres": ["E1", "D5"],
                    "texte": "Vous souhaitez exclure les énergies fossiles, mais vous avez cité l'énergie fossile parmi vos "
                             "thèmes d'intérêt. Que préférez-vous ?",
                    "options": [("Les exclure", {"D5": [t for t in d5 if t != "energie_fossile"] or ["aucun"]}),
                                ("Elles m'intéressent finalement, je préfère seulement les limiter", {"E1": ["limiter"]})]})
    d12 = _v(profil, "D12")
    if d12 == ["sans_speculatif"] and d2 and d2[0] != "0":
        out.append({"id": "R5", "criteres": ["D12", "D2"],
                    "texte": f"Vous ne voulez pas de placements spéculatifs, mais vous accepteriez jusqu'à {d2[0]} % de "
                             "cryptoactifs, qui en font partie. Que préférez-vous ?",
                    "options": [("Pas de cryptoactifs", {"D2": ["0"]}),
                                ("Une petite part spéculative, limitée à 5 %", {"D12": ["plafonne_5"], "D2": ["5"]})]})
    e5 = _v(profil, "E5")
    commun = sorted(set(e5) & set(d5) - {"aucun", "aucune"})
    if commun:
        out.append({"id": "R7", "criteres": ["E5", "D5"],
                    "texte": f"Vous excluez {', '.join(commun)}, mais vous l'avez aussi cité parmi vos thèmes d'intérêt. Que préférez-vous ?",
                    "options": [("L'exclure", {"D5": [t for t in d5 if t not in commun] or ["aucun"]}),
                                ("Ne pas l'exclure", {"E5": [t for t in e5 if t not in commun] or ["aucune"]})]})
    return out


def signaux_coherence(profil: dict) -> list[dict]:
    """Constats explicatifs sans question, correction ou inférence comportementale.

    Une limite de volatilité et un seuil de vente ne mesurent pas la même chose.
    Accepter du risque n'oblige pas à le rechercher. Enfin, choisir un titre
    médiatisé n'isole pas la cause du choix. Ces observations ne constituent donc
    pas des contradictions démontrées ; elles ne déclenchent aucune relance.
    Les identifiants historiques restent stables pour la traçabilité.
    """
    out = []
    b1, b5, b6 = _v(profil, "B1"), _v(profil, "B5"), _v(profil, "B6")
    if b5 == ["faible_moins_8"] and b1 and b1[0] in ("40", "50_plus"):
        out.append({"id": "R6", "criteres": ["B5", "B1"],
                    "texte": "Préférer de faibles variations annuelles et conserver un placement malgré une forte baisse "
                             "décrivent deux aspects différents du risque. Ces deux réponses sont conservées."})
    if b6 == ["prudent"] and b5 and b5[0] in ("elevee_15_25", "tres_elevee_plus_25"):
        out.append({"id": "R8", "criteres": ["B5", "B6"],
                    "texte": "Vous avez choisi une fourchette prudente tout en acceptant des variations plus fortes. "
                             "Le risque maximal accepté n'est pas un minimum à rechercher ; ces réponses sont compatibles."})
    elif b6 == ["dynamique"] and b5 == ["faible_moins_8"]:
        out.append({"id": "R8", "criteres": ["B5", "B6"],
                    "texte": "Le choix d'une fourchette dynamique ne mesure pas directement la volatilité acceptée. "
                             "Les deux réponses sont conservées et leurs limites devront être vérifiées séparément."})
    if _v(profil, "D8") == ["non"] and _v(profil, "D8O") == ["oui"]:
        out.append({"id": "R9", "criteres": ["D8", "D8O"],
                    "texte": "Le titre choisi est médiatisé. Ce choix peut aussi refléter son secteur ou ses caractéristiques ; "
                             "il ne démontre pas une attirance pour sa popularité. Vos préférences et plafonds restent conservés."})
    return out


# ---------- Déductions certaines (sans IA) : une réponse en entraîne une autre, qu'on ne demande donc plus ----------
# (critère source, valeur(s) qui déclenchent, critère déduit, valeur déduite, raison affichée)
REGLES_DEDUCTION = [
    ("A12", ["retraite"], "A6", ["retraite"], "à la retraite : les revenus sont ceux de la retraite"),
    ("A6", ["retraite"], "A12", ["retraite"], "revenus de retraite : la personne est à la retraite"),
    ("C2", ["aucun"], "B3", ["jamais"], "aucun placement détenu : jamais vécu de baisse de ses placements"),
    ("D1", None, "D2", ["0"], "cryptoactifs non retenus parmi les placements acceptés : 0 % de cryptoactifs"),
]


def deduire(profil: dict) -> list[str]:
    """Applique les déductions certaines aux critères encore inconnus. Renvoie les critères ajoutés."""
    ajoutes = []
    for src, declencheurs, cible, valeurs, raison in REGLES_DEDUCTION:
        v = _v(profil, src)
        if not v or _v(profil, cible) or profil.get(cible, {}).get("statut") == "analyse en cours":
            continue
        if declencheurs is None:  # cas D1 : la règle porte sur l'absence de « crypto » parmi les placements acceptés
            if "crypto" in v:
                continue
        elif not set(v) & set(declencheurs):
            continue
        profil[cible] = entree(valeurs, "déduction (règle)", citation=f"{src} = {', '.join(v)}", motif=raison)
        ajoutes.append(cible)
    return ajoutes


def connu(profil: dict, cid: str) -> bool:
    """Critère déjà renseigné de façon utilisable (validé ou retenu), quelle qu'en soit la source."""
    return profil.get(cid, {}).get("statut") in UTILISABLES


ORDRE_RUPTURE = ["5", "10", "20", "30", "40", "50_plus", "jamais"]
POURCENT_RUPTURE = {"5": 5, "10": 10, "20": 20, "30": 30, "40": 40, "50_plus": 50}


def _ecart(i: int) -> str:
    return "aucun" if i == 0 else "grand" if i >= 2 else "faible"


def recouper_rupture(profil: dict) -> str | None:
    """Compare le point de rupture déclaré (B1) et observé au replay (B2) ; retient le plus prudent.

    - B2 n'est fixé que par « Tout vendre ». Une réduction partielle est un signal (champ « reduction » de B2),
      pas un point de rupture : la question B1 porte sur la baisse à laquelle on vendrait « à coup sûr ».
    - La valeur DÉCLARÉE est conservée dans B1["declare"] : elle n'est jamais perdue.
    - « non_atteint » ne confirme le déclaré que jusqu'à la baisse réellement montrée : au-delà, H1 = non_teste.
    - Peut être rappelée à tout moment (après un correctif de cohérence) : B1 ne dépasse jamais B2.
    Renvoie un message pour l'utilisateur, ou None.
    """
    b1, b2 = _v(profil, "B1"), _v(profil, "B2")
    if not b1 or not b2:
        return None
    e2 = profil["B2"]
    if b2[0] == "non_atteint":
        if b1[0] == "jamais":
            profil["H1"] = entree(["non_teste"], "comparaison",
                                  citation="déclaré : ne jamais vendre ; seuil non atteint dans le replay",
                                  motif="Un replay limité ne peut pas confirmer l'absence de tout seuil de vente.")
            return None
        montree = e2.get("baisse_max_montree")  # en %, None si inconnue
        teste = montree is None or POURCENT_RUPTURE[b1[0]] <= montree
        profil["H1"] = entree(["aucun" if teste else "non_teste"], "comparaison",
                              citation=f"déclaré {b1[0]} %, non atteint" + (f" (baisse montrée : {montree:.0f} %)" if montree else ""),
                              motif="" if teste else f"Le replay n'a montré qu'une baisse de {montree:.0f} % : la tolérance "
                                                     f"déclarée (−{POURCENT_RUPTURE[b1[0]]} %) n'a pas été mise à l'épreuve.")
        return None
    # On compare toujours à la valeur DÉCLARÉE (gardée dans B1["declare"] quand B1 a déjà été ramené à l'observé) :
    # la fonction peut ainsi être rappelée sans effacer l'écart constaté.
    declare = profil["B1"].get("declare", b1[0])
    declaration = "ne jamais vendre" if declare == "jamais" else f"vendre vers −{declare.replace('_plus', '')} %"
    i1, i2 = ORDRE_RUPTURE.index(declare), ORDRE_RUPTURE.index(b2[0])
    profil["H1"] = entree([_ecart(abs(i1 - i2))], "comparaison", citation=f"déclaré : {declaration}, observé {b2[0]} %")
    if i2 >= i1 or b1[0] == b2[0]:  # le déclaré est déjà le plus prudent, ou B1 a déjà été ramené à l'observé
        return None
    perte = e2.get("perte")  # perte réelle au moment de la vente, en %
    observe = f"−{perte:.1f} %".replace(".", ",") if perte is not None else f"−{b2[0]} %"
    profil["B1"] = entree([b2[0]], "replay (plus prudent que le déclaré)", citation=e2["citation"],
                          motif=f"Déclaré : {declaration} ; observé : tout vendu à {observe}", declare=declare)
    return (f"Vous aviez indiqué {declaration}, mais dans la simulation vous avez tout vendu "
            f"à {observe}. L'outil retient le plus prudent : la classe « −{b2[0]} % ».")


def appliquer_correctif(profil: dict, correctif: dict, texte_option: str) -> list[str]:
    """Applique le choix fait à une question de cohérence. Renvoie les critères À REDEMANDER (correctif None).

    Après tout correctif, la règle « le plus prudent l'emporte » est réappliquée : une déclaration ne peut pas
    remonter le point de rupture au-dessus de ce qui a été observé au replay.
    """
    a_redemander = []
    for cid, vals in correctif.items():
        if vals is None:
            profil[cid] = entree([], "cohérence", citation=texte_option, confiance=0.0, statut="à préciser",
                                 motif="Réponses contradictoires : valeur à redemander plutôt qu'à deviner")
            a_redemander.append(cid)
            continue
        valides = [v for v in vals if v in CRITERES[cid]["valeurs"]]
        profil[cid] = entree(valides, "cohérence", citation=texte_option)
    recouper_rupture(profil)
    return a_redemander
