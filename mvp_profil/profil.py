"""Logique déterministe du profil : conversion des réponses fermées et règles de cohérence.

Aucune IA ici : même réponse, même valeur, pour tout le monde.
"""
from __future__ import annotations

from criteres import CRITERES

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
           statut: str = "validé", motif: str = "") -> dict:
    return {"valeurs": valeurs, "source": source, "citation": citation, "confiance": round(confiance, 2),
            "statut": statut, "motif": motif}


# ---------- Règles de cohérence ----------
# Chaque règle repère deux réponses qui se contredisent et propose une question de clarification (QCM).
# Une option applique un « correctif » : {critère: nouvelles valeurs}.

def _v(profil: dict, cid: str) -> list[str]:
    e = profil.get(cid)
    return e["valeurs"] if e and e["statut"] == "validé" else []


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
                                    ("Je profiterais de la baisse pour racheter", {"B1": ["30"]})]})
    a3, a2 = _v(profil, "A3"), _v(profil, "A2")
    if a3 == ["coussin_securite"] and a2 and a2[0] in ("10_15_ans", "plus_15_ans"):
        out.append({"id": "R2", "criteres": ["A3", "A2"],
                    "texte": "Un coussin de sécurité sert d'habitude à faire face à un imprévu rapidement, mais vous prévoyez "
                             "de garder cet argent plus de 10 ans. Pour vous, il s'agit plutôt :",
                    "options": [("D'une réserve pour les imprévus, disponible rapidement", {"A2": ["moins_3_ans"]}),
                                ("D'une épargne de long terme à faire fructifier", {"A3": ["croissance"]})]})
    d1, d2 = _v(profil, "D1"), _v(profil, "D2")
    if "D1" in profil and "crypto" not in d1 and d2 and d2[0] != "0":
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
    b5 = _v(profil, "B5")
    if b5 == ["faible_moins_8"] and b1 and b1[0] in ("40", "50_plus"):
        out.append({"id": "R6", "criteres": ["B5", "B1"],
                    "texte": "Vous préférez des placements qui varient peu (moins de 8 % par an), mais vous ne vendriez qu'après "
                             "une baisse de 40 % ou plus. Qu'est-ce qui vous ressemble le plus ?",
                    "options": [("Je supporte mal les variations : je vendrais bien avant −40 %", {"B1": ["10"]}),
                                ("Les variations ne m'inquiètent pas tant que je ne vends pas", {"B5": ["moderee_8_15"]})]})
    e5 = _v(profil, "E5")
    commun = sorted(set(e5) & set(d5) - {"aucun", "aucune"})
    if commun:
        out.append({"id": "R7", "criteres": ["E5", "D5"],
                    "texte": f"Vous excluez {', '.join(commun)}, mais vous l'avez aussi cité parmi vos thèmes d'intérêt. Que préférez-vous ?",
                    "options": [("L'exclure", {"D5": [t for t in d5 if t not in commun] or ["aucun"]}),
                                ("Ne pas l'exclure", {"E5": [t for t in e5 if t not in commun] or ["aucune"]})]})
    b6, d8, d8o = _v(profil, "B6"), _v(profil, "D8"), _v(profil, "D8O")
    if b6 and b5 and ((b6[0] == "prudent" and b5[0] in ("elevee_15_25", "tres_elevee_plus_25"))
                      or (b6[0] == "dynamique" and b5[0] == "faible_moins_8")):
        out.append({"id": "R8", "criteres": ["B5", "B6"],
                    "texte": "Dans les fourchettes, vous avez choisi un portefeuille "
                             + ("prudent, alors que vous acceptiez de fortes variations." if b6[0] == "prudent"
                                else "dynamique, alors que vous préfériez des variations faibles.")
                             + " Qu'est-ce qui vous ressemble le plus ?",
                    "options": [("Des variations faibles à modérées", {"B5": ["moderee_8_15"] if b6[0] == "prudent" else ["faible_moins_8"], "B6": ["prudent"]}),
                                ("Des variations plus fortes, pour un meilleur rendement espéré", {"B5": ["elevee_15_25"], "B6": ["dynamique"]})]})
    if d8 == ["non"] and d8o == ["oui"]:
        out.append({"id": "R9", "criteres": ["D8", "D8O"],
                    "texte": "Vous aviez dit ne pas être tenté par les titres dont tout le monde parle, mais dans la mise en "
                             "situation vous avez choisi un titre très médiatisé, aux variations fortes. Qu'en pensez-vous ?",
                    "options": [("J'ai été tenté : je préfère que l'outil limite ce type de titre", {"D8": ["parfois"], "D12": ["plafonne_5"]}),
                                ("C'était un choix réfléchi, je l'assume", {"D8": ["oui"]})]})
    return out


ORDRE_RUPTURE = ["5", "10", "20", "30", "40", "50_plus"]


def recouper_rupture(profil: dict) -> str | None:
    """Compare le point de rupture déclaré (B1) et observé au replay (B2) ; retient le plus prudent.

    Renvoie un message pour l'utilisateur, ou None. Écart d'au moins 2 classes = « grand » (profil incertain sur ce point).
    """
    b1, b2 = _v(profil, "B1"), _v(profil, "B2")
    if not b1 or not b2:
        return None
    if b2[0] == "non_atteint" or ORDRE_RUPTURE.index(b2[0]) >= ORDRE_RUPTURE.index(b1[0]):
        ecart = "aucun" if b2[0] == "non_atteint" or b2[0] == b1[0] else "faible"
        profil["H1"] = entree([ecart], "comparaison", citation=f"déclaré {b1[0]} %, observé {b2[0]}")
        return None
    ecart = ORDRE_RUPTURE.index(b1[0]) - ORDRE_RUPTURE.index(b2[0])
    profil["H1"] = entree(["grand" if ecart >= 2 else "faible"], "comparaison", citation=f"déclaré {b1[0]} %, observé {b2[0]} %")
    profil["B1"] = entree([b2[0]], "replay (plus prudent que le déclaré)", citation=profil["B2"]["citation"],
                          motif=f"Déclaré : vendre vers −{b1[0]} % ; observé : réduction vers −{b2[0]} %")
    return (f"Vous aviez indiqué vendre vers −{b1[0].replace('_plus', '')} %, mais dans la simulation vous avez réduit "
            f"vers −{b2[0]} %. L'outil retient le plus prudent : −{b2[0]} %.")


def appliquer_correctif(profil: dict, correctif: dict, texte_option: str) -> None:
    for cid, vals in correctif.items():
        valides = [v for v in vals if v in CRITERES[cid]["valeurs"]]
        profil[cid] = entree(valides, "cohérence", citation=texte_option)
