# AWSome AI — analyse et plan de la partie recommandation

15 novembre 2026. Aucun code écrit, aucun fichier du profil modifié. Simulation éducative : rien ici n'est un conseil financier.

Ce document contient l'étape 1 (analyse) et l'étape 2 (plan), écrits avant le code sur l'univers à 66 actifs. **Le plan a été réalisé le 15 novembre sur l'univers à 111 actifs, puis intégré au site comme quatrième étape (`mvp_profil/recommandation/`) : l'état réel est dans `docs/documentation_technique.md`.** Écarts avec le plan : pas de lanceur séparé, Lambda et X-Ray non retenus, Cognito créé mais non branché.

---

# ÉTAPE 1 — ANALYSE

## 1.1 Ce que j'ai lu et vérifié

| Source | État |
|---|---|
| Consignes officielles (PDF, 19 pages) | Lues en entier |
| Fichier de contexte | Lu en entier |
| README racine, `docs/criteres_profil_actifs.md`, `docs/audit_et_plan.md`, `docs/plan_et_suivi.md` | Lus en entier |
| `config/criteres_appariement.csv`, `correspondances.json`, `seuils_criteres.json`, `hypotheses_profil.json` | Lus en entier |
| `mvp_profil/profil.py`, `synthese.py`, `criteres.py`, les trois personas | Lus en entier, exécutés |
| `data_extended/asset_criteria.csv` | Chargé, colonnes et valeurs manquantes comptées |
| Autres docs (`point_problemes`, `analyse_revue`, `corrections_revue`, `infrastructure_profil`, `DEPLOIEMENT`, README de données) | Titres et passages utiles seulement |
| `app.py`, `agents.py`, `entretien.py`, `chercheur.py`, `criteres_dynamiques.py`, `simulations.py` | Lus par recherche ciblée (statuts, export, applicabilité), pas ligne par ligne |
| Compte AWS | Inventaire en lecture seule, puis tests de création/suppression (section 1.6) |

**Non reçu** : les trois `.docx` (catalogue, tableau des 69 critères, journal de justification) et la « doc partagée ». Je prends donc `config/criteres_appariement.csv` et `mvp_profil/criteres.py` comme liste de référence. Le contexte parle de « 69 critères » dans le tableau officiel ; le dépôt en a 51 dans la grille : l'écart ne peut pas être contrôlé sans ce fichier.

## 1.2 Ce qui existe réellement

| Élément | Constat vérifié |
|---|---|
| Profil | 42 critères fixes à listes fermées (`criteres.py`), plus des critères dynamiques X1, X2… |
| Synthèse du profil | `synthese.synthetiser(profil)` existe et fonctionne : budget de perte, niveau 1 à 5, plafonds, alertes, réglages prudents, réponses décisives, robustesse |
| Personas | Trois fichiers JSON chargeables. Budgets recalculés : Robert 15 %, Mateo 22 %, Amira 45 % |
| Actifs | 66 actifs × 109 colonnes, dont 23 colonnes `kw_*` |
| Grille d'appariement | 51 lignes. Types : plafond 11, calcul_capacite 9, preference 9, exclusion 7, information 6, seuil 5, controle 4 |
| Correspondances de vocabulaire | `config/correspondances.json` : thèmes, régions, classes, secteur d'emploi, E1, E5, F2, G3 |
| Tests | 8 suites sur 18 passent ici. Les 10 autres échouent seulement parce que Streamlit et le SDK ne sont pas installés dans cet environnement (à installer à l'étape 3) |
| Moteur d'appariement, portefeuille, recherche, comparaison, « Et si… ? », agents de recommandation, gouvernance | **Absents.** Aucun code |

## 1.3 Écarts entre la documentation et le code

| # | Ce qui est écrit | Ce que montre le code ou le compte |
|---|---|---|
| 1 | Contexte : 33 critères, 29 questions, table de 50 critères, 100 colonnes | 42 critères, 51 lignes de grille, 109 colonnes. Le README racine, lui, est à jour |
| 2 | Contexte : états `INCONNU`, `INCERTAIN`, `NON_APPLICABLE`, `DONNÉE_MANQUANTE` | **Ces quatre états n'existent pas dans le code.** Les statuts réels sont `validé`, `retenu`, `incertain`, `à préciser`, `analyse en cours` (section 1.4) |
| 3 | « Appliquer les règles de `criteres_appariement.csv` » | La colonne `regle_appariement` est une phrase en français. Aucun moteur ne la lit : seuls `sync_grille.py`, `test_grille.py` et `build_asset_criteria.py` ouvrent le fichier. Il faut une traduction exécutable |
| 4 | Contexte : résultats de référence des personas (45/21/0/0, 18/6/22/20, 4/3/55/4) | Le script qui les a produits est absent. `audit_et_plan.md` (H6) dit déjà : non reproductible, à ne pas présenter au jury. Je ne m'en sers pas comme test de régression |
| 5 | Contexte, problème 3 : libellés divergents (`court (<3 ans)` contre `moins_3_ans`) | Déjà corrigé : `test_grille.py` passe (« 42 critères alignés »). Restent de petites différences d'écriture côté actifs (`fossil_involvement` = « non applicable » contre `fossil_categorie` = `non_applicable` ; `max_severity` avec accents) |
| 6 | Contexte, problèmes 2 et 6 : README qui annonce Lambda et Secrets Manager ; identifiants dans `DEPLOIEMENT.md` | Déjà corrigés dans l'archive : aucun identifiant de compte, d'instance ni d'IP trouvé. `DEPLOIEMENT.md` garde un schéma « HTTP 8501 » périmé |
| 7 | Grille D5 : une préférence « n'améliore JAMAIS la compatibilité » | La demande actuelle veut un score avec « préférences pondérées ». Les deux se concilient seulement si la préférence ne peut pas compenser une tension (section B du plan) |
| 8 | Synthèse : « un critère inconnu reçoit le réglage le plus prudent » | Vrai pour 14 critères (`reglages_prudents`). Pour les autres (E1, E2, E5, D1, D6, F2…), rien n'est prévu : c'est au moteur de les traiter explicitement |
| 9 | `stress_loss` présenté comme une mesure de stress | Identique à `max_drawdown` pour les 66 actifs. Une seule crise (2022) dans la fenêtre |
| 10 | Contexte : Athena écarté ; déploiement GitHub Actions « absent » | Le bucket contient `donnees/*.parquet` et des `athena-resultats/` datés d'aujourd'hui, et un rôle IAM `GitHubActions-AWSomeAIDeploy` existe. Rien de cela n'est dans l'archive : un coéquipier travaille peut-être en parallèle |
| 11 | Rôle IAM du serveur | Il n'autorise que Haiku 5.5. Sonnet 5.5, DynamoDB, Lambda et Guardrails demanderont une politique supplémentaire |

## 1.4 Contrat de données du profil

### Ce que le profil produit

La session Streamlit tient `S.profil` (critères fixes) et `S.dynamiques` (critères propres à la personne). L'export JSON contient : `profil`, `criteres_dynamiques`, `synthese`, `replay`, `debats`, `parcours`, `persona`, `version_application`, `modele`.

Une entrée de `profil` :

| Champ | Contenu |
|---|---|
| `valeurs` | Liste de codes de la liste fermée du critère (liste vide possible) |
| `source` | `QCM`, `curseur`, `quiz`, `réponse libre (IA)`, `réponse orale (IA)`, `déduit (IA)`, `déduction (règle)`, `cohérence`, `replay`, `fourchettes`, `test effet de mode`, `comparaison`, `énoncé`, `hypothèse de test` |
| `citation` | Phrase exacte de l'utilisateur, ou vide |
| `confiance` | 0 à 1 |
| `statut` | `validé`, `retenu`, `incertain`, `à préciser`, `analyse en cours` |
| `motif` | Justification courte |
| Champs en plus | `declare` (B1 avant le replay), `perte`, `reduction`, `baisse_max_montree` (B2) |

Seuls `validé` et `retenu` sont utilisables (`profil.UTILISABLES`). Pour un critère dynamique, il faut en plus `est_applicable(c)`.

La synthèse fournit déjà : `budget_perte_pct`, `niveau`, `limite_par`, `composantes_pct`, `volatilite_max_pct`, `duree_sous_eau_max_jours`, `plafonds` (crypto, titre, spéculatif), `acces`, `reglages_prudents_appliques`, `alertes`, `besoins_liquidite`, `reponses_decisives`, `robustesse`, `synthese_provisoire`.

### Correspondance proposée vers les quatre états demandés

Ces états seront calculés par une couche d'adaptation neuve, sans toucher au profil.

| État | Côté profil | Côté actif |
|---|---|---|
| `INCONNU` | Critère absent, `à préciser`, `analyse en cours`, ou `valeurs` vide | — |
| `INCERTAIN` | Statut `incertain`. Un `retenu` reste utilisable mais porte la mention « confiance réduite » | — |
| `NON_APPLICABLE` | Valeur neutre (`indifferent`, `aucun`, `aucune`, `non_requis`) | Colonne à `non_applicable` (frais d'une action, fossile d'un FNB obligataire…) |
| `DONNÉE_MANQUANTE` | — | Cellule vide (24 colonnes en ont), ou valeur du profil marquée `aucun_actif` dans `correspondances.json` |

### Ce que les personas ne contiennent pas

Chaque persona renseigne 22 ou 23 critères sur 42. Manquent pour les trois : A9, A10, B7, B1R, B2, H1, C2, D3, D4, D6, E5, F2, G1, G2. Conséquences mesurées :

- `synthese_provisoire` vaut `True` pour les trois (retraits et besoin de revenu non renseignés).
- B7 reçoit le réglage prudent « 365 jours sous l'eau ». Presque aucun portefeuille ne le respecte (le portefeuille 30 ZST / 40 XBB / 30 XEQT de l'audit reste 714 jours sous l'eau).
- Mateo et Robert n'ont pas D1 : aucune classe n'est refusée par déclaration. La crypto n'est écartée que par D2 = 0.
- Le montant investi (G1) est inconnu : la tension « en dollars » demande un montant fictif saisi à l'écran.

**À signaler sans le faire** : compléter B7, A9, A10 et G1 dans les fichiers de personas rendrait la démonstration plus nette. Ces fichiers sont dans `mvp_profil/`, donc je n'y touche pas.

## 1.5 Pondération par critère et par personne

Il n'y en a pas. La grille a un `type_regle` par critère et une colonne `personas` qui dit qui est concerné, sans poids chiffré. Les « poids » présents ailleurs sont des poids de portefeuille. Le score 0 à 100 demande donc une table de pondération nouvelle, déclarée comme hypothèse (section B).

## 1.6 AWS : inventaire et preuves

Région `us-east-1`, compte d'atelier, rôle `WSParticipantRole`. Chaque test ci-dessous a créé puis supprimé une ressource nommée `awsome-ai-test-perm-*`. Contrôle final : aucune ressource de test ne reste.

| Service | Test | Résultat |
|---|---|---|
| Bedrock, Sonnet 5.5 | `Converse` avec un outil déclaré | OK, le modèle demande l'outil (`tool_use`) |
| Bedrock, Haiku 5.5 | Idem | OK |
| Bedrock Guardrails | Création (sujet interdit, PII, ancrage), `ApplyGuardrail`, suppression | OK |
| DynamoDB | Table à la demande, écriture, lecture, suppression | OK |
| IAM | Création d'un rôle, politique en ligne, suppression | OK |
| Lambda | Création (Python 3.13, traçage X-Ray actif), invocation, suppression | OK, statut 200 |
| CloudWatch Logs | Groupe, flux, écriture, suppression | OK |
| X-Ray | Lecture des traces | OK. L'écriture directe n'a pas été testée ; le traçage actif de Lambda a été accepté |
| Cognito | Groupe d'utilisateurs créé puis supprimé | OK |
| CloudFormation | Pile minimale créée puis supprimée | OK. **CDK n'est pas initialisé** (pas de pile `CDKToolkit`) |
| AWS Budgets | Budget créé puis supprimé | OK |

Non testé : modification de la fonction CloudFront et du groupe de sécurité (elle toucherait le site en service), page de connexion hébergée Cognito, Knowledge Bases, AgentCore.

## 1.7 Ce qui manque pour la recommandation

1. Une couche qui transforme le profil en contraintes typées avec les quatre états.
2. Des règles d'appariement exécutables, reliées une à une aux lignes de la grille.
3. Une pondération du score, déclarée.
4. Les séries de prix en CAD chargées pour mesurer un portefeuille (volatilité, perte maximale, durée sous l'eau, 2022).
5. L'exposition effective à travers les FNB (10 premières positions et secteurs).
6. Un registre de preuves et la correspondance colonne → fichier source → date → conditions d'utilisation.
7. Le parcours « demande d'un titre » (Robert) avec verdict figé.
8. Les agents à outils, le vérificateur de fidélité, les contrôles de gouvernance.
9. Les écrans, l'accès du jury, le mode de secours.
10. Les livrables : doc technique, one-pager, script de vidéo.

---

# ÉTAPE 2 — PLAN

## Principes fixés pour tout le plan

- **Rien n'est écrit dans `mvp_profil/`.** Le nouveau code vit dans `recommandation/`, la nouvelle configuration dans `config/`, les tests dans `tests_recommandation/`.
- **L'univers n'est jamais codé en dur.** Le moteur lit `asset_criteria.csv` à chaque démarrage. Aucun ticker ni nombre d'actifs dans le code. Un test ajoute un actif fictif dans une copie du fichier et vérifie qu'il est évalué, cherché et comparé comme les autres.
- **Le code décide.** Un modèle ne produit jamais un verdict, un score, un poids ni un chiffre.
- **Tout seuil nouveau est écrit dans `config/hypotheses_recommandation.json`**, avec son origine (hypothèse d'équipe ou source citée).
- **Chaque phase se termine par ses tests exécutés et un résumé de trois lignes.**

## Calendrier (dimanche, remise du code à 23 h 59)

| Phase | Contenu | Durée visée | Fin visée |
|---|---|---|---|
| 0 | Contrat, adaptation, tests de libellés | 30 min | 13 h 00 |
| 1 | Profil dynamique et moteur d'appariement (A, B) | 1 h 30 | 14 h 30 |
| 2 | Mini-portefeuille (C) | 1 h 15 | 15 h 45 |
| 3 | Recherche, comparaison, « Et si… ? » (D, E, F) | 1 h | 16 h 45 |
| 4 | Agents, vérificateur, gouvernance (G, H) | 1 h 15 | 18 h 00 |
| 5 | Interface (J) | 1 h 30 | 19 h 30 |
| 6 | AWS et déploiement (I) | 1 h 15 | 20 h 45 |
| 7 | Tests de bout en bout, README, doc technique (K) | 1 h | 21 h 45 |
| Marge | Corrections, répétition de la démo | 2 h | 23 h 45 |

Si le retard dépasse une heure à 18 h : Lambda, X-Ray et CloudFormation sont abandonnés en premier (le moteur tourne alors dans le serveur), puis Cognito est remplacé par un code d'accès simple.

**Travail en parallèle pour les trois autres membres** : (1) essai du parcours vocal et répétition de la démo, (2) one-pager et script de vidéo à partir de la section K, (3) vérification des conditions d'utilisation des données et relecture des hypothèses.

---

## Phase 0 — Contrat et adaptation

| | |
|---|---|
| Fichiers créés | `recommandation/contrat.py` (types), `recommandation/chargement.py` (actifs, prix en CAD, positions des FNB, sources), `config/hypotheses_recommandation.json`, `config/sources_colonnes.json`, `tests_recommandation/test_contrat.py` |
| Entrée | Profil (session ou JSON exporté ou persona), fichiers de données |
| Sortie | `ProfilLu` : pour chaque critère, valeur, état parmi les quatre, source, citation, confiance. `Univers` : tableau des actifs validé |
| Tests | Les trois personas se chargent. Chaque valeur de profil utilisée par une règle existe dans `criteres.py` et a une correspondance ou une mention `aucun_actif`. Colonnes obligatoires présentes. Actif fictif ajouté : accepté. Ligne sans prix : marquée `DONNÉE_MANQUANTE` |
| Acceptation | Un test échoue si un libellé du profil n'a pas de pendant côté actif, ou si une colonne requise disparaît |

`config/sources_colonnes.json` relie chaque famille de colonnes à son fichier, sa source, sa date de collecte et ses conditions d'utilisation, à partir des trois fichiers `sources_*.csv` existants. C'est la base du registre de preuves.

## Phase 1 — A. Profil dynamique et B. Moteur d'appariement

### A. Profil dynamique

| | |
|---|---|
| Fichier | `recommandation/contraintes.py` |
| Entrée | `ProfilLu`, synthèse (`synthese.synthetiser`, appelée en lecture), critères dynamiques applicables |
| Sortie | `Contraintes` : exclusions dures, plafonds, budget de risque, préférences pondérées, liste des inconnus |

| Famille | Contenu | Critères |
|---|---|---|
| Exclusions dures | Classe refusée, thème refusé, controverse, fossile, activité, pays, accès, crypto à 0 %, spéculatif refusé, critère dynamique « exclure » | D1, D6, E2, E1, E5, F2, G3, D2, D12, X* |
| Plafonds | Par titre, crypto, spéculatif, secteur de l'emploi, hors CAD, fonds exposés au fossile ou aux émergents, complexité, critère dynamique « plafonner » | D9, D2, D12, A12, D4, E1, F2, C1, X* |
| Budget de risque | Budget de perte, volatilité maximale, durée sous l'eau maximale, composante qui limite | Synthèse (A2, A4 à A8, B1, B1R, B2, B3, B5, B6, B7) |
| Préférences | Thèmes, régions, style, revenu, FNB ou titres, critère dynamique « privilégier » | D5, D3, D7, A10, D11, A3, X* |

**Traitement des inconnus, sans valeur inventée :**

| Cas | Traitement | Affichage |
|---|---|---|
| Critère de risque inconnu avec réglage prudent prévu (14 critères) | Le réglage de `hypotheses_profil.json` s'applique, comme dans la synthèse | « Réglage prudent appliqué faute de réponse », jamais « votre réponse » |
| Critère d'exclusion inconnu (E1, E2, E5, D6, F2, D1) | Aucun filtre appliqué | « Non renseigné : aucun filtre appliqué sur ce point » |
| Préférence inconnue | Ne compte pas dans le score | « Non renseigné » |
| Valeur du profil sans actif (`aucun_actif`) | Aucun effet | « Ce filtre n'agit sur aucun actif de l'univers » avec la raison du fichier |

### B. Moteur d'appariement

| | |
|---|---|
| Fichiers | `config/regles_appariement.json` (règles exécutables, une par ligne de la grille), `recommandation/appariement.py`, `recommandation/preuves.py`, `tests_recommandation/test_appariement.py` |
| Entrée | `Contraintes`, `Univers`, montant fictif |
| Sortie par actif | Verdict, score 0 à 100, bande, poids maximal compatible, critères en tension, détail critère par critère, preuves, part des critères évalués |

**Règles exécutables.** Chaque entrée de `regles_appariement.json` porte l'identifiant de la grille (`D6`, `E2`…), son effet (`DURE`, `CALIBRAGE`, `PREFERENCE`, `INFORMATION`), la colonne d'actif, l'opérateur et la phrase d'origine pour l'affichage. Un test vérifie que chaque ligne de type exclusion, plafond, seuil ou préférence de la grille a une règle, ou une mention « non codée » avec sa raison (critères non posés : A11, C3, D10, E3, F1, G4, G5).

**Ordre d'application : `DURE` > `CALIBRAGE` > `PREFERENCE`.**

1. **`DURE`.** Une exclusion donne le verdict « exclu ». Le score n'est alors pas affiché comme une note : l'écran montre « exclu » et la règle en cause. Aucun score ne peut compenser.
2. **`CALIBRAGE`.** Le risque ne se juge pas actif par actif (59 actifs sur 66 dépassent 15 % de volatilité). Pour un actif seul, le moteur calcule le **poids maximal compatible** : le plus petit de (budget de perte ÷ perte maximale de l'actif) et des plafonds qui le concernent. Exemple de lecture : « au plus X % du portefeuille ». Un poids maximal sous un plancher (hypothèse : 2 %) donne « en tension ».
3. **`PREFERENCE`.** Chaque préférence satisfaite ajoute des points, pondérés.

**Score.** Score = 100 × somme(poids × note) ÷ somme(poids), sur les seuls critères évalués. Note : 1 (cohérent), 0,5 (à surveiller), 0 (en tension).

Pondération proposée (hypothèse d'équipe, fichier `hypotheses_recommandation.json`) :

| Élément | Poids de base |
|---|---|
| Critère de calibrage | 3 |
| Plafond | 2 |
| Préférence | 1 |

Pondération **selon la personne**, calculée par le code à partir de ses propres réponses : E4 (`prefere` × 1, `exige` × 2) pour les critères ESG ; A10 (`souhaite` × 1, `essentiel` × 2) pour le revenu ; D7 pour le style ; un critère dont la source est une citation validée garde son poids, un `retenu` est réduit (× 0,5). Chaque multiplicateur appliqué est affiché avec la réponse qui le déclenche.

**Règle qui concilie la grille et le score** : une préférence ne compense jamais une tension. Si un critère de calibrage ou un plafond est « en tension », le score est borné à 49 ; s'il est « à surveiller », à 69. Les préférences ne déplacent le score qu'à l'intérieur de sa bande.

**Bandes (hypothèse ajustable)** : 70 et plus « compatible » ; 50 à 69 « à examiner » ; moins de 50 « peu adapté » ; exclusion dure « exclu ».

**Données insuffisantes.** Si la part des critères évalués passe sous un seuil (hypothèse : 60 %), le verdict devient « données insuffisantes » et les colonnes manquantes sont listées.

**Preuve.** Chaque critère évalué produit une fiche : identifiant (`P-0001`…), ticker, colonne, valeur, date (dernière observation ou date de collecte), fichier, source, conditions d'utilisation. Côté profil : critère, valeur, source, citation, statut.

**Verdict figé (H2).** Pour une demande précise (titre et montant), le moteur calcule le verdict au niveau du portefeuille, l'enregistre avec son horodatage et son empreinte, puis seulement après transmet la justification de l'utilisateur au modèle. Le texte de la justification n'est pas un paramètre du moteur.

| Tests | Acceptation |
|---|---|
| Amira : BTC et ETH non exclus, plafonnés à 10 % | Passe |
| Mateo : tout actif à controverse « élevée » est exclu ; crypto et spéculatif exclus | Passe |
| Robert : crypto exclue ; NVDA non exclu mais poids maximal faible et score borné | Passe |
| Exclu avec toutes les préférences satisfaites : reste exclu | Passe |
| Même profil, même univers : résultat identique octet pour octet | Passe |
| Tableau des verdicts par persona produit par un script versionné | Remplace le tableau non reproductible |

## Phase 2 — C. Mini-portefeuille

| | |
|---|---|
| Fichiers | `recommandation/mesures.py` (risque d'un portefeuille), `recommandation/portefeuille.py`, `tests_recommandation/test_portefeuille.py` |
| Entrée | `Contraintes`, résultats du moteur, séries de prix en CAD, positions et secteurs des FNB, montant fictif |
| Sortie | Poids, mesures du portefeuille, tension, tableau des contraintes (valeur, limite, état, preuve), actifs écartés et raison |

**Mesures, calculées sur les séries en CAD de 2021-11-12 à 2026-11-12 :** volatilité annualisée, perte maximale, durée sous l'eau, rendement de 2022, exposition effective par secteur, devise, région et titre à travers les FNB.

**Perte de stress** = la pire de : perte maximale historique du portefeuille, perte de 2022, et un choc de taux déclaré (colonne `rate_sensitivity_pct_per_pt` × hausse hypothétique). Un scénario « krach des actions » est proposé en sensibilité seulement, étiqueté « scénario fictif ».

**Construction, déterministe, sans bibliothèque d'optimisation :**

1. Candidats : actifs non exclus dont le score atteint le seuil d'entrée (défaut 80, ajustable). S'il y en a trop peu pour respecter les plafonds, le seuil descend par paliers jusqu'à 70 et l'écran le dit.
2. Deux poches selon le rôle des actifs : amortisseur (`liquidites`, `obligations_amortisseur`) et croissance (les autres).
3. Dans chaque poche, poids proportionnels au score, puis rabotés par les plafonds (titre, crypto, spéculatif, secteur, secteur de l'emploi, hors CAD, fonds plafonnés), l'excédent étant redistribué.
4. La part de la poche de croissance est la plus grande qui garde la perte de stress sous 0,8 × budget, la volatilité sous le plafond B5 et la durée sous l'eau sous la limite B7. Recherche par pas de 5 points.
5. Si aucune part ne satisfait tout, le moteur garde la solution la plus prudente et **nomme la contrainte en conflit** au lieu de la masquer.

**Tension, au niveau du portefeuille et du montant :** ratio = perte de stress ÷ budget. Moins de 0,8 « cohérent » ; 0,8 à 1 « à surveiller » ; plus de 1 « en tension » (seuils déjà écrits dans la grille, B1). Affichage en pourcentage et en dollars sur le montant fictif.

**Demande d'un titre (Robert) :** le moteur ajoute le titre au montant demandé, recalcule, et rend le verdict avec le montant maximal compatible.

| Tests | Acceptation |
|---|---|
| Somme des poids = 100 % ; aucun actif exclu ; tous les plafonds respectés | Passe pour les trois personas |
| Robert : le portefeuille contient des actions, perte de stress ≤ 15 % | Passe, ou conflit nommé |
| Mateo : aucune controverse « élevée », volatilité ≤ 15 % | Passe |
| Amira : crypto ≤ 10 %, spéculatif ≤ 10 %, exposition effective au secteur de son emploi sous le plafond, perte de stress ≤ 45 % | Passe |
| Robert demande 20 % de NVDA : « en tension », montant maximal donné | Passe |
| Chaque ligne du tableau des contraintes a une preuve | Passe |

## Phase 3 — D. Recherche, E. Comparaison, F. « Et si… ? »

| | |
|---|---|
| Fichiers | `recommandation/recherche.py`, `recommandation/comparaison.py`, `recommandation/et_si.py`, `tests_recommandation/test_recherche_et_si.py` |

**D. Recherche.** Entrée : texte libre. Recherche sur le ticker et le nom, sans accents ni casse, avec suggestions proches. Sortie : fiche d'actif, score, seuil en vigueur, bande, explication.

| Cas | Réponse |
|---|---|
| Score au-dessus du seuil | Les critères qui soutiennent la compatibilité, avec preuves, et le poids maximal |
| Zone « à examiner » | Ce qui soutient, ce qui retient, ce qu'il faudrait vérifier |
| Sous le seuil | Les critères qui posent problème, avec preuves, sans jugement sur la personne |
| Exclu | La règle d'exclusion et la réponse de l'utilisateur qui la déclenche |
| Absent de l'univers | « Cet actif n'est pas dans l'univers analysé », suggestions proches, aucune évaluation inventée |
| Données insuffisantes | Les colonnes manquantes |

**E. Comparaison.** Entrée : deux tickers. Sortie : tableau critère par critère (valeur A, valeur B, état pour ce profil), puis l'**écart décisif** : le critère de rang le plus élevé (`DURE`, puis `CALIBRAGE`, puis `PREFERENCE`) où les deux actifs diffèrent, avec sa raison et ses preuves.

**F. « Et si… ? »** Entrée : un critère et sa nouvelle valeur, ou une hypothèse modifiée. Le profil d'origine n'est jamais modifié : le calcul se fait sur une copie (`synthese.avec_valeur` existe déjà pour cela). Sortie : ce qui change dans les contraintes, les actifs qui changent de bande, les poids avant et après, et la règle responsable de chaque changement.

Sensibilité aux hypothèses, sur trois axes : horizon (A2 d'un cran), seuils (70/50 à ± 5 ; ratio 0,8), période (avec et sans 2022). Résultat : nombre d'actifs qui changent de bande et variation de la perte de stress. Ce n'est ni un intervalle de confiance ni une prévision.

| Tests | Acceptation |
|---|---|
| « nvidia », « NVDA », « nvda » trouvent le même actif | Passe |
| Ticker inconnu : message « absent », aucun score | Passe |
| Comparaison NVDA / XBB.TO pour Robert : écart décisif = calibrage du risque | Passe |
| Horizon de Robert allongé : budget en hausse, changements listés avec leur règle | Passe |
| Profil d'origine inchangé après un « Et si… ? » | Passe |

## Phase 4 — G. Agents et H. Gouvernance

### G. Agents

| Composant | Type | Pourquoi il existe | Entrées | Sorties | Outils |
|---|---|---|---|---|---|
| **Conseiller** | Modèle avec outils (Sonnet 5.5) | Une demande en langage courant demande de choisir et d'enchaîner des outils : c'est le rôle d'orchestration | Demande, identifiant de session | Résumé du portefeuille avec identifiants de preuve | `lire_contraintes`, `evaluer_actif`, `construire_portefeuille`, `evaluer_demande`, `et_si` |
| **Explicateur** | Modèle avec outils (Sonnet 5.5) | Répondre à « pourquoi ? » sur un actif ou une comparaison, et refuser ce que les données ne soutiennent pas | Question, verdict déjà figé | Réponse courte, preuves citées, limites, « je ne peux pas le dire » si rien ne le soutient | `chercher_actif`, `fiche_actif`, `comparer`, `lire_preuve` |
| **Détecteur d'incohérence** | Code | Le cas Robert : une demande contraire au profil doit être relevée avant toute rédaction | Demande (titre, montant), contraintes | Liste de tensions avec preuves, verdict figé | — |
| **Vérificateur de fidélité** | Code | Empêcher un chiffre inventé d'atteindre l'écran | Texte du modèle, sorties d'outils de l'échange | Accepté, ou liste des chiffres sans origine | — |

Deux agents à modèle, pas plus. Le détecteur et le vérificateur sont du code, et présentés comme tels. Les mises en situation restent du code, pas un agent.

**Vérificateur de fidélité.** Il extrait tous les nombres du texte (pourcentages, montants, décimales à la française), les compare aux nombres présents dans les sorties d'outils de l'échange, à la précision affichée. Un nombre sans origine fait rejeter le texte : une régénération, puis un texte de secours produit par gabarit à partir des seules sorties d'outils. Chaque passage est journalisé.

**Explications fidèles aux actions observables.** L'écran « Pourquoi ? » montre les outils appelés, leurs entrées et sorties, et les preuves. Il ne montre pas de raisonnement interne du modèle.

| Fichiers | `recommandation/outils.py` (une fonction par outil, schémas d'entrée), `recommandation/agents.py`, `recommandation/fidelite.py`, `recommandation/incoherence.py`, `recommandation/traces.py`, tests associés |
|---|---|
| Tests | Faux modèle : un texte avec un chiffre absent des outils est rejeté. Verdict de Robert identique avec dix justifications différentes. Question sans donnée (« NVDA va-t-elle monter ? ») : refus. Trace : l'horodatage du verdict précède celui de la justification |
| Acceptation | Aucun chiffre affiché sans origine dans les tests ; le verdict ne dépend jamais du texte libre |

### H. Gouvernance

| Contrôle | Mécanisme |
|---|---|
| Mention « simulation » | Bandeau sur chaque écran et phrase finale de chaque réponse, ajoutés par le code |
| Aucun conseil personnalisé | Guardrail (sujet interdit) et consigne ; formulations « cohérent avec le profil saisi », jamais « achetez » |
| Aucune prédiction | Guardrail et refus ; les rendements passés ne sont affichés que comme description, avec la période |
| Données manquantes visibles | État `DONNÉE_MANQUANTE` affiché, part des critères évalués sur chaque fiche |
| Faits, hypothèses, scénarios | Étiquette sur chaque valeur : fait (donnée datée), hypothèse (seuil), scénario fictif (stress) |
| Contraintes respectées | Tableau de contrôle du portefeuille, recalculé après la rédaction |
| Aucun ordre réel | Aucune fonction d'exécution n'existe ; dit à l'écran |

Fichier : `recommandation/gouvernance.py`. Test : un portefeuille qui viole un plafond est bloqué avant affichage.

## Phase 5 — J. Interface

**Sans modifier `mvp_profil/`.** Un lanceur neuf à la racine (`awsome-ai_app.py`) utilise la navigation à pages de Streamlit : la page « Profil » exécute `mvp_profil/app.py` tel quel, et les nouvelles pages lisent `S.profil` dans la même session. À vérifier en premier, en 20 minutes, y compris le composant vocal. En cas d'échec : application séparée qui charge un persona en un clic ou le JSON exporté.

| Écran | Contenu |
|---|---|
| Mini-portefeuille | Poids, mesures, tension en % et en dollars, tableau des contraintes avec preuves |
| Recherche | Champ de recherche, score, seuil, bande, explication |
| Fiche d'actif | Critères, valeurs, états, sources et dates |
| Comparaison | Tableau critère par critère, écart décisif |
| « Pourquoi ? » | Outils appelés, preuves, hypothèses, limites, résultat du vérificateur |
| Reprise des questions | Modifier une réponse ou une hypothèse, voir les changements et leur cause |
| Demande d'un titre | Titre, montant, verdict figé, puis champ de justification |

Fichiers : `awsome-ai_app.py`, `recommandation/pages/*.py`, `tests_recommandation/test_interface.py`.

**Accès du jury.** Formulaire de connexion dans l'application, vérifié par Cognito (appel direct, sans Lambda@Edge) ; un compte « jury ». La fonction CloudFront de filtrage par IP est alors retirée et le groupe de sécurité ne garde que CloudFront. **Ces deux changements touchent le site en service : je les soumets avant de les faire.**

**Mode de secours.** Trois niveaux : (1) personas en un clic, sans voix ; (2) mode « sans modèle » : les textes viennent des gabarits, tout le reste fonctionne ; (3) vidéo préenregistrée et lancement local documenté.

Acceptation : les sept écrans s'affichent pour les trois personas dans le test d'interface ; le parcours Robert tient en moins de deux minutes.

## Phase 6 — I. AWS

| Service | Rôle concret | Entrée → sortie | Alternative écartée | État |
|---|---|---|---|---|
| EC2 | Héberge l'application | Requêtes → pages | Fargate : plus long à mettre en place | En place |
| CloudFront | HTTPS, exigé par le micro | Navigateur → serveur | Certificat sur l'instance : domaine requis | En place |
| S3 | Paquet du site et données versionnées | Fichiers → objets | Disque de l'instance : non versionné | En place ; versions à activer |
| IAM | Privilèges minimaux par composant | — | Rôle large | En place ; politique à étendre |
| Transcribe, Polly | Voix de l'entretien | Audio ↔ texte | — | En place, gelés |
| Bedrock Haiku 5.5 | Entretien | Texte → classement | — | En place, gelé |
| Bedrock Sonnet 5.5 | Conseiller et Explicateur avec outils | Demande + sorties d'outils → texte | Haiku : moins fiable sur l'enchaînement d'outils | Prouvé |
| Bedrock Guardrails | Bloque conseil personnalisé et prédiction ; masque les données personnelles ; contrôle d'ancrage | Texte → accepté ou bloqué | Consigne seule : non vérifiable | Prouvé |
| DynamoDB | Verdicts figés, registre de preuves, traces d'outils, résultats du vérificateur | Événement → ligne horodatée | Fichier local : perdu au redémarrage, pas de preuve d'ordre | Prouvé |
| Lambda | Outils des agents, isolés, avec leur propre rôle | Nom d'outil + paramètres → résultat | Appel en mémoire : gardé comme secours | Prouvé ; **priorité 2** |
| CloudWatch Logs, X-Ray | Traces d'exécution observables, exigées par la doc technique | Appels → journaux et traces | Journal systemd : non consultable par le jury | Prouvé ; X-Ray en priorité 2 |
| Cognito | Accès du jury | Identifiant → jeton | Liste d'IP : inutilisable pour un jury | Prouvé (création) |
| CloudFormation | Déploiement reproductible des ajouts | Gabarit → ressources | CDK : non initialisé dans le compte, plus long | Prouvé |
| AWS Budgets | Alerte de coût | Seuil → alerte | — | Prouvé ; 5 minutes |

**Écartés** : Step Functions (aucun enchaînement de Lambda), Knowledge Bases (les preuves sont des colonnes, pas des documents), AgentCore, API Gateway, Glue. **Athena** : écarté sauf décision contraire, voir les décisions ouvertes.

Ordre : politique IAM du serveur (Sonnet, DynamoDB, Guardrail) → table DynamoDB → Guardrail → Cognito → Lambda et X-Ray si le temps le permet → gabarit CloudFormation → Budgets. Chaque ajout est réversible et étiqueté `projet = awsome-ai-mvp`. Les sept Lambda et l'instance de l'atelier ne sont pas touchées.

Limite à écrire dans la doc : région américaine et profil d'inférence américain, donc pas de résidence canadienne des données.

Acceptation : une session de démonstration laisse dans DynamoDB une suite de lignes où le verdict précède la justification ; un texte de conseil personnalisé est bloqué par le Guardrail.

## Phase 7 — K. Tests et livrables

| Test | Contenu |
|---|---|
| Régression des personas | Invariants des phases 1 et 2, plus un instantané versionné des verdicts |
| Fidélité des chiffres | Phase 4 |
| Correspondance des libellés | Phase 0 |
| Univers variable | Actif fictif ajouté, actif retiré |
| Déterminisme | Deux exécutions, même résultat |
| Suites existantes du profil | Relancées après installation des dépendances ; elles doivent rester vertes |

| Livrable | Contenu | Échéance |
|---|---|---|
| README | Lancement, dépendances, sources, configuration | Dimanche 23 h 59 |
| Documentation technique | Méthodes et justification ; sources, licences et traitements ; hypothèses ; mécanisme d'explication avec un exemple tracé de la conclusion à la donnée ; validations ; limites ; tableau « service AWS → rôle → alternative écartée » | Dimanche 23 h 59 |
| One-pager | Problème, approche agentique, originalité (déclaré contre vécu), sources, explication, bénéfices | Lundi 14 h |
| Script de vidéo, 5 minutes | 0:00 problème · 0:30 Amira : profil, portefeuille, « oui, mais plafonné » · 1:45 Robert : demande d'un titre médiatisé, « non, voici pourquoi », preuve · 3:15 « Et si… ? » et sensibilité · 4:00 agents, outils, vérificateur, AWS · 4:40 limites | Lundi 14 h |

**Licences.** Les prix, fondamentaux, fiches de FNB et actualités viennent de Yahoo Finance par yfinance. Les conditions de Yahoo limitent la redistribution. À écrire dans la doc et à faire trancher par l'équipe : garder ces fichiers dans le dépôt remis, ou ne remettre que les scripts et les indicateurs dérivés.

---

# Ce que je n'ai pas pu vérifier

- Les trois `.docx` de critères et la « doc partagée ».
- Le contenu exact du paquet actuellement installé sur le serveur.
- Les suites de tests qui demandent Streamlit et le SDK (10 sur 18).
- La cohabitation du lanceur à pages avec le composant vocal.
- L'exactitude des prix postérieurs à juin 2026 et les liens des controverses.
- La modification de CloudFront et du groupe de sécurité.
