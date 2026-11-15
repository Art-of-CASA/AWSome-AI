"""Critères du profil et questionnaire FIXE (identique pour tous les utilisateurs).

Les identifiants (A2, B1…) sont ceux de config/criteres_appariement.csv : chaque valeur pourra être
comparée au critère correspondant des actifs (data_extended/asset_criteria.csv).
Les valeurs possibles forment une liste FERMÉE : c'est ce qui rend le profil reproductible.

Types de questions :
  qcm        une réponse ; chaque option donne directement la valeur (pas d'IA)
  qcm_multi  plusieurs réponses possibles (pas d'IA)
  curseur    une valeur numérique rangée dans une classe (pas d'IA)
  quiz       questions à bonne réponse ; le score donne la valeur (pas d'IA)
  libre      texte libre ; classé par les deux agents (IA), en arrière-plan
Une option « Je ne sais pas » (valeur None) renvoie le critère aux précisions de fin de parcours.
"""
from __future__ import annotations

THEMES = ["ia", "semi-conducteurs", "logiciel", "sante", "energie_fossile", "banque", "assurance", "luxe",
          "vehicule_electrique", "or", "crypto", "dividendes", "consommation", "infrastructures", "telecoms",
          "immobilier", "armes", "tabac", "alcool", "jeux_argent", "aucun"]
SECTEURS_EMPLOI = ["technologie", "sante", "finance", "energie", "industrie", "commerce", "education",
                   "fonction_publique", "telecoms", "immobilier", "autre", "sans_emploi", "etudiant", "retraite"]

# id -> définition. « relance » : question de précision posée en fin de parcours si le critère reste incertain.
CRITERES: dict[str, dict] = {
    "A2": {"nom": "Horizon de placement", "multiple": False,
           "valeurs": ["moins_3_ans", "3_5_ans", "5_10_ans", "10_15_ans", "plus_15_ans"], "aide": "",
           "relance": "Pensez au moment où vous aurez besoin de la majeure partie de cet argent : est-ce plutôt dans 2 ans, 5 ans, 10 ans ou davantage ? Dites-le avec vos mots."},
    "A3": {"nom": "Objectif principal", "multiple": False,
           "valeurs": ["coussin_securite", "projet_date", "retraite", "revenu", "croissance", "transmission"],
           "aide": "projet_date = achat ou projet à une date connue (maison, études…).",
           "relance": "Si cet argent réussissait parfaitement sa mission, à quoi aurait-il servi ?"},
    "A4": {"nom": "Part de l'épargne totale", "multiple": False,
           "valeurs": ["faible_moins_25", "moyenne_25_60", "forte_plus_60"], "aide": "",
           "relance": "Si ce placement perdait la moitié de sa valeur, quelle part de toutes vos économies cela représenterait-il, à peu près ?"},
    "A5": {"nom": "Fonds d'urgence", "multiple": False,
           "valeurs": ["aucun", "moins_3_mois", "3_6_mois", "plus_6_mois"], "aide": "Mois de dépenses couverts sans toucher à ce placement.",
           "relance": "Si vous perdiez vos revenus demain, combien de temps pourriez-vous payer vos dépenses sans toucher à ce placement ?"},
    "A6": {"nom": "Stabilité des revenus", "multiple": False,
           "valeurs": ["stables", "variables", "incertains", "retraite"], "aide": "",
           "relance": "Vos revenus sont-ils à peu près les mêmes chaque mois, ou varient-ils beaucoup ?"},
    "A7": {"nom": "Dettes à taux élevé", "multiple": False, "valeurs": ["oui", "non"],
           "aide": "Dettes à plus de 8 % d'intérêt (cartes de crédit, prêts personnels coûteux).",
           "relance": "Avez-vous en ce moment un solde de carte de crédit ou un prêt personnel à taux élevé ?"},
    "A8": {"nom": "Personnes à charge", "multiple": False, "valeurs": ["0", "1_2", "3_plus"], "aide": "",
           "relance": "Combien de personnes dépendent de vos revenus (enfants, conjoint, parents) ?"},
    "A9": {"nom": "Retraits prévus avant l'échéance", "multiple": False,
           "valeurs": ["aucun", "ponctuel", "reguliers"], "aide": "",
           "relance": "Voyez-vous une dépense pour laquelle vous pourriez puiser dans ce placement avant l'échéance ?"},
    "A10": {"nom": "Besoin de revenu régulier", "multiple": False, "valeurs": ["non", "souhaite", "essentiel"],
            "aide": "Le placement doit-il verser un revenu (dividendes, intérêts) ?",
            "relance": "Comptez-vous sur ce placement pour payer certaines dépenses chaque mois ou chaque année ?"},
    "A12": {"nom": "Secteur d'emploi", "multiple": False, "valeurs": SECTEURS_EMPLOI,
            "aide": "Sert à éviter de doubler son exposition : un choc sectoriel toucherait l'emploi et le portefeuille.",
            "relance": "Dans quel domaine travaillez-vous (ou travailliez-vous) ?"},
    "B1R": {"nom": "Réaction déclarée à une baisse de 20 %", "multiple": False,
            "valeurs": ["vendre_tout", "vendre_partie", "attendre", "acheter_plus"], "aide": "",
            "relance": "Vos 10 000 $ deviennent 8 000 $ en trois mois. Concrètement, que feriez-vous la semaine suivante ?"},
    "B1": {"nom": "Point de rupture déclaré (baisse à laquelle on vendrait)", "multiple": False,
           "valeurs": ["5", "10", "20", "30", "40", "50_plus", "jamais"],
           "aide": "Pourcentage de baisse à partir duquel la personne vendrait.",
           "relance": "À partir de quelle baisse, en pour cent, vous diriez-vous : « j'arrête les frais et je vends » ?"},
    # Valeurs identiques aux mots-clés des actifs (kw_volatilite, kw_recuperation…) : comparaison directe.
    "B5": {"nom": "Volatilité acceptée", "multiple": False,
           "valeurs": ["faible_moins_8", "moderee_8_15", "elevee_15_25", "tres_elevee_plus_25"], "aide": "",
           "relance": "Si vos 10 000 $ montaient et descendaient chaque année de 500 $, de 1 500 $ ou de 3 000 $, laquelle de ces variations vous laisserait serein ?"},
    "B7": {"nom": "Durée de récupération supportable", "multiple": False,
           "valeurs": ["rapide_moins_1_an", "moyenne_1_2_ans", "longue_plus_2_ans"], "aide": "",
           "relance": "Après une forte baisse, combien de temps pourriez-vous attendre que votre placement retrouve sa valeur ?"},
    # Critères mesurés par les mises en situation (simulations.py), pas déclarés.
    "B2": {"nom": "Point de rupture observé (replay)", "multiple": False,
           "valeurs": ["5", "10", "20", "30", "40", "50_plus", "non_atteint"], "aide": "", "relance": ""},
    "B6": {"nom": "Arbitrage risque/rendement choisi (fourchettes)", "multiple": False,
           "valeurs": ["prudent", "equilibre", "dynamique"], "aide": "", "relance": ""},
    "D8O": {"nom": "Attrait observé pour un titre médiatisé (test)", "multiple": False, "valeurs": ["non", "oui"],
            "aide": "", "relance": ""},
    "H1": {"nom": "Écart entre déclaré et observé (rupture)", "multiple": False, "valeurs": ["aucun", "faible", "grand"],
           "aide": "", "relance": ""},
    "B3": {"nom": "Expérience d'une forte baisse", "multiple": False,
           "valeurs": ["jamais", "oui_garde", "oui_vendu", "oui_renforce"], "aide": "",
           "relance": "Avez-vous déjà vu vos placements perdre beaucoup, en 2020 ou 2022 par exemple ? Qu'avez-vous fait ?"},
    "B4": {"nom": "Fréquence de consultation", "multiple": False,
           "valeurs": ["quotidienne", "hebdomadaire", "mensuelle", "rarement"], "aide": "",
           "relance": "À quelle fréquence pensez-vous regarder la valeur de vos placements ?"},
    "C1": {"nom": "Niveau de connaissances (quiz)", "multiple": False,
           "valeurs": ["debutant", "intermediaire", "avance"], "aide": "", "relance": ""},
    "C2": {"nom": "Produits déjà détenus", "multiple": True,
           "valeurs": ["aucun", "fonds_communs", "fnb", "actions", "obligations", "crypto"], "aide": "",
           "relance": "Quels placements avez-vous déjà eus (fonds, FNB, actions, obligations, cryptos) ?"},
    "D1": {"nom": "Classes d'actifs acceptées", "multiple": True,
           "valeurs": ["actions", "fnb_actions", "obligations", "or", "crypto"], "aide": "",
           "relance": "Quels types de placements seriez-vous à l'aise de détenir ?"},
    "D2": {"nom": "Part maximale en cryptoactifs", "multiple": False, "valeurs": ["0", "5", "10", "20"],
           "aide": "En pour cent du portefeuille. 0 si la personne refuse les cryptos.",
           "relance": "Sur 100 $ investis, combien seriez-vous prêt à mettre au maximum en cryptoactifs ?"},
    "D12": {"nom": "Tolérance aux placements spéculatifs", "multiple": False,
            "valeurs": ["sans_speculatif", "plafonne_5", "plafonne_10", "accepte"],
            "aide": "Spéculatif = cryptoactif, ou volatilité >= 45 %, ou perte maximale >= 60 %.",
            "relance": "Seriez-vous à l'aise de détenir un placement qui peut perdre plus de la moitié de sa valeur ? Si oui, pour quelle part au maximum ?"},
    "D4": {"nom": "Risque de change accepté", "multiple": False,
           "valeurs": ["cad_seulement", "limite", "accepte"],
           "aide": "Variations du dollar canadien face aux autres devises.",
           "relance": "Si le dollar américain baissait de 10 % face au dollar canadien, vos placements américains perdraient autant. Est-ce acceptable pour vous ?"},
    "D3": {"nom": "Régions souhaitées", "multiple": True,
           "valeurs": ["canada", "etats_unis", "europe", "asie", "afrique", "emergents", "monde"], "aide": "",
           "relance": "Préférez-vous investir surtout au Canada, ou aussi ailleurs dans le monde ?"},
    "D5": {"nom": "Thèmes d'intérêt", "multiple": True, "valeurs": THEMES, "aide": "aucun si pas de préférence.",
           "relance": "Y a-t-il un domaine (technologie, santé, énergie…) dans lequel vous aimeriez particulièrement investir ?"},
    "D6": {"nom": "Secteurs refusés", "multiple": True, "valeurs": THEMES, "aide": "aucun si rien n'est refusé.",
           "relance": "Y a-t-il des secteurs dans lesquels vous refuseriez d'investir, par conviction ?"},
    "D7": {"nom": "Style recherché", "multiple": False,
           "valeurs": ["croissance", "etablie", "dividende", "indifferent"], "aide": "",
           "relance": "Préférez-vous des entreprises jeunes qui grandissent vite, ou des entreprises solides et établies ?"},
    "D8": {"nom": "Attrait pour les titres très médiatisés", "multiple": False, "valeurs": ["non", "parfois", "oui"],
           "aide": "", "relance": "Quand une action fait la une des journaux, avez-vous envie d'en acheter ?"},
    "E1": {"nom": "Énergies fossiles", "multiple": False,
           "valeurs": ["exclure_directe", "exclure_toute_implication", "limiter", "indifferent"], "aide": "",
           "relance": "Investir dans le pétrole, le gaz ou le charbon vous poserait-il problème ?"},
    "E2": {"nom": "Controverses", "multiple": False, "valeurs": ["aucune", "pas_de_grave", "indifferent"],
           "aide": "aucune = refuse toute entreprise visée par une controverse ; pas_de_grave = refuse seulement les graves.",
           "relance": "Investiriez-vous dans une entreprise condamnée pour pollution ou corruption ?"},
    "E4": {"nom": "Niveau d'exigence ESG", "multiple": False,
           "valeurs": ["non_requis", "prefere", "exige", "meilleurs_categorie"], "aide": "",
           "relance": "Les critères environnementaux et sociaux doivent-ils être un filtre strict, une préférence, ou ne comptent-ils pas ?"},
    "E5": {"nom": "Exclusions sectorielles", "multiple": True,
           "valeurs": ["contrats_de_defense", "armes", "alcool", "tabac", "jeux_argent", "tests_sur_animaux",
                       "energie_nucleaire", "atteinte_droits_autochtones", "aucune"],
           "aide": "Comparées au mot-clé kw_exclusions des actifs.",
           "relance": "Y a-t-il des activités dans lesquelles vous refusez d'investir (armement, alcool, tabac, jeux d'argent…) ?"},
    "F2": {"nom": "Risque pays", "multiple": True,
           "valeurs": ["exclure_chine", "exclure_emergents", "exclure_devise_instable", "aucune"],
           "aide": "Comparé au mot-clé kw_risque_pays des actifs.",
           "relance": "Y a-t-il des pays ou des types de marchés où vous ne voulez pas investir ?"},
    "G2": {"nom": "Type de compte", "multiple": False, "valeurs": ["celi", "reer", "non_enregistre", "ne_sait_pas"],
           "aide": "", "relance": ""},
}

# Critères qu'une réponse libre peut renseigner (les autres sont MESURÉS : quiz et mises en situation).
MESURES = {"C1", "B2", "B6", "D8O", "H1"}
DECLARATIFS = [c for c in CRITERES if c not in MESURES]


def est_deduit(justification: str) -> bool:
    return justification.strip().lower().startswith("déduit")


NSP = ("Je ne sais pas", None)

# Questionnaire fixe : 6 pages, mêmes questions dans le même ordre pour tout le monde.
SECTIONS: list[dict] = [
    {"titre": "Votre projet", "items": [
        {"id": "q_a3", "type": "qcm", "critere": "A3", "texte": "À quoi servira principalement cet argent ?",
         "options": [("Avoir un coussin de sécurité pour les imprévus", "coussin_securite"),
                     ("Financer un projet à une date précise (maison, études…)", "projet_date"),
                     ("Préparer ma retraite", "retraite"), ("Me verser un revenu", "revenu"),
                     ("Faire croître mon capital", "croissance"), ("Transmettre un patrimoine", "transmission"), NSP]},
        {"id": "q_a2", "type": "qcm", "critere": "A2", "texte": "Dans combien de temps aurez-vous besoin de la majeure partie de cet argent ?",
         "options": [("Moins de 3 ans", "moins_3_ans"), ("3 à 5 ans", "3_5_ans"), ("5 à 10 ans", "5_10_ans"),
                     ("10 à 15 ans", "10_15_ans"), ("Plus de 15 ans", "plus_15_ans"), NSP]},
        {"id": "q_a9", "type": "qcm", "critere": "A9", "texte": "Prévoyez-vous de retirer une partie de cet argent avant cette échéance ?",
         "options": [("Non, je n'y toucherai pas", "aucun"), ("Oui, une fois (achat, projet…)", "ponctuel"),
                     ("Oui, régulièrement", "reguliers"), NSP]},
        {"id": "q_a10", "type": "qcm", "critere": "A10", "texte": "Avez-vous besoin que ce placement vous verse un revenu régulier ?",
         "options": [("Non", "non"), ("Ce serait un plus", "souhaite"), ("Oui, j'en ai besoin pour vivre", "essentiel"), NSP]},
    ]},
    {"titre": "Votre situation", "items": [
        {"id": "q_a4", "type": "qcm", "critere": "A4", "texte": "Quelle part de votre épargne totale ce placement représente-t-il ?",
         "options": [("Moins du quart", "faible_moins_25"), ("Entre le quart et environ 60 %", "moyenne_25_60"),
                     ("Plus de 60 %", "forte_plus_60"), NSP]},
        {"id": "q_a5", "type": "qcm", "critere": "A5", "texte": "Sans toucher à ce placement, combien de mois de dépenses pourriez-vous couvrir en cas d'imprévu ?",
         "options": [("Aucun", "aucun"), ("Moins de 3 mois", "moins_3_mois"), ("3 à 6 mois", "3_6_mois"),
                     ("Plus de 6 mois", "plus_6_mois"), NSP]},
        {"id": "q_situation", "type": "libre", "criteres": ["A6", "A12", "A8", "A7"],
         "texte": "Décrivez votre situation en quelques phrases : vos revenus sont-ils stables, dans quel secteur travaillez-vous, avez-vous des personnes à charge ou des dettes à taux élevé (cartes de crédit…) ?",
         "aide": "Exemple : « Salarié dans la santé depuis 10 ans, deux enfants, aucune dette sauf l'hypothèque. »"},
    ]},
    {"titre": "Vous et le risque", "items": [
        {"id": "q_b1r", "type": "qcm", "critere": "B1R",
         "texte": "Vous investissez 10 000 $. Trois mois plus tard, ils ne valent plus que 8 000 $. Que faites-vous ?",
         "options": [("Je vends tout pour arrêter les pertes", "vendre_tout"), ("J'en vends une partie", "vendre_partie"),
                     ("J'attends sans rien faire", "attendre"), ("J'en rachète, c'est moins cher", "acheter_plus"), NSP]},
        {"id": "q_b1", "type": "curseur", "critere": "B1", "texte": "À partir de quelle baisse vendriez-vous à coup sûr ? (en %)",
         "min": 5, "max": 60, "pas": 5, "defaut": 20, "unite": "%",
         "classes": [(7, "5"), (15, "10"), (25, "20"), (35, "30"), (45, "40"), (999, "50_plus")],
         "case_nsp": "Je ne sais pas", "case_jamais": "Je ne vendrais jamais à cause d’une baisse", "valeur_jamais": "jamais"},
        {"id": "q_b5", "type": "qcm", "critere": "B5",
         "texte": "Sur 10 000 $ investis, quelle variation annuelle typique (à la hausse comme à la baisse) acceptez-vous ?",
         "options": [("Moins de 800 $ (volatilité faible, moins de 8 %)", "faible_moins_8"),
                     ("800 à 1 500 $ (modérée, 8 à 15 %)", "moderee_8_15"),
                     ("1 500 à 2 500 $ (élevée, 15 à 25 %)", "elevee_15_25"),
                     ("Plus de 2 500 $ (très élevée, plus de 25 %)", "tres_elevee_plus_25"), NSP]},
        {"id": "q_b7", "type": "qcm", "critere": "B7",
         "texte": "Après une forte baisse, combien de temps pourriez-vous attendre que votre placement retrouve sa valeur ?",
         "options": [("Moins d'un an", "rapide_moins_1_an"), ("Un à deux ans", "moyenne_1_2_ans"),
                     ("Plus de deux ans si nécessaire", "longue_plus_2_ans"), NSP]},
        {"id": "q_b3", "type": "qcm", "critere": "B3", "texte": "Avez-vous déjà vécu une forte baisse de vos placements (2020, 2022…) ?",
         "options": [("Jamais", "jamais"), ("Oui, et j'ai gardé mes placements", "oui_garde"),
                     ("Oui, et j'ai vendu", "oui_vendu"), ("Oui, et j'en ai racheté", "oui_renforce"), NSP]},
        {"id": "q_b4", "type": "qcm", "critere": "B4", "texte": "À quelle fréquence regardez-vous (ou regarderez-vous) vos placements ?",
         "options": [("Tous les jours", "quotidienne"), ("Chaque semaine", "hebdomadaire"),
                     ("Chaque mois", "mensuelle"), ("Rarement", "rarement"), NSP]},
    ]},
    {"titre": "Vos connaissances", "items": [
        {"id": "q_c1", "type": "quiz", "critere": "C1",
         "texte": "Trois petites questions (aucune pression : elles servent à adapter les explications).",
         "questions": [
             {"texte": "Vous placez 1 000 $ à 5 % par an pendant 2 ans, intérêts réinvestis. Au bout de 2 ans, vous avez :",
              "options": ["Exactement 1 100 $", "Plus de 1 100 $", "Moins de 1 100 $", "Je ne sais pas"], "bonne": 1},
             {"texte": "Acheter une seule action est en général … risqué qu'acheter un fonds qui en contient des centaines.",
              "options": ["plus", "moins", "aussi", "Je ne sais pas"], "bonne": 0},
             {"texte": "Si les taux d'intérêt montent, le prix des obligations existantes a tendance à :",
              "options": ["monter", "baisser", "ne pas changer", "Je ne sais pas"], "bonne": 1}],
         "niveaux": {0: "debutant", 1: "debutant", 2: "intermediaire", 3: "avance"}},
        {"id": "q_c2", "type": "qcm_multi", "critere": "C2", "texte": "Quels produits avez-vous déjà détenus ?",
         "options": [("Aucun", "aucun"), ("Fonds communs de placement", "fonds_communs"), ("FNB (fonds indiciels)", "fnb"),
                     ("Actions d'entreprises", "actions"), ("Obligations", "obligations"), ("Cryptoactifs", "crypto")]},
    ]},
    {"titre": "Vos préférences", "items": [
        {"id": "q_d1", "type": "qcm_multi", "critere": "D1", "texte": "Quels types de placements acceptez-vous ?",
         "options": [("Actions d'entreprises", "actions"), ("FNB d'actions", "fnb_actions"), ("Obligations", "obligations"),
                     ("Or", "or"), ("Cryptoactifs", "crypto")]},
        {"id": "q_d2", "type": "qcm", "critere": "D2", "texte": "Quelle part maximale de votre portefeuille en cryptoactifs ?",
         "options": [("Aucune", "0"), ("Jusqu'à 5 %", "5"), ("Jusqu'à 10 %", "10"), ("Jusqu'à 20 %", "20"), NSP]},
        {"id": "q_d12", "type": "qcm", "critere": "D12",
         "texte": "Placements spéculatifs (cryptoactifs, titres qui peuvent perdre plus de la moitié de leur valeur) :",
         "options": [("Je n'en veux pas", "sans_speculatif"), ("Au plus 5 % du portefeuille", "plafonne_5"),
                     ("Au plus 10 % du portefeuille", "plafonne_10"), ("Je les accepte sans limite particulière", "accepte"), NSP]},
        {"id": "q_d4", "type": "qcm", "critere": "D4",
         "texte": "Les placements en devises étrangères varient aussi avec le taux de change. Vous préférez :",
         "options": [("Rester en dollars canadiens", "cad_seulement"), ("Limiter la part en devises étrangères", "limite"),
                     ("Les variations de change ne me dérangent pas", "accepte"), NSP]},
        {"id": "q_d3", "type": "qcm_multi", "critere": "D3", "texte": "Où souhaitez-vous investir ?",
         "options": [("Canada", "canada"), ("États-Unis", "etats_unis"), ("Europe", "europe"), ("Asie", "asie"),
                     ("Afrique", "afrique"), ("Pays émergents", "emergents"), ("Partout dans le monde", "monde")]},
        {"id": "q_d7", "type": "qcm", "critere": "D7", "texte": "Quel type d'entreprises préférez-vous ?",
         "options": [("En forte croissance", "croissance"), ("Établies et stables", "etablie"),
                     ("Qui versent des dividendes", "dividende"), ("Pas de préférence", "indifferent"), NSP]},
        {"id": "q_d8", "type": "qcm", "critere": "D8", "texte": "Seriez-vous tenté par une action dont tout le monde parle en ce moment ?",
         "options": [("Non", "non"), ("Parfois", "parfois"), ("Oui", "oui"), NSP]},
        {"id": "q_themes", "type": "libre", "criteres": ["D5", "D6"],
         "texte": "Y a-t-il des thèmes ou des secteurs qui vous intéressent particulièrement, et d'autres que vous refusez ? Pourquoi ?",
         "aide": "Exemple : « L'IA et la santé m'intéressent ; je refuse le tabac et les armes. »"},
    ]},
    {"titre": "Vos valeurs et votre compte", "items": [
        {"id": "q_e1", "type": "qcm", "critere": "E1", "texte": "Les énergies fossiles (pétrole, gaz, charbon) :",
         "options": [("Je veux exclure les entreprises qui en produisent ou en transportent", "exclure_directe"),
                     ("Je veux exclure toute implication, même partielle", "exclure_toute_implication"),
                     ("Je préfère les limiter sans les exclure", "limiter"), ("Ce n'est pas un critère pour moi", "indifferent"), NSP]},
        {"id": "q_e2", "type": "qcm", "critere": "E2", "texte": "Les entreprises visées par des controverses (pollution, corruption, droits humains) :",
         "options": [("Je les refuse toutes", "aucune"), ("Je refuse seulement les cas graves", "pas_de_grave"),
                     ("Ce n'est pas un critère pour moi", "indifferent"), NSP]},
        {"id": "q_e4", "type": "qcm", "critere": "E4", "texte": "Les critères environnementaux, sociaux et de gouvernance (ESG) doivent être :",
         "options": [("Un filtre strict", "exige"), ("Les meilleurs de chaque secteur, sans exclure de secteur", "meilleurs_categorie"),
                     ("Une préférence, sans obligation", "prefere"), ("Pas un critère pour moi", "non_requis"), NSP]},
        {"id": "q_e5", "type": "qcm_multi", "critere": "E5", "texte": "Excluez-vous certaines activités ?",
         "options": [("Aucune exclusion", "aucune"), ("Armement", "armes"), ("Contrats de défense", "contrats_de_defense"),
                     ("Alcool", "alcool"), ("Tabac", "tabac"), ("Jeux d'argent", "jeux_argent"),
                     ("Tests sur les animaux", "tests_sur_animaux"), ("Énergie nucléaire", "energie_nucleaire"),
                     ("Atteintes aux droits des peuples autochtones", "atteinte_droits_autochtones")]},
        {"id": "q_f2", "type": "qcm_multi", "critere": "F2", "texte": "Excluez-vous certains pays ou marchés ?",
         "options": [("Aucune exclusion", "aucune"), ("Chine", "exclure_chine"), ("Pays émergents", "exclure_emergents"),
                     ("Pays à devise instable", "exclure_devise_instable")]},
        {"id": "q_g2", "type": "qcm", "critere": "G2", "texte": "Dans quel type de compte investirez-vous ?",
         "options": [("CELI", "celi"), ("REER", "reer"), ("Compte non enregistré", "non_enregistre"),
                     ("Je ne sais pas encore", "ne_sait_pas")]},
    ]},
]


def describe(ids: list[str]) -> str:
    """Texte décrivant les critères à classer, inséré dans les consignes des agents."""
    lines = []
    for cid in ids:
        c = CRITERES[cid]
        kind = "plusieurs valeurs possibles" if c["multiple"] else "UNE seule valeur"
        lines.append(f"- {cid} « {c['nom']} » ({kind}) : {', '.join(c['valeurs'])}"
                     + (f". Note : {c['aide']}" if c["aide"] else ""))
    return "\n".join(lines)
