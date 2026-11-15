# Audit du projet AlphaForge AI, 15 novembre 2026

**Suite de l'audit :** les bugs reproduits ont été corrigés localement après ce diagnostic. Voir [les corrections et leurs 28 suites de validation](correctifs_audit_multi_agents_2026-11-15.md). La note et les exemples ci-dessous restent l'instantané de l'état audité avant correction.

Note estimée sur l'état local examiné : **75/100, soit 15/20**. Cette appréciation applique les six pondérations officielles. Elle ne prétend pas reproduire la grille détaillée, réservée au jury, ni anticiper une présentation non observée. L'admissibilité reste conditionnée à la démonstration d'une contribution effective d'AWS.

L'audit a mobilisé un agent principal et trois agents spécialisés : code et agents IA ; données et calculs financiers ; consignes, livrables et infrastructure. Les constats principaux ont ensuite été reproduits par l'agent principal. Le code de production n'a pas été modifié. Aucun déploiement ni appel volontaire aux services cloud n'a été réalisé.

La version locale du contenu de production examinée est `profil-57bc447b2a10`, avec un inventaire de 59 fichiers. L'audit porte sur les fichiers locaux, y compris les modifications non validées dans Git ; il ne prouve pas que ce contenu est installé sur le site partagé.

**Références officielles.** `Datathon2026/Datathon - Case Officiel 2026 FR.pdf`, pages 3 à 18, et grille de la page 19, rendue et inspectée visuellement ; `Datathon2026/Presentation_AlphaForge_AI_Participants.pptx`, diapositives 7, 9 et 10. La présentation précise l'exigence d'admissibilité AWS. Une allocation fictive, un nombre particulier d'agents ou un nombre minimal d'actifs ne sont pas obligatoires.

## Appréciation selon les consignes

| Critère officiel | Maximum | Note estimée | Raisons principales |
|---|---:|---:|---|
| Qualité, pertinence et innovation de la solution | 20 | 17 | Question utile ; parcours complet du profil aux propositions ; comparaison déclaré/comportement et cas Robert convaincants. Validation auprès d'utilisateurs et de spécialistes encore absente. |
| Intelligence agentique et explicabilité | 20 | 15 | Rôles, outils, preuves, verdicts déterministes et secours solides. Contrôle sémantique insuffisant des explications ; interprétation des refus et confirmations défectueuse dans le secours sans modèle. |
| Capacité d'analyse et traitement des données | 20 | 15 | Univers enrichi, conversion CAD, traitements et provenance documentés ; indicateurs reproductibles. Défauts de change, rentabilité et portée des exclusions indirectes. |
| Expérience utilisateur UX/UI | 10 | 8 | Présentation soignée et parcours Robert observé dans le navigateur ; résultats et preuves accessibles. Oral obligatoire pour établir un nouveau profil ; densité de la synthèse et absence de mesure de durée/complétion. |
| Qualité de l'intégration AWS | 15 | 11 | Services liés à des fonctions réelles, infrastructure et CI présentes. Version hébergée et parcours réel non vérifiés ; accès jury encore filtré ; retour arrière incomplet dans un cas. |
| Présentation, valeur business et marketing | 15 | 9 | Proposition de valeur et script démonstratif clairs. Vidéo finale non constatée ; one pager non paginé et long ; déclarations documentaires contradictoires ; valeur métier non mesurée. |
| **Total** | **100** | **75** | **15/20** |

Une incertitude d'environ cinq points est raisonnable : le vrai pitch, la vidéo éventuellement conservée ailleurs et la démonstration AWS peuvent changer l'appréciation. Une intégration AWS réellement absente entraînerait un problème d'admissibilité, pas seulement une petite déduction dans cette table.

## Ce que le projet réussit

Le problème choisi correspond directement au défi : transformer des données publiques et un contexte d'investisseur en une décision compréhensible. La séparation entre modèle et code est défendable. Les modèles comprennent, classent, choisissent des outils et rédigent ; le calcul déterministe applique les contraintes et fixe les verdicts. Les organisateurs encouragent précisément une approche focalisée et vérifiable : davantage d'agents ou de services n'apporterait pas automatiquement de points.

La solution contient bien une chaîne complète : profil, mises en situation, synthèse, portefeuille fictif, recherche d'actif, comparaison, demandes d'ajout, alternatives, sensibilité et sources. Les décisions sont liées à des réponses du profil, des données ou des hypothèses explicites. La distinction des inconnues, réponses incertaines et données manquantes est un point fort.

Les trois tensions des personas sont représentées : Amira accepte le risque avec des plafonds et une diversification ; Mateo introduit des contraintes non financières ; Robert reçoit une objection à une demande trop risquée. Les compléments fictifs des personas sont distingués des faits de l'énoncé.

Dans le navigateur local, l'accueil, le chargement de Robert, la synthèse, le portefeuille et le conseiller ont été inspectés. La demande « J'aimerais 20 % de Nvidia » reçoit correctement un refus de 20 %, une proposition de 5 % et deux boutons de confirmation. La mise en page est cohérente et les limites de simulation sont visibles. Le micro et les vrais services vocaux n'ont pas été testés.

La préparation des données et du paquet est substantielle : inventaire, empreintes, version du contenu, tests de synchronisation et CI avant déploiement. Les modes de secours évitent qu'une indisponibilité du modèle empêche toute démonstration.

## Vérifications des données et résultats

L'agent données a contrôlé **111 actifs uniques et 140 159 lignes de prix** : 40 049 du jeu initial et 100 110 ajoutées. Aucun doublon `(date, ticker)` ni prix ajusté nul, négatif ou non fini n'a été trouvé. Le recalcul des indicateurs numériques des 111 séries reproduit les valeurs stockées à une tolérance de `1e-9`. Cela vérifie la reproductibilité du calcul, pas sa validité économique à lui seul.

Les résultats suivants ont aussi été recalculés par l'agent principal :

| Persona | Positions | Poche croissance | Perte de stress | Conflits signalés par les contrôles actuels |
|---|---:|---:|---:|---:|
| Amira | 12 | 92,1 % | 22,5 % | 0 |
| Mateo | 12 | 60,0 % | 12,8 % | 0 |
| Robert | 12 | 40,0 % | 6,0 % | 0 |

L'absence de conflit signifie que les règles actuellement codées passent ; elle ne corrige pas les lacunes de leur périmètre, décrites ci-dessous. Les poids et l'encaisse totalisent 100 % à l'arrondi près.

Le jeu annoté du classificateur est structurellement valide : **51 phrases et 88 couples phrase–critère**, vérifiés avec `mvp_profil/evaluer_classement.py --verifier`. Cette commande ne mesure pas l'exactitude du modèle réel.

Le bilan d'exécution des suites est consigné en fin de rapport.

## Constats prioritaires et corrections proposées

### 1. Une explication contradictoire avec le verdict est acceptée

**Priorité haute ; reproduction confirmée.** `mvp_profil/recommandation/agents.py:163` à `:170` accepte un texte si ses nombres passent la fidélité et ses formulations passent les regex. Le sens de la phrase n'est pas comparé au verdict.

Pour Robert et NVDA à 20 %, le verdict reste `en_tension`. Un faux modèle renvoyant « NVDA est compatible avec votre profil. Toutes vos limites sont respectées. » est cependant accepté avec `fidele=True`, `conforme=True` et zéro rejet. Le faux modèle démontre une lacune de contrôle ; il ne mesure pas sa fréquence avec Bedrock.

L'invariance du verdict est une garantie utile, mais elle ne garantit pas la fidélité de son explication. Les essais de dix justifications de `test_reco_agents.py:94` utilisent `modele=None` : ils ne couvrent pas cette contradiction textuelle.

**Correction proposée :** rendre le verdict, les limites et les raisons structurées directement depuis les outils ; vérifier l'accord du texte généré avec ces champs, puis revenir au gabarit en cas de contradiction. Ajouter un cas de régression avec une phrase erronée sans chiffres.

### 2. Le secours sans modèle agit malgré une négation ou une question

**Priorité haute ; reproduction confirmée.** `mvp_profil/recommandation/conversation.py:252` à `:265` transforme la reconnaissance d'un nom d'actif en action d'ajout.

Avec Amira, « Je ne veux pas de Nvidia » et « Est-ce que Nvidia est risqué ? » ajoutent chacune NVDA à 5 %. Aucune transaction réelle n'est concernée, mais le portefeuille fictif change contre l'intention exprimée.

**Correction proposée :** distinguer demande d'information, refus, retrait et ajout affirmatif ; n'ajouter qu'après une intention positive reconnue. Une phrase ambiguë doit demander une précision. C'est particulièrement important pour un mode de secours susceptible d'être utilisé devant le jury.

### 3. Une confirmation contenant un refus est appliquée

**Priorité haute ; reproduction confirmée.** `mvp_profil/recommandation/conversation.py:236` à `:247` reconnaît d'abord le préfixe « oui ».

Après une proposition de D9 de 5 % à 20 %, « Oui, mais pas maintenant, ne modifiez rien. » applique D9=20. La citation enregistrée contient pourtant le refus.

**Correction proposée :** donner priorité au refus et à la réserve ; exiger une confirmation non ambiguë, et conserver la proposition en attente sinon. Les boutons Oui/Non du parcours nominal sont clairs ; le traitement du texte doit offrir le même niveau de contrôle.

### 4. Risque de change masqué par la devise de cotation

**Priorité haute ; reproduction confirmée.** `scripts/build_asset_criteria.py:239` fixe `fx_risk="aucun"` pour les actifs cotés CAD. Pourtant XEQT.TO est explicitement décrit comme `cad_actifs_etrangers_non_couverts`, ligne 478.

`mesures.expositions({"XEQT.TO": 1.0}, univers)["hors_cad_pct"]` renvoie **0,0 %**. Les contrôles D4 utilisent ce champ (`recommandation/mesures.py:103`, `portefeuille.py:62` et `:270`). Le plafond économique de change peut donc être sous-estimé via un FNB coté CAD.

**Correction proposée :** séparer devise de cotation, exposition économique et couverture. Utiliser l'exposition sous-jacente connue et signaler le solde inconnu ; ne pas assimiler cotation en CAD et absence de risque de change.

### 5. Rentabilité et qualité financière inversées avec des capitaux propres négatifs

**Priorité haute ; reproduction confirmée.** `scripts/build_asset_criteria.py:202` déduit le signe du bénéfice à partir de `ROE > 0`. Un bénéfice négatif divisé par des capitaux propres négatifs produit pourtant un ROE positif.

Les données du dépôt indiquent des pertes pour Boeing en 2022, 2023 et 2024. Sa part d'années rentables vaut pourtant **1,0**, avec `established=True`. Philip Morris a des bénéfices positifs sur les quatre exercices et reçoit **0,0**, `established=False` et `pertes_recurrentes`.

La ligne 433 étiquette aussi un ratio dette/capitaux propres négatif comme `faible_endettement`. Ces étiquettes interviennent dans la préférence pour les entreprises établies.

**Correction proposée :** lire directement `Net Income` ; traiter ROE et dette/capitaux propres comme non interprétables lorsque les capitaux propres sont nuls ou négatifs. Régénérer les fichiers dérivés et embarqués ensuite.

### 6. Portée des exclusions ESG indirectes insuffisamment définie

**Priorité moyenne à haute ; résultat confirmé, choix métier à clarifier.** Mateo exclut GOOGL pour une controverse grave. Son portefeuille contient toutefois **1,4 % d'exposition connue à GOOGL via les fonds**, sans conflit signalé.

E2 examine la sévérité de la ligne d'actif (`contraintes.py:135`) ; le contrôle « Aucun actif exclu dans le portefeuille » ne vérifie que les positions directes (`portefeuille.py:281`). Les expositions indirectes sont déjà disponibles dans `mesures.py:115`.

Une exclusion limitée aux détentions directes peut être un choix de simulation défendable, à condition de l'annoncer. L'expression générale actuelle laisse entendre une portée plus large.

**Correction proposée :** soit appliquer les exclusions aux sous-jacents connus et afficher la couverture inconnue, soit renommer explicitement le contrôle « aucune détention directe exclue » et montrer les expositions indirectes restantes.

### 7. Les regex ne garantissent pas l'absence de conseil ou de prédiction

**Priorité haute pour les promesses du produit ; reproduction confirmée.** `gouvernance.py:13` à `:32` accepte notamment « Investissez dans NVIDIA dès maintenant. », « NVIDIA prendra de la valeur cette année. » et « Je recommande de placer toutes vos économies dans ce titre. ».

Ces formulations passent aussi le contrôle numérique faute de chiffres. Le Guardrail étant désactivé par défaut, le contrôle local n'est pas équivalent au service supplémentaire évoqué dans la documentation.

**Correction proposée :** réduire les promesses de garantie, renforcer le contrôle du texte et le secours, puis évaluer les vrais modèles sur un jeu de formulations interdites, négations et détournements. La mention éducative seule ne corrige pas un texte contradictoire.

## Autres points techniques

- **Ponctuation :** « Je veux Nvidia » est reconnu, mais « Je veux Nvidia. » échoue dans l'interprète sans modèle. Le découpage conserve le point final (`conversation.py:252`).
- **Sensibilité :** les variantes de `Analyse.sensibilite()` ne transmettent pas `self.ajouts` (`analyse.py:425` et appels suivants). Sur une analyse contenant des ajouts imposés, le test risque de changer plusieurs facteurs. Constat statique ; impact à confirmer dans les parcours exposés.
- **Retour arrière :** sous `set -e`, un échec de `systemctl restart` dans `scripts/installer_serveur.sh:25` quitte le script avant le bloc de restauration, lignes 44 à 52. Ce cas doit être inclus dans la gestion d'échec.
- **État du journal :** si une écriture locale échoue directement, `traces.py:50` conserve `persister=True` et `stockage()` annonce toujours un fichier local. Le résultat devrait devenir « mémoire seulement ». Reproduction par simulation de `PermissionError`.
- **Reproductibilité :** les dépendances ont des bornes minimales sans verrouillage constaté. L'installation sur le serveur ne met pas à jour les dépendances ; une CI fraîche peut donc réussir là où l'environnement ancien échoue.
- **Archives de remise périmées :** `mvp_profil.zip` contient la version `profil-970d7c7ff946` (26 fichiers avec manifeste) ; `artifacts/alphaforge-refonte-2026-11-15.zip`, `profil-a07d721a7d20` (35 fichiers). Le vérificateur actuel `scripts/preparer_mvp.py:16` rejette les deux avec « Le manifeste ne décrit pas exactement tous les fichiers de production requis ». Il faut construire un nouveau paquet avant remise ; l'audit n'a pas remplacé ces archives.
- **Traces :** le texte des demandes peut être conservé ; aucune politique applicative de durée/suppression n'est constatée. C'est une limite d'exploitation avec des profils réels, pas une violation automatique pour les personas fictifs. Ne pas prétendre que DynamoDB est sans chiffrement : aucun tel défaut n'a été démontré.

## Conformité des livrables et de la démonstration

| Livrable ou exigence | Constat | Action avant remise |
|---|---|---|
| Prototype et code | Présents ; parcours démonstratif local observé | Figer une version et conserver sa preuve d'exécution |
| README reproductible | Instructions présentes, mais contradictoires sur l'état du moteur | Supprimer les passages « pas encore implémenté » ou « aucune allocation » devenus faux |
| Documentation technique | Méthodes, sources, hypothèses, preuves et limites présentes | Harmoniser les états local/publié/vérifié |
| Vidéo | Script présent ; aucun fichier vidéo final trouvé dans les fichiers examinés | Enregistrer et fournir la vidéo ; si elle existe ailleurs, l'intégrer à la remise |
| One pager | Environ 787 mots, huit sections, deux tableaux ; pas de rendu paginé constaté | Produire un document lisible tenant réellement sur une page maximum |
| AWS réel | Code, architecture, configuration et vérifications historiques documentés | Démontrer la version actuelle depuis le site : appel Bedrock, sortie d'outil, trace et voix |
| Accès du jury | Filtrage IP maintenu ; Cognito non branché | Tester l'accès depuis le contexte prévu du jury, sans modifier la sécurité dans cet audit |
| Présentation business | Bénéfice compréhensible | Préciser utilisateur cible, situation d'usage, coût et indicateur de valeur mesurable |

Les passages obsolètes sont notamment `README.md:69`, `mvp_profil/README.md:9` et `:157`. Les conditions d'accès sont explicites dans `docs/deploiement_recommandation.md:60`. La documentation technique reconnaît que le parcours complet avec le vrai modèle depuis le serveur et l'exactitude du classement libre n'ont pas été validés.

Ne pas affirmer qu'une simulation mesure ce qu'une personne « supporte réellement » avec de l'argent réel. La formulation défendable est « comportement observé dans la simulation ». De même, « provenance numérique contrôlée » est plus précis que « aucun chiffre inventé », car un nombre admissible peut encore être utilisé dans une phrase fausse.

## Limites méthodologiques à défendre devant le jury

Les seuils et scores sont des hypothèses ajustables, non des vérités calibrées. La fenêtre historique contient surtout la crise de 2022 ; elle ne borne pas une perte future. L'univers choisi aujourd'hui comporte un biais de sélection. Les tests de sensibilité sont utiles mais ne remplacent pas une validation externe.

Les FNB se recouvrent : plusieurs lignes ne suffisent pas à démontrer une diversification. Les positions connues sont partielles, par exemple environ 20 % pour VT et 4,7 % pour USMV ; les positions de XEQT ne sont pas rattachées dans la table utilisée pour les expositions par titre. La documentation reconnaît ces limites, ce qui est positif.

L'expérience de neuf portefeuilles construits par le modèle seul est une bonne justification exploratoire de l'architecture. Elle ne constitue pas une comparaison statistique générale ni une vérité externe : le moteur sert lui-même de référence d'évaluation. Le rapport reconnaît d'ailleurs les cas où le modèle utilise davantage le budget d'Amira.

## Ordre de travail recommandé

1. Corriger les refus et confirmations, ainsi que la restitution contraire au verdict ; ajouter des régressions ciblées sur les cas reproduits.
2. Corriger change et rentabilité ; régénérer les données et vérifier les changements des trois personas.
3. Définir la portée des exclusions indirectes et rendre les inconnues des fonds visibles.
4. Harmoniser README, documentation et pitch ; terminer la vidéo et le one pager paginé.
5. Vérifier un vrai parcours sur la version AWS destinée au jury, avec accès, outils et journal démontrés.
6. Mesurer le classement réel et quelques parcours utilisateurs ; annoncer les résultats observés, y compris les erreurs et délais.

La priorité est la fiabilité de la démonstration et la fidélité des explications. Ajouter des actifs ou des agents avant ces corrections apporte moins que sécuriser les cas centraux déjà promis.

## Traces de l'audit

Les extractions des consignes, l'image de la grille, les journaux et le script de reproduction sont dans `tmp/audit_2026-11-15/`. Le script `reproduire_constats.py` s'exécute avec le Python du projet et n'appelle aucun modèle réel.

**Bilan des suites : 26/26 réussies.** Commande : `.venv/Scripts/python.exe -u scripts/lancer_tests.py --timeout 300`, avec modèles désactivés, traces locales et métadonnées AWS désactivées. Journal : `tmp/audit_2026-11-15/tests_hors_restriction.txt`. Le jeu annoté a été vérifié séparément avec `mvp_profil/evaluer_classement.py --verifier` : 51 phrases, 88 couples, aucun appel au modèle.

Le premier lancement dans l'environnement restreint ne produisait pas de bilan. Un diagnostic par pile d'exécution a identifié une attente dans `socket._fallback_socketpair`, appelée lors de la création de la boucle asyncio de Streamlit, avant l'exécution de l'application. Les essais incomplets ont été arrêtés, puis la suite a été relancée après autorisation automatique de l'exécution hors restriction. Le succès des 26 suites confirme que cette attente était liée à l'environnement ; elle n'est pas retenue comme un défaut du projet.

Les constats adverses de cet audit passent malgré les tests existants. Ils montrent des lacunes de couverture des tests et de certaines règles, pas un échec du lanceur ni une preuve de fréquence d'erreur du modèle réel.
