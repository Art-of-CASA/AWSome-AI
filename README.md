# AlphaForge AI : outil de décision d'investissement explicable (Datathon PolyFinances 2026)

Prototype du cas « AlphaForge AI » (Banque Nationale, AWS) : un outil **agentique et explicable** qui établit le profil d'un investisseur par une conversation, puis vérifie si des actifs lui correspondent, critère par critère, avec des données publiques datées. **Simulation éducative uniquement** : aucun conseil financier personnalisé, aucune transaction réelle.

Ce document explique toute la démarche : le but, les principes, les données, les critères, le fonctionnement du site et des agents, ce qui reste à faire. Il s'adresse aussi aux **assistants IA** qui reprendront le projet (voir « Pour les assistants IA » à la fin).

**Site en ligne : https://d29e3l5vv5fmjy.cloudfront.net** (accès limité aux IP de l'équipe ; voir [mvp_profil/DEPLOIEMENT.md](mvp_profil/DEPLOIEMENT.md)).

---

## 1. Le problème et les trois personas

Le cas demande un outil qui aide trois profils fictifs à prendre une décision d'investissement **compréhensible et vérifiable** :

| Persona | Profil | Ce que l'outil doit savoir faire |
|---|---|---|
| **Amira** | Risque élevé, horizon de 15 ans ou plus | Accepter la volatilité, sans la laisser concentrer tout son risque au même endroit |
| **Mateo** | Risque modéré, préférences ESG | Appliquer ses exclusions (fossiles, controverses) de façon traçable |
| **Robert** | Risque faible à modéré, 3 à 5 ans, tenté par les titres à la mode | Détecter l'écart entre ce qu'il dit et ce qu'il ferait, et le protéger de l'effet de mode |

## 2. L'idée centrale : un profil reproductible, comparé aux actifs par des mots-clés

1. **On pose des questions** (conversation orale ou écrite, QCM, curseurs, quiz, mises en situation).
2. **L'IA classe les réponses dans une liste fermée de mots-clés** par critère (exemple : horizon = `moins_3_ans`, `3_5_ans`, `5_10_ans`, `10_15_ans` ou `plus_15_ans`). Avec la même réponse, on obtient le même profil : il est **reproductible**.
3. **Chaque actif est classé sous les mêmes mots-clés**, cette fois par du code, à partir de données datées : volatilité, perte maximale, récupération, exclusions ESG, risque pays, devise, attention médiatique…
4. **Une règle d'appariement écrite à l'avance** compare les deux côtés. Elle donne un verdict par critère : cohérent, à surveiller ou en tension.

Les principes qui en découlent, à respecter partout :

- **Les modèles classent, le code décide.** Seuils, valeurs autorisées, validation, verdicts, règle « le plus prudent l'emporte » : tout ce qui décide est déterministe.
- **Tout est justifié.** Chaque valeur du profil garde sa source (QCM, curseur, quiz, IA, mise en situation, cohérence), la citation exacte de l'utilisateur et la confiance. Chaque valeur d'actif renvoie à un fichier daté.
- **On mesure aussi ce que la personne fait.** Trois mises en situation comparent le comportement observé au déclaré. En cas d'écart, le plus prudent des deux l'emporte.
- **Dans le doute, on applique le réglage le plus prudent.**

## 3. Architecture d'ensemble

```
            DONNÉES (scripts/ -> data_extra/, data_extended/)
  prix, change, dividendes, états financiers, FNB, ESG, attention, macro
                              │  code (scripts/build_asset_criteria.py)
                              ▼
     asset_criteria.csv : 66 actifs × 100 colonnes, dont 23 mots-clés kw_*
                              │
  PROFIL (mvp_profil/, site Streamlit + Claude Haiku 5.5 sur Bedrock)     │
  conversation ─▶ classificateur ⇄ critique ─▶ critères fixes (37)        │
  questionnaire, quiz, mises en situation ─▶ valeurs sans IA              │
  question ouverte ─▶ découvreur ⇄ critique ─▶ critères dynamiques (X1…) ─┤
        └─ concept sans valeur ─▶ chercheur (données + Wikipédia) ⇄ critique  │
                                  ─▶ nouveau mot-clé kw_dyn_… (preuves)  ──┤
                              │                                          │
                              ▼                                          ▼
          APPARIEMENT (à construire) : règles de config/criteres_appariement.csv
          exclusions -> plafonds -> seuils -> préférences -> verdict expliqué
```

## 4. Les données

| Dossier | Contenu | Produit par |
|---|---|---|
| `Datathon2026/alphaforge_starter/` | Jeu de départ des organisateurs : 31 actifs (Canada, États-Unis, FNB, obligations, or, cryptos), prix, USD/CAD, taux | Organisateurs |
| `data_extra/` | Pour les 31 actifs de départ : états financiers et ratios, FNB (frais, positions, secteurs), ESG (implication fossile, controverses sourcées), attention Wikipédia, actualités, dates de publication macro (ALFRED) | `scripts/fetch_extra_data.py`, `build_esg.py`, `fetch_macro_release_dates.py` |
| `data_extended/` | **35 actifs ajoutés** (10 Europe, 10 Asie, 10 Afrique, 5 FNB mondiaux), même jeu de données ; change vers le CAD pour 12 devises ; puis **indicateurs et mots-clés des 66 actifs** | `build_extended_prices.py`, `compute_metrics.py`, `fetch_market_caps.py`, `build_asset_criteria.py` |
| `config/` | `criteres_appariement.csv` (50 critères : question, valeurs du profil, critère d'actif, règle, type de règle, personas) et `seuils_criteres.json` (tous les seuils, qui sont des hypothèses) | Équipe |
| `docs/criteres_profil_actifs.md` | La grille lisible : principe, 8 blocs de critères (A situation à H gouvernance), calcul des mots-clés, test sur les 3 personas | Équipe |

Ordre pour tout régénérer : `fetch_extra_data.py` → `fetch_macro_release_dates.py` → `build_esg.py` → `build_extended_prices.py` → `compute_metrics.py` → `fetch_market_caps.py` → `build_asset_criteria.py` → `build_scenarios.py` → `build_vocabulaire.py` → `build_donnees_chercheur.py`.

Points à connaître (le détail est dans les README de chaque dossier) :
- Tout est **converti en CAD**, car l'investisseur est canadien. Change de la Banque du Canada ; taux croisés pour DKK et EGP.
- Corrections faites : sous-unités (pence, cents sud-africains) ; deux jours avec des prix 100 fois trop petits ; un faux fractionnement 5000:1 de Naspers.
- Sources : Yahoo/yfinance, Banque du Canada (Valet), ALFRED, Wikimedia Pageviews, BlackRock (positions de XEN), Norme d'hypothèses de projection 2026 de FP Canada et de l'IPF (rendements attendus des fourchettes).
- Afrique : Yahoo ne couvre ni Lagos, ni Nairobi, ni Casablanca. Neuf actions africaines sur dix sont donc sud-africaines.

## 5. Les critères

### Côté profil : 37 critères fixes ([mvp_profil/criteres.py](mvp_profil/criteres.py))

Les identifiants sont ceux de la grille : A situation et capacité, B risque, C connaissances, D préférences, E valeurs, F pays, G compte, H cohérence. Chaque critère a une **liste fermée** de valeurs et une question de précision. Quatre sont **mesurés** par les mises en situation et non déclarés :
- B2, le point de rupture observé au replay ;
- B6, l'arbitrage risque-rendement choisi dans les fourchettes ;
- D8O, l'attrait observé pour un titre médiatisé ;
- H1, l'écart entre le déclaré et l'observé.

### Côté actifs : mots-clés calculés ([data_extended/asset_criteria.csv](data_extended/asset_criteria.csv))

Pour chacun des 66 actifs, le fichier donne :
- les indicateurs en CAD : volatilité, perte maximale, jours de récupération, choc de 2022, bêta, corrélations, dividendes, ratios financiers ;
- 23 mots-clés `kw_*` : `kw_volatilite`, `kw_recuperation`, `kw_exclusions`, `kw_risque_pays`, `kw_devise`, `kw_attention`, `kw_frais`…

Plusieurs critères du profil utilisent **exactement les mêmes valeurs** que les mots-clés d'actif (B5 ↔ `kw_volatilite`, B7 ↔ `kw_recuperation`, E5 ↔ `kw_exclusions`, F2 ↔ `kw_risque_pays`) : la comparaison est directe.

### Critères dynamiques : propres à chaque personne ([mvp_profil/criteres_dynamiques.py](mvp_profil/criteres_dynamiques.py))

Les critères fixes couvrent les cas prévus, pas les particularités de chacun. Par exemple : « je travaille chez Shopify et j'ai déjà beaucoup d'actions de mon employeur », « je m'installe en Europe dans 5 ans », « pas plus de 10 % de banques », « rien qui touche à Elon Musk ». **À la toute fin du parcours, une question ouverte** demande ce que la personne aimerait encore préciser, et l'IA en tire des critères créés pour elle (X1, X2…).

**Un critère dynamique est relié aux données des actifs dès sa création.** Ce n'est pas du texte libre, mais une règle `(effet, dimension, valeurs)` exprimée avec le **vocabulaire réel des actifs**. Ce vocabulaire est contenu dans [vocabulaire_actifs.json](mvp_profil/vocabulaire_actifs.json), extrait de `asset_criteria.csv` par `scripts/build_vocabulaire.py`. Il compte 17 dimensions et 234 valeurs, chacune avec la liste des tickers qui l'ont :

| Effet | Type de règle (même typologie que la grille) | Exemple |
|---|---|---|
| `exclure` | `exclusion` : l'actif est retiré | titre = `SHOP.TO` (son employeur) → 1 actif |
| `plafonner` (+ %) | `plafond` : poids maximal | thème = `banque`, 10 % au plus → 8 actifs |
| `privilegier` | `preference` : trie les suggestions, n'améliore jamais la compatibilité | devise = `EUR` → 5 actifs |
| `note` | `information` : gardé et cité, aucun filtre automatique | « rien qui touche à Elon Musk » (aucune valeur existante ne le traduit) |

Dimensions disponibles :
- `titre`, `classe`, `region`, `pays`, `devise`, `secteur`, `theme` ;
- les mots-clés `exclusion`, `risque_pays`, `exposition_devise`, `taille`, `distribution`, `cycle`, `concentration`, `attention` et `fiscalite` ;
- `role`.

Le code contrôle tout :
- la dimension doit exister et les valeurs y être présentes, sinon le critère devient une note : on ne filtre jamais sur une valeur inventée ;
- la citation doit être exacte, sinon le critère est écarté ;
- le critique doit être d'accord avec les deux confiances au-dessus du seuil pour que le critère soit **validé** ;
- au-dessus du plancher de 50 %, le critère est **retenu** et signalé ;
- en dessous, il n'est pas créé.

Le code calcule aussi les **actifs concernés**. Chaque critère est exporté avec sa règle lisible, sa colonne d'actif, sa citation et sa confiance.

**Quand le vocabulaire ne suffit pas : l'agent chercheur ([mvp_profil/chercheur.py](mvp_profil/chercheur.py)).** Certaines idées visent des actifs, mais aucune valeur existante ne les traduit : « rien qui touche à Elon Musk », « les entreprises qui recyclent ». Le découvreur crée alors le critère « à étiqueter », avec un **concept** à rechercher. Un deuxième agent, le **chercheur**, prend le relais **en arrière-plan**, pendant que le profil s'affiche :

1. **La recherche.** Le chercheur reçoit le tableau des 66 actifs et quatre outils :
   - `chercher_dans_donnees` : noms, secteurs, thèmes, controverses, actualités récentes et positions des FNB ;
   - `fiche_actif` ;
   - `recherche_web` et `lire_page_web` : Wikipédia en français ou en anglais.

   Pour chaque actif concerné, il rend « oui » ou « partiel », avec une **preuve**. La preuve est un passage recopié mot pour mot d'un résultat d'outil, et l'identifiant de sa source.
2. **Le contrôle par le code.** Le ticker doit exister, et le passage doit se trouver **mot pour mot dans une source réellement lue** pendant cette recherche. C'est le même principe que la citation exacte de l'utilisateur. Sinon, le verdict est écarté.
3. **La vérification par le critique.** Il contrôle que chaque preuve justifie bien le verdict. Un désaccord écarte le verdict.
4. **La transparence des FNB, calculée par le code.** Un FNB qui détient un actif concerné parmi ses principales positions est signalé avec le poids de cette position : SPY détient TSLA à 1,7 %, XIU.TO détient SHOP.TO à 6,4 %. Cela vaut aussi pour l'exclusion d'un titre choisi directement. Le moteur d'appariement pourra en faire un **plafond** plutôt que d'exclure tout le fonds, ce qui serait disproportionné.
5. **Le nouveau mot-clé.** Le résultat devient un **mot-clé d'actif** `kw_dyn_<concept>`, enregistré avec ses preuves, ses adresses, sa date et le modèle utilisé (cache `mots_cles_dynamiques.json`). Le critère devient alors une règle normale. Exemple : « Exclure : kw_dyn_entreprises_liees_a_elon_musk = oui (TSLA) ; FNB qui en détiennent : QQQ (3,4 %), ESGV (1,7 %), SPY (1,7 %) ».

Le même concept, exprimé plus tard par un autre utilisateur, est **repris du cache sans nouvelle recherche** : le vocabulaire s'enrichit avec l'usage et reste reproductible. Les preuves s'affichent sur la page finale et figurent dans le JSON exporté.

*Recherche web :* l'outil web_search intégré d'Anthropic n'est pas offert sur Amazon Bedrock. La recherche est donc un outil à nous, limité à Wikipédia, qui n'envoie que le concept, jamais une information sur l'utilisateur.

*Mesuré sur le serveur (Bedrock, 14 novembre 2026)* pour « Je travaille chez Shopify et j'ai déjà plein d'actions de mon employeur. Et je ne veux rien qui touche à Elon Musk, ni aux réseaux sociaux » :

| Étape | Durée | Résultat |
|---|---|---|
| Découvreur et critique | 8,1 s | 3 critères |
| Chercheur, pour « Elon Musk » | 12,0 s | 4 outils, page Wikipédia de Tesla : TSLA, avec la phrase « Elon Musk led Tesla's first funding round and became the company's chairman » |

Les trois critères obtenus :
- Shopify : « exclure SHOP.TO », et XIU.TO signalé (6,4 %) ;
- Elon Musk : « exclure TSLA », et QQQ, ESGV et SPY signalés ;
- réseaux sociaux : le thème existait déjà, donc Tencent est exclu sans recherche, et VWO signalé.

Dans le moteur d'appariement, les critères dynamiques s'appliquent **au même rang** que les fixes : exclusions, puis plafonds, puis seuils, puis préférences. Le verdict est « le pire critère », et l'explication cite le critère et la phrase de l'utilisateur. Exemple : « SHOP.TO exclu : critère X1, d'après "j'ai déjà plein d'actions de mon employeur" ».

## 6. Le site ([mvp_profil/](mvp_profil/), détail dans [mvp_profil/README.md](mvp_profil/README.md))

Site Streamlit. Les modèles sont **Claude Haiku 5.5 sur Amazon Bedrock**, dans le compte du datathon (profil d'inférence `us.anthropic.claude-haiku-5-5`), via le rôle IAM du serveur : aucune clé à gérer. Une clé de l'API Anthropic peut servir de secours.

### Parcours

1. **Conversation orale mains libres (recommandé) ou écrite.** Elle couvre 15 critères de contexte : objectif, horizon, retraits, revenu, épargne, situation, emploi, personnes à charge, dettes, expérience d'une baisse, produits détenus, régions, thèmes.
   - La voix est détectée dans le navigateur, transcrite par **Amazon Transcribe** (fr-CA) et lue par **Amazon Polly** (voix Gabrielle).
   - L'utilisateur n'attend qu'un appel court par tour (la réplique, environ 1,7 s). Le classement se fait en arrière-plan, et le panneau de droite coche ✅ au fil de l'eau.
2. **Questions fixes**, les mêmes pour tous : QCM, curseur, quiz de connaissances, deux questions libres. En parcours conversation, il ne reste que ce que la conversation n'a pas validé, dans une page « Compléments ».
3. **Trois mises en situation** :
   - le replay d'un marché en baisse (2022, date masquée), qui mesure le point de rupture ;
   - des fourchettes de résultats, construites par bootstrap par blocs et centrées sur les hypothèses de FP Canada 2026 ;
   - l'effet de mode, avec 4 titres masqués dont 2 très médiatisés.
4. **Précisions, à la voix** : réponses « Je ne sais pas », réponses libres non validées, et **10 règles de cohérence** entre réponses.
   - L'IA lit chaque question à voix haute, et on répond à l'oral ou au clavier.
   - Pour une contradiction, elle énonce les possibilités (« Première possibilité : … ») ; un agent reconnaît celle que la personne choisit (« plutôt la deuxième »), sinon il redemande.
   - « Pardon, pouvez-vous répéter ? » fait relire la question.
5. **Question ouverte finale, à la voix → critères dynamiques.**

   Le **composant vocal est unique** et toujours au même endroit de la page, donc il n'est jamais recréé : un seul clic « Démarrer » suffit pour tout le parcours. Pendant les questions à choix et les mises en situation, il reste **en veille**, micro coupé, puis reprend tout seul aux précisions.
6. **Profil final**, téléchargeable en JSON. Il contient les critères fixes et dynamiques, les sources, les citations, les confiances et la trace des débats.

### Les agents

| Agent | Rôle | Sortie imposée |
|---|---|---|
| **Réplique** ([entretien.py](mvp_profil/entretien.py)) | Ce que l'IA dit : courte reprise et UNE question ; répète si on le lui demande | `message`, `termine` |
| **Classificateur** ([agents.py](mvp_profil/agents.py)) | Range les paroles de l'utilisateur dans les valeurs autorisées, avec la citation exacte et une confiance | `propositions[]` |
| **Critique** | Conteste les classifications trop rapides (la citation soutient-elle la valeur ? autre lecture possible ?), sans excès de zèle | `avis[]`, `question_relance` |
| **Découvreur** ([criteres_dynamiques.py](mvp_profil/criteres_dynamiques.py)) | Transforme la réponse ouverte en règles `(effet, dimension, valeurs)` du vocabulaire des actifs, ou en concept à rechercher | `criteres[]` |
| **Choix oral** ([entretien.py](mvp_profil/entretien.py)) | Reconnaît la possibilité choisie à l'oral pour une contradiction (« plutôt la deuxième ») | `option` |
| **Chercheur** ([chercheur.py](mvp_profil/chercheur.py)) | Agent à outils (nos données, Wikipédia) : trouve les actifs qu'un concept concerne, preuve recopiée à l'appui ; 5 allers-retours d'outils au plus | `definition`, `verdicts[]` |

Toutes les sorties sont **structurées** (schémas Pydantic) et générées sans raisonnement étendu, avec un effort faible, pour la vitesse.

**Règle de décision, une seule fois par critère et sans boucle :**
1. **1re tentative, seuil de 80 %** (réglable dans la barre latérale). Le critère est validé si les valeurs sont autorisées, si la citation existe vraiment dans les mots de l'utilisateur (comparaison tolérante à la ponctuation et à la casse), si le critique est d'accord et si les deux confiances atteignent le seuil.
2. Sinon, **une seule reformulation**, posée autrement et avec un exemple concret, **avec un seuil abaissé à 65 %**.
3. Si ce n'est toujours pas validé, on **retient la meilleure réponse obtenue** sur toutes les tentatives (statut « retenu », confiance affichée), à condition qu'elle atteigne le **plancher de 50 %**. En dessous, ce serait une devinette : le critère reste « incertain », et l'outil appliquera le réglage le plus prudent.

On ne pose donc jamais trois fois la même question. Un sujet que l'utilisateur n'a jamais abordé n'est pas compté comme un échec : il reste simplement à couvrir.

### Des questions qui s'adaptent à ce que la personne a déjà dit

Le but est de ne jamais demander ce que l'on sait déjà, et de comprendre l'implicite.

- **Déductions par l'IA.** Le classificateur peut conclure une valeur que la personne n'a pas dite mot pour mot, si elle découle **nécessairement** de ses paroles :
  - « je rembourse le crédit pour les études de mon fils » : au moins une personne à charge ;
  - « je suis à la retraite » : revenus et secteur = retraite ;
  - « c'est pour une maison dans deux ans » : objectif et horizon.

  La citation reste la phrase exacte, et la justification commence par « Déduit : ». Le profil indique la source « déduit (IA) ». Le critique accepte une déduction certaine et refuse une supposition.
- **Confirmation au lieu d'une question neuve.** Quand le critique hésite sur une déduction, l'IA la **fait confirmer** en une phrase naturelle. Exemple : « Si je comprends bien, votre fils est encore à votre charge financièrement, ou il a déjà quitté le foyer ? ». Après « oui, il habite encore avec nous », le critère est validé.
- **Critères dits au passage.** Chaque réponse libre est analysée pour ses propres critères, mais aussi pour **tous les autres critères encore inconnus** (dits « facultatifs »). Par exemple, « je préfère les entreprises qui versent des dividendes », dit pendant la conversation, valide le style D7 : la question à choix sur le style **disparaît** ensuite de sa page, avec la mention « ✨ 1 question retirée : vous y avez déjà répondu ».
- **Déductions certaines, sans IA** (`profil.deduire`). Par exemple :
  - à la retraite : revenus de retraite ;
  - aucun placement détenu : jamais vécu de baisse ;
  - cryptoactifs non acceptés : 0 % de cryptoactifs.

  Source « déduction (règle) ».
- **Les précisions se raccourcissent toutes seules.** Un critère devenu connu entre-temps n'est plus demandé.

*Mesuré sur le serveur (Bedrock, 14 novembre 2026)* pour « Je mets de côté pour ma retraite, dans une quinzaine d'années. En ce moment je rembourse le crédit pour les études de mon fils, et je préfère les entreprises qui versent des dividendes », en 6 à 8 s, en arrière-plan :
- critères validés : objectif = retraite, horizon = 10-15 ans, thème = dividendes, et style = dividendes (dit au passage) ;
- personnes à charge : proposé par déduction, puis confirmé par l'IA en une question, puis validé à 90 %.

## 7. Déploiement

Le site tourne sur une instance EC2 t3.small (Amazon Linux 2023, service systemd `alphaforge`). Il est servi en HTTPS par CloudFront, ce qui est nécessaire pour le micro. Une fonction CloudFront filtre les IP de l'équipe. Les mises à jour passent par S3 et Session Manager. Tout est décrit dans [mvp_profil/DEPLOIEMENT.md](mvp_profil/DEPLOIEMENT.md), y compris l'ajout d'une IP et la suppression complète après le datathon.

## 8. Lancer et tester en local

```bash
py -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt -r mvp_profil/requirements.txt
.venv/Scripts/streamlit run mvp_profil/app.py
```

En local, il faut des identifiants AWS temporaires (variables `AWS_*` ou `~/.aws`), ou une clé Anthropic dans la barre latérale. Les tests sont hors ligne, sans coût : un faux serveur remplace l'API, et le vrai SDK construit les requêtes.

```bash
.venv/Scripts/python mvp_profil/test_profil.py
.venv/Scripts/python mvp_profil/test_debat.py
.venv/Scripts/python mvp_profil/test_dynamiques.py
.venv/Scripts/python mvp_profil/test_chercheur.py
.venv/Scripts/python mvp_profil/test_app.py
.venv/Scripts/python mvp_profil/test_conversation.py
```

## 9. Où on en est, et où on veut aller

**Fait :**
- les données des 66 actifs et les mots-clés ;
- la grille de 50 critères ;
- le profil complet : conversation vocale, questionnaire, mises en situation, cohérence, critères dynamiques ;
- le déploiement HTTPS sur AWS.

**Prochaines étapes, par ordre de priorité :**
1. **Moteur d'appariement profil ↔ actifs.** Il applique les règles de `config/criteres_appariement.csv` et les critères dynamiques, dans l'ordre exclusions, plafonds, seuils, préférences, et donne un verdict par actif expliqué critère par critère.
2. **Proposition de portefeuille et explication.** Elle part des actifs compatibles. Un agent rédige l'explication, mais uniquement à partir des verdicts calculés.
3. **Élargir le chercheur.** Ajouter des sources autorisées en plus de Wikipédia (rapports annuels, sites des émetteurs). Utiliser toutes les positions des FNB, pas seulement les 10 principales. Faire relire par l'équipe les mots-clés `kw_dyn_*` avant de les partager entre utilisateurs.
4. **Démonstration sur les trois personas.** Amira, Mateo et Robert passent le parcours, et on vérifie que le verdict change pour de bonnes raisons.
5. Critères encore absents de la grille : frais, accès chez le courtier, inquiétude face aux taux…

## 10. Organisation du dépôt

```
Datathon2026/         matériel des organisateurs (les PDF et PPTX ne sont pas versionnés)
scripts/              collecte et calcul des données, scénarios, vocabulaire des actifs
data_extra/           données ajoutées pour les 31 actifs de départ
data_extended/        univers étendu (35 actifs) + indicateurs et mots-clés des 66 actifs
config/               grille d'appariement (50 critères) et seuils
docs/                 grille lisible des critères
mvp_profil/           site Streamlit : agents, critères, conversation vocale, simulations, tests, déploiement
```

## 11. Pour les assistants IA qui reprennent le projet

- **Langue** : le code, les commentaires, l'interface et la documentation sont en **français**.
- **Ne laissez jamais un modèle décider.** Un modèle propose une valeur d'une liste fermée, avec une citation et une confiance. Le code valide (`agents.evaluer`, `precontrole`, `retenable`, `criteres_dynamiques._nettoyer`). Toute nouvelle sortie de modèle doit passer par un schéma Pydantic et un contrôle déterministe.
- **Listes fermées des deux côtés.** Si vous ajoutez une valeur à un critère d'actif, relancez `scripts/build_asset_criteria.py` puis `scripts/build_vocabulaire.py`. Si vous ajoutez un critère de profil, ajoutez-le dans `criteres.py` (valeurs, question de précision) et dans `config/criteres_appariement.csv` (règle d'appariement).
- **Chercheur** : il n'invente jamais un lien. Le code jette tout verdict dont le passage n'a pas été lu mot pour mot pendant la recherche (`chercheur._preuve_valide`). Pour ajouter une source web, ajoutez un outil qui enregistre ce qu'il lit dans `Recherche.journal`. Regénérez `donnees_chercheur.json` avec `scripts/build_donnees_chercheur.py` quand les données changent.
- **Seuils** : ce sont des hypothèses, centralisées dans `config/seuils_criteres.json` pour les actifs. Pour le profil, ils sont dans `agents.py` : seuil réglable, `BAISSE_REFORMULATION`, `SEUIL_PLANCHER`.
- **Statuts du profil** : `validé`, `retenu` (meilleure réponse sous le seuil, au-dessus du plancher), `incertain` et `à préciser`. Seuls `validé` et `retenu` sont utilisables (`profil.UTILISABLES`, `profil.connu`).
- **Sources du profil** : QCM, curseur, quiz, réponse libre (IA), conversation (IA), **déduit (IA)**, **déduction (règle)**, cohérence, replay… Une question n'est posée que si son critère n'est pas déjà connu (`app.a_demander`). Pour ajouter une déduction certaine, il suffit d'ajouter une ligne à `profil.REGLES_DEDUCTION`.
- **Voix** : `app.dire(texte, etape)` fait dire une nouvelle phrase à l'IA, une seule fois par étape. `app.entendu()` renvoie ce que la personne vient de dire. Le composant (`composant_voix/index.html`) n'existe qu'en un seul exemplaire, en haut de la colonne principale. Ne le déplacez pas : il serait recréé, et la voix serait coupée.
- **Tests** : faites passer les 6 tests de la section 8 avant tout commit. Les tests d'interface utilisent `streamlit.testing.v1.AppTest`, avec des agents simulés et de faux identifiants AWS.
- **Windows** : utilisez `py` ou `.venv/Scripts/python`, avec `PYTHONIOENCODING=utf-8` pour les accents dans la console.
- **Déploiement** : zip du dossier `mvp_profil` (y compris `vocabulaire_actifs.json`, `donnees_chercheur.json` et `scenarios.json`), envoi sur S3, puis redémarrage par Session Manager (voir DEPLOIEMENT.md).
- **Collaboration** : travaillez sur une branche, ouvrez une pull request, et attendez la relecture d'un coéquipier avant de fusionner dans `main`. Ne versionnez aucun secret (voir ci-dessous).

## Security and collaboration

- This repository is private.
- Do not commit API keys, tokens, passwords, `.env` files, or AWS credential
  files. The included `.env.example` contains names only, never values.
- Runtime secrets are stored in AWS Secrets Manager. AWS Lambda receives only
  the permissions it needs to use its designated secret.
- Deployment uses GitHub Actions with OIDC-issued, short-lived AWS credentials;
  it does not use long-lived AWS access keys stored in GitHub.
- Open a pull request for changes and obtain a teammate review before merging
  to `main`.

## Local setup

1. Copy `.env.example` to `.env`.
2. Add only your own development credentials to `.env`.
3. Do not share or commit that file.
