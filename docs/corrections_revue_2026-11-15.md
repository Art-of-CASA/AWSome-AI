# Corrections de la revue du 15 novembre 2026

Implémentation locale des cinq groupes retenus dans l'analyse, avec suppression du défaut d'exposition de clé serveur. Aucun envoi AWS ni publication sur CloudFront n'a été effectué par cette intervention. Le paquet a ensuite été publié le 15 novembre 2026 : le serveur affiche la version `profil-970d7c7ff946`.

## 1. Coordination du parcours vocal

Le conteneur du composant conserve sa place dans tous les rendus. La page prépare d'abord sa question, puis lui transmet le texte, l'audio et les identifiants de session, question et lecture. Chaque réponse transporte aussi une identité d'instance du composant. Python vérifie ces identités avant de transcrire : un audio ancien n'est pas interprété dans le nouveau contexte. Les compteurs sont dédupliqués par instance et resynchronisés lors d'un remontage.

Le micro n'écoute qu'après la fin de lecture de la question active. Les pistes sont désactivées pendant une lecture, une pause, une attente ou un QCM ; elles sont libérées à la fin. Une erreur de lecture reste visible avec une action de reprise. Les anciens callbacks et doubles fins sont ignorés. La pause conserve la position du lecteur. Les questions de précision ont une identité immuable ; le texte et les cibles effectivement présentés restent le référent de la réponse même si une analyse termine entre deux rendus.

## 2. Reprise après erreur et limites de ressources

Les erreurs de schéma, de transport, d'authentification et de SDK deviennent des erreurs contrôlées. Toute tâche échouée ou expirée est retirée du suivi et la réponse reste conservée. Le questionnaire propose de relancer le contrôle sans redire la réponse. Les précisions et la création des critères personnels sont traitées en arrière-plan ; une fermeture de conversation n'attend plus dans une boucle bloquante.

Le SDK utilise un délai I/O de 30 secondes et une reprise maximum. L'orchestration impose une échéance de 90 secondes et un exécuteur de quatre travailleurs avec quatre places d'attente ; un résultat expiré est abandonné. Les délais réseau réels sont aussi bornés : abandonner une future seule n'arrête pas son appel réseau. Polly et Transcribe ont leurs propres délais. Les WAV invalides, incomplets, excessifs ou de plus de 30 secondes sont refusés proprement.

## 3. Protection des réponses récentes

Chaque contrôle classique conserve les versions et un état de départ des critères ciblés et facultatifs. Une écriture récente, un changement de profil ou un critère facultatif déjà connu rendent le résultat ancien inapplicable. Le journal identifie les résultats ignorés. La conversation conserve sa protection par critère.

Le point de rupture B1 n'est plus préselectionné à 20 % : un choix fermé explicite est requis, avec possibilité de répondre « Je ne sais pas ». Le montant fictif de scénario reste identifié comme hypothèse.

## 4. Intégrité des valeurs, citations et preuves

Le lecteur direct refuse les durées contradictoires, les consignes de manipulation et les bornes insuffisantes. Les nuances de langage passent à l'IA sans demander automatiquement une reformulation. Un oui/non sur les dettes exige une question univoque, identifiée et conservée dans son contexte.

Une citation doit être un passage contigu d'une seule réponse ; elle ne peut plus être recomposée en supprimant une négation. Les valeurs hors vocabulaire ou multiples pour un critère unique sont rejetées sans troncature silencieuse ; un tour interne peut réparer la sortie à partir de la même réponse.

Un minimum ou une fourchette ne devient plus un plafond numérique. Une limite qualitative reste à préciser, sans exclusion inventée. Les preuves du chercheur sont rattachées à l'entité de la source et vérifiées individuellement par un identifiant de preuve. Un accord pour un ticker ne valide pas toutes ses preuves. L'absence de résultat reste distincte d'un négatif démontré.

Les outils, arguments et hôtes sont validés par le code ; seules les API Wikipédia française et anglaise en HTTPS sont autorisées, sans redirection et avec une limite de réponse. Le cache est versionné et écrit atomiquement ; les requêtes brutes et rejets privés en sont retirés. La clé de secours serveur reste côté serveur, sans valeur préremplie dans un widget.

## 5. Données, configuration et publication

Le rendement 2022 part de la dernière clôture 2021. Les indicateurs et critères dérivés locaux ont été recalculés. Les positions FNB sont rapprochées par des correspondances explicites ; GOOG contribue à l'exposition au même émetteur que GOOGL sans être déclaré titre interchangeable.

Les seuils SRRI, de frais et de change proviennent de la configuration. Les bornes de frais déjà utilisées ont été conservées et nommées ; aucun nouveau barème financier n'a été inventé. La grille et la documentation distinguent les correspondances de valeurs, les durées de récupération et les observations R8/R9.

Le préparateur est l'unique procédure de paquet. Il vérifie l'inventaire, toutes les empreintes et la version, y compris avec Python `-O`. Les validations de corpus en production sont des exceptions explicites. `scripts/lancer_tests.py` découvre toutes les suites Python et JavaScript, borne leur durée et propage les échecs.

## Validation et limites

Exécuter `python scripts/lancer_tests.py`, `python mvp_profil/evaluer_classement.py --verifier` et `python scripts/preparer_mvp.py` depuis la racine. Sous Windows, Streamlit AppTest a besoin de sockets locales pour sa boucle asyncio.

Les régressions couvrent les transitions et identités vocales, les lectures retardées, la pause/reprise, les erreurs, les réponses périmées, les règles directes et les preuves avec des services simulés. Elles ne mesurent ni la précision réelle du modèle, ni un gain statistique de durée, ni le fonctionnement du micro sur le site déployé. Avant publication finale, comparer la version du manifeste à celle du serveur et essayer le parcours vocal dans le navigateur cible.

Validation locale terminée : **18 suites sur 18 réussies**, corpus de **51 phrases / 88 couples** valide, vérification de diff sans erreur d'espacement. Les deux suites d'interface ont également été relancées après l'ajout du dernier cas de panne d'interprétation d'un choix oral. Le paquet `mvp_profil.zip` contient **25 fichiers**, version **`profil-970d7c7ff946`** ; manifeste et empreintes revérifiés avec Python `-O`. Aucun appel réel à Bedrock, Transcribe, Polly ou Wikipédia pendant ces tests.
