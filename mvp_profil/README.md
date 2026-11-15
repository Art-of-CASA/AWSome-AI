# MVP : questionnaire de profil d'investisseur

Site Streamlit qui établit le profil d'un investisseur. Il combine des questions fermées (QCM, curseurs, quiz) et des questions libres, classées par deux agents Claude Haiku 5.5. Les critères sont ceux de [config/criteres_appariement.csv](../config/criteres_appariement.csv). Simulation éducative : aucun conseil financier.

**Version hébergée sur AWS : https://d29e3l5vv5fmjy.cloudfront.net** (HTTPS via CloudFront, micro disponible ; accès limité à une IP ; voir [DEPLOIEMENT.md](DEPLOIEMENT.md)). Les modèles tournent sur **Amazon Bedrock**, dans le compte du datathon (us-east-1, profil d'inférence `us.anthropic.claude-haiku-5-5`), grâce au rôle IAM du serveur : aucune clé à gérer.

## Parcours

L'accueil propose deux parcours.

**🎙️ Conversation vocale mains libres (recommandé).** Une discussion à voix haute, comme le mode vocal de ChatGPT, couvre les 16 critères de contexte : objectif, horizon, retraits, revenu, épargne, fonds d'urgence, situation, emploi, personnes à charge, dettes, expérience d'une baisse, produits détenus, régions et thèmes.
- **Un seul clic, « Démarrer »**, exigé par les navigateurs pour le micro et le son. Ensuite, aucun bouton ni enregistrement à gérer. Le composant ([composant_voix/index.html](composant_voix/index.html)) détecte dans le navigateur quand l'utilisateur commence à parler, puis quand il a fini (0,8 s de silence), et envoie la phrase tout seul.
- **Voix (services AWS)** : la phrase est transcrite par **Amazon Transcribe** (fr-CA). La réplique de l'IA est lue par **Amazon Polly** (voix neuronale « Gabrielle », fr-CA), sans lecteur visible, puis l'écoute reprend automatiquement. Pendant que l'IA parle, le micro n'écoute pas, pour qu'elle ne s'entende pas elle-même.
- **« Pouvez-vous répéter ? »** à l'oral suffit : l'IA répète ou reformule sa question.
- **Rapidité** : l'utilisateur n'attend qu'**un appel court** par tour, la réplique ([entretien.py](entretien.py)). Le classificateur et le critique travaillent **en arrière-plan** pendant que l'IA parle et que l'utilisateur répond. Le panneau de droite passe de ⏳ à ✅ tout seul, avec la citation qui justifie chaque critère. Un sujet abordé mais pas assez clair (🔁) est **reformulé une seule fois**, avec un seuil abaissé à 65 % ; ensuite, la meilleure réponse obtenue est **retenue** (☑️, si elle atteint 50 %), au lieu de reposer la question.
- **La voix n'est plus coupée** : le composant est placé à une position fixe de la page, donc il n'est jamais recréé quand une coche ✅ rafraîchit l'écran. Auparavant, chaque rafraîchissement recréait le lecteur audio et interrompait la voix.
- On peut aussi répondre au clavier, à tout moment.
- À la fin, ou sur « Passer aux questions suivantes », ce que la conversation n'a pas validé **revient sous forme de QCM** dans une page « Compléments ». Le parcours continue ensuite avec les pages ci-dessous, à partir de « Vous et le risque ».

Mesuré en ligne le 14 novembre 2026 : réplique de l'IA en **1,7 s** sur le serveur (contre 4,5 s avant), réponse jouée environ 3 s après l'envoi, transcription en 1,4 s. Une réponse (« retraite dans une quinzaine d'années, infirmier, deux enfants ») a coché 4 critères **pendant** que l'IA parlait, et la réplique de 13 s a été lue en entier.

**📝 Questionnaire classique.** Toutes les questions page par page, comme ci-dessous.

**1. Questionnaire fixe : les mêmes 34 questions, dans le même ordre, pour tout le monde.** 6 pages (4 en parcours conversation) :

| Page | Contenu |
|---|---|
| Votre projet | Objectif, horizon, retraits prévus, besoin de revenu (QCM) |
| Votre situation | Part de l'épargne, fonds d'urgence (QCM) + situation personnelle (**libre**) |
| Vous et le risque | Réaction à −20 % (QCM), baisse à laquelle on vendrait (**curseur**), volatilité acceptée, durée de récupération supportable, expérience d'une baisse, fréquence de consultation |
| Vos connaissances | **Mini-quiz** de 3 questions (le score donne le niveau), produits déjà détenus |
| Vos préférences | Classes d'actifs, part de cryptos, placements spéculatifs, risque de change, régions, style, attrait des titres médiatisés + thèmes aimés et refusés (**libre**) |
| Vos valeurs et votre compte | Énergies fossiles, controverses, exigence ESG, exclusions sectorielles, pays exclus, type de compte |

Les valeurs de volatilité, de récupération, d'exclusions et de risque pays sont **les mêmes que les mots-clés calculés pour les actifs** (`kw_*` dans [asset_criteria.csv](../data_extended/asset_criteria.csv)) : la comparaison profil ↔ actif est directe.

- **Réponses fermées :** la valeur vient directement de la réponse, sans IA. C'est instantané et reproductible.
- **Réponses libres :** elles sont classées par les deux agents **en arrière-plan**, pendant que l'utilisateur passe à la page suivante.

**1 bis. Trois mises en situation : ce que l'utilisateur fait, pas seulement ce qu'il dit** ([simulations.py](simulations.py)). Les données sont précalculées dans [scenarios.json](scenarios.json) par `scripts/build_scenarios.py`.

| Mise en situation | Déroulement | Ce qu'on mesure |
|---|---|---|
| **Replay d'un marché qui baisse** | 10 000 $ dans un portefeuille proche du profil déclaré (équilibré 60/40, 100 % actions ou technologie), sur une vraie période dont la date est masquée (2022). 4 arrêts identiques pour tous (mois 3, 6, 9, 12) : garder, réduire de moitié, tout vendre, renforcer. Ensuite, on révèle la suite et ce qu'aurait donné « ne rien faire » | **Point de rupture observé (B2)**, comparé au déclaré (B1) : **le plus prudent l'emporte**. Un écart de 2 classes ou plus rend le profil incertain sur ce point (H1) |
| **Fourchettes de résultats** | Choix entre 5 portefeuilles décrits par ce qu'ils pourraient valoir dans un an (mauvaise année 1 sur 20, année typique, bonne année) | **Arbitrage risque/rendement (B6)**, comparé à la volatilité déclarée (B5) |
| **Effet de mode** | Placer 1 000 $ dans un seul titre parmi 4 (noms masqués) : 2 très médiatisés (Nvidia, Tesla : pic d'attention, forte volatilité) et 2 établis peu médiatisés (Fortis, RBC), avec leurs faits mesurés | **Attrait observé pour un titre médiatisé (D8O)**, comparé au déclaré (D8) : c'est le test de Robert |

Les fourchettes reprennent la **dispersion** réelle des rendements 2021-2026 (10 000 années rééchantillonnées par blocs d'un mois), centrée sur les **rendements attendus de la Norme d'hypothèses de projection 2026** de FP Canada et de l'Institut de planification financière (revenu fixe 3,2 %, actions entre 6,3 % et 7,5 %). Nos 5 années seules auraient été trompeuses : en 2022, obligations et actions ont baissé ensemble, et le portefeuille très prudent y paraissait plus risqué que le 100 % actions.

**Questions qui s'adaptent.**
- L'IA **déduit** ce qui découle nécessairement des paroles. Par exemple, « le crédit pour les études de mon fils » donne au moins une personne à charge ; quand le critique hésite, l'IA fait **confirmer** en une phrase.
- Chaque réponse libre est aussi lue pour **tous les critères encore inconnus**.
- Des **règles certaines** s'appliquent (`profil.REGLES_DEDUCTION`).

Une question dont le critère est déjà connu est **retirée de sa page** (« ✨ 1 question retirée »). Détail et mesures dans le [README principal](../README.md#des-questions-qui-sadaptent-à-ce-que-la-personne-a-déjà-dit).

**2. Précisions de fin de parcours, à la voix.** L'IA lit la question, et on répond à l'oral ou au clavier.
- Pour une contradiction, elle énonce les possibilités, et un agent reconnaît celle qui est choisie à l'oral.
- « Pouvez-vous répéter ? » fait relire la question.
- Le composant vocal est le même que celui de la conversation : il reste en veille pendant les questions à choix, et aucun nouveau clic n'est nécessaire.

Trois cas déclenchent une question de précision :
- une option « Je ne sais pas » ou une case vide ;
- une réponse libre que les agents n'ont pas pu valider ;
- une **contradiction** entre deux réponses, repérée par des règles fixes ([profil.py](profil.py)). Par exemple : « je vends tout à −20 % » avec un curseur réglé à −40 % ; un coussin de sécurité placé pour plus de 10 ans ; des cryptos refusées mais 10 % acceptés ; l'exclusion des fossiles alors que l'énergie fossile est citée parmi les intérêts ; « pas de spéculatif » mais des cryptos acceptées ; une faible volatilité acceptée mais un point de rupture à −40 % ; une activité à la fois exclue et citée parmi les intérêts ; un portefeuille choisi dans les fourchettes qui contredit la volatilité déclarée ; « pas tenté par les titres médiatisés » mais un titre médiatisé choisi (10 règles en tout).

Chaque précision n'est posée **qu'une fois** : c'est déjà une question reformulée, donc le seuil est abaissé à 65 %. Si elle ne suffit pas, on **retient la meilleure réponse** obtenue sur toutes les tentatives (statut « retenu », confiance affichée), à condition qu'elle atteigne le plancher de 50 %. Sinon, le critère est marqué **« incertain »**, et l'outil devra appliquer le réglage le plus prudent.

**2 bis. Question ouverte finale, à la voix → critères dynamiques** ([criteres_dynamiques.py](criteres_dynamiques.py)). « Y a-t-il quelque chose de particulier que nous n'avons pas abordé et que vous aimeriez préciser ? » L'agent **découvreur** transforme la réponse en critères propres à la personne (X1, X2…). Chacun est une règle `exclure` / `plafonner` (avec un %) / `privilegier` / `note`, exprimée avec le **vocabulaire réel des actifs** ([vocabulaire_actifs.json](vocabulaire_actifs.json) : 17 dimensions, 234 valeurs, issu de `asset_criteria.csv`).

Le **critique** vérifie chaque critère, et le code contrôle la dimension, les valeurs et la citation, puis calcule les actifs concernés. Exemple : « je travaille chez Shopify et j'ai déjà plein d'actions de mon employeur » donne « Exclure : titre = SHOP.TO (1 actif) ». Exclure ou plafonner un titre signale aussi les **FNB qui le détiennent** : XIU.TO détient 6,4 % de Shopify. Une idée qui vise des actifs sans valeur existante pour la traduire (« rien qui touche à Elon Musk ») part à l'**agent chercheur** ([chercheur.py](chercheur.py)), en arrière-plan. Il fouille nos données et Wikipédia, et n'accepte que des preuves recopiées mot pour mot d'une source réellement lue, vérifiées ensuite par le critique. Il en fait un nouveau mot-clé `kw_dyn_…`, mis en cache pour les utilisateurs suivants. Les preuves s'affichent sur la page finale. Une idée qui ne vise aucun actif devient une **note** : elle est conservée et citée, mais ne filtre rien. Le principe est détaillé dans le [README principal](../README.md#critères-dynamiques--propres-à-chaque-personne-mvp_profilcriteres_dynamiquespy).

**3. Profil final.** Chaque critère est affiché avec sa source (QCM, curseur, quiz, IA, cohérence ou question ouverte), sa confiance et son statut (validé, retenu ou incertain), puis les critères dynamiques. Le tout se télécharge en JSON, avec la trace des débats.

## Débat des agents (réponses libres)

1. Le **classificateur** propose une valeur de la liste fermée, avec la citation exacte de l'utilisateur et une confiance.
2. Le code fait un **précontrôle** : la valeur est-elle autorisée, la citation existe-t-elle vraiment, la confiance atteint-elle le seuil (**80 % par défaut**) ? Si non, le critère part directement en précision : le critique n'est pas appelé, ce qui fait gagner du temps.
3. Le **critique** vérifie les autres critères. S'il conteste, le classificateur révise, sur au plus 2 tours.
4. Un critère est validé seulement si le critique est d'accord et si les deux confiances atteignent le seuil. C'est le code qui décide, pas les modèles.
5. La citation est comparée sans tenir compte de la ponctuation ni de la casse, car la transcription vocale ponctue au hasard. Le critique a pour consigne de ne pas contester une réponse claire pour une nuance : cela faisait reposer des questions déjà répondues.

**Vitesse mesurée sur le serveur** (14 novembre 2026, Bedrock) : une réponse claire sur 4 critères est validée en 4,5 s (2 appels) ; une réponse vague est renvoyée en précision en 2,2 s (1 appel). Les appels se font sans raisonnement étendu, avec des réponses courtes.

## Lancer en local

```bash
.venv/Scripts/python -m pip install -r mvp_profil/requirements.txt
.venv/Scripts/streamlit run mvp_profil/app.py
```

En local, le SDK a besoin d'identifiants AWS : il les lit dans les variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` et `AWS_SESSION_TOKEN` (identifiants temporaires de la page de l'événement) ou dans `~/.aws`. En secours, la barre latérale permet de passer à l'API Anthropic avec une clé.

## Fichiers

| Fichier | Rôle |
|---|---|
| `synthese.py`, `hypotheses_profil.json` | Synthèse déterministe du profil : capacité, tolérance déclarée et observée, budget de perte, réglages prudents appliqués. Toutes les tables sont des hypothèses déclarées |
| `personas/` | Les trois profils fictifs de l'énoncé (Amira, Mateo, Robert) ; chaque valeur est marquée « énoncé » ou « hypothèse de test » |
| `criteres.py` | Les 42 critères fixes (valeurs autorisées, question de précision) et le questionnaire fixe |
| `profil.py` | Logique déterministe : curseur et quiz vers valeurs, règles de cohérence, comparaison déclaré/observé |
| `simulations.py` | Les 3 mises en situation (replay, fourchettes, effet de mode) |
| `entretien.py` | Conversation : réplique rapide, analyse en arrière-plan (classificateur + critique), Transcribe et Polly |
| `voix_composant.py`, `composant_voix/index.html` | Composant vocal mains libres : détection de la parole, envoi automatique, lecture de la voix de l'IA |
| `test_conversation.py` | Parcours conversation (agents et voix simulés) : coche en direct, critère refusé puis repris, page Compléments, conversion audio |
| `scenarios.json` | Données précalculées des mises en situation (`scripts/build_scenarios.py`) |
| `agents.py` | Classificateur, critique, débat accéléré, accès Bedrock, règle de relance (seuil 80 % puis 65 %, meilleure réponse, plancher 50 %) |
| `criteres_dynamiques.py` | Question ouverte finale : agent découvreur + critique, contrôle sur le vocabulaire des actifs, actifs concernés |
| `chercheur.py` | Agent chercheur : boucle d'outils (nos données, Wikipédia), contrôle des preuves, critique, FNB exposés, cache des mots-clés `kw_dyn_*` |
| `donnees_chercheur.json` | Fiches, positions des FNB, actualités et controverses des 66 actifs (`scripts/build_donnees_chercheur.py`) |
| `test_chercheur.py` | Chercheur sur faux serveur : 3 outils, preuves vérifiées ou écartées, identifiant de source corrigé, FNB exposés, cache |
| `vocabulaire_actifs.json` | Dimensions et valeurs des 66 actifs, avec les tickers de chaque valeur (`scripts/build_vocabulaire.py`) |
| `test_dynamiques.py` | Critères dynamiques (exclusion d'un titre, préférence retenue, plafond, note, citation inventée écartée) et règles de relance |
| `app.py` | Interface Streamlit (questionnaire, précisions, profil) |
| `test_profil.py` | Tests de la logique déterministe et de la cohérence du questionnaire |
| `test_debat.py` | Tests du débat (7 scénarios, dont Bedrock) : faux serveur, vrai SDK, aucun coût |
| `test_app.py` | Parcours complet dans l'interface (agents simulés) : « Je ne sais pas », réponse floue, mises en situation, 4 contradictions ; second scénario où l'utilisateur vend pendant le replay |

```bash
.venv/Scripts/python mvp_profil/test_profil.py
.venv/Scripts/python mvp_profil/test_debat.py
.venv/Scripts/python mvp_profil/test_dynamiques.py
.venv/Scripts/python mvp_profil/test_chercheur.py
.venv/Scripts/python mvp_profil/test_app.py
.venv/Scripts/python mvp_profil/test_conversation.py
```

## Limites

- **Micro :** les navigateurs n'autorisent le micro qu'en **HTTPS** (ou sur `localhost`) : utiliser l'adresse CloudFront. Le navigateur demande l'autorisation au clic sur « Démarrer ». L'adresse HTTP directe reste utilisable à l'écrit.
- **Conversation à l'alternat :** on ne peut pas couper la parole à l'IA pendant qu'elle parle ; on répond quand elle a fini. Dans une pièce bruyante, la détection de la parole peut se déclencher sur un bruit (une phrase vide est ignorée) ; le seuil est calibré sur le bruit ambiant pendant 0,7 s au démarrage.
- **Transcription :** Transcribe peut mal entendre un mot (« dettes » compris « de ») ; le critère concerné reste alors sous le seuil et l'IA le redemande.
- **Couverture :** le questionnaire couvre 38 critères déclarés ou mesurés par le quiz. Restent hors parcours, par choix : A11, C3, D10, E3, F1, G4, G5 (voir la colonne `demande` de la grille). (Ancienne note : frais, inquiétude face aux taux…) restent à ajouter.
- **Mises en situation :** en simulation, on est souvent plus courageux qu'avec son propre argent. C'est pourquoi le plus prudent entre le déclaré et l'observé l'emporte. Un utilisateur qui reconnaît 2022 peut aussi anticiper la remontée.
- **Seuils :** les seuils, les classes du curseur et les règles de cohérence sont des hypothèses. Les confiances des modèles ne sont pas des probabilités calibrées.
- **Aucun lien avec les actifs :** l'étape suivante est de comparer le profil à [asset_criteria.csv](../data_extended/asset_criteria.csv).
