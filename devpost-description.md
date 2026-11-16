## Inspiration

Robert a 59 ans, un horizon de trois à cinq ans et un profil prudent. Pourtant, il veut placer 20 % de son portefeuille dans NVIDIA : tout le monde en parle.

Comment répondre utilement à cette envie ? Il faut comprendre la personne, mesurer les conséquences et expliquer la décision. C'est ce qui nous a guidés pour le cas AlphaForge AI : **comprendre l'investisseur avant de composer le portefeuille**.

Une personne peut se déclarer à l'aise avec le risque et réagir autrement devant une baisse. Un modèle peut comprendre ses mots et produire une réponse financière plausible sans en vérifier les contraintes. Nous avons construit AWSome autour de cette double incertitude : croiser les réponses avec les choix faits en simulation, puis confier les calculs et les contrôles à un moteur déterministe.

## Ce que fait AWSome

AWSome est un système agentique de simulation éducative qui accompagne l'utilisateur de son profil à un mini-portefeuille fictif explicable. Il réunit **un entretien vocal en français canadien, un questionnaire, trois mises en situation et un univers de 111 actifs**.

Le parcours renseigne **42 critères**, conserve la provenance des réponses et permet d'ajouter des contraintes personnelles. Le replay d'une baisse réelle de 2022, le choix entre des fourchettes de résultats et des titres masqués apportent une lecture complémentaire de la tolérance déclarée. Le budget de perte retient la composante la plus prudente entre capacité financière, tolérance déclarée et décisions observées dans ces exercices.

Le moteur applique ensuite exclusions, plafonds et préférences à chaque actif. Il construit un mini-portefeuille fictif, en mesure le risque sur les séries historiques en dollars canadiens et donne accès aux preuves. L'utilisateur peut comparer des actifs, poser une question à la voix ou à l'écrit, demander une modification et explorer « Et si… ? ».

**Chaque proposition répond à trois questions : pourquoi est-elle cohérente avec mon profil, qu'est-ce qui la limite, et qu'est-ce qui ferait changer la réponse ?**

## Trois personas, trois preuves concrètes

Les personas Amira, Mateo et Robert sont fictifs et leurs réponses complémentaires sont simulées. Les chiffres suivants sont reproductibles avec le moteur du dépôt sur les données arrêtées au 12 novembre 2026.

**Amira : accompagner l'ambition avec des limites visibles.** À 26 ans, avec un horizon de quinze ans et plus et un intérêt pour l'IA et les cryptoactifs, son budget de perte est de 45 %. NVIDIA est compatible, avec un score de 88/100, mais reste plafonné à 10 % du portefeuille. Son intérêt pour un thème ne supprime pas les contrôles de concentration.

**Mateo : rendre les valeurs effectives.** À 41 ans, avec un profil modéré et des exigences ESG, il obtient 57 actifs exclus sur 111 par l'ensemble de ses contraintes. NVIDIA est exclu. Les exclusions et controverses documentées priment sur les préférences ; les expositions connues des fonds sont prises en compte, avec une couverture partielle explicitement signalée.

**Robert : savoir dire non, puis montrer une possibilité.** Son budget de perte est de 15 %. À 20 % de NVIDIA, la perte de stress calculée passerait de 5,3 % à 18,4 %, et son plafond par titre serait dépassé. AWSome explique le conflit et propose 5 %. À cette part, la perte de stress calculée est de 8,4 %. Le système attend sa confirmation avant de modifier le portefeuille fictif.

Un même titre reçoit ainsi trois réponses différentes, reliées au profil et aux données. Le score est une mesure de compatibilité selon notre grille, jamais une prévision de rendement. La perte de stress est une mesure fondée sur l'historique et nos hypothèses, pas une borne garantie des pertes futures.

## Comment nous l'avons construit

Nous avons réparti les responsabilités selon ce que chaque composant doit faire de manière vérifiable.

**Les agents comprennent et orchestrent.** Sur Amazon Bedrock, un Classificateur et un Critique interprètent les réponses avec leurs citations. Un Découvreur transforme les demandes ouvertes en critères personnels ; un Chercheur recherche les liens documentés avec les actifs. Le Conseiller et l'Explicateur utilisent des outils pour consulter les contraintes, évaluer une demande, comparer des actifs et retrouver les preuves. Le profil utilise Claude Haiku 5.5 ; les agents de recommandation utilisent Claude Sonnet 5.5.

**Le code calcule et contrôle.** Les exclusions, plafonds, scores, pondérations et mesures sont déterministes. Le code rejette les valeurs hors liste, vérifie les citations et encadre les appels d'outils. Pour la restitution financière, le modèle sélectionne des détails autorisés ; le code conserve les verdicts, chiffres, avertissements et confirmations. Une sortie hors contrat revient à un gabarit fondé sur les résultats calculés.

**AWS porte le parcours complet.** Amazon Transcribe et Amazon Polly assurent la voix en français canadien. Streamlit est hébergé sur EC2 derrière CloudFront pour l'accès HTTPS. DynamoDB reçoit les traces des propositions. S3 et Systems Manager servent au déploiement, avec des rôles IAM temporaires et GitHub OIDC pour la livraison. GitHub Actions lance les tests, prépare un paquet vérifié et orchestre son installation. Bedrock Guardrails est provisionné mais désactivé par défaut, car il bloquait aussi des refus légitimes ; les contrôles du code restent actifs.

**Les données restent inspectables.** Nous avons étendu les 31 actifs de départ à 111, enrichi leurs caractéristiques et converti les séries en dollars canadiens. Prix, change, fondamentaux, données de fonds, attention et controverses proviennent de sources publiques documentées. Chaque hypothèse de seuil ou de pondération reste écrite et consultable.

## Défis rencontrés

Le premier défi était de rendre le risque compréhensible au niveau du portefeuille : un titre peut convenir à petite dose et créer une tension à une autre pondération. Nous avons relié les limites du profil aux expositions et aux mesures du portefeuille, puis rendu le conflit visible en pourcentages et en montants fictifs.

Le deuxième était de conserver une explication fidèle après le passage par un modèle. Une consigne de prompt ne suffisait pas : nous avons fermé le contrat de restitution, conservé les conclusions obligatoires dans le code et contrôlé les actions et confirmations.

Le troisième était de rendre comparables des sources hétérogènes sans masquer leur couverture. Les devises, les historiques incomplets, les positions partielles des fonds et les controverses non exhaustives devaient apparaître comme des limites des données, plutôt que disparaître derrière un score.

## Réalisations dont nous sommes fiers

- **Un parcours intégré**, de la conversation vocale aux propositions, à la comparaison et aux scénarios « Et si… ? ».
- **Un refus utile et mesuré**, illustré par Robert : le conflit, son effet chiffré et une alternative soumise à confirmation.
- **Une traçabilité consultable**, depuis une conclusion jusqu'à la réponse du profil, la donnée datée ou l'hypothèse qui la soutient.
- **Des règles reproductibles**, où une préférence ne compense pas une exclusion et où les résultats financiers restent calculés par le code.
- **Une vérification accessible**, avec des suites locales portant sur les contraintes, outils, restitution, confidentialité et interface, ainsi qu'un script qui régénère les résultats des personas.

Les tests locaux substituent les services cloud. Ils vérifient les contrôles et l'orchestration, sans démontrer la précision des modèles ou de la reconnaissance vocale. Le corpus de validation comprend 51 phrases et 88 couples phrase–critère ; sa présence ne constitue pas un taux de réussite du modèle.

## Ce que nous avons appris

Nous avons fait construire neuf portefeuilles par le modèle seul, trois pour chaque persona. Dans cette expérience exploratoire, antérieure aux derniers correctifs, les propositions respectaient les contraintes explicites, mais trois omettaient une limite d'exposition au secteur de l'emploi qui n'avait pas été rappelée au modèle. Les poids variaient aussi d'un essai à l'autre.

Ce résultat a conforté notre choix : réserver les règles aux résultats qui doivent être reproductibles et utiliser les agents pour comprendre les demandes et consulter les bons outils. Neuf essais ne permettent pas de généraliser à tous les modèles ; le protocole et ses limites sont documentés dans le dépôt.

Nous avons également appris à distinguer une information absente d'une information négative, une décision en simulation d'un comportement réel et une mesure historique d'une prévision. Cette précision rend les explications plus utiles et les limites plus faciles à discuter.

## La suite pour AWSome

Nous voulons mesurer la qualité de la transcription et de l'interprétation sur des conversations annotées, tester l'expérience avec davantage d'utilisateurs et confronter nos règles à des experts. Nous voulons aussi élargir les historiques et les scénarios de stress, enrichir les controverses et les positions de fonds, et mieux calibrer la construction des portefeuilles.

Le prototype utilise une heuristique explicable, des seuils d'équipe et une couverture de données partielle. Il ne démontre ni une allocation optimale ni une surperformance. Les décisions observées dans les mises en situation ne prouvent pas le comportement avec de l'argent réel.

**AWSome aide à comprendre une proposition, à en voir les limites et à savoir pourquoi la réponse change.** L'ensemble est une simulation éducative sur des profils fictifs, sans conseil financier personnalisé et sans transaction réelle.

## Essayer et vérifier

Application : https://d29e3l5vv5fmjy.cloudfront.net

Code, guide d'installation et documentation : https://github.com/Art-of-CASA/AWSome-AI

Pour une démonstration rapide, charger Robert, ouvrir « Découvrir mes propositions », puis demander « J'aimerais 20 % de Nvidia ». Comparer ensuite le même titre avec Amira et Mateo. Les résultats locaux et leur méthode sont disponibles dans `docs/resultats_personas.md` et `docs/documentation_technique.md`.
