# Point d'étape : écarts avec les consignes et incohérences du projet

Version du 14 novembre 2026, branche `feat/profil-donnees-streamlit` (commit `47f6cd2`).
Référence : énoncé officiel « Datathon 2026 – AWSome AI » (PDF FR) et présentation aux participants (PPTX).

Ce document liste les problèmes trouvés en confrontant le dépôt aux consignes. Pour chacun : ce qui ne va pas, où, la preuve, l'impact et la correction proposée. Les six tests hors ligne de `mvp_profil/` passent tous ; les problèmes ci-dessous sont des écarts de démarche ou de cohérence, pas des tests qui échouent.

---

## Résumé

| # | Problème | Gravité | Effort |
|---|---|---|---|
| 1 | Aucun résultat : ni appariement, ni portefeuille, ni explication finale | **Bloquant** | Élevé |
| 2 | Les trois tests des personas ne sont pas démontrables | **Bloquant** | Découle de 1 |
| 3 | Grille `config/` et code du profil n'utilisent pas les mêmes valeurs | Élevée | Faible |
| 4 | 12 critères de la grille ne sont jamais demandés, dont ceux des personas | Élevée | Moyen |
| 5 | Thèmes du profil ≠ thèmes des actifs | Élevée | Faible |
| 6 | Durée de récupération mesurée depuis le creux, pas depuis le sommet | Élevée | Faible |
| 7 | Horizon minimal pénalise les titres défensifs qui n'ont pas retrouvé leur sommet | Moyenne | Faible |
| 8 | Classe de risque peu discriminante actif par actif | Moyenne | Découle de 1 |
| 9 | Le replay rend le profil plus prudent qu'il ne faut | Moyenne | Faible |
| 10 | Le test de l'effet de mode se devine | Faible | Faible |
| 11 | La trace complète des débats entre modèles est exposée | Moyenne | Faible |
| 12 | Section sécurité du README fausse | Moyenne | Faible |
| 13 | Parcours trop long pour la démonstration, pas de personas préchargés | Élevée | Moyen |
| 14 | Pas de test de sensibilité | Moyenne | Moyen |
| 15 | Périmètre : complexité qui ne sert pas les personas | Moyenne | — |
| 16 | Livrables absents | **Bloquant** | Moyen |

---

## A. Écarts avec les consignes

### 1. Aucun résultat d'investissement n'est produit

**Consigne.** « Un prototype démontrable présentant un cas d'utilisation complet et une explication accessible du résultat : sources, hypothèses, principaux facteurs et limites » (p. 15). « Le jury doit comprendre ce que fait la solution et ce qui justifie ses résultats » (p. 16).

**Constat.** Le parcours s'arrête au profil (`page_termine` dans [app.py](../mvp_profil/app.py)). Le README le dit lui-même : « APPARIEMENT (à construire) » ; les étapes 1 (moteur d'appariement) et 2 (portefeuille et explication) de la feuille de route ne sont pas faites. Le profil est un moyen, pas le résultat attendu.

**Impact.** Les critères « Qualité et pertinence de la solution » (20 %), « Intelligence agentique et explicabilité » (20 %) et une partie de « Capacité d'analyse » (20 %) reposent sur ce résultat. Aujourd'hui l'outil n'explique aucune conclusion d'investissement, puisqu'il n'en produit pas.

**Correction.** Construire en priorité :
1. un moteur d'appariement déterministe qui lit `config/criteres_appariement.csv` et les critères dynamiques : exclusions → plafonds → seuils → préférences ;
2. une allocation fictive simple au niveau du **portefeuille** (voir problème 8) ;
3. un agent d'explication qui rédige **uniquement à partir des verdicts calculés**, chaque phrase reliée à sa source.

### 2. Les tests des trois personas ne sont pas démontrables

**Consigne.** Chaque persona teste une capacité précise (p. 5 à 7, diapo 4).

| Persona | Ce qui est testé | État actuel |
|---|---|---|
| Amira | « Risque élevé » ≠ « tout est acceptable » ; garder la diversification, ne pas miser exclusivement sur la technologie | Pas de portefeuille, donc pas de diversification à montrer. D9 (concentration) et D10 (diversification) ne sont pas demandés |
| Mateo | Intégrer autre chose que rendement et risque (ESG, controverses) | E1, E2, E5 sont demandés et les données ESG existent, mais rien ne les applique aux actifs |
| Robert | Remettre en question une demande incohérente avec le profil, expliquer le risque, ne pas acquiescer | Aucun parcours où Robert **demande** un titre. Le test de l'effet de mode (D8O) mesure un attrait, il ne répond pas à une demande |

**Correction.**
- Robert : ajouter un parcours « demande d'un titre précis » (critère H2 de la grille) : « Je veux mettre 20 % dans NVDA » → verdict figé avant de lire la justification, critères en tension cités, alternative proposée (plafond à 5 %, ou FNB).
- Amira : plafonds par titre et par secteur, plafond plus bas sur son secteur d'emploi (A12), contrôle de la corrélation moyenne du portefeuille.
- Mateo : appliquer E1, E2, E5 et montrer le désaccord entre méthodes (Enbridge et CNQ dans l'indice Jantzi, critère E4).

### 11. La trace complète des débats entre modèles est exposée

**Consigne.** Les explications doivent rester « synthétiques, vérifiables et fidèles aux sources et aux actions observables, sans inventer de justification ni **exposer les raisonnements internes détaillés des modèles** » (p. 17).

**Constat.** `Debat.tours` est décrit comme « trace complète, affichée à l'utilisateur » ([agents.py](../mvp_profil/agents.py)) et le JSON exporté contient « la trace des débats » (README, section 6).

**Correction.** Montrer à l'utilisateur ce qui est vérifiable : valeur retenue, citation exacte, source, contrôles passés (valeur autorisée, citation trouvée, accord du critique, seuil). Garder la trace complète dans un journal d'audit séparé (fichier ou CloudWatch), présenté comme tel.

### 13. Parcours trop long pour la démonstration, pas de personas préchargés

**Consigne.** Vidéo d'environ 5 minutes « montrant un exemple de bout en bout » ; « une comparaison de deux situations d'investisseurs contrastées peut illustrer l'adaptabilité » (p. 8 et 15, diapo 4 : « démontrez au moins deux situations contrastées »).

**Constat.** Le parcours complet enchaîne conversation, compléments, trois mises en situation, précisions et question ouverte. Il est impossible de le faire deux fois en 5 minutes, et la démonstration dépendrait d'appels aux modèles non déterministes.

**Correction.** Ajouter un bouton « Charger Amira / Mateo / Robert » qui remplit le profil (fichier JSON versionné), puis une vue qui compare deux profils côte à côte sur les mêmes actifs. Cela rend aussi la démonstration reproductible et évite de saisir de vraies données personnelles (consigne « Protection des renseignements », p. 14).

### 14. Pas de test de sensibilité

**Consigne.** « Mettre les résultats à l'épreuve : étudier leur sensibilité à des hypothèses, données ou scénarios différents » (p. 8) ; « Changez une hypothèse. Changez un scénario. Changez un profil. Est-ce que votre solution reste cohérente ? » (diapo 8).

**Constat.** Tous les seuils sont centralisés dans [seuils_criteres.json](../config/seuils_criteres.json) et déclarés comme hypothèses, ce qui est bien, mais rien ne montre l'effet de leur variation sur un verdict.

**Correction.** Une fois le moteur fait : faire varier un seuil (par exemple la borne « spéculatif » à 40 % ou 50 % de volatilité) ou un scénario (choc de 2022), et afficher quels verdicts changent et pourquoi.

### 15. Périmètre : de la complexité qui ne sert pas les personas

**Consigne.** « La sophistication technique et le nombre d'agents ne sont pas des fins en soi » (p. 8) ; « Évitez la complexité décorative » et « Pourquoi cet agent existe-t-il et quelle valeur apporte-t-il ? » (diapo 5) ; « Ne multipliez pas les services pour impressionner » (diapo 7).

**Constat.**
- Le chercheur (Wikipédia, « Elon Musk ») et la conversation vocale sont réussis, mais aucun persona n'en a besoin, alors que la sortie attendue n'existe pas.
- 35 actifs ont été ajoutés (Europe, Asie, Afrique). 24 actifs de l'univers ne sont accessibles que par un courtier international (`access_canada = courtier_international`). Les actions africaines ont demandé plusieurs corrections (sous-unités, prix 100 fois trop petits, faux fractionnement de Naspers), et 9 sur 10 sont sud-africaines faute de couverture. La consigne autorise d'autres actifs « à condition d'en expliquer la pertinence » (p. 10) : cette justification n'est écrite nulle part.

**Correction.** Geler la partie profil. Présenter le chercheur comme un bonus. Écrire en une phrase pourquoi l'univers étendu sert un investisseur canadien, ou le laisser hors de la démonstration.

### 16. Livrables absents

**Consigne.** Quatre livrables (p. 15-16) : prototype et code avec README, vidéo d'environ 5 minutes, documentation technique, page de synthèse (une page).

**Constat.** Seuls le prototype et le README existent. La documentation technique doit notamment contenir « un exemple reliant une conclusion aux données ou aux traces d'exécution observables » et « les validations des résultats et des explications » : impossible tant qu'il n'y a pas de conclusion (problème 1).

---

## B. Incohérences entre la grille et le code

### 3. La grille `config/` et le code du profil n'utilisent pas les mêmes valeurs

[criteres.py](../mvp_profil/criteres.py) affirme que ses identifiants « sont ceux de config/criteres_appariement.csv », mais les valeurs diffèrent :

| Critère | `criteres_appariement.csv` | `criteres.py` |
|---|---|---|
| A2 Horizon | `court (<3 ans), court_moyen (3-5), moyen (5-10), long (10-15), tres_long (>15)` | `moins_3_ans, 3_5_ans, 5_10_ans, 10_15_ans, plus_15_ans` |
| A8 Personnes à charge | `0, 1-2, 3+` | `0, 1_2, 3_plus` |
| C1 Connaissances | Score 0 à 3 ; règle « complexité ≤ score + 1 » | `debutant, intermediaire, avance` : les scores 0 et 1 donnent tous deux `debutant` (`niveaux` du quiz), la règle ne peut pas s'appliquer telle qu'écrite |
| D3 Régions | `canada, amerique_du_nord, monde, emergents_ok, regions_exclues` | `canada, etats_unis, europe, asie, afrique, emergents, monde` |
| D8O / D13 | `D13` (« D8O dans le MVP ») | `D8O` |
| B1R | absent | présent (réaction déclarée à une baisse de 20 %) |
| G2 | `celi, reer, non_enregistre` | ajoute `ne_sait_pas` |
| C2 | `aucun, fnb, actions, obligations, crypto` | ajoute `fonds_communs` |

La documentation est aussi incohérente sur le type de règle : `docs/criteres_profil_actifs.md` présente B5 comme une comparaison de classe, le CSV le type `plafond` ; D8 est décrit comme « avertissement » mais typé `plafond`.

**Impact.** Le futur moteur lira le CSV : il ne reconnaîtra pas les valeurs produites par le profil.

**Correction.** Faire du CSV (ou de `criteres.py`) la source unique, et ajouter un test qui vérifie que, pour chaque critère commun, les valeurs sont identiques.

### 4. 12 critères de la grille ne sont jamais demandés

Critères présents dans `criteres_appariement.csv` mais absents de `CRITERES` :

| Critère | Pourquoi il compte |
|---|---|
| **D9** Concentration (poids max par titre) | Test d'Amira (diversification) |
| **D10** Importance de la diversification | Test d'Amira |
| **C3** Comprendre le modèle d'affaires | Robert « préfère les placements dont il comprend bien le modèle d'affaires » |
| **G1** Montant investi | Nécessaire pour construire un portefeuille et pour l'avertissement prix unitaire |
| A1 Âge et étape de vie | Cohérence de l'horizon (Robert pré-retraite) |
| A11 Patrimoine hors portefeuille | Capacité de perte |
| E3 Priorité E, S ou G | Mateo |
| F1 Inquiétude inflation et taux | Robert |
| G3 Accès aux bourses étrangères | Indispensable vu les 24 actifs « courtier international » |
| G4 Frais acceptés | Plafond sur les FNB |
| G5 Temps de suivi | Préférence FNB |
| D11 Fonds indiciels ou titres | Préférence |

**Correction.** Ajouter au moins D9, D10, C3 et G1 ; pour les autres, soit les ajouter, soit les retirer de la grille et le documenter. Attention : le parcours est déjà long (problème 13) ; des personas préchargés évitent d'allonger la démonstration.

### 5. Les thèmes du profil ne correspondent pas aux thèmes des actifs

`THEMES` (profil, D5 et D6) : `ia, semi-conducteurs, logiciel, sante, energie_fossile, banque, assurance, luxe, vehicule_electrique, or, crypto, dividendes, consommation, infrastructures, telecoms, immobilier, armes, tabac, alcool, jeux_argent`.

Colonne `themes` de `asset_criteria.csv` : `pharmacie`, `petrole;gaz`, `pipelines;infrastructures`, `supermarches`, `produits_menagers`, etc.

| Valeur du profil | Problème |
|---|---|
| `sante` | les actifs disent `pharmacie`, `dispositifs_medicaux` |
| `energie_fossile` | les actifs disent `petrole`, `gaz`, `sables_bitumineux`, `pipelines` |
| `consommation` | les actifs disent `supermarches`, `produits_menagers`, `alimentation`… |
| `dividendes` | n'est pas un thème d'actif (c'est `income_asset` / `kw_rendement_dividende`) |
| `immobilier`, `armes`, `tabac`, `jeux_argent` | aucun actif concerné |

**Impact.** Une exclusion D6 « energie_fossile » ou une préférence D5 « sante » ne trouverait aucun actif par simple comparaison. Mateo pourrait se croire protégé alors que rien n'est filtré.

**Correction.** Une table de correspondance explicite (thème du profil → liste de thèmes ou de colonnes d'actif), versionnée dans `config/`, avec un test qui vérifie que chaque thème du profil touche au moins un actif ou est signalé « aucun actif concerné ».

---

## C. Problèmes de calcul dans les données

### 6. La durée de récupération est mesurée depuis le creux, pas depuis le sommet

**Où.** [compute_metrics.py:80](../scripts/compute_metrics.py:80) : `recovery_days = (rec.index[0] - trough).days`.

**Preuve.**

| Actif | Perte maximale | `recovery_days` | `kw_recuperation` |
|---|---|---|---|
| NVDA | −63 % | 216 | `rapide_moins_1_an` |
| JNJ | −16 % | 91 | `rapide_moins_1_an` |
| TSLA | −71 % | 702 | `moyenne_1_2_ans` |

NVDA a mis environ un an et demi à retrouver son sommet de fin 2021, mais elle sort en « récupération rapide », comme JNJ.

**Impact.** La question B7 porte sur le temps passé sous l'eau (« combien de temps pourriez-vous attendre que votre placement retrouve sa valeur »). Avec le calcul actuel, un titre très volatil peut paraître cohérent avec un profil qui ne supporte qu'un an de baisse.

**Correction.** Mesurer du sommet précédant la pire baisse jusqu'au retour à ce sommet (durée sous l'eau), voire la plus longue durée sous l'eau de la période. Puis relancer `build_asset_criteria.py`, `build_vocabulaire.py` et `build_donnees_chercheur.py`.

### 7. L'horizon minimal pénalise les titres défensifs qui n'ont pas retrouvé leur sommet

**Où.** [build_asset_criteria.py:168](../scripts/build_asset_criteria.py:168) : +2 ans si `recovery_days` est vide.

**Preuve.** PG, Nestlé (NESN.SW), GLD et TLT ont un horizon minimal de **9 ans**, contre 7 pour SPY. Leur pire baisse est simplement encore en cours à la fin de la fenêtre de 5 ans.

**Impact.** Les « entreprises établies, stables et de qualité » que recherche Robert ressortent plus en tension qu'un indice large : résultat contre-intuitif que le jury remarquera.

**Correction.** Ne pas confondre « pas encore récupéré à la date de fin des données » et « long à récupérer » : pondérer par la profondeur de la baisse en cours (`current_drawdown`) ou signaler « baisse en cours » comme information, sans allonger l'horizon. Vérifier aussi les cas GLD et TLT dans les données.

### 8. La classe de risque ne départage presque rien quand on juge actif par actif

**Preuve.** Répartition de `risk_class` sur les 66 actifs : classe 7 = 37, classe 6 = 22, classe 5 = 3, classe 4 = 3, classe 2 = 1. Les bandes de volatilité sont celles du SRRI, ce qui est défendable, mais 59 actifs sur 66 se retrouvent dans les deux classes les plus élevées. Le test de `docs/criteres_profil_actifs.md` en tire déjà la conséquence : Robert a 55 actifs « en tension » et seuls les FNB obligataires passent.

**Impact.** Juger chaque actif seul contre B5 ou A2 ne distingue pas un SPY à 30 % d'un SPY à 100 %.

**Correction.** Faire porter les règles de risque (B1, B5, A2) sur le **portefeuille** : volatilité et perte de stress du portefeuille, pondérées par les poids. Les verdicts par actif ne servent qu'aux exclusions, aux plafonds et aux avertissements.

---

## D. Problèmes de méthode dans les mises en situation

### 9. Le replay rend le profil plus prudent qu'il ne faut

**Où.** [simulations.py](../mvp_profil/simulations.py) (`replay`) et [profil.py:161](../mvp_profil/profil.py:161) (`recouper_rupture`).

**Constat 1 : « réduire » est assimilé à « vendre à coup sûr ».** La question B1 demande « À partir de quelle baisse vendriez-vous **à coup sûr** ? ». Dans le replay, la première action « Réduire de moitié » **ou** « Tout vendre » fixe B2. Si B2 est plus prudent que B1, B1 est **remplacé** par B2. Une simple réduction de moitié écrase donc le point de rupture déclaré.

**Constat 2 : « non atteint » est pris pour une confirmation.** Le creux du portefeuille équilibré est de 8 386 $ pour 10 000 $ (−16 %), celui du portefeuille 100 % actions de 8 198 $ (−18 %). Une personne qui a déclaré −50 % et qui a tout gardé obtient `H1 = aucun` : sa tolérance n'a pas été testée au-delà de −16 %, mais l'écart est noté comme nul.

**Constat 3 (mineur).** Quand la personne tient **plus** longtemps qu'elle ne l'a déclaré, l'écart est toujours noté « faible », quel que soit le nombre de classes d'écart.

**Correction.**
- Ne fixer B2 que sur « Tout vendre » ; garder « Réduire » comme un signal distinct (par exemple une décote de confiance).
- Remplacer `non_atteint` par « non contredit jusqu'à −X % », avec X = creux du portefeuille montré, et ne pas en déduire `H1 = aucun` si B1 dépasse X.

### 10. Le test de l'effet de mode se devine

**Où.** [simulations.py](../mvp_profil/simulations.py), `effet_de_mode`.

**Constat.** Les titres médiatisés portent la mention « 📣 On en parle partout », les autres « Entreprise établie, peu médiatisée ». La personne voit ce qui est mesuré et peut choisir la réponse « raisonnable » (biais de désirabilité sociale). Les quatre titres actuels sont NVDA, FTS.TO, TSLA et RY.TO.

**Correction.** Afficher des faits neutres et comparables pour les quatre titres (rendement sur 3 mois, volatilité, perte maximale, dividende, niveau d'attention chiffré) sans étiquette qui porte un jugement.

---

## E. Documentation

### 12. La section sécurité du README décrit une infrastructure qui n'existe pas

**Où.** [README.md](../README.md), sections « Security and collaboration » et « Local setup » (ajoutées par les commits de base de sécurité), et [.env.example](../.env.example).

**Constat.**
- Le README mentionne AWS Lambda, Secrets Manager et un déploiement par GitHub Actions avec OIDC. Le déploiement réel est EC2, S3, Session Manager et CloudFront ([DEPLOIEMENT.md](../mvp_profil/DEPLOIEMENT.md)).
- `.env.example` déclare `FINANCIAL_DATA_API_KEY`, utilisée nulle part.
- Ces sections sont en anglais, le reste du dépôt en français.

**Impact.** Le jury lit le README (livrable 1) et note la qualité de l'intégration AWS (15 %). Une description fausse de l'architecture nuit à la crédibilité.

**Correction.** Réécrire ces sections pour décrire l'architecture réelle (rôle IAM de l'instance, filtrage IP par CloudFront, aucune clé dans le dépôt), en français, et retirer la variable inutilisée.

---

## Ordre de traitement proposé

1. **Corrections rapides qui conditionnent le moteur** : problèmes 3, 5 et 6 (vocabulaires alignés, table des thèmes, durée sous l'eau), puis régénération des fichiers.
2. **Moteur d'appariement au niveau du portefeuille** (problèmes 1 et 8), avec les critères manquants indispensables (problème 4 : D9, D10, C3, G1).
3. **Parcours de Robert « demande d'un titre »** et **agent d'explication** (problème 2).
4. **Personas préchargés et comparaison côte à côte** (problème 13), puis **test de sensibilité** (problème 14).
5. **Ajustements de méthode et de présentation** : problèmes 7, 9, 10, 11, 12.
6. **Livrables** : documentation technique, page de synthèse, vidéo (problème 16).
