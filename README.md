# AlphaForge AI : outil de décision d'investissement explicable (Datathon PolyFinances 2026)

Prototype du cas « AlphaForge AI » (Banque Nationale, AWS) : un outil **agentique et explicable** qui établit le profil d'un investisseur par une conversation et prépare sa comparaison à des actifs décrits par des données publiques datées. Le moteur d'appariement et les suggestions personnalisées restent à construire. **Simulation éducative uniquement** : aucun conseil financier personnalisé, aucune transaction réelle.

Ce document explique toute la démarche : le but, les principes, les données, les critères, le fonctionnement du site et des agents, ce qui reste à faire. Il s'adresse aussi aux **assistants IA** qui reprendront le projet (voir « Pour les assistants IA » à la fin).

**Site en ligne : https://d29e3l5vv5fmjy.cloudfront.net** (accès limité aux IP de l'équipe ; voir [mvp_profil/DEPLOIEMENT.md](mvp_profil/DEPLOIEMENT.md)).

**État de cette évolution : publiée sur le site partagé le 15 novembre 2026.** L'ordre adaptatif, les nouveaux contrôles, les confirmations, les états de recherche et la restitution décrits ci-dessous sont en ligne ; le parcours vocal n'a pas encore été réessayé sur le site. Le parcours et ses garanties sont détaillés dans [docs/infrastructure_profil.md](docs/infrastructure_profil.md). Aucun nouveau résultat réel Bedrock ni gain de durée avec des utilisateurs n'a été mesuré pour cette évolution.

---

## 1. Le problème et les trois personas

Le cas demande un outil qui aide trois profils fictifs à prendre une décision d'investissement **compréhensible et vérifiable** :

| Persona | Profil | Ce que l'outil doit savoir faire |
|---|---|---|
| **Amira** | Risque élevé, horizon de 15 ans ou plus | Accepter la volatilité, sans la laisser concentrer tout son risque au même endroit |
| **Mateo** | Risque modéré, préférences ESG | Intégrer ses exigences ESG et son refus des controverses importantes de façon traçable |
| **Robert** | Risque faible à modéré, 3 à 5 ans, tenté par les titres à la mode | Détecter l'écart entre ce qu'il dit et ce qu'il ferait, et le protéger de l'effet de mode |

## 2. L'idée centrale : un profil reproductible, comparé aux actifs par des mots-clés

1. **On pose les questions restantes par ordre d'utilité**, selon leurs prérequis de sécurité et leur impact sur le profil (conversation orale ou écrite, QCM, curseurs, quiz, mises en situation). Le tri ne supprime aucune information nécessaire.
2. **L'IA classe les réponses dans une liste fermée de mots-clés** par critère (exemple : horizon = `moins_3_ans`, `3_5_ans`, `5_10_ans`, `10_15_ans` ou `plus_15_ans`). Les réponses fermées donnent toujours la même valeur. Pour les réponses libres, `mvp_profil/evaluer_classement.py` compare les valeurs et statuts effectifs sur un jeu de **51 phrases / 88 couples phrase–critère**, avec erreurs des réponses validées et retenables distinguées. **La mesure avec le vrai modèle reste à lancer.**
3. **Chaque actif est classé sous les mêmes mots-clés**, cette fois par du code, à partir de données datées : volatilité, perte maximale, récupération, exclusions ESG, risque pays, devise, attention médiatique…
4. **Les règles d'appariement sont préparées** pour comparer les deux côtés et expliquer les exclusions, plafonds et tensions. Leur exécution et la construction d'un résultat personnalisé ne sont pas encore implémentées.

Les principes qui en découlent, à respecter partout :

- **Les modèles classent, le code décide.** Seuils, valeurs autorisées, validation, verdicts, règle « le plus prudent l'emporte » : tout ce qui décide est déterministe.
- **Tout est justifié.** Chaque valeur du profil garde sa source (QCM, curseur, quiz, IA, mise en situation, cohérence), la citation exacte de l'utilisateur et la confiance. Chaque valeur d'actif renvoie à un fichier daté.
- **On mesure aussi ce que la personne fait.** Trois mises en situation comparent le comportement observé au déclaré. En cas d'écart, le plus prudent des deux l'emporte.
- **Une inconnue reste visible.** Un réglage prudent peut compléter la synthèse en étant signalé ; il ne vaut pas confirmation d'une réponse, d'un pourcentage ou d'une exclusion.

## 3. Architecture d'ensemble

```
            DONNÉES (scripts/ -> data_extra/, data_extended/)
  prix, change, dividendes, états financiers, FNB, ESG, attention, macro
                              │  code (scripts/build_asset_criteria.py)
                              ▼
     asset_criteria.csv : 66 actifs × 109 colonnes, dont 23 mots-clés kw_*
                              │
  PROFIL (mvp_profil/, site Streamlit + Claude Haiku 5.5 sur Bedrock)     │
  conversation ─▶ classificateur ⇄ critique ─▶ critères fixes (42)        │
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
| `config/` | `criteres_appariement.csv` (51 critères, alignés sur `criteres.py` par `scripts/sync_grille.py` : question, valeurs du profil, critère d'actif, règle, type de règle, personas) et `seuils_criteres.json` (tous les seuils, qui sont des hypothèses) | Équipe |
| `docs/criteres_profil_actifs.md` | La grille lisible : principe, 8 blocs de critères (A situation à H gouvernance), calcul des mots-clés, test sur les 3 personas | Équipe |

Ordre pour tout régénérer : `fetch_extra_data.py` → `fetch_macro_release_dates.py` → `build_esg.py` → `build_extended_prices.py` → `compute_metrics.py` → `fetch_market_caps.py` → `build_asset_criteria.py` → `build_scenarios.py` → `build_vocabulaire.py` → `build_donnees_chercheur.py` → `sync_grille.py` → `test_grille.py`. Les quatre premiers scripts téléchargent des données : les relancer change les prix (Yahoo réajuste l'historique). Pour appliquer une correction de calcul, repartir de `compute_metrics.py`.

Points à connaître (le détail est dans les README de chaque dossier) :
- Tout est **converti en CAD**, car l'investisseur est canadien. Change de la Banque du Canada ; taux croisés pour DKK et EGP.
- Corrections faites : sous-unités (pence, cents sud-africains) ; deux jours avec des prix 100 fois trop petits ; un faux fractionnement 5000:1 de Naspers.
- Sources : Yahoo/yfinance, Banque du Canada (Valet), ALFRED, Wikimedia Pageviews, BlackRock (positions de XEN), Norme d'hypothèses de projection 2026 de FP Canada et de l'IPF (rendements attendus des fourchettes).
- Afrique : Yahoo ne couvre ni Lagos, ni Nairobi, ni Casablanca. Neuf actions africaines sur dix sont donc sud-africaines.

## 5. Les critères

### Côté profil : 42 critères fixes ([mvp_profil/criteres.py](mvp_profil/criteres.py))

Les identifiants sont ceux de la grille : A situation et capacité, B risque, C connaissances, D préférences, E valeurs, F pays, G compte, H cohérence. Chaque critère a une **liste fermée** de valeurs et une question de précision. Le profil se termine par une **synthèse déterministe** ([synthese.py](mvp_profil/synthese.py)) : le budget de perte du portefeuille est le plus prudent de la capacité, de la tolérance déclarée et de la tolérance observée, et la composante qui limite est affichée. Quatre critères sont **mesurés** par les mises en situation et non déclarés :
- B2, le point de rupture observé au replay ;
- B6, l'arbitrage risque-rendement choisi dans les fourchettes ;
- D8O, l'attrait observé pour un titre médiatisé ;
- H1, l'écart entre le déclaré et l'observé.

La synthèse affiche aussi les **réponses décisives**, leurs sources et les dimensions qu'elles modifient, ainsi qu'une **robustesse locale** : une réponse ordonnée varie d'un cran à la fois, les autres étant conservées. La plage des résultats n'est ni un intervalle de confiance ni une prévision. Les observations du replay ne sont pas réécrites pour fabriquer des variantes. Un profil incomplet ou des besoins de liquidité non chiffrés restent signalés comme provisoires.

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
| `note` | `information` : gardé et cité, aucun filtre automatique | particularité sans cible d'actif traduisible |

Dimensions disponibles :
- `titre`, `classe`, `region`, `pays`, `devise`, `secteur`, `theme` ;
- les mots-clés `exclusion`, `risque_pays`, `exposition_devise`, `taille`, `distribution`, `cycle`, `concentration`, `attention` et `fiscalite` ;
- `role`.

Le code contrôle tout :
- la dimension doit exister et les valeurs y être présentes, sinon le critère devient une note : on ne filtre jamais sur une valeur inventée ;
- la citation doit être exacte, sinon le critère est écarté ;
- le critique doit être d'accord avec les deux confiances au-dessus du seuil pour que le critère soit **validé** ;
- avec l'accord du critique mais une confiance réduite au-dessus du plancher de 50 %, le critère peut être **retenu** et signalé ;
- un désaccord ou un plafond sans chiffre étayé laisse le critère **à préciser**, sans filtre automatique ;
- en dessous, il n'est pas créé.

**« Limiter les banques » reste un plafond à préciser.** Un chiffre absent de la citation n'est jamais remplacé par une exclusion totale. L'interface permet de confirmer la cible et un pourcentage ; sans confirmation, la règle reste non applicable. Le code calcule aussi les **actifs concernés**. Chaque critère est exporté avec sa règle lisible, sa colonne d'actif, sa citation, sa confiance et son applicabilité. Confirmer une intention ne remplace pas les preuves d'exposition.

**Quand le vocabulaire ne suffit pas : l'agent chercheur ([mvp_profil/chercheur.py](mvp_profil/chercheur.py)).** Certaines idées visent des actifs, mais aucune valeur existante ne les traduit : « rien qui touche à Elon Musk », « les entreprises qui recyclent ». Le découvreur crée alors le critère « à étiqueter », avec un **concept** à rechercher. Un deuxième agent, le **chercheur**, prend le relais **en arrière-plan**, pendant que le profil s'affiche :

1. **La recherche.** Le chercheur reçoit le tableau des 66 actifs et quatre outils :
   - `chercher_dans_donnees` : noms, secteurs, thèmes, controverses, actualités récentes et positions des FNB ;
   - `fiche_actif` ;
   - `recherche_web` et `lire_page_web` : Wikipédia en français ou en anglais.

   Il peut établir « oui », « partiel » ou « non_concerne », avec une **preuve**. La preuve est un passage recopié mot pour mot d'un résultat d'outil et l'identifiant de sa source. Tout actif sans conclusion suffisamment étayée conserve l'état **« inconnu »** ; une recherche sans résultat n'établit pas l'absence du lien.
2. **Le contrôle par le code.** Le ticker doit exister, et le passage doit se trouver **mot pour mot dans une source réellement lue** pendant cette recherche. C'est le même principe que la citation exacte de l'utilisateur. Sinon, le verdict est écarté.
3. **La vérification par le critique.** Il contrôle que chaque preuve justifie bien le verdict. Un désaccord, une confiance insuffisante ou une contradiction entre preuves laisse l'actif inconnu. Une conclusion « non concerné » exige elle aussi une preuve explicite.
4. **La transparence des FNB, calculée par le code.** Un FNB qui détient un actif concerné parmi ses principales positions est signalé avec le poids de cette position : SPY détient TSLA à 1,7 %, XIU.TO détient SHOP.TO à 6,4 %. Cela vaut aussi pour l'exclusion d'un titre choisi directement. Le moteur d'appariement pourra en faire un **plafond** plutôt que d'exclure tout le fonds, ce qui serait disproportionné.
5. **Le nouveau mot-clé.** Le résultat devient un **mot-clé d'actif** `kw_dyn_<concept>`, enregistré avec ses preuves, ses adresses, sa date, les quatre états et la couverture de recherche. Une règle peut viser les actifs positivement identifiés ; les inconnus ne sont pas déclarés compatibles. Les principales positions des FNB décrivent une exposition minimale connue, pas une vérification exhaustive du fonds.

Le **cache versionné** utilise le concept complet et une empreinte des données, consignes et du modèle. Une entrée n'est réutilisée que si elle est compatible et encore valide ; la durée de sept jours est une hypothèse de fraîcheur. Les anciennes entrées ne présentant pas ces garanties sont invalidées. Les preuves, états inconnus et limites de couverture s'affichent sur la page finale et figurent dans le JSON exporté.

*Recherche web :* l'outil web_search intégré d'Anthropic n'est pas offert sur Amazon Bedrock. La recherche est donc un outil à nous, limité à Wikipédia, qui n'envoie que le concept, jamais une information sur l'utilisateur.

*Mesure historique sur la version du serveur du 14 novembre 2026, avant les nouveaux contrôles et le cache versionné.* Ce relevé ne mesure pas la version locale actuelle. Cas : « Je travaille chez Shopify et j'ai déjà plein d'actions de mon employeur. Et je ne veux rien qui touche à Elon Musk, ni aux réseaux sociaux » :

| Étape | Durée | Résultat |
|---|---|---|
| Découvreur et critique | 8,1 s | 3 critères |
| Chercheur, pour « Elon Musk » | 12,0 s | 4 outils, page Wikipédia de Tesla : TSLA, avec la phrase « Elon Musk led Tesla's first funding round and became the company's chairman » |

Les trois critères obtenus :
- Shopify : « exclure SHOP.TO », et XIU.TO signalé (6,4 %) ;
- Elon Musk : « exclure TSLA », et QQQ, ESGV et SPY signalés ;
- réseaux sociaux : le thème existait déjà, donc Tencent est exclu sans recherche, et VWO signalé.

Dans le futur moteur d'appariement, seuls les critères dynamiques **applicables** pourront intervenir, au même rang que les fixes : exclusions, puis plafonds, puis seuils, puis préférences. L'explication devra citer la règle et la phrase de l'utilisateur, sans transformer une contrainte encore à préciser en filtre.

## 6. Le site ([mvp_profil/](mvp_profil/), détail dans [mvp_profil/README.md](mvp_profil/README.md))

Site Streamlit. Les modèles sont **Claude Haiku 5.5 sur Amazon Bedrock**, dans le compte du datathon (profil d'inférence `us.anthropic.claude-haiku-5-5`), via le rôle IAM du serveur : aucune clé à gérer. Une clé de l'API Anthropic peut servir de secours.

### Parcours

1. **Conversation orale mains libres (recommandé) ou écrite.** Elle couvre 16 critères de contexte : objectif, horizon, étape de vie, retraits, revenu, épargne, situation, emploi, personnes à charge, dettes, expérience d'une baisse, produits détenus, régions, thèmes.
   - La voix est détectée dans le navigateur, transcrite par **Amazon Transcribe** (fr-CA) et lue par **Amazon Polly** (voix Gabrielle).
   - La réplique et le classement ont des tâches distinctes : l'analyse se fait en arrière-plan, et le panneau de droite coche ✅ après contrôle. Les analyses sont regroupées sur l'historique à jour ; un résultat périmé ne remplace pas une correction récente.
2. **Questions de référence à ordre adaptatif** : QCM, curseur, quiz de connaissances, deux questions libres. L'ordre privilégie projet et horizon, liquidité et capacité, risque et connaissances, contraintes et accès, puis préférences. Les pages déjà ouvertes ne sont pas déplacées. En parcours conversation, une page « Compléments » reprend ce qui reste inconnu.
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
6. **Profil final**, téléchargeable en JSON. Il contient les critères fixes et dynamiques, les sources, les citations, les confiances, les réponses décisives, la robustesse locale et la trace des contrôles. Les contraintes à confirmer et les actifs encore inconnus restent visibles.

### Les agents

| Agent | Rôle | Sortie imposée |
|---|---|---|
| **Réplique** ([entretien.py](mvp_profil/entretien.py)) | Ce que l'IA dit : courte reprise et UNE question ; répète si on le lui demande | `message`, `termine` |
| **Classificateur** ([agents.py](mvp_profil/agents.py)) | Range les paroles de l'utilisateur dans les valeurs autorisées, avec la citation exacte et une confiance | `propositions[]` |
| **Critique** | Vérifie la proposition avec sa question, les échanges et les libellés exacts ; accepte les réponses claires et refuse les inférences non étayées | `avis[]`, `question_relance` |
| **Découvreur** ([criteres_dynamiques.py](mvp_profil/criteres_dynamiques.py)) | Transforme la réponse ouverte en règles `(effet, dimension, valeurs)` du vocabulaire des actifs, ou en concept à rechercher | `criteres[]` |
| **Choix oral** ([entretien.py](mvp_profil/entretien.py)) | Reconnaît la possibilité choisie à l'oral pour une contradiction (« plutôt la deuxième ») | `option` |
| **Chercheur** ([chercheur.py](mvp_profil/chercheur.py)) | Agent à outils (nos données, Wikipédia) : trouve les actifs qu'un concept concerne, preuve recopiée à l'appui ; 5 allers-retours d'outils au plus | `definition`, `verdicts[]` |

Toutes les sorties sont **structurées** (schémas Pydantic) et générées sans raisonnement étendu, avec un effort faible, pour la vitesse.

**Validation et relance bornée :**
1. **1re tentative, seuil de 80 %** (réglable dans la barre latérale). Le critère est validé si les valeurs sont autorisées, si la citation existe vraiment dans les mots de l'utilisateur (comparaison tolérante à la ponctuation et à la casse), si le critique est d'accord et si les deux confiances atteignent le seuil.
2. Sinon, **une seule reformulation**, posée autrement et avec un exemple concret, **avec un seuil abaissé à 65 %**.
3. Si ce n'est toujours pas validé, une réponse peut rester **retenue avec confiance réduite**, à condition d'être étayée, d'avoir reçu **l'accord du critique** et d'atteindre le **plancher de 50 %**. Une proposition contestée ou non vérifiée ne devient jamais utilisable par ce mécanisme. Une nouvelle valeur différente ou une objection récente prime sur l'ancienne confiance. À défaut, le critère reste « incertain » ; les réglages prudents éventuels sont signalés.

Les reformulations libres sont bornées ; une information toujours inconnue reste visible et peut être reprise dans les compléments structurés. Un sujet que l'utilisateur n'a jamais abordé n'est pas compté comme un échec : il reste à couvrir.

### Des questions qui s'adaptent à ce que la personne a déjà dit

Le but est de recueillir rapidement les informations utiles sans deviner celles qui manquent. Le fonctionnement précis est décrit dans [l'infrastructure du profil](docs/infrastructure_profil.md).

- **Ordre déterministe** (`pilotage.py`). Les prérequis de sécurité passent avant les préférences. À priorité égale, le code compare les effets possibles des valeurs autorisées sur la synthèse et les limites. Il classe les questions restantes sans en supprimer ; cette heuristique n'est pas un optimum de durée démontré.
- **Contexte et sens des codes.** Les deux agents reçoivent les libellés du questionnaire pour les critères concernés. Un « oui/non » à une question précise peut suffire ; à une question composée, il ne remplit pas automatiquement tous les champs. A9 « aucun retrait » ne prouve pas A10 « aucun besoin de revenu ».

- **Déductions par l'IA.** Le classificateur peut conclure une valeur que la personne n'a pas dite mot pour mot, si elle découle **nécessairement** de ses paroles :
  - « je suis à la retraite » : secteur = retraite ;
  - « c'est pour une maison dans deux ans » : objectif et horizon.

  La citation reste la phrase exacte, et la justification commence par « Déduit : ». Le profil indique la source « déduit (IA) ». Le critique accepte une déduction certaine et refuse une supposition. Être parent, rembourser un prêt pour les études d'un fils ou partager un logement ne suffit pas à établir le nombre de personnes financièrement à charge ; le métier seul ne prouve pas la stabilité des revenus.
- **Confirmation ciblée.** Quand une information manque, l'IA fait préciser le point utile : « Combien de personnes dépendent financièrement de vos revenus ? ». Une confirmation doit porter sur une question univoque, pas sur deux alternatives simultanément.
- **Critères dits au passage.** Chaque réponse libre est analysée pour ses propres critères, mais aussi pour **tous les autres critères encore inconnus** (dits « facultatifs »). Par exemple, « je préfère les entreprises qui versent des dividendes », dit pendant la conversation, valide le style D7 : la question à choix sur le style **disparaît** ensuite de sa page, avec la mention « ✨ 1 question retirée : vous y avez déjà répondu ».
- **Déductions certaines, sans IA** (`profil.deduire`). Par exemple :
  - à la retraite : revenus de retraite ;
  - aucun placement détenu : jamais vécu de baisse ;
  - cryptoactifs non acceptés : 0 % de cryptoactifs.

  Source « déduction (règle) ».
- **Les précisions se raccourcissent toutes seules.** Un critère devenu connu entre-temps n'est plus demandé.
- **Corrections récentes.** La citation récente doit étayer la nouvelle valeur. L'application termine les vérifications et leur rattrapage avant de décider quels compléments restent nécessaires.

## 7. Déploiement

Le site tourne sur une instance EC2 t3.small (Amazon Linux 2023, service systemd `alphaforge`). Il est servi en HTTPS par CloudFront, ce qui est nécessaire pour le micro. Une fonction CloudFront filtre les IP de l'équipe. Les mises à jour passent par S3 et Session Manager. Tout est décrit dans [mvp_profil/DEPLOIEMENT.md](mvp_profil/DEPLOIEMENT.md), y compris l'ajout d'une IP et la suppression complète après le datathon.

L'évolution du profil décrite dans ce README a été **publiée le 15 novembre 2026** (paquet précédent sauvegardé dans `app/backup/` du bucket). Les anciennes mesures du serveur ne valident pas les nouvelles formulations ni leur gain de temps.

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
.venv/Scripts/python mvp_profil/test_synthese.py
.venv/Scripts/python mvp_profil/test_pilotage.py
.venv/Scripts/python mvp_profil/test_evaluation.py
.venv/Scripts/python scripts/test_grille.py
.venv/Scripts/python mvp_profil/evaluer_classement.py --verifier
```

La vérification comprend **9 suites dans `mvp_profil/` et le contrôle de grille**, ainsi que la validation du jeu de phrases. Les réponses de modèle simulées vérifient les règles et l'orchestration ; elles ne mesurent pas l'exactitude réelle du modèle. L'évaluation réelle doit encore être lancée explicitement et produit un rapport séparant exactitude, stabilité, erreurs des sorties validées et erreurs des sorties retenables. Les confiances déclarées ne sont pas des probabilités calibrées.

## 9. Où on en est, et où on veut aller

**Fait :**
- les données des 66 actifs et les mots-clés ;
- la grille de 51 critères, alignée sur le code et vérifiée par `scripts/test_grille.py` ;
- la synthèse du profil : capacité, tolérance déclarée et observée, budget de perte, réponses décisives et robustesse locale ([mvp_profil/synthese.py](mvp_profil/synthese.py)) ;
- le pilotage déterministe des questions restantes, les contrôles de corrections et les confirmations des contraintes personnelles ;
- le chercheur à quatre états, sa couverture explicite et son cache versionné ;
- le mode démonstration : les trois personas de l'énoncé, chargés en un clic ;
- le profil complet : conversation vocale, questionnaire, mises en situation, cohérence, critères dynamiques ;
- le déploiement HTTPS sur AWS.

**Prochaines étapes, par ordre de priorité :**
1. **Moteur d'appariement profil ↔ actifs.** Il applique les règles de `config/criteres_appariement.csv` et les critères dynamiques, dans l'ordre exclusions, plafonds, seuils, préférences, et donne un verdict par actif expliqué critère par critère.
2. **Proposition de portefeuille et explication.** Elle part des actifs compatibles. Un agent rédige l'explication, mais uniquement à partir des verdicts calculés.
3. **Élargir le chercheur.** Ajouter des sources autorisées en plus de Wikipédia (rapports annuels, sites des émetteurs). Utiliser toutes les positions des FNB, pas seulement les 10 principales. Faire relire par l'équipe les mots-clés `kw_dyn_*` avant de les partager entre utilisateurs.
4. **Démonstration sur les trois personas.** Amira, Mateo et Robert passent le parcours, et on vérifie que le verdict change pour de bonnes raisons.
5. **Compléter la couverture si le besoin le justifie.** A11, C3, D10, E3, F1, G4 et G5 restent non demandés selon la grille ; l'accès aux marchés G3 est déjà recueilli.

## 10. Organisation du dépôt

```
Datathon2026/         matériel des organisateurs (les PDF et PPTX ne sont pas versionnés)
scripts/              collecte et calcul des données, scénarios, vocabulaire des actifs
data_extra/           données ajoutées pour les 31 actifs de départ
data_extended/        univers étendu (35 actifs) + indicateurs et mots-clés des 66 actifs
config/               grille d'appariement (51 critères), seuils et correspondances profil ↔ actifs
docs/                 grille lisible des critères
mvp_profil/           site Streamlit : agents, critères, conversation vocale, simulations, tests, déploiement
```

## 11. Pour les assistants IA qui reprennent le projet

- **Langue** : le code, les commentaires, l'interface et la documentation sont en **français**.
- **Ne laissez jamais un modèle décider.** Un modèle propose une valeur d'une liste fermée, avec une citation et une confiance. Le code valide (`agents.evaluer`, `precontrole`, `retenable`, `criteres_dynamiques._nettoyer`). Toute nouvelle sortie de modèle doit passer par un schéma Pydantic et un contrôle déterministe.
- **Listes fermées des deux côtés.** Si vous ajoutez une valeur à un critère d'actif, relancez `scripts/build_asset_criteria.py` puis `scripts/build_vocabulaire.py`. Si vous ajoutez un critère de profil, ajoutez-le dans `criteres.py` (valeurs, question de précision) et dans `config/criteres_appariement.csv` (règle d'appariement).
- **Chercheur** : il n'invente jamais un lien. Le code jette tout verdict dont le passage n'a pas été lu mot pour mot pendant la recherche (`chercheur._preuve_valide`). Pour ajouter une source web, ajoutez un outil qui enregistre ce qu'il lit dans `Recherche.journal`. Regénérez `donnees_chercheur.json` avec `scripts/build_donnees_chercheur.py` quand les données changent.
- **Seuils** : ce sont des hypothèses, centralisées dans `config/seuils_criteres.json` pour les actifs et dans `mvp_profil/hypotheses_profil.json` pour la synthèse du profil (capacité, stress, réglages prudents). Pour le profil, ils sont dans `agents.py` : seuil réglable, `BAISSE_REFORMULATION`, `SEUIL_PLANCHER`.
- **Statuts du profil** : `validé`, `retenu` (accord du critique avec confiance réduite au-dessus du plancher), `incertain` et `à préciser`. Seuls `validé` et `retenu` sont utilisables pour les critères fixes (`profil.UTILISABLES`, `profil.connu`). Pour les critères dynamiques, vérifier aussi `criteres_dynamiques.est_applicable` : une confirmation, une cible ou des preuves peuvent encore manquer. Un désaccord du critique ne devient pas « retenu ».
- **Sources du profil** : QCM, curseur, quiz, réponse libre (IA), conversation (IA), **déduit (IA)**, **déduction (règle)**, cohérence, replay… Une question n'est posée que si son critère n'est pas déjà connu (`app.a_demander`). Pour ajouter une déduction certaine, il suffit d'ajouter une ligne à `profil.REGLES_DEDUCTION`.
- **Voix** : `app.dire(texte, etape)` fait dire une nouvelle phrase à l'IA, une seule fois par étape. `app.entendu()` renvoie ce que la personne vient de dire. Le composant (`composant_voix/index.html`) n'existe qu'en un seul exemplaire, en haut de la colonne principale. Ne le déplacez pas : il serait recréé, et la voix serait coupée.
- **Tests** : faites passer les 9 suites de la section 8 et `scripts/test_grille.py` avant tout commit. `test_evaluation.py` vérifie les métriques sans cloud ; `evaluer_classement.py --verifier` contrôle les 51 phrases et 88 couples. Les tests d'interface utilisent `streamlit.testing.v1.AppTest`, avec des agents simulés et de faux identifiants AWS.
- **Windows** : utilisez `py` ou `.venv/Scripts/python`, avec `PYTHONIOENCODING=utf-8` pour les accents dans la console.
- **Cohérence** : un correctif de cohérence n'écrit jamais une valeur que la personne n'a pas choisie (`None` = critère redemandé), et `profil.recouper_rupture` est rappelée après chaque correctif : le point de rupture retenu ne dépasse jamais celui observé au replay.
- **Déploiement** : zip du dossier `mvp_profil` (y compris `vocabulaire_actifs.json`, `donnees_chercheur.json`, `scenarios.json`, `hypotheses_profil.json`, `synthese.py`, `pilotage.py` et le dossier `personas/`), envoi sur S3, puis redémarrage par Session Manager (voir DEPLOIEMENT.md). Ne pas supposer que l'archive existante ou le serveur incluent les modifications locales.
- **Collaboration** : travaillez sur une branche, ouvrez une pull request, et attendez la relecture d'un coéquipier avant de fusionner dans `main`. Ne versionnez aucun secret (voir ci-dessous).

## Sécurité et collaboration

Ce qui suit décrit l'infrastructure **réellement en place** (détail dans [mvp_profil/DEPLOIEMENT.md](mvp_profil/DEPLOIEMENT.md)).

- **Aucune clé dans le dépôt ni sur le serveur.** Le site appelle Amazon Bedrock, Transcribe et Polly avec le **rôle IAM de l'instance EC2**, limité à ces actions et à la lecture du paquet du site sur S3.
- **Accès au site** : HTTPS par CloudFront, avec une fonction CloudFront qui ne laisse passer que les adresses IP de l'équipe. Le groupe de sécurité de l'instance n'accepte que CloudFront et ces mêmes adresses. Il n'y a ni mot de passe ni comptes utilisateurs : c'est suffisant pour une démonstration, pas pour de vrais utilisateurs.
- **Mises à jour** : un paquet zip déposé sur S3, puis un redémarrage par Session Manager. Aucun port SSH n'est ouvert. Il n'y a pas de déploiement automatique.
- **Données personnelles** : aucune. Les profils sont fictifs ; le mode démonstration charge les trois personas de l'énoncé.
- **En local** : identifiants AWS temporaires (variables `AWS_*` ou `~/.aws`), jamais versionnés. Le fichier `.env.example` ne contient que des noms de variables.
- **Collaboration** : une branche par changement, une pull request, la relecture d'un coéquipier avant de fusionner dans `main`. Ne versionnez aucun secret, aucun identifiant de compte, aucune adresse IP.
