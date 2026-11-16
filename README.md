# AWSome — comprendre son profil d'investisseur et ce qui lui correspond

**Datathon PolyFinances 2026 · cas « AlphaForge AI » (Banque Nationale × AWS)**

AWSome est un outil **agentique et explicable** : il établit le profil d'un investisseur par une conversation vocale, un questionnaire et trois mises en situation, puis compare ce profil à 111 actifs décrits par des données publiques datées. Il en tire un verdict par actif, un mini-portefeuille fictif et des explications que l'on peut vérifier jusqu'à la donnée source.

> **Simulation éducative.** Profils et montants fictifs, aucun conseil financier personnalisé, aucune transaction réelle.

| | |
|---|---|
| **Application en ligne** | **https://d29e3l5vv5fmjy.cloudfront.net** (HTTPS, micro disponible) |
| Une page | [docs/one_pager.md](docs/one_pager.md) |
| Documentation technique | [docs/documentation_technique.md](docs/documentation_technique.md) : méthodes, sources et licences, hypothèses, explicabilité avec un exemple tracé, validations, limites |
| Script de la vidéo | [docs/script_video.md](docs/script_video.md) |
| Résultats sur les trois personas | [docs/resultats_personas.md](docs/resultats_personas.md) |

---

## Essayer en deux minutes

1. Ouvrir l'application. À l'accueil, **« Charger Amira »**, **« Charger Mateo »** ou **« Charger Robert »** charge un des trois personas de l'énoncé, complété par un questionnaire simulé.
2. La **synthèse** montre le niveau de risque, le budget de perte du portefeuille et la réponse qui le limite. L'onglet **« Hypothèses du profil »** montre, pour chaque critère, ce que l'outil a compris, la citation exacte et la source.
3. **« Découvrir mes propositions »** ouvre le mini-portefeuille fictif, la recherche et la comparaison d'actifs, « Et si… ? » et la **conversation avec le conseiller** : par exemple, Robert demande « 20 % de Nvidia ».
4. **« Découvrir le replay »** (accueil) fait revivre une vraie baisse de marché en accéléré, sans créer de profil.

Le parcours complet (conversation vocale, questionnaire, mises en situation) utilise le micro : autoriser le navigateur à l'utiliser.

## Le problème

Un investisseur dit ce qu'il accepte de perdre ; ce qu'il fait quand la baisse arrive est souvent différent. Un outil qui n'écoute que la déclaration propose des placements que la personne abandonnera au pire moment, et un outil qui dit toujours oui n'aide personne. Les trois personas de l'énoncé testent chacun une capacité :

| Persona | Profil | Ce que l'outil montre |
|---|---|---|
| **Amira**, 26 ans | Risque élevé, 15 ans et plus, intérêt pour l'IA et les cryptoactifs | Un portefeuille de croissance qui reste diversifié et plafonné : 45 % de budget de perte, cryptoactifs limités |
| **Mateo**, 41 ans | Modéré, 8 à 12 ans, exigences ESG | Exclusions et controverses appliquées actif par actif, avec leurs sources : 57 actifs exclus sur 111 |
| **Robert**, 59 ans | Faible à modéré, 3 à 5 ans, tenté par les titres médiatisés | Un « non » argumenté : à 20 % de Nvidia, la perte de stress passerait de 5,3 % à 18,4 % pour un budget de 15 % ; l'outil propose 5 % et n'ajoute rien sans son accord |

## Comment ça marche

```
 PROFIL                         CONTRAINTES               PROPOSITIONS
 conversation vocale  ─┐
 questionnaire         ├─▶ 42 critères ─▶ synthèse ─▶ appariement des 111 actifs ─▶ mini-portefeuille fictif
 3 mises en situation ─┘    (listes       (budget de     (exclusions, plafonds,       conversation, recherche,
 question ouverte ─▶ critères personnels   perte, plafonds)  seuils, préférences)        comparaison, « Et si… ? »
```

1. **Profil.** L'entretien vocal en français et le questionnaire alimentent **42 critères à valeurs fermées**. Trois mises en situation mesurent le comportement : le **replay** d'une vraie baisse (2022, date masquée), le choix entre des **fourchettes** de résultats, et l'**effet de mode** (titres masqués, dont deux très médiatisés). Une dernière question ouverte crée des **critères personnels** (« je travaille chez Shopify », « rien qui touche à Elon Musk », « au moins 10 % en or »).
2. **Synthèse.** Le budget de perte est le plus prudent de trois composantes : ce que la personne **peut** perdre, ce qu'elle **dit** accepter et ce qu'elle a **fait** dans les simulations. La réponse qui limite est nommée.
3. **Appariement.** Chaque actif reçoit un verdict (compatible, à examiner, peu adapté, exclu, données insuffisantes) et un score de 0 à 100, avec ses preuves. Une exclusion ne se rachète par aucune préférence.
4. **Mini-portefeuille fictif.** Construit au niveau du portefeuille : perte de stress, volatilité, durée sous l'eau et tension par rapport au budget. Une contrainte impossible à tenir est nommée, et la part non plaçable reste en encaisse, expliquée.

### Les agents : les modèles comprennent, le code décide

| Agent | Modèle (Amazon Bedrock) | Rôle |
|---|---|---|
| Classificateur et Critique | Claude Haiku 5.5 | Ranger les paroles dans les valeurs autorisées avec la citation exacte ; le critique conteste les lectures trop rapides |
| Découvreur | Claude Haiku 5.5 | Transformer la réponse ouverte en règles exprimées avec le vocabulaire réel des actifs |
| Chercheur | Claude Haiku 5.5 + outils | Trouver les actifs liés à un concept (nos données, Wikipédia), preuve recopiée mot pour mot |
| Conseiller et Explicateur | Claude Sonnet 5.5 + outils | Comprendre une demande, appeler l'outil voulu, expliquer un verdict déjà calculé |

Seuils, validations, verdicts, scores et poids sont **déterministes**. Une citation absente des mots de l'utilisateur, une valeur hors liste ou une preuve introuvable dans une source réellement lue sont rejetées par le code. Le verdict d'une demande est figé avant que le modèle lise la justification de la personne.

### Explicabilité

- Chaque valeur du profil garde sa **source** (QCM, conversation, simulation, déduction), la **citation exacte** et la **confiance**.
- Chaque chiffre affiché renvoie à une **donnée datée** (fichier, valeur, période, origine).
- Ce qui reste inconnu est **affiché comme inconnu**, jamais comblé par une valeur inventée.
- « Détails techniques » montre les outils appelés, leurs entrées et sorties, et le journal des contrôles ; le raisonnement interne des modèles n'est ni affiché ni journalisé.
- Une expérience compare avec un portefeuille construit par le modèle seul : [docs/experience_modele_seul.md](docs/experience_modele_seul.md).

## Services AWS

| Service | Usage |
|---|---|
| Amazon Bedrock | Claude Haiku 5.5 (profil, critères, chercheur), Claude Sonnet 5.5 (conseiller, explicateur) |
| Amazon Bedrock Guardrails | Créé (ni conseil personnalisé, ni prédiction, données personnelles masquées) mais désactivé par défaut : il bloquait aussi des refus légitimes. Les contrôles de gouvernance du code s'appliquent toujours |
| Amazon Transcribe et Amazon Polly | Entretien vocal en français canadien (transcription en continu, voix Gabrielle) |
| Amazon EC2 | Application Streamlit (service systemd), rôle IAM aux droits minimaux, aucune clé stockée |
| Amazon CloudFront | HTTPS, nécessaire au micro du navigateur |
| Amazon S3 et AWS Systems Manager | Paquet de déploiement vérifié, installation à distance sans port SSH |
| Amazon DynamoDB | Traces observables des propositions (verdicts figés, appels d'outils, contrôles) |
| AWS Budgets, IAM | Alerte de coût ; rôles séparés pour le serveur et pour le déploiement (GitHub OIDC, sans clé longue durée) |

## Données

- **111 actifs** : les 31 du jeu de départ des organisateurs et 80 ajoutés (Europe, Asie, Afrique, Amérique latine, Moyen-Orient, FNB mondiaux, actifs stables, et des secteurs qui contrastent les valeurs : tabac, armement, alcool, jeux d'argent, nucléaire, fossiles, renouvelables).
- Période du **12 novembre 2021 au 12 novembre 2026**, tout converti en **dollars canadiens** (Banque du Canada).
- Sources : Yahoo Finance (yfinance), Banque du Canada (Valet), ALFRED, Wikimedia Pageviews, BlackRock (positions de XEN, indice Jantzi), Norme d'hypothèses de projection 2026 de FP Canada et de l'IPF. Sources, traitements, licences et limites : [docs/documentation_technique.md](docs/documentation_technique.md) et `data_extended/README.md`.
- Toutes les règles et tous les seuils sont des **hypothèses écrites** dans `config/` et `mvp_profil/hypotheses_profil.json`, et non des normes.

## Lancer en local

```bash
py -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt -r mvp_profil/requirements.txt
.venv/Scripts/streamlit run mvp_profil/app.py
```

Les personas, la synthèse et les propositions fonctionnent sans accès au modèle. Les parcours qui analysent de nouvelles réponses demandent des identifiants AWS temporaires (variables `AWS_*` ou `~/.aws`) ou une clé de l'API Anthropic saisie dans « Connexion et réglages ». Les versions des dépendances sont figées par `mvp_profil/constraints.txt`.

```bash
.venv/Scripts/python scripts/lancer_tests.py
.venv/Scripts/python mvp_profil/evaluer_classement.py --verifier
```

Les tests sont hors ligne et sans coût : les réponses des modèles et des services vocaux sont simulées. Ils vérifient les règles, l'orchestration et l'interface, pas l'exactitude réelle des modèles. Node.js est nécessaire aux tests du composant vocal.

## Déploiement et sécurité

- **Déploiement continu.** Chaque mise à jour de `main` qui touche le site lance tous les tests dans GitHub Actions, construit un paquet vérifié (`scripts/preparer_mvp.py` : inventaire, empreintes, version), puis l'installe sur l'instance par Systems Manager (`scripts/installer_serveur.sh`). Si la page ne s'ouvre pas, la version précédente est remise en place automatiquement. La version installée s'affiche dans « Connexion et réglages ».
- **Aucun secret** dans le dépôt ni dans l'application : le serveur utilise son rôle IAM, la CI un rôle temporaire obtenu par OIDC.
- **Site public, sans fuite.** Les messages d'erreur montrés à l'écran sont nettoyés de tout identifiant d'infrastructure (compte, rôle, instance, adresse, clé : `mvp_profil/confidentialite.py`) ; le site n'affiche aucune trace d'erreur ni menu de développement ; chaque session ne voit que ses propres données. Un test vérifie qu'aucun fichier publié ne contient d'identifiant.
- **Données saisies.** Les réponses orales passent par Amazon Transcribe et Amazon Bedrock. Utilisez des informations fictives : l'outil est une simulation.

## Organisation du dépôt

```
mvp_profil/                  application Streamlit : profil, agents, voix, mises en situation, interface, tests
mvp_profil/recommandation/   propositions : appariement, portefeuille fictif, agents, conversation, écrans
scripts/                     collecte et calcul des données, préparation et installation du paquet, tests
config/                      grille des critères, seuils, correspondances profil ↔ actifs, règles d'appariement
data_extended/, data_extra/  données des actifs (prix, change, états financiers, FNB, ESG, attention)
Datathon2026/                jeu de départ des organisateurs
infra/                       ressources AWS des propositions (CloudFormation)
docs/                        documentation technique, une page, script vidéo, résultats, fonctionnement détaillé
```

Le fonctionnement détaillé du profil (critères, agents, chercheur, règles de validation) est décrit dans [docs/fonctionnement_profil.md](docs/fonctionnement_profil.md) ; l'infrastructure du parcours dans [docs/infrastructure_profil.md](docs/infrastructure_profil.md).

## Limites

- Les indicateurs décrivent le passé (2021-2026) et ne prédisent rien ; les seuils sont des hypothèses de l'équipe.
- Les choix faits dans une simulation complètent la tolérance déclarée, sans prouver le comportement avec de l'argent réel.
- Le portefeuille fictif est une heuristique explicable, pas une optimisation.
- La fiabilité réelle de la transcription et du classement par les modèles n'a pas été mesurée sur un jeu annoté ; les confiances déclarées ne sont pas des probabilités calibrées.
- Les exclusions ESG ne couvrent que les implications connues, sans seuil de revenus.
