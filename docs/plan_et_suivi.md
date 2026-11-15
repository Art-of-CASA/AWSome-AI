# Plan retenu et suivi des modifications

15 novembre 2026. Ce document fait suite à l'audit (`audit_et_plan.md`). Il fixe les choix retenus, dit ce qui a été fait dans cette version du dossier, et ce qui reste.

**Rien n'a été publié sur le site partagé.** Le paquet S3 et l'instance n'ont pas été touchés.

## 1. Ce que l'énoncé officiel change par rapport aux audits

L'énoncé (PDF, 19 pages) a été lu en entier. Trois points corrigent les audits précédents :

| Sujet | Ce que disaient les audits | Ce que dit l'énoncé |
|---|---|---|
| Robert | « Débutant » | Expérience en investissement : **avancée** (p. 7). La règle de complexité ne doit donc pas le bloquer. |
| Mateo | « Exclusions fossiles » | L'énoncé ne parle **pas** d'énergies fossiles. Il parle de facteurs ESG et de controverses environnementales ou sociales importantes (p. 6). |
| Mateo | Horizon de 10 ans ou 10-15 ans | 8 à 12 ans : à cheval sur deux classes. La plus courte (5-10 ans) est retenue. |

L'énoncé confirme le reste : la grille d'évaluation (20, 20, 20, 10, 15, 15 %), les quatre livrables, et le fait que le résultat peut être « un portefeuille simulé, une analyse comparative, une aide à la décision ou un autre résultat défendable » (p. 8). Il précise aussi : « expliquer leurs indicateurs, leurs limites et les incertitudes, plutôt que d'assimiler un profil à un actif de façon automatique » (p. 18).

## 2. Choix retenus

| # | Décision | Choix |
|---|---|---|
| 1 | Échelle du profil | Budget de perte en %, continu ; niveau de 1 à 5 comme étiquette. La classe 1 à 7 reste un descripteur d'actif. |
| 2 | Niveau du jugement de risque | Le portefeuille. Par actif : exclusions, plafonds, poids maximal. |
| 3 | Replay | Seul « Tout vendre » fixe le point de rupture observé. « Réduire » est un signal. |
| 4 | Cohérence | Un correctif n'écrit jamais une valeur non choisie : le critère est redemandé. |
| 5 | Source de vérité | `mvp_profil/criteres.py` ; la grille CSV est alignée par `scripts/sync_grille.py`. |
| 6 | Questions | Ajoutées : A1, G1, D11, D9, G3. Non posées : A11, C3, D10, E3, F1, G4, G5. |
| 7 | Données | Corrections de calcul sans nouveau téléchargement des prix. |
| 8 | AWS, chercheur, voix | Gelés. Aucun service ajouté. |

## 3. Ce qui a été fait

Les 7 tests de `mvp_profil/` et `scripts/test_grille.py` passent. Avant toute modification, j'ai vérifié que les fichiers de données d'origine se régénéraient à l'identique.

### Étape 0. Personas de l'énoncé

- `mvp_profil/personas/amira.json`, `mateo.json`, `robert.json`. Chaque valeur est marquée « énoncé » (avec la phrase citée) ou « hypothèse de test » (avec la raison).

### Étape 1. Une seule source de vérité

- `config/criteres_appariement.csv` : valeurs alignées sur le code, B1R ajouté, D13 renommé D8O, colonne `demande`, règles de risque réécrites au niveau du portefeuille.
- `config/correspondances.json` : thèmes, secteur d'emploi vers GICS, secteurs des FNB vers GICS, régions, classes, E1, E5, F2, G3. Les valeurs sans actif sont déclarées (immobilier, armes, tabac, jeux d'argent, nucléaire).
- `scripts/sync_grille.py` et `scripts/test_grille.py`.

### Étape 2. Données des actifs

Fichiers : `scripts/compute_metrics.py`, `scripts/build_asset_criteria.py`, `scripts/fetch_extra_data.py`, `scripts/build_scenarios.py`, `config/seuils_criteres.json`, puis régénération de `asset_metrics_cad.csv`, `asset_criteria.csv` (109 colonnes), `vocabulaire_actifs.json`, `donnees_chercheur.json`, `scenarios.json`.

| Correction | Résultat vérifié |
|---|---|
| Durée sous l'eau du sommet au retour | NVDA : 535 jours (216 avant). TSLA : 1 067. |
| Baisse non récupérée | 11 `baisse_en_cours` (creux de moins de 12 mois) et 3 `jamais_recupere` (TLT, Nestlé, Sasol). L'horizon n'est plus allongé pour une baisse en cours. |
| Rôles | ZST `liquidites` ; XBB, AGG, BNDW `obligations_amortisseur` ; TLT `obligations_longues` ; FNB d'actions `coeur` ; actions `satellite*` ou `speculatif`. |
| Spéculatif testé avant revenu | Novo Nordisk et Gold Fields : `speculatif`, plus `income_asset`. |
| Liquidité des FNB | `elevee` (ZST n'est plus « faible »). |
| Complexité | 1 pour les FNB larges, obligataires et les actions ; 2 pour l'or et TLT ; 3 pour crypto, Naspers, CIB. |
| Dividendes | Plus de fausse baisse pour TotalEnergies, HSBC et ZST. Restent : Sasol, Aspen, CIB. |
| Rentabilité | Signe du résultat net lu dans le RCP : Manuvie 0,75 au lieu de 0,25. |
| « Établie » | Sans condition de dividende, seuil de 75 % d'années rentables : Alphabet, Amazon et Manuvie le sont. |
| « Diversifiant » | Condition ajoutée sur 2022 et le spéculatif : Bitcoin, Novo, Sasol, Aspen ne le sont plus. |
| Risque pays | Étiquettes multiples : VWO `marche_emergent`, VT et XEQT `marche_emergent_partiel`. |
| Devise | VT, VEA, VWO : `multidevise_non_couvert`. |
| Énergies fossiles | `fossil_categorie` et `fossil_part_energie_fnb` ; mot-clé `energie_fossile_via_fonds` (XIU 18 %) ; Ether : `aucune`. |
| Pays | Canada ou États-Unis pour les 29 actifs du jeu de départ. |
| Cycle | Alphabet et Tencent `cyclique` ; télécoms `defensif`. |
| Secteurs de BNDW | Lignes fausses retirées ; filtre ajouté au script de collecte. |
| Emballement récent | `attention_ratio_30j_sur_1an` et `hype_recent` : NVDA seulement (ratio 4,9). |
| Ratio de distribution | `ratio_distribution_non_comparable` pour Enbridge, Fortis, Toyota et les flux libres négatifs. |
| Cotation américaine | Colonne `adr_us` pour 15 titres, à vérifier auprès du courtier. |

### Étape 3. Logique du profil

Fichiers : `mvp_profil/profil.py`, `simulations.py`, `criteres.py`, `entretien.py`, `app.py`, tests.

- Le point de rupture déclaré est conservé (`B1["declare"]`). `recouper_rupture` est rappelée après chaque correctif et à chaque précision : le retenu ne dépasse jamais l'observé.
- R1b, R6 : le critère est redemandé au lieu de recevoir 30, 10 ou « modérée ». R2, R8, R9 : l'option énonce la valeur. R8 n'écrase plus B6, qui est mesuré. R9 n'assouplit plus D12. R3 corrigée.
- Replay : « Tout vendre » seul fixe B2, avec la perte réelle ; « Réduire » est gardé comme signal ; « non atteint » donne H1 = `non_teste` quand le déclaré dépasse la baisse montrée.
- Portefeuille du replay : choisi sur le risque et l'horizon, plus sur le thème.
- Effet de mode : mêmes faits pour les quatre titres, sans étiquette de jugement.
- 5 critères ajoutés (42 au total, 34 questions).

### Étape 4. Synthèse du profil

- `mvp_profil/synthese.py` et `mvp_profil/hypotheses_profil.json`. Le budget de perte est le plus prudent de la capacité, de la tolérance déclarée et de la tolérance observée. La composante qui limite est nommée. Les critères inconnus reçoivent un réglage prudent, signalé à l'écran.
- Résultat sur les personas : Robert niveau 2, budget 15 % ; Mateo niveau 3, 22 % ; Amira niveau 5, 45 %.
- `mvp_profil/test_synthese.py` vérifie l'ordre, la sensibilité à une réponse et l'absence d'effet de seuil.

### Étape 6. Conformité et présentation

- Page finale : synthèse, alertes, « ce que l'outil ne sait pas ». Export JSON : synthèse incluse.
- Accueil : trois boutons de chargement des personas.
- Bandeau « simulation éducative » sur chaque page. Le « débat des agents » devient un « journal des contrôles ».
- `README.md`, `SECURITY.md`, `.env.example` : la sécurité décrit l'architecture réelle.
- `mvp_profil/DEPLOIEMENT.md` : identifiant du compte, identifiants de ressources et adresses IP retirés.

## 4. Hypothèses à valider par l'équipe

Elles sont déclarées dans `mvp_profil/hypotheses_profil.json` et `config/seuils_criteres.json`. Aucune n'est une norme.

- Stress maximal par niveau : 8, 15, 22, 32, 45 %. Ordre de grandeur : part d'actions × 45 %.
- Plafond de capacité par horizon, et crans retirés pour A4, A5, A6, A8.
- Niveau associé au choix des fourchettes (B6).
- Réglages prudents par défaut.
- Valeurs « hypothèse de test » des personas, en particulier les points de rupture (20, 30, 50 %).
- Seuils nouveaux : 12 mois pour une baisse en cours, 75 % d'années rentables, 1 % de part d'énergie, ratio d'audience de 1,5.
- Classification des pays émergents selon MSCI.

### Compléments du 15 novembre (clôture de la partie profil)

- Étiquettes fait, hypothèse, scénario fictif sur les mises en situation ; colonne « nature » dans le tableau du profil ; limite des fourchettes affichée.
- `docs/criteres_profil_actifs.md` régénéré à partir des fichiers à jour.
- `mvp_profil/evaluer_classement.py` et 43 phrases étiquetées : la mesure est prête, **non exécutée** (elle appelle le vrai modèle).
- `docs/journal_modifications.md` pour l'équipe.
- Paquet de déploiement `mvp_profil.zip` préparé, **non publié**.

## 5. Ce qui n'est pas fait

| Reste à faire | Qui | Pourquoi ce n'est pas fait |
|---|---|---|
| Relire les hypothèses de la synthèse et des personas | Équipe | Ce sont des choix, pas des calculs |
| Lancer la mesure du classement sur Bedrock | Équipe | Appels réels au modèle, à la charge du compte |
| Publier le paquet et essayer le parcours vocal | Équipe | Accord explicite requis ; la voix ne se teste que sur le site |
| Fermer l'accès direct au port 8501 | Équipe | Modification de l'infrastructure |
| **Moteur d'appariement, allocation fictive, explication, contrôles de gouvernance** | Suite | Manque principal face à l'énoncé. Tout ce qui précède le prépare. |
| **Parcours « demande d'un titre » (test de Robert)** | Suite | Dépend du moteur |
| Scénarios de stress hors 2022, historique long | Suite | À choisir par l'équipe ; l'historique long demande un téléchargement |
| Test de sensibilité affiché | Suite | Dépend du moteur |
| Positions complètes des FNB | Suite | Téléchargement chez les émetteurs |
| Documentation technique, page de synthèse, vidéo | Suite | Dépendent du moteur |

## 6. Vérifier

```bash
python mvp_profil/test_profil.py
```

```bash
python mvp_profil/test_synthese.py
```

```bash
python mvp_profil/test_app.py
```

```bash
python scripts/test_grille.py
```
