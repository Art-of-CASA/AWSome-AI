# Journal des modifications : partie profil

Du 14 au 15 novembre 2026. Point de départ : l'archive `datathon-main-2.zip`, identique au paquet alors en ligne sur S3. Ce journal dit ce qui a changé, pourquoi, et ce que l'équipe doit retester. Le détail des choix est dans [plan_et_suivi.md](plan_et_suivi.md), les constats d'origine dans [audit_et_plan.md](audit_et_plan.md).

**Rien n'a été publié.** Le site en ligne tourne encore sur l'ancienne version.

## À faire par l'équipe avant de s'appuyer sur cette version

1. **Relire les hypothèses** de `mvp_profil/hypotheses_profil.json` et les valeurs « hypothèse de test » de `mvp_profil/personas/*.json`. Elles ont été posées pendant la correction, pas décidées en équipe.
2. **Lancer les tests** (commandes en bas de page).
3. **Lancer la mesure du classement** : `python mvp_profil/evaluer_classement.py --repetitions 10`. Elle appelle le vrai modèle sur Bedrock. Recopier le tableau obtenu dans la documentation technique.
4. **Publier** le paquet `mvp_profil.zip` fourni, puis **essayer le parcours vocal** : la question redemandée après une contradiction, l'étape de vie dans la conversation, les cinq nouvelles questions.

## Ce qui change pour l'utilisateur

| Avant | Maintenant |
|---|---|
| Le profil se terminait par une liste de 37 valeurs | Une synthèse : niveau de risque, budget de perte du portefeuille, ce qui le limite, et « ce que l'outil ne sait pas » |
| Aucun profil de démonstration | Trois boutons à l'accueil : Amira, Mateo, Robert (personas de l'énoncé) |
| « Réduire de moitié » au replay fixait le point de rupture | Seul « Tout vendre » le fixe ; la perte réelle est affichée |
| Une contradiction pouvait écrire une valeur jamais donnée (30 %, 10 %) | Le critère est redemandé |
| Une contradiction pouvait remonter le point de rupture au-dessus de l'observé | Le plus prudent l'emporte toujours |
| Citer l'IA suffisait à revivre un replay 100 % technologie | Le portefeuille du replay suit le risque et l'horizon déclarés |
| Effet de mode : étiquettes « On en parle partout » et « peu médiatisée » | Mêmes faits pour les quatre titres, sans jugement |
| 29 questions, 37 critères | 34 questions, 42 critères : étape de vie, montant, FNB ou titres, poids maximal par titre, accès aux bourses étrangères |
| Mention « simulation » en bas de la barre latérale | Bandeau sur chaque page ; étiquettes fait, hypothèse, scénario fictif |
| « Dernier débat des agents » | « Journal des contrôles », replié |

## Fichiers modifiés

### Site (`mvp_profil/`)

| Fichier | Changement |
|---|---|
| `profil.py` | `recouper_rupture` réécrite (valeur déclarée conservée, rappelable sans effet de bord, statut `non_teste`) ; correctifs sans valeur inventée ; règles R1b, R2, R3, R6, R8, R9 corrigées |
| `simulations.py` | Replay (vente totale, réduction comme signal, perte réelle) ; choix du portefeuille ; effet de mode neutre ; étiquettes et limite des fourchettes |
| `criteres.py` | Critères A1, D9, D11, G1, G3 et leurs questions ; valeur `non_teste` pour H1 |
| `entretien.py` | A1 ajouté aux sujets de la conversation (16 critères) |
| `app.py` | Synthèse sur la page finale et dans l'export ; chargement des personas ; bandeau ; colonne « nature » ; critère redemandé après un correctif |
| `synthese.py` (nouveau) | Capacité, tolérance déclarée, tolérance observée, budget de perte, réglages prudents |
| `hypotheses_profil.json` (nouveau) | Toutes les tables de la synthèse, déclarées comme hypothèses |
| `personas/` (nouveau) | Amira, Mateo, Robert, d'après l'énoncé |
| `evaluer_classement.py`, `validation/` (nouveaux) | Mesure de la fiabilité du classement, 43 phrases étiquetées |
| `test_profil.py`, `test_app.py` | Deux assertions adaptées au nouveau comportement ; tests de non-régression ajoutés |
| `test_synthese.py` (nouveau) | Trois personas, sensibilité, absence d'effet de seuil |
| `scenarios.json`, `vocabulaire_actifs.json`, `donnees_chercheur.json` | Régénérés |
| `DEPLOIEMENT.md`, `README.md` | Identifiants et adresses IP retirés ; liste des fichiers du paquet ; chiffres à jour |

### Données et configuration

| Fichier | Changement |
|---|---|
| `scripts/compute_metrics.py` | Durée sous l'eau du sommet au retour |
| `scripts/build_asset_criteria.py` | Rôles, liquidité, complexité, dividendes, rentabilité, « établie », « diversifiant », risque pays, devise, fossiles, pays, cycle, emballement, cotation américaine |
| `scripts/fetch_extra_data.py` | Répartitions sectorielles factices des fonds obligataires écartées |
| `scripts/build_scenarios.py` | Audience quotidienne ajoutée aux quatre titres de l'effet de mode |
| `scripts/sync_grille.py`, `scripts/test_grille.py` (nouveaux) | Alignement de la grille sur le code ; test de couverture du vocabulaire |
| `config/criteres_appariement.csv` | Valeurs alignées, colonne `demande`, règles de risque au niveau du portefeuille |
| `config/correspondances.json` (nouveau) | Vocabulaire du profil vers les colonnes des actifs |
| `config/seuils_criteres.json` | Sept seuils ajoutés |
| `data_extended/asset_criteria.csv`, `asset_metrics_cad.csv` | Régénérés, sans nouveau téléchargement des prix |
| `data_extended/etf_sector_weights.csv` | Lignes de BNDW retirées |

### Documentation

`README.md` (sécurité réécrite, chiffres, reproductibilité nuancée), `SECURITY.md`, `.env.example`, `docs/criteres_profil_actifs.md` (régénéré), `docs/plan_et_suivi.md`, `docs/audit_et_plan.md`.

## Ce que les tests couvrent, et ce qu'ils ne couvrent pas

- **Couvert** : toute la logique déterministe, le parcours d'interface avec des agents simulés, la synthèse sur les trois personas, l'alignement de la grille, les corrections de données sur des cas nommés.
- **Non couvert** : le comportement du vrai modèle, la voix (Transcribe, Polly), le site déployé.

## Commandes

```bash
python mvp_profil/test_profil.py
```

```bash
python mvp_profil/test_debat.py
```

```bash
python mvp_profil/test_dynamiques.py
```

```bash
python mvp_profil/test_chercheur.py
```

```bash
python mvp_profil/test_app.py
```

```bash
python mvp_profil/test_conversation.py
```

```bash
python mvp_profil/test_synthese.py
```

```bash
python scripts/test_grille.py
```

```bash
python mvp_profil/evaluer_classement.py --verifier
```
