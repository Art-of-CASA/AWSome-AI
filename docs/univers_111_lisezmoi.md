# Univers porté à 111 actifs : fichiers à copier dans le dépôt

Ce dossier reprend l'arborescence du dépôt. Base : la branche `feat-profil-donnees-streamlit`. Copier son contenu à la racine du dépôt en acceptant d'écraser les fichiers existants (ce fichier et `POINT_COHERENCE.md` n'ont pas besoin d'être copiés).

## Ce qui change

L'univers passe de 66 à **111 actifs** (80 dans `data_extended`, 31 dans le jeu de départ), cotés dans 17 devises :
- **35 actifs** pour diversifier et contraster les valeurs des clients : tabac, armement, alcool, jeux d'argent, nucléaire, fossiles, face aux énergies renouvelables ; trois régions nouvelles.
- **10 actifs stables** (liquidités, obligations courtes, actions à faible volatilité) : l'univers a maintenant 19 actifs sous la classe de risque 6, contre 9.

La liste complète et les justifications sont dans `data_extended/README.md`.

## Contenu

| Fichier | Rôle pour le site |
|---|---|
| `data_extended/asset_criteria.csv` | **Le fichier que le site et l'appariement lisent** : 111 actifs, 109 colonnes, mêmes colonnes qu'avant |
| `data_extended/` (le reste) | Données brutes et indicateurs des 80 actifs du dossier |
| `mvp_profil/vocabulaire_actifs.json` | Régénéré : 333 valeurs. Lu par les critères dynamiques |
| `mvp_profil/donnees_chercheur.json` | Régénéré : 111 actifs, 17 FNB. Lu par l'agent chercheur |
| `mvp_profil/test_dynamiques.py` | Une attente mise à jour (8 titres en euros au lieu de 5) |
| `config/correspondances.json` | `armes`, `tabac`, `jeux_argent`, `energie_nucleaire` et `immobilier` désignent maintenant de vrais actifs |
| `config/correspondances_positions_fnb.json` | 3 émetteurs reliés : `TSM`, `ASML`, `SKHY` |
| `scripts/universe_extended.csv` | Les 80 actifs de l'univers étendu |
| `scripts/build_asset_criteria.py` | Thèmes, exclusions, marchés et pays des nouveaux actifs |
| `scripts/build_esg.py` | 6 controverses sourcées, 6 implications fossiles |
| `scripts/ajouter_actifs.py` | Nouveau : ajoute des actifs sans retélécharger les anciens |
| `data_extra/raw/xen_holdings_2026-11-13.csv` | Fichier de l'indice Jantzi utilisé par `build_esg.py` |

## Ce qui est vérifié

- Les lignes des 66 actifs d'origine sont identiques dans `asset_criteria.csv`, sauf la notoriété (`media_hype`, `kw_attention`) de LVMH, Sony, Siemens et Samsung, qui se mesure par rapport à l'univers.
- Les suites de tests de la branche passent (17 sur 18) une fois ces fichiers en place. La dernière, `test_voix.cjs`, demande Node.js et n'a pas été lancée.

## À faire côté site, par ordre d'importance

1. **Consignes du chercheur** : `mvp_profil/chercheur.py` dit encore « 66 actifs » à l'agent, lignes 6, 100, 113 et 277. Mettre 111, ou mieux, le nombre lu dans les données.
2. **Régions** : « Amérique latine » (3 actifs) et « Moyen-Orient » (1 actif) n'existent pas dans le critère D3 du profil. Ces actifs ne sont atteints que par « pays émergents ». Soit ajouter les deux valeurs (`criteres.py`, `config/correspondances.json`, puis `scripts/sync_grille.py`), soit le déclarer dans les limites.
3. **Valeurs nouvelles dans les colonnes**, à prévoir si l'interface a des listes ou des couleurs codées en dur :
   - `region` : Amérique latine, Moyen-Orient ;
   - `sector` : Real Estate, et des libellés de FNB sectoriels ;
   - `kw_exclusions` : armes, tabac, jeux_argent, energie_nucleaire ;
   - `currency` : BRL, MXN, SGD, SAR ;
   - `risk_class` : les classes 1 et 3 apparaissent pour la première fois.
4. **Paquet du site** : le reconstruire avec `scripts/preparer_mvp.py` et le publier. Vider aussi le cache des mots-clés dynamiques (`kw_dyn_*`) du serveur, calculé sur 66 actifs.
5. **Textes** : les README et documents qui annoncent 66 ou 35 actifs sont listés ligne par ligne dans `POINT_COHERENCE.md`.

## Hypothèses écrites à la main, à valider en équipe

- NextEra, Iberdrola et Enel sont marqués « nucléaire » alors que c'est une part minoritaire de leur production.
- Les FNB sectoriels (ICLN, ITA, VNQ, SMH) ont le rôle `satellite` et non `coeur`.
- 23 des actions ajoutées ont « aucune controverse trouvée » : la recherche n'a pas été exhaustive.
- BIL et SHY sont stables en dollars américains mais varient de 5,4 % en CAD à cause du change ; les vraies liquidités d'un client canadien sont PSA.TO et CASH.TO.

## Relancer la chaîne après un changement

```bash
python scripts/ajouter_actifs.py
python scripts/build_esg.py --universe scripts/universe_extended.csv --out data_extended
python scripts/compute_metrics.py
python scripts/build_asset_criteria.py
python scripts/build_vocabulaire.py
python scripts/build_donnees_chercheur.py
python scripts/lancer_tests.py
```
