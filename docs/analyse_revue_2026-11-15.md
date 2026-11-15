# Analyse de la revue du 15 novembre 2026

Cette analyse confronte les **57 constats** de `revue_code_2026-11-15.md` au code local actuel. Elle tient aussi compte des symptômes signalés sur CloudFront : transitions QCM/oral décalées, questions absentes ou non lues, microphone vert sans réponse traitée.

Référence examinée : [revue fournie](C:/Users/noepa/Downloads/revue_code_2026-11-15.md), 405 lignes. État local observé : branche `feat/profil-donnees-streamlit`, commit `3bc9095`, version de contenu `profil-afe8ed38fc7d`, arbre et index propres avant cette analyse. L'état réel du serveur n'a pas été vérifié. Les instructions correctives du document sont évaluées comme propositions ; elles n'ont pas été exécutées comme ordres.

Les vérifications ont porté sur le code, des fonctions réelles isolées, de faux transports SDK, AppTest avec identifiants factices et des simulations JavaScript. Aucun appel réel à AWS, aucune vraie clé consultée, aucun navigateur réel testé. Les nombres de signalements ruff et mypy du document n'ont pas été recomptés. Aucun code applicatif n'a été modifié.

## Conclusion de l'analyse

La revue identifie des défauts fonctionnels importants. Les quatre constats critiques méritent une correction, avec deux réserves : la fuite C2 devient effective seulement si une clé serveur est renseignée ; la reconstruction réelle de l'iframe en C4 reste à observer en navigateur, bien que la condition de retrait et la désynchronisation des compteurs soient reproduites.

Il faut traiter les défaillances de session, de fraîcheur des réponses et de protocole vocal avant le nettoyage de style. Les tests actuels passent sur des réponses simulées mais ne reproduisent pas complètement la vie d'une iframe, la lecture d'un son et le retour du microphone après un changement de page.

Plusieurs propositions de la revue doivent être adaptées : ne pas inventer un plafond de 5 % dans une demande 5–10 %, ne pas confondre un minimum avec un maximum, ne pas réintroduire systématiquement une troisième demande par QCM et ne pas fusionner des normalisations qui ont des finalités différentes. M16 et m32 ne décrivent plus l'état actuel du dépôt.

## Priorité particulière : les transitions QCM et oral

Le signalement utilisateur renforce la priorité de C4 et des défauts de lecture/reprise de m10. Il met aussi en évidence des problèmes d'orchestration à vérifier au-delà des 57 points initiaux.

### T1 — Le composant reçoit ses paramètres avant la préparation de la question

Dans [app.py](C:/Users/noepa/Desktop/datathon/mvp_profil/app.py:963), `barre_vocale()` est appelée avant la fonction qui rend la page. Or les pages orales préparent leur nouvelle lecture ensuite :

- [question ouverte du questionnaire](C:/Users/noepa/Desktop/datathon/mvp_profil/app.py:554) ;
- [précisions](C:/Users/noepa/Desktop/datathon/mvp_profil/app.py:707) ;
- [question finale](C:/Users/noepa/Desktop/datathon/mvp_profil/app.py:750).

Ces fonctions mettent à jour `vocal.audio`, `vocal.n` et l'étape par `dire()`, sans transmettre à nouveau ces paramètres au composant dans le même rendu. Le composant peut donc recevoir l'ancien audio et passer en écoute pendant que la nouvelle question n'a pas encore été lue. Un rerun ultérieur peut livrer la question trop tard. **Reproduit sous AppTest dans les trois pages** : le composant reçoit `n=7`, tandis que l'état Python passe à `n=8` ; le nouvel audio n'est transmis qu'au rendu suivant. Le texte de la question est bien émis dans ce test : une absence visuelle complète sur CloudFront reste à reproduire en navigateur. Ce mécanisme est distinct d'une mauvaise compréhension par le modèle.

### T2 — Une réponse audio n'est pas liée à une question précise

Le message audio contient `kind`, un compteur `n` et `wav`, mais aucun identifiant de question ou d'instance. Python choisit ensuite le traitement à partir de la phase actuelle. Il manque donc une garantie explicite qu'un son reçu appartient à la question affichée/lue, notamment après une transition ou une reconstruction du composant. **Reproduit sous AppTest** : un message audio simulé comme provenant de l'horizon est accepté pendant une précision sur la réserve ; « six mois » devient A5 avec confiance 1. Le compteur de réception seul ne fournit pas la correspondance sémantique avec la question.

### T3 — L'identité d'une précision dépend de critères qui peuvent changer

L'étape d'une précision est construite à partir de `item['criteres']`. Cette liste peut être réduite lorsque des critères sont renseignés. Une précision de groupe peut alors changer d'identifiant alors qu'elle est encore active ; les critères restants ont déjà consommé leur compteur de clarification. **Reproduit sous mutation simulée entre deux rendus** : A7 est renseigné dans le groupe A6/A7, puis A6 est retiré de la file sans réponse. Toutefois, cette mutation pendant une précision n'est pas démontrée dans le flux normal actuel, qui attend les analyses avant cette phase. C'est une fragilité conditionnelle, moins prioritaire que T1/T2. Une identité immuable reste la bonne conception.

### Correction de conception recommandée

Préparer une question identifiée avant de rendre le composant, puis utiliser un cycle explicite :

```text
Choix QCM validé
  → question suivante préparée avec un identifiant stable
  → question affichée et audio transmis
  → lecture terminée ou erreur de lecture explicite
  → microphone en écoute pour CETTE question
  → réponse reçue avec identifiants de question et d'instance
  → transcription et intégration une seule fois
```

Le microphone vert doit signifier que l'application est prête à traiter une réponse pour la question active. Une panne de Polly ne doit pas silencieusement faire passer le parcours en écoute. Une pause doit conserver ou rejouer la question ; un double callback ne doit pas produire deux fins. Le budget de clarification doit être attaché à l'identifiant de question, pas recalculé à partir d'une liste mutable.

Ces mécanismes doivent être vérifiés en navigateur avec changements de phase, lecture retardée, rechargement du composant, pause/reprise et messages audio arrivant en retard. Les tests Python de transcription simulée ne suffisent pas.

## Les quatre constats critiques

| ID | Verdict actuel | Correction pertinente |
|---|---|---|
| C1 | **Confirmé.** Un JSON tronqué provoque une `ValidationError` non convertie en `AgentError`. Dans le questionnaire, la future fautive reste dans `en_cours` : trois reruns ont reproduit trois erreurs. La conversation principale possède déjà un filet différent. | Normaliser les erreurs de service et de validation ; retirer chaque tâche dans un `finally` ; conserver la réponse ; permettre une reprise sans recommencer tout le profil. Ne pas convertir tout `RuntimeError` en erreur d'identifiants sans distinguer sa cause. |
| C2 | **Défaut confirmé, exposition conditionnelle.** Une clé factice placée dans l'environnement ressort dans la valeur protobuf du widget, malgré le champ masqué. La présence d'une vraie clé serveur est inconnue. | Aucun secret serveur comme valeur de widget. Une clé de secours serveur reste exclusivement côté serveur. Si une clé réelle a été ainsi exposée, envisager sa révocation après vérification. |
| C3 | **Confirmé.** Un ancien résultat facultatif peut remplacer un QCM plus récent ; reproduction du budget de **20 à 40 %**. | Protéger les écritures du questionnaire comme celles de la conversation : version ou empreinte par critère, priorité aux réponses explicites récentes, résultat tardif ignoré. Le garde-fou proposé sur les seuls facultatifs est un correctif minimal. |
| C4 | **Mécanisme confirmé, effet navigateur à vérifier.** En attente conversationnelle, le composant n'est pas rendu. Un compteur client réinitialisé à 1 avec un `ack` serveur à 7 est ignoré. | Maintenir le composant monté ; synchroniser la nouvelle instance ; lier événements, question et instance. Corriger aussi T1–T3 : la seule modification du `return` ne résout pas tout le protocole. |

Sources principales : [adaptateur SDK](C:/Users/noepa/Desktop/datathon/mvp_profil/agents.py:212), [enregistrement des débats](C:/Users/noepa/Desktop/datathon/mvp_profil/app.py:171), [composant vocal](C:/Users/noepa/Desktop/datathon/mvp_profil/app.py:314), [récupération des analyses](C:/Users/noepa/Desktop/datathon/mvp_profil/app.py:598).

## Les vingt constats majeurs

| ID | Appréciation | Action et nuance |
|---|---|---|
| M1 | **Confirmé, prioritaire.** La ponctuation change le traitement de « 20 ans, ou 10. » ; un horizon probablement déclaré, une borne supérieure et l'instruction méta P43 peuvent court-circuiter le modèle. | Renforcer la grammaire et tester la cascade complète règles puis IA. Certains exemples courts sont déjà refusés ; le défaut apparaît avec leur contexte. Sortir du raccourci déterministe ne doit pas automatiquement faire répéter l'utilisateur : le modèle peut résoudre le contexte. |
| M2 | **Confirmé.** A7 accepte certains oui/non composés, mais ignore sa propre formulation conversationnelle et « Non, aucune. ». | Identifier le critère demandé par des métadonnées et un contexte mono-sujet. Ne pas interdire tous les « ou » : une carte ou un prêt sont deux exemples du même critère. |
| M3 | **Confirmé, prioritaire.** Les morceaux d'une citation peuvent être réordonnés ou provenir de réponses distinctes. | Une citation normalisée **contiguë dans un message identifié** est préférable. Le correctif proposé par la revue reste insuffisant : « je veux … de crypto » peut supprimer « vraiment pas » même avec des morceaux ordonnés. |
| M4 | **Confirmé, prioritaire.** Deux valeurs distinctes sur un critère unique sont tronquées ; une valeur interdite peut être filtrée en laissant valider le reste. | Rejeter la proposition incohérente au lieu de la réparer silencieusement. Faire corriger la sortie entre agents ; un défaut du modèle ne prouve pas une ambiguïté de la réponse humaine. |
| M5 | **Confirmé.** Minimum et fourchette peuvent devenir un plafond de 10 %. | Préserver le sens de la contrainte ; garder une fourchette à préciser. Ne pas choisir automatiquement 5 %. Ne pas rejeter « pas plus de 10 % » à cause des seuls mots « plus de ». |
| M6 | **Confirmé.** Une source d'un autre actif peut justifier un verdict ; un accord unique par ticker couvre plusieurs preuves. | Rattacher chaque preuve à l'entité et au contexte de la source ; un avis par verdict. Le test utilise un critique simulé : il ne démontre pas que le vrai modèle juge « Tesla, classe equity » probant pour Musk. Exiger le nom dans chaque phrase web peut rejeter des preuves pronominales légitimes. |
| M7 | **Confirmé, exploitation conditionnelle.** Une langue non autorisée peut produire un autre hôte ; `getattr` accepte une méthode hors outils. | Liste d'hôtes et d'outils autorisés, validation des arguments et taille maximale de réponse dans le code. L'hôte `evil.com` a été reproduit sans appel réseau. Les redirections sont déjà désactivées par défaut dans la bibliothèque installée ; les expliciter reste utile. |
| M8 | **Partage confirmé, fuite privée et injection conditionnelles.** Le second utilisateur peut récupérer les requêtes du premier pour un même concept. | Séparer traces de session et faits publics réutilisables ; ne pas partager les requêtes brutes ; corriger l'affirmation sur l'absence de données personnelles. Les résultats utilisent déjà des blocs `tool_result` ; ajouter des balises XML ne suffit pas à sécuriser un contenu non fiable. |
| M9 | **Confirmé, très pertinent pour les blocages.** SDK à 600 s de lecture et deux reprises ; quatre fils communs et attentes sans délai. | Borner chaque I/O et le temps applicatif, gérer expiration et saturation. Un timeout sur `future.result` ne libère pas un fil déjà bloqué : il faut traiter la cause réseau aussi. |
| M10 | **Comportement confirmé, choix UX.** Un B1 laissé à 20 % est enregistré comme validé à confiance 1. | Une valeur initiale sans réponse ou un choix explicite unique est préférable. Pas besoin de confirmer deux fois toutes les réponses. Le montant fictif G1 peut rester une hypothèse de scénario s'il est nommé comme tel. |
| M11 | **Choix produit à arbitrer, pas correctif automatique.** Les inconnues déjà clarifiées sont exclues des compléments. | Offrir une résolution fermée **facultative** ou une relecture modifiable. Retirer simplement le filtre imposerait une troisième demande, contraire au besoin exprimé. Garder les inconnues et l'effet des défauts prudents visibles. |
| M12 | **Déclencheur trop large confirmé ; impact exagéré.** « En fait » réouvre tous les critères connus. Cela ne les efface pas automatiquement et n'annule pas matériellement toutes les tâches. | Cibler le sujet de la correction. Ne pas supprimer aveuglément cette expression, qui introduit aussi de vraies corrections naturelles. |
| M13 | **Confirmé.** Certaines clés de configuration ne pilotent pas les calculs annoncés. Le seuil de change est utilisé à un endroit, puis doublé par une constante différente ailleurs. | Une source de vérité pour chaque seuil ; supprimer les clés mortes ou expliquer des dimensions réellement distinctes. Ne pas choisir un nouveau seuil financier sans justification. |
| M14 | **Confirmé pour le périphérique.** Le flux reste ouvert malgré « micro coupé ». | Mettre les pistes en sourdine pendant la veille et libérer les ressources à la fin. Le traitement ignore déjà les trames hors écoute : cela ne prouve pas une transmission continue au serveur. |
| M15 | **Maintenance pertinente, urgence surclassée.** Le type concret des sorties est perdu derrière `BaseModel`. | Un générique et des noms de variables distincts aident mypy. Utiliser `TypeVar` si le Python du serveur est antérieur à 3.12 ; PEP 695 n'est pas universellement compatible. Aucun plantage runtime démontré ici. |
| M16 | **Dépassé.** Le dépôt actuel possède un commit, des modules suivis, un arbre et un index propres. | Aucun `git add` ou premier commit correctif à effectuer sur la base de ce constat historique. |
| M17 | **Vrai défaut documentaire ; archive actuelle complète.** La recette manuelle oublie cinq modules, mais le préparateur les embarque. | Faire de `scripts/preparer_mvp.py` l'unique procédure ; vérifier le manifeste et la version après publication. Ne pas présenter l'archive actuelle comme cassée. |
| M18 | **Partiellement pertinent.** Les validations de production par `assert` disparaissent sous `-O`, reproduit sur le corpus. | Remplacer ces validations par des exceptions explicites. Les tests avec `assert` restent utiles sous l'exécution normale ; la migration pytest n'est pas une urgence fonctionnelle. Un lanceur exhaustif qui propage tout échec et une liste exacte des suites apportent une valeur immédiate. |
| M19 | **Résidu réel, priorité basse.** L'ancien seuil à 65 % n'est plus utilisé par le parcours. | Supprimer ou déprécier les fonctions, imports et messages périmés. Ne pas réactiver cette baisse pour satisfaire une ancienne documentation. |
| M20 | **Vrai défaut documentaire pour la suite.** Les valeurs profil/actifs ne sont pas toutes identiques. | B5 est identique ; E5/F2 utilisent des correspondances. B7 requiert durées et états de récupération explicites : `correspondances.json` n'a pas de clé B7, contrairement à ce que suggère le correctif de la revue. |

## Les trente-trois constats mineurs

Le classement « mineur » mélange de la présentation et des défauts touchant réellement les résultats. m26 et m27 méritent une priorité supérieure à une règle de style.

| ID | Pertinence | Traitement recommandé |
|---|---|---|
| m1 | Nettoyage réel, peu urgent. | Retirer les imports inutilisés et commentaires obsolètes après les corrections fonctionnelles. Éviter un `ruff --fix` large non relu. |
| m2 | Code mort réel ; `voix=True` répond aussi au choix produit oral obligatoire. | Retirer les chemins non utilisés et la documentation d'un agent Réplique actif ; conserver une politique vocale explicite. |
| m3 | Style et lisibilité. | Formater par lots ciblés avec diff relu ; les nombres de lignes longues ne mesurent pas la gravité du projet. |
| m4 | Gestion des erreurs trop silencieuse. | Journaliser les exceptions inattendues et borner les exceptions de service ; garder un filet qui préserve la session, plutôt que réintroduire un plantage permanent. |
| m5 | **Vrai défaut d'entrée audio.** Un WAV invalide produit `wave.Error` hors du traitement attendu. | Décodage protégé et limite de taille cohérente avec le format et la durée réellement autorisés. |
| m6 | Robustesse du cache. | Écriture atomique et purge ; le verrou protège déjà les fils du processus, mais pas un arrêt pendant l'écriture. |
| m7 | **À traiter avec les contenus non fiables.** HTML/Markdown peut modifier l'affichage ou charger une image distante. | Citations affichées comme texte et liens construits explicitement. `html.escape` seul ne neutralise pas les images Markdown. Pas de preuve d'exécution JavaScript obtenue. |
| m8 | Durcissement utile. | Vérifier l'émetteur des messages ; retirer ou désactiver les points de test en production. Cela ne remplace pas l'identité de question/instance. |
| m9 | Maintenance audio. | Préparer `AudioWorklet` et la reprise du contexte, après le protocole de transition. `demarrer` possède déjà un `try/catch` : l'absence d'un `.catch` externe n'est pas seule une panne démontrée. |
| m10 | **Deux vrais défauts audio reproduits.** Double fin et perte de lecture après pause/reprise. | Callbacks idempotents par lecture ; reprise ou rejeu de la question. L'adaptation au bruit doit ensuite être testée avec des enregistrements représentatifs. |
| m11 | Traçabilité temporelle utile. | Dates UTC avec fuseau dans les exports et évaluations. |
| m12 | Défense en profondeur ; aucune troncature actuelle démontrée. | `zip(strict=True)` là où une égalité de longueur est un invariant. Pas de remplacement mécanique partout. |
| m13 | **Unification générale déconseillée.** Citation, nombre et slug ont des sémantiques différentes. | Partager les constantes identiques ; garder des fonctions de normalisation distinctes et testées pour chaque usage. |
| m14 | Maintenance. | API interne nommée clairement ; `contextlib.nullcontext` si cela simplifie réellement. |
| m15 | Documentation résiduelle. | Supprimer la chaîne inutile et les références à la réponse au clavier. |
| m16 | Reproductibilité utile, installation cassée non démontrée. | Déclarer les imports directs et figer un environnement. Les dépendances citées sont déjà transitivement apportées par les paquets et l'extra activé. |
| m17 | Maintenance de scripts. | `main()` et garde d'exécution pour rendre les imports testables. Ne pas appliquer `sort=True` sans vérifier le résultat et la chronologie. |
| m18 | Robustesse de collecte et liens. | Fermer les ressources, vérifier les statuts, encoder les paramètres et identifier correctement le client. Certains liens fonctionnent déjà : ne pas annoncer une panne systématique. |
| m19 | Mineur réel. | Fermer le fichier dans le test avec un contexte. |
| m20 | Latence potentielle. | Mettre en cache la détection d'identifiants avec une stratégie de rafraîchissement. Aucun délai IMDS réel n'a été mesuré ici. |
| m21 | **Trace incomplète confirmée.** `evenements_questions` n'est jamais alimenté. | Enregistrer les événements du questionnaire avec des identifiants stables. Ne pas confondre cette lacune avec une preuve de dépassement actuel des budgets. |
| m22 | Message trompeur confirmé. | N'annoncer un défaut prudent que s'il existe ; distinguer les notes et contraintes inconnues. |
| m23 | Réglage partiellement ignoré. | Passer le budget de débat à tous les chemins ou retirer le contrôle trompeur ; ne pas ajouter des appels inutiles par défaut. |
| m24 | Vrai problème d'explication ; budget exact déjà conservé. | Vente à 16 % et déclaration à 20 % peuvent produire H1 « aucun », mais le budget reste 16 %. Afficher et comparer les mesures exactes plutôt que changer arbitrairement leur classe. |
| m25 | Cohérence future de l'appariement. | Conventions explicites aux frontières. Conserver la distinction entre classe descriptive SRRI et limite de volatilité du profil. |
| m26 | **Vrai bug de données, à remonter en priorité.** Le premier rendement de 2022 est omis. | Base de fin 2021. Recalcul CAD en mémoire : XOM 92,806 % devient 100,210 % ; l'écart n'est donc pas toujours négligeable. Vérifier les indicateurs dérivés après correction. |
| m27 | **Vrai défaut d'exposition FNB.** GOOG n'est pas relié à l'émetteur alors que GOOGL l'est. | Correspondances explicites de titres et d'émetteurs. Positions GOOG non reliées observées : SPY 2,0247 %, ESGV 2,7139 %, VT 1,3586 %. |
| m28 | Risque d'unité/date, pas erreur générale établie. | Vérifier l'unité du champ et son origine avant conversion : `fast_info` et son fallback ne garantissent pas la même convention. Ne pas imposer `/100` par simple analogie aux cours. La date de collecte est déjà documentée. |
| m29 | Grille périmée réelle. | Aligner les règles écrites R8/R9 et A8 avec le code, puis tester les colonnes textuelles que le synchroniseur ne réécrit pas. |
| m30 | Documentation incohérente réelle. | Compter 242 valeurs ; distinguer version locale, paquet et serveur avec preuve/date. La contradiction documentaire ne prouve pas la version du serveur. |
| m31 | Information sur le fichier fourni par les organisateurs. | Ne pas modifier ce fichier pour satisfaire une revue de notre implémentation. `date.today` est une date civile, pas un datetime naïf. |
| m32 | **Dépassé.** Les trois doublons racine n'existent plus. | Aucune suppression à effectuer. |
| m33 | Messages de tests périmés ; fragilité à cibler. | Corriger le texte des assertions et les attentes temporelles. Conserver aussi des tests d'intégration sur le jeu de données figé : tout remplacer par des mocks retirerait une couverture utile. |

## Ordre de correction recommandé

1. **Sessions et voix :** C1, C3, C4, T1/T2, m10 ; borner M9 et protéger m5. Durcir T3 dans la même refonte, en conservant sa portée conditionnelle. Corriger C2 sans attendre si une clé serveur existe, et supprimer le défaut latent dans tous les cas.
2. **Intégrité des valeurs :** M1–M7 et M10. Chaque changement doit avoir un cas positif clair et un cas adverse ; un garde-fou ne doit pas faire répéter les réponses légitimes.
3. **Confidentialité et traçabilité :** M8, M14, m7/m8, m21/m22 ; identifiants de question et d'instance dans les événements.
4. **Données et publication :** m26/m27, M13, M17/M20, m25/m29/m30, validations explicites de M18. Le paquet actuel est complet ; la procédure manuelle reste à corriger.
5. **Maintenance :** M15/M19 et le reste des règles de style. Un lanceur de tests complet est utile rapidement ; une migration générale de framework et d'API audio peut être séparée.

M11 doit être tranché comme un choix de parcours : proposer de résoudre une inconnue par un choix fermé, sans imposer à nouveau une troisième réponse. L'objectif reste de préserver les informations et les contraintes avec moins de répétitions, pas d'afficher artificiellement un profil complet.

## Critères de validation avant publication

- Une erreur SDK ou un WAV invalide laisse les réponses accessibles et ne réapparaît pas à chaque rerun.
- Un résultat tardif ne remplace jamais un choix explicite plus récent, quelle que soit la phase.
- QCM → oral : la question courante est affichée et lue avant que le micro soit prêt à répondre.
- Une attente, une pause, une reprise et une reconstruction de l'iframe conservent la correspondance entre question et réponse.
- La fin d'une lecture n'est traitée qu'une fois ; une précision partiellement résolue ne disparaît pas sans réponse.
- Les citations ne peuvent pas inverser une négation ; un minimum n'est pas transformé en maximum ; aucune valeur hors schéma n'est réparée silencieusement.
- Les évaluations couvrent toute la cascade, y compris les règles directes et les transitions du vrai composant.
- Le numéro de version du paquet est comparé à celui affiché par le serveur. Un succès des seuls tests simulés ne vaut pas vérification du parcours vocal déployé.
