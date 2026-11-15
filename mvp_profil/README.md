# MVP : profil d'investisseur explicable

**Correctif des relances (publié le 15 novembre 2026, version `profil-afe8ed38fc7d`).** Les questions ouvertes et leurs réponses sont exclusivement orales. Le pilote `questions_conversation.py` choisit les cibles, `reponses_directes.py` traite les faits explicites A2/A5/A7 et `moteur_conversation.py` intègre les analyses avec une fraîcheur par critère. Aucun appel de génération n'est requis pour choisir la question suivante. Les ambiguïtés réelles ont une seule clarification ; les erreurs techniques conservent la réponse. La calibration du micro conserve aussi la parole reçue pendant ses premières 700 ms. R6/R8/R9 restent des observations sans relance ni modification des réponses.

La version est affichée dans la barre latérale et exportée avec les questions et les échanges oraux. `python scripts/preparer_mvp.py` construit un paquet intégral avec un manifeste vérifié, sans accès AWS. Détails : [diagnostic et protocole](../docs/fiabilite_questions.md), [recherche de questionnaires](../docs/recherche_questionnaires.md).

Site Streamlit qui établit un profil à partir d'une conversation, de questions fermées et de mises en situation. Les réponses libres sont classées puis vérifiées par deux agents Claude Haiku 5.5. Les critères sont alignés avec [config/criteres_appariement.csv](../config/criteres_appariement.csv). **Simulation éducative : aucun conseil financier personnalisé, aucune transaction réelle.** Le moteur de suggestions personnalisées reste à développer.

**Version hébergée sur AWS : https://d29e3l5vv5fmjy.cloudfront.net** (HTTPS via CloudFront, accès limité aux IP de l'équipe ; voir [DEPLOIEMENT.md](DEPLOIEMENT.md)). Les appels utilisent Amazon Bedrock, Transcribe et Polly avec le rôle IAM du serveur.

**Les changements décrits ici sont implémentés localement et n'ont pas été publiés sur le site partagé.** Aucun nouveau résultat réel du modèle ni gain de temps avec des utilisateurs n'a été mesuré pour cette version. Le détail des responsabilités, de l'ordre des questions et des garanties est dans [l'infrastructure du profil](../docs/infrastructure_profil.md).

## Parcours

L'accueil propose une conversation exclusivement orale et un questionnaire à choix complété oralement. Il permet aussi de charger les trois personas fictifs de l'énoncé, avec leurs hypothèses de test identifiées.

### Conversation et analyse en arrière-plan

La conversation couvre 16 critères de contexte : objectif, horizon, retraits, revenu, étape de vie, épargne, réserve, situation, emploi, personnes à charge, dettes, expérience d'une baisse, produits détenus, régions et thèmes.

- Le pilote déterministe choisit une question courte et ses cibles parmi les sujets restant réellement à demander. Le classificateur et le critique analysent les réponses en arrière-plan ; une information n'est cochée comme validée qu'après contrôle.
- Une information spontanée peut renseigner d'autres critères encore inconnus. Une proposition facultative non validée n'est pas conservée comme réponse acquise.
- Les analyses sont regroupées sur l'historique à jour. Les numéros d'échange empêchent un ancien résultat de remplacer une correction récente. Avant de quitter la conversation, le code termine les vérifications et leur rattrapage.
- Une précision est reformulée une seule fois. Si le critique refuse encore la proposition, elle reste incertaine ; sa confiance élevée ne permet pas de contourner le refus.
- La conversation est bornée à dix tours. Les informations manquantes sont reprises dans les « Compléments » ; passer aux questions suivantes ne les remplit pas automatiquement.

Pour la voix, un clic « Démarrer » autorise le micro et le son. Le composant [composant_voix/index.html](composant_voix/index.html) détecte la parole et envoie les énoncés ; Amazon Transcribe les transcrit en fr-CA et Amazon Polly lit les questions avec la voix Gabrielle. Le même composant reste à sa place pendant les changements de page, en veille pendant les QCM. Les champs de réponse libre écrite sont supprimés. On peut demander oralement de répéter la question.

### Questions restantes à ordre adaptatif

Les 34 questions de référence couvrent les mêmes critères, mais leur ordre est piloté par [pilotage.py](pilotage.py). Les questions déjà renseignées sont retirées ; le tri ne supprime aucune information nécessaire et ne déplace pas une page déjà ouverte.

| Ordre des pages classiques | Contenu |
|---|---|
| Votre projet | Objectif, horizon, retraits du capital, besoin de revenu |
| Votre situation | Réserve, dettes, part d'épargne engagée, stabilité des revenus, emploi, personnes à charge |
| Vous et le risque | Réaction à une baisse, point de rupture, variation acceptée, récupération, expérience et consultation |
| Vos connaissances | Quiz de trois questions et produits déjà détenus |
| Vos valeurs et votre compte | Exclusions, exigences ESG, pays refusés, montant, accès aux marchés et compte |
| Vos préférences | Contraintes restantes sur les classes, la crypto et la concentration, puis régions, style et thèmes |

Dans chaque groupe de priorité, le code compare l'effet possible des valeurs autorisées sur la synthèse et les limites. La réserve, les dettes, la liquidité et les contraintes passent avant les préférences, même si une préférence aurait un effet numérique plus grand. Les coûts relatifs des formats sont des hypothèses de classement ; il ne s'agit pas d'un optimum de durée démontré.

Les réponses fermées donnent leurs valeurs sans IA. Les réponses libres sont vérifiées en arrière-plan. Après une conversation, les « Compléments » reprennent les critères de contexte encore inconnus, puis les autres pages suivent leurs prérequis.

### Mises en situation et précisions

| Mise en situation | Observation conservée |
|---|---|
| Replay de 2022, date masquée | « Tout vendre » fixe le point de rupture observé B2 avec la perte réelle. « Réduire » reste un signal distinct. Si la baisse montrée n'a pas atteint le seuil déclaré, la tolérance est marquée non testée. |
| Cinq fourchettes de résultats | Le choix renseigne B6. Les fourchettes sont simulées par bootstrap de blocs sur 2021-2026, centrées sur les hypothèses FP Canada/IPF 2026 ; leur limite face aux crises extrêmes est affichée. |
| Quatre titres aux noms masqués | Le choix renseigne D8O et peut déclencher une précision face au déclaré. Ce signal ne démontre pas à lui seul que la médiatisation a causé le choix. |

Les précisions reprennent les réponses manquantes ou ambiguës et les contradictions repérées par les dix règles de cohérence de [profil.py](profil.py). L'utilisateur choisit explicitement la correction ; lorsqu'aucune valeur n'est choisie, le critère est redemandé. Le déclaré et l'observé restent distincts, et le recoupement avec le replay est réappliqué.

### Dernière question et contraintes personnelles

« Y a-t-il quelque chose de particulier que nous n'avons pas abordé ? » peut créer des critères X1, X2… : `exclure`, `plafonner`, `privilegier` ou `note`. Leur cible utilise le vocabulaire réel des actifs. Les citations, dimensions et valeurs sont contrôlées.

**Une intention de limiter sans chiffre reste un plafond à préciser.** « Limiter les banques » ne devient pas une exclusion totale. L'interface permet de confirmer la cible et le pourcentage ; sans confirmation, aucun filtre automatique ne s'applique. Un désaccord du critique reste à préciser. `criteres_dynamiques.est_applicable` distingue une règle confirmée d'une règle utilisable avec les données disponibles.

Si un concept ne peut pas être traduit par le vocabulaire existant, le chercheur consulte nos données et Wikipédia en arrière-plan. Il conserve quatre états pour les actifs : **`oui`, `partiel`, `non_concerne`, `inconnu`**. Une conclusion positive ou négative exige un ticker connu, une preuve réellement lue, l'accord du critique et une confiance suffisante. Une absence de résultat ou une preuve contradictoire laisse l'actif inconnu.

Les preuves, les inconnus et la couverture sont affichés et exportés. Les principales positions d'un FNB ne donnent qu'une exposition minimale connue, sans garantir le reste du fonds. Le cache utilise le concept complet et une empreinte des données, des consignes et du modèle, avec une validité de sept jours : c'est une hypothèse de fraîcheur. Les anciennes entrées incompatibles sont invalidées.

### Synthèse du profil

La page finale affiche la capacité, la tolérance déclarée et la tolérance observée, puis le budget de perte le plus prudent et sa composante limitante. Toutes les tables sont des hypothèses déclarées dans [hypotheses_profil.json](hypotheses_profil.json).

- **Réponses décisives :** leurs valeurs, sources et citations sont reliées aux dimensions qu'elles peuvent modifier. Une exclusion est expliquée comme contrainte pour la future comparaison, sans prétendre qu'elle change le budget.
- **Robustesse locale :** le code fait varier une réponse ordonnée d'un cran à la fois et affiche les budgets, niveaux ou limites qui changent. Il conserve les mesures observées du replay et ne crée pas d'ordre artificiel entre métiers ou objectifs.
- **Informations à compléter :** les inconnues, réglages prudents et besoins de liquidité non chiffrés restent visibles. La synthèse peut être provisoire.

La plage de robustesse n'est ni un intervalle de confiance ni une prévision, et ne teste pas plusieurs changements simultanés. Le JSON téléchargeable conserve la synthèse, les critères, leurs sources, les contraintes personnelles, les résultats de recherche et le journal des contrôles.

## Classificateur et critique

Les deux agents reçoivent les critères et les libellés exacts des choix du questionnaire pour les sujets concernés. Le critique lit chaque citation avec sa question et les échanges utiles ; une autre interprétation doit être plausible et changer la valeur pour justifier une objection.

- Un « non » à une question précise peut être suffisant. Un « oui/non » à une question composée ne renseigne pas tous les champs.
- Les négations et les corrections récentes sont prises en compte. Les mots récents doivent étayer la nouvelle valeur ; une citation ancienne ne suffit pas.
- Une fourchette contenue dans une classe peut être reconnue ; si elle chevauche des classes, elle reste à préciser.
- Être parent, rembourser un prêt pour les études d'un fils ou vivre ensemble ne suffit pas à connaître le nombre actuel de personnes financièrement à charge. Le métier seul ne prouve pas la stabilité des revenus.
- Aucun retrait du capital ne signifie pas absence de besoin de revenu : les intérêts ou dividendes peuvent financer des dépenses essentielles.

Le code précontrôle les listes autorisées, la citation et la confiance avant le critique. Le seuil de validation reste 80 % dans le parcours, y compris lors d'une clarification. Une faible confiance seule ne déclenche pas de nouvelle question. Un résultat approuvé par le critique peut rester « retenu » avec confiance réduite au-dessus de 50 % ; **un désaccord ou une absence de vérification ne deviennent pas utilisables par repli**. Les confiances sont déclarées par les modèles, sans calibration probabiliste démontrée.

## Lancer en local

```bash
.venv/Scripts/python -m pip install -r mvp_profil/requirements.txt
.venv/Scripts/streamlit run mvp_profil/app.py
```

Le SDK lit les identifiants AWS temporaires dans les variables `AWS_*` ou `~/.aws`. La barre latérale permet aussi d'utiliser l'API Anthropic avec une clé. Ne versionner aucun identifiant.

## Fichiers principaux

| Fichier | Rôle |
|---|---|
| `criteres.py` | 42 critères fixes, valeurs autorisées et questions de référence |
| `pilotage.py` | Priorité déterministe des critères, questions et pages restantes |
| `agents.py` | Classement, critique contextualisé, contrôles, débat et maintien prudent |
| `entretien.py` | Réplique, classement en arrière-plan, Transcribe et Polly |
| `app.py` | Orchestration, versions des analyses, précisions, confirmations et restitution |
| `profil.py` | Déductions déterministes, quiz, curseur et cohérence |
| `simulations.py`, `scenarios.json` | Replay, fourchettes et choix de titres |
| `synthese.py`, `hypotheses_profil.json` | Calcul, réponses décisives et robustesse locale |
| `criteres_dynamiques.py` | Critères personnels, pourcentages à confirmer et applicabilité |
| `chercheur.py`, `donnees_chercheur.json` | Recherche à quatre états, preuves, couverture et cache versionné |
| `vocabulaire_actifs.json` | Dimensions et valeurs réellement présentes parmi les 66 actifs |
| `personas/` | Profils fictifs, sources de l'énoncé et hypothèses de test distinguées |
| `voix_composant.py`, `composant_voix/index.html` | Composant vocal commun aux étapes orales |
| `evaluer_classement.py`, `validation/phrases_etiquetees.json` | Évaluation sur 51 phrases et 88 couples, dont des échanges multi-tours |

## Vérifications hors ligne

Neuf suites testent le profil, le débat, les contraintes, la recherche, les deux parcours d'interface, la synthèse, le pilotage et l'évaluation. Les agents et services vocaux sont simulés ; ces vérifications ne prouvent pas la compréhension du vrai modèle.

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

`test_evaluation.py` vérifie notamment que deux mauvaises valeurs différentes ne sont pas répétables, qu'une erreur stable reste fausse et qu'un refus diffère d'une sortie retenable. L'évaluation réelle reste à lancer explicitement : elle appelle le modèle et entraîne des coûts. Son rapport compare les valeurs triées et les statuts effectifs, distingue les erreurs validées et retenables, et conserve les sorties de chaque passage. « Retenable » décrit l'admissibilité après un débat ; ce n'est pas une simulation complète de la réponse utilisateur à une relance.

## Limites

- Le micro exige HTTPS ou `localhost`. L'utilisateur peut écrire si la voix est indisponible.
- La conversation fonctionne à l'alternat ; la reconnaissance et la détection de parole peuvent être affectées par le bruit ou une transcription imparfaite.
- Les seuils, coûts relatifs du pilotage et hypothèses de risque demandent encore une validation sur le modèle et avec des utilisateurs. Aucune nouvelle latence réelle n'est revendiquée.
- Les simulations ne prouvent pas le comportement avec de l'argent réel. L'historique de cinq ans et la couverture partielle des FNB limitent certaines conclusions.
- A11, C3, D10, E3, F1, G4 et G5 restent hors parcours par choix, selon la colonne `demande` de la grille.
- Les critères et expositions préparent le futur moteur ; aucune suggestion personnalisée ni allocation n'est produite par cette version.
