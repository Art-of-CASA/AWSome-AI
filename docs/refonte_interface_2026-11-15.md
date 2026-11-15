# Refonte de l'interface et du replay

Date : 15 novembre 2026. Évolution locale du MVP Streamlit ; aucun déploiement AWS n'est effectué par ces modifications.

## Présentation

Le parcours adopte une palette ivoire, encre et vert forêt, une hiérarchie plus lisible et des cartes qui séparent les questions. Les aides expliquent le type de réponse attendu ; les réglages techniques sont regroupés. Un aperçu du profil restitue les informations en langage courant, avec les sources et les détails disponibles pour vérification.

Le questionnaire conserve ses choix explicites, sa validation et son ordre adaptatif. Une réponse « Je ne sais pas » n'est pas transformée en réponse confirmée. Les questions ouvertes restent orales et le composant vocal unique conserve sa position dans le parcours afin de ne pas interrompre les échanges.

Le thème Streamlit est défini dans `.streamlit/config.toml` à la racine et dans `mvp_profil/.streamlit/config.toml`. Les deux fichiers portent les mêmes couleurs claires : le premier s'applique au lancement depuis le dépôt, le second accompagne le paquet installé et le lancement depuis `mvp_profil/`. Le composant vocal est visuellement masqué lorsqu'il est en veille, en conservant son instance et ses identifiants de session.

## Replay continu

La courbe se dessine progressivement dans le navigateur à partir des prix historiques quotidiens déjà présents dans le dépôt. L'observation ne demande aucun clic de confirmation et aucun arrêt n'est imposé. L'utilisateur peut réduire le montant investi, renforcer sa position fictive ou tout vendre au moment qu'il choisit. Une pause éventuelle de lecture ne signifie pas une vente.

Le bouton **Découvrir le replay** de l'accueil ouvre un aperçu interactif sans identifiants AWS ni clé de modèle. Cet aperçu permet de parcourir la simulation et sa révélation, puis de revenir à l'accueil sans créer de profil. Les trois personas sont également accessibles sans connexion ; les parcours qui analysent de nouvelles réponses nécessitent toujours le modèle et les services vocaux configurés.

Le navigateur transmet un journal cumulatif des décisions, identifié par une session et un numéro d'événement. Le serveur vérifie l'ordre et les actions, rejette les événements périmés et recalcule les montants aux prix de la série. Les calculs du profil ne dépendent donc pas des valeurs de portefeuille envoyées par le navigateur.

La vente totale fixe le point de rupture observé B2 ; une réduction reste un signal distinct. Une absence de vente produit `non_atteint` avec la plus forte baisse réellement présentée. La suite historique n'est révélée qu'à la fin de l'expérience et ne relève pas rétroactivement la tolérance mesurée. Les anciens personas conservent leurs traces fictives d'origine.

## Fichiers et vérification

`interface.py` et `design.css` portent la présentation commune. `replay_composant.py`, `composant_replay/index.html` et `composant_replay/replay.js` portent l'animation. `replay_moteur.py` vérifie les événements et la comptabilité ; `replay_quotidien.json` contient les séries locales.

Tous les fichiers nécessaires à l'exécution sont inclus dans `version_profil.FICHIERS` : la version de contenu et le paquet vérifié de `scripts/preparer_mvp.py` couvrent également les styles et le composant de replay. Les tests hors ligne utilisent un composant de replay simulé ; ils ne mesurent pas la compréhension des vrais services vocaux ou du modèle.

Le moteur d'appariement des actifs et les suggestions personnalisées restent à construire. Cette refonte ne modifie pas cet état fonctionnel.
