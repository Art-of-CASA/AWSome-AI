# Déployer le site (profil et propositions)

État au 15 novembre 2026. Le site est **une seule application** : `mvp_profil/app.py`. Les propositions en sont la quatrième étape (`mvp_profil/recommandation/`). Le déploiement existant ne change pas.

## 1. Pousser, c'est déployer

Le flux `.github/workflows/deploy.yml` fait tout à chaque fusion dans `main` qui touche `mvp_profil/` ou `config/` :

1. il lance toutes les suites (`python scripts/lancer_tests.py`), dont les quatre suites `test_reco_*` ;
2. il construit le paquet vérifié (`python scripts/preparer_mvp.py`) : les fichiers de recommandation et leurs données sont dans l'inventaire `version_profil.FICHIERS` ;
3. il installe le paquet sur l'instance, vérifie la page d'accueil et revient en arrière en cas d'échec.

Rien à changer sur le serveur : même point d'entrée (`app.py`), mêmes dépendances (`pandas`, `streamlit`, `boto3` déjà installés avec le SDK). Vérifié ici : le paquet décompressé seul passe la vérification du serveur, puis ouvre les six écrans pour un persona.

## 2. Avant de pousser

```bash
python scripts/build_donnees_recommandation.py
```

```bash
python scripts/lancer_tests.py
```

La première commande n'est nécessaire qu'après un changement de `data_extended/asset_criteria.csv`, des prix ou de `config/` : elle régénère `mvp_profil/recommandation/donnees/`. Si elle est oubliée, `test_reco_contrat.py` échoue et le déploiement n'a pas lieu.

## 3. Ce qui est déjà en place dans le compte AWS

Pile CloudFormation `alphaforge-recommandation` (`infra/alphaforge-recommandation.yaml`), additive : la supprimer retire tout.

| Ressource | Rôle | État |
|---|---|---|
| Politique `alphaforge-recommandation`, attachée au rôle du serveur | Autorise Sonnet 5.5, la table de traces et le Guardrail | Attachée : les agents fonctionneront dès le déploiement |
| Table DynamoDB `alphaforge-traces` | Journal des actions (verdicts figés, appels d'outils, contrôles) | Utilisée automatiquement ; sinon fichier local |
| Guardrail `alphaforge-gouvernance` | Bloque conseil personnalisé et prédiction | Créé, **désactivé par défaut** : il bloque aussi certains refus de prédiction |
| Groupe Cognito `alphaforge-jury` | Accès par identifiant et mot de passe | Créé, **non branché au site** |
| Budget `alphaforge-mvp` | Suivi du coût | Créé |

Les identifiants des ressources se lisent dans l'onglet « Sorties » de la pile.

## 4. Variables d'environnement (toutes facultatives)

| Variable | Effet | Par défaut |
|---|---|---|
| `ALPHAFORGE_TABLE_TRACES` | Nom de la table du journal | `alphaforge-traces` ; fichier local si elle est inaccessible |
| `ALPHAFORGE_TRACES_LOCALES=1` | Force le journal en fichier local | DynamoDB si possible |
| `ALPHAFORGE_GUARDRAIL_ID`, `ALPHAFORGE_GUARDRAIL_VERSION` | Active le Guardrail sur les deux agents | Désactivé |
| `ALPHAFORGE_MODELE_RECOMMANDATION` | Modèle des deux agents | `us.anthropic.claude-sonnet-5-5` |
| `ALPHAFORGE_SANS_MODELE=1` | Force les textes de gabarit | Modèle actif si AWS répond |

## 5. À vérifier après le premier déploiement

1. « Charger Robert » → « Découvrir mes propositions » → « Demande d'un titre » : la ligne « Rédigé par » doit indiquer le modèle, pas « gabarit ».
2. « Pourquoi ? » → « Journal des actions » : le stockage doit indiquer Amazon DynamoDB.
3. Un parcours vocal complet, puis l'ouverture des propositions : le composant vocal n'est pas monté sur ces écrans.

## 6. Accès du jury

Le site reste filtré par adresse IP (fonction CloudFront et groupe de sécurité). Rien n'a été changé. Deux voies :

- ajouter les adresses du jury à la fonction CloudFront, comme pour un coéquipier ;
- brancher le groupe Cognito déjà créé devant le site, puis retirer le filtre. Ce branchement n'est pas fait.

## 7. Mode de secours pour la démonstration

| Niveau | Quand | Quoi |
|---|---|---|
| 1 | Micro ou réseau instable | Personas en un clic, sans voix |
| 2 | Bedrock indisponible | « Réglages de la simulation » → couper la rédaction par le modèle : tout fonctionne, textes de gabarit |
| 3 | Site inaccessible | Lancement local (`streamlit run mvp_profil/app.py`) ou vidéo préenregistrée |
