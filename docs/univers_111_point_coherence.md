# Univers à 111 actifs : ce qui est fait, ce qu'il reste à aligner

Point du 15 novembre 2026.

> **Mise à jour à la publication (15 novembre 2026).** Faits depuis ce point : les consignes du chercheur lisent le nombre d'actifs dans les données (111, point 3.7) ; les README principaux annoncent 111 actifs ; le paquet a été reconstruit et publié (point 3.9). Les anciens mots-clés dynamiques en cache ne sont plus réutilisés : leur clé inclut les données et les consignes, qui ont changé. Restent à décider : les régions D3 (3.1), les règles et exclusions écrites à la main (3.3, 3.4), la table des sources (3.8) et les documents historiques qui citent encore 66 actifs. Base de travail : la branche `feat-profil-donnees-streamlit`. Ses scripts sont bien ceux qui produisent les 109 colonnes de `asset_criteria.csv` ; ils reproduisent à l'identique le fichier de la branche.

## 1. Ce qui est fait

- **45 actifs ajoutés** à `data_extended` en deux lots (80 dans le dossier, 111 avec le jeu de départ) : 35 pour diversifier et contraster les valeurs, puis 10 actifs stables. Liste et justification dans `data_extended/README.md`.
- **Devises** : les 111 actifs sont cotés dans 17 devises ; aucun ajout n'était nécessaire sur ce point.
- **Données brutes** : les lignes des 35 actifs d'origine sont inchangées, fichier par fichier ; seules des lignes ont été ajoutées.
- **`asset_metrics_cad.csv` et `asset_criteria.csv`** : recalculés pour 111 actifs avec les scripts de la branche. Les 66 lignes d'origine sont identiques, sauf deux colonnes pour 4 actifs (voir 3.2). L'ajout des 10 actifs stables n'a modifié aucune des 101 lignes précédentes.
- **Tests de la branche** : 17 suites sur 18 passent avec les 111 actifs. La dix-huitième (`test_voix.cjs`) demande Node.js, absent du poste : elle n'a pas été lancée.

## 2. Fichiers à déposer dans la branche

Tout est dans ce dossier. Chemins relatifs à la racine du dépôt.

| Fichier | Nature du changement |
|---|---|
| `data_extended/` (dossier entier) | 80 actifs ; indicateurs et critères des 111 actifs |
| `scripts/universe_extended.csv` | 45 lignes ajoutées |
| `scripts/ajouter_actifs.py` | **Nouveau.** Ajoute des actifs sans retélécharger les anciens ; peut être relancé après une interruption |
| `scripts/build_esg.py` | 6 controverses sourcées, 6 implications fossiles, correspondance `BEP-UN` / `BEP.UN`, reprise du dernier fichier Jantzi si celui du jour est inutilisable |
| `scripts/build_asset_criteria.py` | Thèmes, exclusions, cotations américaines, marchés, pays émergents des nouveaux actifs ; 4 règles (voir 3.3) |
| `config/correspondances.json` | `armes`, `tabac`, `jeux_argent`, `energie_nucleaire` et `immobilier` touchent maintenant des actifs (ils étaient déclarés « aucun actif ») |
| `config/correspondances_positions_fnb.json` | 3 émetteurs reliés : `TSM`, `ASML`, `SKHY` |
| `mvp_profil/vocabulaire_actifs.json` | Régénéré : 333 valeurs, 111 actifs |
| `mvp_profil/donnees_chercheur.json` | Régénéré : 111 actifs, 17 FNB |
| `mvp_profil/test_dynamiques.py` | Une attente mise à jour : 8 titres en euros au lieu de 5 |

`mvp_profil/scenarios.json` n'a pas changé de contenu : garder celui de la branche.

## 3. À décider ou à corriger pour que tout soit cohérent

### 3.1 Régions absentes du profil — à décider
Deux régions nouvelles, « Amérique latine » (3 actifs) et « Moyen-Orient » (1 actif). Le critère D3 du profil ne les propose pas : ces 4 actifs ne sont atteints que par « pays émergents ». Deux options :
- ajouter les deux valeurs à D3 (`criteres.py`, `config/correspondances.json`, puis `scripts/sync_grille.py`) ;
- ne rien changer et l'écrire dans les limites.

### 3.2 Notoriété de 4 anciens actifs — à savoir
`media_hype` et `kw_attention` se mesurent par quantiles sur l'univers. L'univers ayant changé, LVMH et Sony passent de « très médiatisé » à « très suivi », Siemens et Samsung de « peu médiatisé » à « très suivi ». Rien à corriger, mais un exemple de démonstration qui cite ces valeurs doit être revu.

### 3.3 Règles ajoutées dans `build_asset_criteria.py` — à valider
- **FNB sectoriels** (ICLN, ITA, VNQ, SMH) : rôle `satellite` au lieu de `coeur`. Sans cette règle, tout FNB d'actions était un cœur de portefeuille.
- **Complexité** : SoftBank à 3 (holding à étages, comme Naspers) ; TIP et Brookfield Renewable à 2.
- **Immobilier** : secteur `Real Estate` classé cyclique ; ratio de distribution « non comparable » comme pour les services publics.
- **Fiscalité** : Brookfield Renewable en « distributions canadiennes » (société en commandite, pas des dividendes admissibles).

### 3.4 Exclusions écrites à la main — à valider
- **Nucléaire** : NextEra, Iberdrola et Enel sont marqués parce qu'ils exploitent des centrales, alors que c'est une part minoritaire de leur production. Cameco (uranium) est le cas net.
- **Contrats de défense** : Palantir est marqué, sans la mention « armes ».
- **Non marqués** : Costco et Walmart de México vendent de l'alcool et du tabac (distribution) ; aucun seuil de revenus n'est disponible.
- **FNB** : seul ITA porte des exclusions (fonds entièrement en défense). L'intérieur des autres FNB n'est pas mesuré au-delà des 10 premières positions.

### 3.5 Controverses — limite à déclarer
6 controverses ajoutées, chacune avec sa source. Les 23 autres actions ajoutées ont « aucune trouvée » : la recherche n'a pas été exhaustive, ce n'est pas une absence établie.

### 3.6 Classes de risque écrasées vers le haut — problème existant, atténué par les actifs stables
Sur 111 actifs : 56 en classe 7, 36 en classe 6, 19 dans les classes 1 à 5 (9 avant l'ajout des actifs stables). Le bas de l'échelle est maintenant couvert, mais les actions restent presque toutes en classe 6 ou 7. `docs/point_problemes.md` signalait déjà ce défaut sur 66 actifs : une échelle où presque tout est au maximum ne distingue plus les actions entre elles.

### 3.7 Textes qui annoncent encore 66 ou 35 actifs — à corriger
- **Consignes du chercheur** (`mvp_profil/chercheur.py`, lignes 6, 100, 113 et 277) : l'agent reçoit 111 actifs mais on lui dit « 66 ». À corriger en priorité ; cela change la version du paquet (`version_profil.py`).
- `mvp_profil/test_chercheur.py` ligne 99 (commentaire).
- `README.md` lignes 50, 70, 96, 132, 254 et 276 ; `mvp_profil/README.md` ligne 111.
- `docs/criteres_profil_actifs.md` ligne 12 ; `docs/audit_et_plan.md` lignes 63, 105 et 273 ; `docs/point_problemes.md` lignes 93 et 201.
- `data_extended/README.md` : le haut du fichier décrit encore « 35 actifs » ; la section d'ajout en bas est à jour.

### 3.8 Table des sources — à compléter
`data_extended/sources_extended.csv` n'a pas été modifié : il indique une collecte du 14 novembre et ne mentionne ni les 45 nouveaux actifs (collecte du 15 novembre), ni les devises BRL, MXN, SGD et SAR. La ligne 11 (controverses) contient toujours une virgule non protégée.

### 3.9 Paquet du site et serveur — à refaire
- Reconstruire le paquet avec `scripts/preparer_mvp.py`, puis le publier : le site en ligne utilise encore le vocabulaire et les données du chercheur à 66 actifs.
- Les mots-clés dynamiques en cache sur le serveur (`kw_dyn_*`) ont été calculés sur 66 actifs : les vider, sinon « rien qui touche à l'armement » ne verra pas les nouveaux titres.

### 3.10 Copie de travail du poste — à abandonner
Le dossier `datathon-main` du poste contient une synthèse du profil, des règles de cohérence et un script d'évaluation écrits hier sur une version antérieure. La branche a depuis ses propres `synthese.py`, 42 critères et ses évaluations : ne pas fusionner l'ancienne copie.

## 4. Points de données à connaître

- **Riyal saoudien** : la Banque du Canada ne le publie plus après le 30 avril 2026 ; la suite est un taux croisé USD/CAD ÷ 3,75 (arrimage officiel), contrôlé sur la période commune (écart maximal 0,43 %).
- **Faux fractionnements** dans Yahoo pour Realty Income (scission) et VDY.TO : consignés dans `data_quality_warnings.txt`, à ne pas appliquer.
- **États financiers dans une autre devise que la cotation** : Diageo, Glencore et Brookfield Renewable (USD), Vestas (EUR).
- **Actifs stables en dollars américains** : BIL et SHY varient de 0,3 % et 2 % en USD, mais de 5,4 % en CAD à cause du change. Les vraies liquidités d'un investisseur canadien sont PSA.TO et CASH.TO.
- **Jantzi** : le fichier de BlackRock du 15 novembre n'avait pas de date ; le script a repris celui du 13 novembre. Cameco figure dans l'indice ; Brookfield Renewable Partners et BCE n'y figurent pas (l'indice contient l'autre catégorie d'actions de Brookfield Renewable, BEPC).

## 5. Pour ajouter d'autres actifs plus tard

```bash
python scripts/ajouter_actifs.py
python scripts/build_esg.py --universe scripts/universe_extended.csv --out data_extended
python scripts/compute_metrics.py
python scripts/build_asset_criteria.py
python scripts/build_vocabulaire.py
python scripts/build_donnees_chercheur.py
python scripts/lancer_tests.py
```

Avant de lancer : ajouter les lignes dans `scripts/universe_extended.csv`, puis les thèmes, exclusions et marchés des nouveaux titres dans `scripts/build_asset_criteria.py`.
