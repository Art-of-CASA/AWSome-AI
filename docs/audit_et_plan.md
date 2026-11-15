# AlphaForge AI : audit de cohérence et plan de correction

15 novembre 2026. Aucun fichier du projet n'a été modifié. Les vérifications ont été faites sur une copie de l'archive `datathon-main-2.zip`, dans un environnement isolé.

## 0. Ce que j'ai pu lire, et ce qui manque

**Lu et vérifié** : tout le code de `mvp_profil/` et de `scripts/`, `config/`, `docs/criteres_profil_actifs.md`, les README, les fichiers de données, et les trois documents d'audit. J'ai lancé les 6 tests, recalculé les chiffres des audits à partir des prix, et comparé le dossier au paquet déployé sur S3.

**Lu en diagonale seulement** : `chercheur.py`, `criteres_dynamiques.py`, le composant vocal et le détail des fichiers de test. Je n'y ai pas cherché de bogue ligne par ligne.

**Absent, donc non vérifié** :

| Élément manquant | Conséquence |
|---|---|
| Énoncé officiel (PDF) et présentation (PPTX), exclus par `.gitignore` | Je ne connais les consignes que par les citations des audits. Les numéros de page, la description exacte des personas et la grille d'évaluation ne sont pas vérifiés à la source. |
| `scripts/audit_criteres.py`, cité comme source de tous les chiffres de `audit_criteres.md` | Les tableaux de verdicts par persona ne sont pas reproductibles. J'ai refait les calculs de portefeuille moi-même (voir 2.1). |
| Script du « test sur les trois personas » de `docs/criteres_profil_actifs.md` | Tableau non reproductible. |
| `alphaforge/evaluation.py` et `resultats/` (dossier parent), cités par `MODIFICATIONS_A_FAIRE.md` | Non vérifiable. |
| Historique git (branche, commit `47f6cd2`) | Non vérifiable. |
| Cache `mots_cles_dynamiques.json` du serveur, « Google Doc de critères » | Non vérifiable. |

**Limite de mes connaissances** : je ne peux pas confirmer les prix de marché postérieurs à juin 2026. J'ai contrôlé la cohérence interne des séries (aucun doublon, 4 variations quotidiennes de plus de 25 %, toutes sur des titres volatils), pas leur exactitude.

---

## 1. Verdict en bref

1. **Ce qui existe fonctionne.** Les 6 tests passent. Le code déployé sur S3 est identique au dossier fourni (seules les fins de ligne diffèrent). Le profil d'inférence Bedrock `us.anthropic.claude-haiku-5-5` existe bien dans le compte.
2. **Le projet ne produit pas encore ce que le datathon demande.** Il s'arrête au profil : pas d'appariement, pas de portefeuille, pas d'explication d'une conclusion. `config/criteres_appariement.csv` n'est lu par aucun code, et ses règles sont du texte libre, pas des règles exécutables.
3. **Les deux audits de fond sont fiables sur les faits.** Sur une soixantaine d'affirmations vérifiables, je n'en infirme que trois, partiellement. Leurs chiffres se reproduisent.
4. **Les trois documents se contredisent sur la suite**, sur cinq points de conception (échelle de risque, niveau du verdict, règle de poids, B2, questions à ajouter). Il faut trancher avant de coder.
5. **J'ai trouvé 9 défauts que les audits n'ont pas vus**, dont un vrai bogue de logique : une règle de cohérence peut effacer le point de rupture observé au replay et le remplacer par une valeur plus risquée que personne n'a donnée.
6. **Les propositions chiffrées des audits pour le moteur sont des inventions assumées** (table de capacité, niveaux de stress, points du score, scénario « actions −45 % »). Elles sont présentées comme hypothèses, ce qui est honnête, mais aucune n'est sourcée.

---

## 2. Évaluation des audits existants

### 2.1 `audit_criteres.md`

| Affirmation | Statut | Preuve ou remarque |
|---|---|---|
| 59 actifs sur 66 ont une volatilité ≥ 15 % ; classes 7 = 37, 6 = 22 | Confirmé | `asset_criteria.csv` |
| Portefeuille 30 ZST / 40 XBB / 30 XEQT : volatilité 5,3 %, perte max −11,2 %, 2022 −7,5 %, 714 jours sous l'eau | Confirmé | Recalcul exact |
| 100 % VT : 15,1 %, −21,4 %, −12,4 %, 690 jours | Confirmé à l'arrondi | J'obtiens 15,2 %, −21,4 %, −12,9 %, 690 |
| Lignes « + 5 % FTS et 5 % JNJ » et « 5 % NVDA » | Confirmé, mais construction non dite | Les chiffres ne sortent que si les 10 % sont pris sur ZST (20/40/30/5/5). Avec une dilution proportionnelle : −10,5 % et −14,1 %. |
| Poids maximaux (SHOP 4 %, NVDA 8 %, TSLA 9 %, BTC 7 %, QQQ 22 %, VT 47 %, JNJ 99 %) | Confirmé, avec une incohérence | Ils correspondent à un budget de 16 % (0,8 × 20). La section 5 du même document donne à Robert un budget de 15 % : NVDA tombe alors à 6 %, QQQ à 17 %, VT à 38 %. |
| 100 % XEQT −19,1 % ; 40 ZST / 60 XBB −9,5 % | Confirmé | |
| 9 thèmes du profil sur 20 sans actif ; 4 valeurs E5 sur 8 sans actif | Confirmé | `sante`, `energie_fossile`, `dividendes`, `consommation`, `immobilier`, `armes`, `tabac`, `alcool`, `jeux_argent` ; E5 : `armes`, `tabac`, `jeux_argent`, `energie_nucleaire` |
| 29 actifs avec `country` = « Amérique du Nord » | Confirmé | Le jeu de départ n'a pas de colonne pays |
| Anomalie 1 : TLT (−39,7 %) et XBB « stabilisateurs » comme ZST | Confirmé | `build_asset_criteria.py:204` |
| Anomalie 2 : NOVO et GFI « revenu » alors que spéculatifs | Confirmé | Ordre de `np.select` |
| Anomalie 3 : ZST liquidité « faible », la règle A9 ne laisse aucun actif | Confirmé | ZST est le seul actif de classe ≤ 3 |
| Anomalie 4 : complexité 2 pour 5 FNB obligataires, GLD et 28 actions étrangères | Confirmé | |
| Anomalie 5 : VWO seulement `exposition_chine_partielle` | Confirmé | `build_asset_criteria.py:312` |
| Anomalie 6 : BNDW = 100 % « technology » | Confirmé | `etf_sector_weights.csv` |
| Anomalie 7 : fausses baisses de dividende TTE, HSBA, ZST | Confirmé | TTE 3,67 → 2,86 ; HSBA 0,646 → 0,496 ; ZST 2,30 → 1,38 |
| Anomalie 8 : `dividends_to_fcf` ENB 2,8, FTS négatif, Toyota 6,9 | Confirmé | |
| Anomalie 9 : MFC `profitable_years_share` = 0,25 | Confirmé | Marge nette négative 3 ans sur 4 parce que le revenu Yahoo est négatif ; le RCP est positif |
| Anomalie 10 : `media_hype` (Nestlé, Reliance, Infosys très médiatisés ; ETH non) ; `variation_recente_extreme` jamais attribué | Confirmé | Aucun rendement sur 3 mois ne dépasse 30 % |
| Anomalie 11 : BTC, NOVO, SOL, APN « diversifiants » | Confirmé | 28 actifs sont diversifiants au seuil de 0,30 |
| Anomalie 12 : 13 des 14 « non récupérés » sont des baisses de 2025-2026 | Confirmé | Seul TLT (creux d'octobre 2023) est une vraie non-récupération |
| `stress_loss` identique à `max_drawdown` pour les 66 actifs | Confirmé | |
| XIU : 18 % d'énergie, CNQ, ENB et SU dans les 10 premières positions ; QQQ 58 % de technologie, NVDA 8 % | Confirmé | |
| 35 actions sur 50 à 10 ou 12 ans d'horizon minimal, 14 à 7 ou 9 ans | Confirmé | |
| Corrélations NVDA-ASML 0,54 et NVDA-QQQ 0,75 | Confirmé | |
| GOOGL et AMZN non « établies » | Confirmé | Mais BYD, CIB (Égypte) et Constellation le sont : le critère est mal calibré dans les deux sens |
| TotalEnergies « élevée » pour de simples « allégations d'un site Web » | **Partiellement infirmé** | La source du dépôt est une décision de justice sur le fond (Paris, octobre 2025). Le classement respecte la définition de l'équipe. La critique sur l'absence d'ampleur reste valable. |
| Liste des ADR américains (G3) | **Incomplet** | ASML (Nasdaq) et Sasol (NYSE) ont aussi une cotation américaine. `access_canada` traite ASML comme « courtier international » et TSMC comme « via ADR » : table manuelle incohérente. |
| Règlement 31-103, art. 13.3 ; ETH en preuve d'enjeu depuis septembre 2022 ; S&P 500 −34 % en 2020 et plus de −50 % en 2007-2009 | Confirmé | De mémoire, sans relecture des textes |
| Tableaux de verdicts par persona (Robert 0 cohérent sur 66) | Non vérifiable | Script absent. Plausible : ZST est bloqué par la complexité 2 pour un débutant. |
| Budgets des personas (Robert 15 %, Mateo 22 %, Amira 40 %) | Cohérent avec ses propres tables | Mais les profils des personas sont des hypothèses de l'auteur, pas ceux de l'énoncé |

**Ce que cet audit propose sans le justifier** (à traiter comme des hypothèses à valider, pas comme des faits) : la table de capacité, les niveaux de stress 8/15/22/32/45 %, le facteur 0,8 × B1, la correspondance B5 → niveau (qui saute le niveau 4), les points du score de préférences, les plafonds de 10 % par titre et 25 % par secteur, et le scénario « actions −45 %, obligations +2 %, or +10 % ». Ce dernier pose un problème de fond : avec des obligations à +2 %, un portefeuille très obligataire paraît sans risque, alors que 2022 montre l'inverse. Il faut au moins deux scénarios (krach boursier, choc de taux).

### 2.2 `point_problemes.md`

| # | Point | Statut | Remarque |
|---|---|---|---|
| 1, 2 | Aucun résultat ; tests des personas non démontrables | Confirmé | Aucun code ne lit la grille ; aucune mention des personas dans `mvp_profil/` |
| 3 | Valeurs différentes entre la grille et `criteres.py` | Confirmé | Les 8 lignes du tableau sont exactes |
| 4 | 12 critères jamais demandés | Confirmé | 15 identifiants manquent ; D13 est l'alias de D8O, H2 et H3 sont des contrôles |
| 5 | Thèmes non alignés | Confirmé | |
| 6 | Récupération mesurée depuis le creux | Confirmé | `compute_metrics.py:80`. NVDA : 216 jours depuis le creux, 535 depuis le sommet. TSLA : 702 contre 1 067. |
| 7 | Horizon de 9 ans pour PG, Nestlé, GLD, TLT contre 7 pour SPY | Confirmé | TLT est un cas différent : il n'a réellement jamais récupéré |
| 8 | Classe de risque peu discriminante | Confirmé | |
| 9 | Replay : « réduire » vaut « vendre », « non atteint » vaut confirmation | Confirmé | Creux 8 386 $ et 8 198 $ exacts. Voir aussi mes ajouts en 3.1. |
| 10 | Le test de l'effet de mode se devine | Confirmé | `simulations.py:157-160` |
| 11 | Trace des débats exposée | Confirmé, à nuancer | Le raisonnement étendu est désactivé. Ce qui est affiché : propositions, confiances, citations et objections. L'export JSON contient aussi les justifications. C'est plus proche d'un journal de contrôle que d'un raisonnement interne, mais la présentation « débat » prête à confusion. |
| 12 | Section sécurité du README fausse | Confirmé | Pas de Lambda, de Secrets Manager ni de dossier `.github` ; `FINANCIAL_DATA_API_KEY` n'est utilisée nulle part |
| 13 | Pas de personas préchargés | Confirmé | |
| 14 | Pas de test de sensibilité | Confirmé | |
| 15 | 24 actifs « courtier international » ; justification de l'univers étendu « écrite nulle part » | **Partiellement infirmé** | `data_extended/README.md` justifie le choix par rapport aux personas. Il manque l'argument de pertinence pour un investisseur canadien. |
| 16 | Livrables absents | Confirmé pour l'archive | Je ne vois pas ce qui existe ailleurs |

### 2.3 `MODIFICATIONS_A_FAIRE.md`

Les constats sont exacts (37 valeurs, 8 règles `calcul_capacite` non codées, A1 absent, 10 règles de cohérence, aucun critère de concentration, documentation de sécurité fausse).

J'ai vérifié deux points directement dans le compte AWS, en lecture seule :
- le port 8501 est ouvert à **trois** adresses de l'équipe et à la liste de préfixes CloudFront. `DEPLOIEMENT.md` en annonce une, puis deux ;
- le paquet S3 date du 14 novembre à 19 h 45, et son contenu est identique au dossier fourni. La crainte « le zip S3 peut être plus récent » ne s'applique pas à cette archive.

Deux réserves sur ce document :
- **B7 (S3 + Glue + Athena + Quick)** pour 66 actifs contredit la consigne citée ailleurs (« ne multipliez pas les services pour impressionner »). Le document le pressent lui-même (« ne pas invoquer le volume »).
- **A1** demande une classe finale de 1 à 7, calquée sur les bandes de volatilité des actifs. C'est justement la comparaison actif par actif que les deux autres audits déconseillent.

### 2.4 Contradictions entre les trois documents

| Sujet | `MODIFICATIONS_A_FAIRE` | `audit_criteres` | `point_problemes` |
|---|---|---|---|
| Échelle du profil | Classe 1 à 7 | Niveau 1 à 5 avec budget de perte | Non précisé |
| Niveau du verdict | Par actif (cohérent, à surveiller, en tension) | Portefeuille ; par actif : exclusions et poids maximal | Portefeuille |
| Règle de poids | Poids égaux ou inverse de la volatilité | Remplissage un actif à la fois, score de préférences | « Allocation simple » |
| B2 (replay) | S'en sert comme argument (« vous avez vendu à −10 % ») | « Point fort », aucun changement | Ne retenir que « Tout vendre » |
| D9, D10, C3 | D9 demandé à tous | D9 par défaut, D10 non demandé, C3 fusionné | Les trois à ajouter au questionnaire |
| A1 | Étape de vie (5 valeurs de la grille) | Tranche d'âge | À ajouter |
| Stress | Perte de 2022 | Pire de l'historique et d'un scénario hypothétique | Choc de 2022 en sensibilité |

---

## 3. Ce qui ne va pas

### 3.1 Bogues et résultats incohérents

Les points marqués « nouveau » ne figurent dans aucun des trois audits.

| # | Problème | Où | Pourquoi c'est un problème |
|---|---|---|---|
| B1 | **Nouveau.** Une règle de cohérence peut annuler le résultat du replay. Exemple : la personne réduit à −5 % au replay, donc B1 devient 5. Si elle avait répondu « j'en rachète » à B1R, la règle R1b se déclenche, et l'option « je profiterais de la baisse » fixe B1 à 30. | `profil.py:51-56`, `161-170` | La règle « le plus prudent l'emporte » n'est plus garantie, alors que c'est le principe central du projet. |
| B2 | **Nouveau.** Les correctifs de cohérence écrivent des valeurs que personne n'a données : B1 = 30 (R1b), B1 = 10 (R6), A2 = moins de 3 ans (R2), D12 = 5 % (R9). Elles sont enregistrées « validé », confiance 100 %. | `profil.py:49-114` | Contredit « tout est justifié par une citation ». C'est une valeur inventée par le code. |
| B3 | **Nouveau.** Le point de rupture observé dépend d'un effet de seuil. Portefeuille équilibré : vendre à l'arrêt 2 (−14,9 %) donne B2 = 10, vendre à l'arrêt 3 (−15,05 %) donne B2 = 20. Le message dit « vous avez réduit vers −10 % » pour une vente à −14,9 %. | `simulations.py:23, 112` ; `scenarios.json` | Le profil bascule d'une classe pour 0,2 point d'écart, et l'explication affichée est inexacte. |
| B4 | « Réduire de moitié » fixe B2 et écrase B1. La valeur déclarée ne survit que dans un champ de texte. | `simulations.py:94` ; `profil.py:167` | Une réduction partielle à −5 % donne un point de rupture de 5 % : le budget de risque devient presque nul. |
| B5 | « Non atteint » donne H1 = aucun, même quand le replay n'a testé que −15 % et que la personne a déclaré −50 %. | `profil.py:161-163` | Une tolérance non testée est notée comme confirmée. |
| B6 | **Nouveau.** Le portefeuille du replay est 100 % QQQ dès que la personne cite l'IA ou les semi-conducteurs, sauf volatilité « faible ». Un profil modéré à horizon de 3 à 5 ans (Robert) revit donc −28 %. | `simulations.py:37` | Le commentaire dit « portefeuille proche du profil déclaré » : ce n'est pas le cas. |
| B7 | Récupération mesurée depuis le creux ; horizon allongé de 2 ans pour les baisses en cours. | `compute_metrics.py:80` ; `build_asset_criteria.py:168` | B7 et A2 jugent mal les actifs (NVDA « rapide », PG et Nestlé pénalisés). |
| B8 | Rôles, liquidité, complexité, risque pays, secteurs de BNDW, dividendes, MFC, médiatisation, diversifiant (anomalies 1 à 12 de l'audit). | `build_asset_criteria.py`, `fetch_extra_data.py` | Chacune fausse ou bloque un critère d'appariement. |
| B9 | **Nouveau.** `fossil_involvement` mélange des catégories (`directe`, `partielle`, `indirecte`, `aucune`) et du texte chiffré (« part énergie 18.0% »). | `esg_screens.csv` | Inutilisable tel quel par une règle. Il faut une colonne de catégorie et une colonne numérique. |
| B10 | **Nouveau.** R3 se déclenche quand D1 est « à préciser » (liste vide) et que D2 n'est pas 0. | `profil.py:65` | Contradiction signalée à tort. |
| B11 | **Nouveau.** Dans l'effet de mode, RY.TO a `pic_recent = true` mais s'affiche « peu médiatisée » ; NVDA s'affiche « on en parle partout » avec −24 % sur 3 mois. | `scenarios.json`, `simulations.py:157` | Incohérence visible à l'écran. |

### 3.2 Affirmations non vérifiées, inexactes ou inventées

| # | Affirmation | Où | Constat |
|---|---|---|---|
| H1 | « La table complète, lisible par le code » ; « le moteur lira le CSV » | `docs/criteres_profil_actifs.md`, README | Faux aujourd'hui : aucun code ne lit le CSV, et la colonne `regle_appariement` est une phrase. |
| H2 | « Avec la même réponse, on obtient le même profil : il est reproductible » | README, section 2 | Non démontré pour les réponses libres. Aucun test n'appelle un vrai modèle ; aucune mesure de répétabilité. |
| H3 | « L'outil appliquera le réglage le plus prudent » pour un critère incertain | `app.py:751`, README | **Nouveau.** Ce réglage n'est défini nulle part : aucune table de valeurs par défaut. |
| H4 | AWS Lambda, Secrets Manager, GitHub Actions OIDC | README, `SECURITY.md`, `.env.example` | Infrastructure inexistante. |
| H5 | « Port 8501 ouvert à une seule IP » | `DEPLOIEMENT.md` | Trois IP en réalité. Le fichier contient aussi l'identifiant du compte, l'IP publique et les IP de l'équipe. |
| H6 | Tableau des verdicts par persona (45/21/0/0, etc.) | `docs/criteres_profil_actifs.md` | Non reproductible, réglages « hypothétiques ». Le second tableau, dans l'audit, donne d'autres chiffres avec d'autres réglages. Aucun des deux ne doit être présenté au jury. |
| H7 | Exclusions écrites à la main : essais sur animaux pour 4 laboratoires seulement, contrats de défense pour 3 sociétés seulement | `build_asset_criteria.py:212-218` | Liste déclarée non exhaustive, mais appliquée de façon inégale (P&G, Nestlé, Siemens, Samsung non examinés). Risque : l'outil affiche « aucune exclusion connue » à tort. |
| H8 | Corée du Sud et Taïwan classés « marché émergent », alors que VEA (pays développés) détient Samsung | `build_asset_criteria.py:313` | **Nouveau.** Deux classifications coexistent (MSCI, FTSE) sans que le choix soit déclaré. XEQT est « pays développé » malgré environ 4,5 % d'émergents. |
| H9 | Bandes « de type SRRI » | `seuils_criteres.json` | Les bornes sont bien celles du SRRI européen. Pour un cas canadien, la référence locale est la méthode des ACVM (5 niveaux, écart-type sur 10 ans). À vérifier avant de défendre ce choix ; ce n'est pas une erreur. |
| H10 | Fourchettes « mauvaise année, 1 sur 20 » : −8,7 % pour le portefeuille équilibré | `scenarios.json` | **Nouveau.** L'utilisateur vient de voir ce même portefeuille perdre 15 % au replay. Le rééchantillonnage sur 5 ans, recentré, sous-estime les mauvaises années. À dire à l'écran. |
| H11 | Contrôle Enbridge « confirmée en appel, 2026 » | `esg_controversies.csv` | Sourcé par un lien, mais postérieur à mes connaissances : non vérifié par moi. Je n'ai ouvert aucun des 19 liens de controverses. |

**Vérifié et exact**, pour lever le doute : les rendements de la Norme d'hypothèses de projection 2026 (revenu fixe 3,2 %, actions canadiennes 6,3 %, américaines 6,4 %, publiée le 16 avril 2026) ; l'identifiant Bedrock ; les versions de bibliothèques de `requirements.txt` (elles s'installent et les tests passent avec le vrai SDK). Je n'ai trouvé aucune fonction ni bibliothèque inexistante.

### 3.3 Écarts avec les consignes et la vision du projet

| # | Écart | Gravité |
|---|---|---|
| E1 | Pas de recommandation de portefeuille, donc pas de conclusion à expliquer | Bloquant |
| E2 | Le test de Robert (contester une demande) n'a pas de parcours. Le test D8O mesure un attrait, pas une demande. | Bloquant |
| E3 | Le profil est une liste de 37 valeurs, sans synthèse : ni capacité, ni tolérance, ni budget de risque | Bloquant pour la suite |
| E4 | Les règles de risque de la grille s'appliquent actif par actif : elles éliminent tout pour un profil prudent | Élevée |
| E5 | Vocabulaires non alignés entre profil et actifs (thèmes, régions, secteur d'emploi, E1, E5) | Élevée |
| E6 | Critères nécessaires à un portefeuille jamais collectés : montant (G1), concentration (D9), FNB ou titres (D11), accès (G3) | Élevée |
| E7 | Une seule crise dans la fenêtre de 5 ans ; `stress_loss` n'apporte rien de plus que la perte maximale | Élevée |
| E8 | Fichiers produits mais jamais utilisés : `macro_release_dates.csv`, seuil `frais_fnb_eleves` | Moyenne |
| E9 | Pas de mode démonstration ni de personas versionnés ; parcours trop long pour deux profils en 5 minutes | Élevée |
| E10 | Encadrement « simulation » présent en bas de barre latérale seulement ; faits, hypothèses et scénarios non étiquetés | Moyenne |
| E11 | Aucune validation chiffrée du classement par les modèles | Moyenne |
| E12 | Documentation technique, page de synthèse et vidéo absentes de l'archive | Bloquant |

---

## 4. Plan proposé

Principe : corriger d'abord ce dont le moteur dépend, dans l'ordre des dépendances, avec un critère de fin vérifiable à chaque étape. Chaque étape se termine par les 6 tests existants, qui doivent rester verts. Rien n'est publié sur le site sans accord explicite.

### Étape 0. Cadrage (aucun code)

- Obtenir les décisions de la section 5, l'énoncé PDF et PPTX, et `scripts/audit_criteres.py`.
- Écrire les trois personas en JSON (`config/personas/amira.json`, etc.) à partir de l'énoncé, pas des suppositions des audits. Ils servent ensuite de tests et de démonstration.
- **Terminé quand** : chaque décision a une réponse, et les trois fichiers de personas sont relus par l'équipe.

### Étape 1. Une seule source de vérité pour les critères

- Fichiers : `mvp_profil/criteres.py`, `config/criteres_appariement.csv`, nouveau `config/correspondances.json`, nouveau `mvp_profil/test_grille.py`.
- Harmoniser les valeurs (A2, A8, C1, D3, G2, C2), un seul identifiant D8O, ajouter B1R à la grille. Garder le score 0 à 3 du quiz en plus du niveau.
- Écrire les tables de correspondance : thème du profil → colonnes et valeurs d'actif ; secteur d'emploi → secteurs GICS ; région → pays et place de cotation ; E1 et E5 → colonnes ESG. Une valeur sans actif est marquée « aucun actif de l'univers ».
- Ajouter à la grille une colonne de règle exécutable (opérateur, colonne, valeurs), la phrase restant pour l'affichage.
- **Terminé quand** : un test échoue si une valeur du profil n'a ni correspondance ni mention « aucun actif », et si une valeur diffère entre le code et la grille.

### Étape 2. Corriger les données des actifs

- Fichiers : `scripts/compute_metrics.py`, `scripts/build_asset_criteria.py`, `scripts/fetch_extra_data.py`, `scripts/build_esg.py`, `config/seuils_criteres.json`, puis régénération de `asset_criteria.csv`, `vocabulaire_actifs.json`, `donnees_chercheur.json` et `scenarios.json`.
- Priorité 1 (bloque le moteur) : durée sous l'eau du sommet au retour et étiquette `baisse_en_cours` ; rôles redéfinis ; test spéculatif avant revenu ; liquidité des FNB ; complexité ; étiquettes multiples de risque pays ; secteurs des FNB obligataires ; `fossil_involvement` scindé en catégorie et part d'énergie ; pays réel pour les 29 actifs nord-américains.
- Priorité 2 (biaise un critère) : dividendes spéciaux ; ratio de distribution des services publics ; rentabilité de MFC ; emballement médiatique relatif à l'actif ; condition de baisse pour « diversifiant » ; colonne `adr_us` vérifiée titre par titre.
- La régénération ne doit pas retélécharger les prix : les valeurs Yahoo changent à chaque téléchargement, et tous les chiffres déjà vérifiés bougeraient.
- **Terminé quand** : un test de non-régression vérifie des cas nommés. NVDA : 535 jours sous l'eau. TLT n'est plus dans le même rôle que ZST. ZST : liquidité élevée, complexité 1. NOVO et GFI : spéculatifs. VWO : `marche_emergent`. BNDW : aucun poids sectoriel. MFC : rentable. Les 14 « non récupérés » deviennent 1 `jamais_recupere` et 13 `baisse_en_cours`.

### Étape 3. Corriger la logique du profil

- Fichiers : `mvp_profil/profil.py`, `simulations.py`, `criteres.py`, `app.py`, `test_profil.py`, `test_app.py`.
- Conserver séparément le point de rupture déclaré, l'observé et le retenu. Le retenu est toujours le plus prudent, recalculé après chaque correctif (corrige B1 et B4).
- B2 fixé seulement par « Tout vendre » ; « Réduire » devient un signal distinct. Afficher la perte réelle, pas la classe. Remplacer « non atteint » par « non contredit jusqu'à −X % » (corrige B3, B5).
- Les correctifs de cohérence ne posent plus de valeur inventée : ils renvoient le critère en question de précision (corrige B2). Corriger R3 (B10).
- Portefeuille du replay choisi sur le risque et l'horizon déclarés, sans le thème (B6).
- Effet de mode : faits neutres et comparables, sans étiquette de jugement (B11).
- Définir la table des réglages prudents par défaut pour chaque critère incertain (H3), dans `config/`.
- Ajouter les critères retenus à l'étape 0 (au minimum G1, D11, A1 ; D9 et G3 avec un défaut).
- **Terminé quand** : un test rejoue le cas « réduit à −5 %, puis R1b » et le point de rupture retenu reste 5 ; aucune entrée du profil n'a une valeur absente des réponses ; chaque critère incertain a un réglage par défaut écrit.

### Étape 4. Synthèse du profil : capacité, tolérance, budget de risque

- Fichiers : `mvp_profil/profil.py`, `config/seuils_criteres.json`, `app.py` (page finale et export), nouveau test.
- Fonction déterministe : capacité (A1, A2, A4, A5, A6, A8, A9), garde-fou A7, tolérance déclarée (B1, B1R, B5, B7), tolérance observée (B2, B6, D8O), budget de perte final = le plus prudent.
- La page finale indique quelle composante a limité le résultat, avec les critères en cause.
- Toutes les tables sont déclarées comme hypothèses, avec leur origine.
- **Terminé quand** : les trois personas obtiennent trois budgets distincts, ordonnés Robert < Mateo < Amira, et un test le vérifie. Changer une seule réponse de capacité change le budget dans le sens attendu.

### Étape 5. Préparer la recommandation de portefeuille (spécification, sans réalisation)

Livrable de cette étape : un document de conception court, validé avant tout code.

- **Contrat d'entrée et de sortie** du moteur : profil synthétisé et critères dynamiques en entrée ; en sortie, exclusions motivées, poids, contrôles et valeurs calculées que l'explication a le droit de citer.
- **Mesure de risque du portefeuille** : fonction unique (volatilité, perte maximale, durée sous l'eau, expositions effectives à travers les FNB), reprise des calculs que j'ai refaits pour cet audit.
- **Stress au-delà de 2022** : deux scénarios déclarés au minimum (krach boursier, choc de taux), et si possible un historique long de quelques FNB. Chaque paramètre est sourcé ou étiqueté « hypothèse ».
- **Demande ponctuelle (Robert)** : poids maximal compatible, avec la borne simple et explicable de l'audit.
- **Critères de réussite fixés d'avance**, tirés des personas : Robert obtient un portefeuille qui contient des actions et respecte son budget ; Mateo n'a aucune énergie directe et XIU est plafonné ; Amira ne dépasse pas le plafond de technologie en exposition effective.
- **Explication** : rédigée seulement à partir des valeurs calculées, avec un contrôle qui rejette toute phrase contenant un chiffre absent de la sortie du moteur.
- **Sensibilité** : une hypothèse, un scénario et un critère de profil modifiés, avec l'effet affiché.
- **Terminé quand** : le document est validé et les arbitrages de la section 5 y figurent.

### Étape 6. Conformité et présentation (peut se faire en parallèle des étapes 3 à 5)

- Fichiers : `README.md`, `SECURITY.md`, `.env.example`, `mvp_profil/DEPLOIEMENT.md`, `app.py`.
- Réécrire la section sécurité selon l'architecture réelle ; retirer l'identifiant du compte et les IP du dépôt ; corriger le nombre d'IP.
- Vue par défaut : une ligne par critère (valeur, citation, source, confiance, statut). Le détail des échanges passe dans un journal de contrôle replié.
- Bandeau « simulation éducative » sur chaque page ; étiquettes fait, hypothèse, scénario fictif.
- Bouton de chargement d'un persona, à partir des fichiers de l'étape 0.
- Retirer des documents les tableaux de verdicts non reproductibles (H6) ou les régénérer par un script versionné.
- **Terminé quand** : aucune phrase du README ne décrit un service absent ; un persona se charge en un clic ; les tests d'interface passent.

### Étape 7. Validation et livrables

- Jeu de phrases étiquetées et mesure du classement (taux de bon classement, fausses validations, répétabilité), contre le vrai modèle, pour appuyer ou corriger l'affirmation H2.
- Documentation technique, page de synthèse, vidéo. Elles dépendent du moteur : à planifier dès maintenant, à produire en dernier.

### Dépendances

```
0 cadrage ─▶ 1 vocabulaire ─▶ 2 données ─▶ 4 synthèse ─▶ 5 spécification du moteur ─▶ (moteur) ─▶ 7 livrables
                    └────────▶ 3 logique du profil ─┘
6 conformité et présentation : en parallèle à partir de l'étape 1
```

---

## 5. Décisions à prendre avant d'exécuter

| # | Décision | Ma recommandation |
|---|---|---|
| 1 | **Temps restant avant la remise.** Il détermine tout le périmètre. | Si le délai est court : étapes 1 à 4 réduites au strict nécessaire, puis le moteur. Un profil parfait sans portefeuille ne répond pas à l'énoncé. |
| 2 | Échelle du profil : classe 1 à 7 ou niveau 1 à 5 avec budget de perte | 5 niveaux avec budget de perte. La classe 1 à 7 reste un descripteur d'actif. |
| 3 | Risque jugé par actif ou sur le portefeuille | Portefeuille. Par actif : exclusions et poids maximal compatible. |
| 4 | B2 : « Réduire de moitié » compte-t-il comme un point de rupture ? | Non. Seul « Tout vendre » le fixe ; « Réduire » reste un signal. |
| 5 | Règle de poids : simple (poids égaux ou inverse de la volatilité) ou remplissage avec score | Commencer par la règle simple, plus facile à expliquer au jury. Le score vient après, s'il reste du temps. |
| 6 | Stress hors 2022 : scénarios hypothétiques, historique long, ou les deux | Les deux. L'historique long demande un nouveau téléchargement : à confirmer. |
| 7 | Univers : garder les 66 actifs dans la démonstration, ou se limiter au jeu de départ et aux FNB mondiaux | Garder les 66 en données, limiter la démonstration à ce qui est accessible depuis le Canada (G3 par défaut : Canada et États-Unis). |
| 8 | Questions à ajouter et à retirer | Ajouter G1, D11, A1. D9 et G3 par défaut, modifiables. Ne plus poser A11, C3, E3, G4, G5, D10. |
| 9 | Source de vérité : `criteres.py` ou le CSV | `criteres.py` génère le CSV. |
| 10 | AWS : ajouter Glue, Athena et Quick, ou rester sur l'existant plus S3 pour les données et les traces | Rester sobre. N'ajouter Athena que si chaque chiffre affiché porte réellement l'identifiant de sa requête. |
| 11 | Chercheur et conversation vocale : geler ? | Oui, geler. |
| 12 | Correctifs de cohérence : accepter de reposer une question plutôt que d'écrire une valeur par défaut | Oui, quitte à allonger un peu les précisions. |
| 13 | Référence de la classe de risque : SRRI européen ou méthode canadienne | À trancher après vérification ; sans effet sur le reste du plan. |
| 14 | Publication : qui donne l'accord avant chaque mise en ligne du site partagé ? | Aucune publication sans accord explicite, à chaque fois. |

## Sources consultées pour la vérification externe

- [Institut de planification financière : Normes d'hypothèses de projection 2026](https://institutpf.org/en/communique/linstitut-de-planification-financiere-et-fp-canada-et-publient-les-normes-dhypotheses-de-projection-2026)
- [Communiqué FP Canada et IPF, 16 avril 2026](https://www.newswire.ca/news-releases/fp-canada-tm-and-the-institute-of-financial-planning-jointly-publish-the-2026-projection-assumption-guidelines-for-financial-planners-804319758.html)
- [Investment Executive : mise à jour des hypothèses de rendement](https://www.investmentexecutive.com/news/fp-canada-institute-of-financial-planning-update-guidelines-on-expected-returns-add-shelter-projection/)
