# Correctifs de l'audit multi-agents

Les corrections sont disponibles **localement**, dans la version de production **`profil-afb08c85729b`**, avec 60 fichiers dans le manifeste. Aucun commit, push ou déploiement AWS n'a été effectué pendant ces corrections.

## Résultats vérifiés

| Cas de l'audit | Comportement corrigé |
|---|---|
| Faux modèle annonçant NVDA compatible pour Robert à 20 % | Sortie hors contrat rejetée ; le verdict « en tension » et ses raisons restent affichés |
| « Je ne veux pas de Nvidia » | Aucun ajout |
| « Est-ce que Nvidia est risqué ? » | Consultation sans modifier le portefeuille ni perdre une proposition en attente |
| « Oui, mais pas maintenant, ne modifiez rien » | Aucune hausse de plafond et aucun ajout confirmé |
| Confirmation fabriquée par le modèle | Le contrôle utilise la phrase réelle de l'utilisateur, pas une citation proposée par l'agent |
| « Je veux Nvidia. », « RY.TO. » | Ponctuation finale traitée sans casser les symboles contenant un point |
| Demande de 0 % | Aucun repli vers les 5 % par défaut, y compris si un modèle tente de remplacer le zéro |
| Fonds XEQT coté CAD et non couvert | Tout son poids est compté prudemment dans le plafond de change ; 100 % de XEQT donne 100 % de poids exposé |
| Rentabilité de Boeing et Philip Morris | Part d'exercices rentables : 25 % et 100 %, calculée depuis Net Income ; capitaux propres non positifs => ROE et dette/capitaux propres non interprétables |
| Exclusion de GOOGL pour Mateo | Les fonds contenant une position GOOGL connue sont exclus ; exposition connue finale à GOOGL : 0 % |
| Exclusions d'activités E5 | Propagées aux positions connues des fonds ; les positions inconnues restent explicitement inconnues |
| Sensibilité après ajout de NVDA | Les ajouts imposés sont conservés dans toutes les variantes |
| Échec d'écriture du journal local | État « mémoire seulement », erreur visible et événement conservé en mémoire |
| Échec du redémarrage après installation | Restauration des fichiers précédents ; cache et traces locales conservés |
| Dépendances et archives | Contraintes de versions ajoutées et incluses dans le paquet ; dépendances installées avant activation ; archives actualisées et vérifiées |

## Restitution des explications

Le modèle continue à comprendre la demande et choisir les outils. Pour la restitution financière, il ne peut renvoyer que des identifiants de détails appartenant au catalogue courant. Le code assemble les phrases et conserve obligatoirement verdicts, avertissements, limites et confirmations. Les actions conversationnelles utilisent intégralement le texte calculé par le code.

Une prose libre, un champ JSON supplémentaire, un doublon ou un identifiant inconnu entraîne une relance, puis le gabarit si nécessaire. La trace indique séparément la rédaction par le code et la sélection par le modèle. Les regex de gouvernance ont été renforcées pour les exemples reproduits ; elles restent un contrôle partiel et ne sont pas présentées comme une validation sémantique universelle.

## Données régénérées et impacts

Les critères d'actifs, scénarios, vocabulaire, données du chercheur, données embarquées et tableaux des personas ont été régénérés **sans téléchargement**. Les données sources de prix ont été conservées.

| Persona | Positions | Perte de stress avant correctifs | Perte de stress actuelle |
|---|---:|---:|---:|
| Amira | 12 | 22,5 % | 22,5 % |
| Mateo | 12 | 12,8 % | 8,6 % |
| Robert | 11 | 6,0 % | 5,3 % |

Les trois budgets de perte restent 45 %, 22 % et 15 %. Aucun conflit n'est signalé par les contrôles actuels. Les nouveaux résultats complets sont dans [resultats_personas.md](resultats_personas.md). Le refus de 20 % de NVDA reste valable pour Robert ; à 5 %, la perte de stress passe désormais de 5,3 % à 8,4 %.

Le contrôle de change compte tout le poids d'un fonds exposé sans couverture CAD : c'est une borne prudente, pas une estimation de son pourcentage exact de sous-jacents étrangers. Les exclusions E2/E5 couvrent les positions connues et la fiche des fonds ; aucune garantie n'est donnée sur leurs positions inconnues.

## Vérifications

- **28/28 suites réussies** avec `python scripts/lancer_tests.py --timeout 300`, modèles et services cloud simulés. Cela inclut les 18 affichages Streamlit, 200 profils aléatoires et les nouvelles régressions adverses.
- **8 scénarios Bash** du déploiement : succès, redémarrage en échec, santé en échec, page en échec, échec du redémarrage de l'ancienne version, mauvaise version, téléchargement en échec et installation pip en échec. Les commandes externes sont simulées ; aucun service réel n'est redémarré.
- Jeu annoté du profil : **51 phrases / 88 couples**, validation structurelle réussie sans modèle réel.
- Dépendances : résolution à blanc hors réseau réussie avec les contraintes du snapshot Python 3.13.
- Données embarquées synchronisées ; manifeste et empreintes des deux paquets MVP vérifiés ; contenu de l'archive de données comparé aux fichiers courants.
- Vérification des espaces du diff réussie en tenant compte des fins de ligne CRLF sous Windows.

Les tests Streamlit et Git Bash ont tourné hors du sandbox après autorisation automatique, car les sockets locales et le démarrage MSYS sont bloqués dans cet environnement restreint.

Les journaux locaux sont dans `tmp/audit_2026-11-15/`, notamment `tests_apres_correctifs.txt` et `reproductions_apres_correctifs.txt`. Le script `reproduire_constats.py` conserve les cas de l'audit et permet de constater le comportement corrigé.

## Paquets prêts

- `mvp_profil.zip` et `artifacts/awsome-ai-refonte-2026-11-15.zip` : même version `profil-afb08c85729b`, 60 fichiers de production et un manifeste.
- `data_extended.zip` : les 20 fichiers actuels de données, comparés à leurs sources locales.

Les README contradictoires et les chiffres de présentation ont été actualisés. Le compte rendu de l'expérience « modèle seul » reste un instantané historique, explicitement identifié comme antérieur aux corrections.

## Limites restantes

Le nouveau contrat de restitution reste à tester sur les vrais modèles Bedrock et sur le site hébergé. La fiabilité du classement vocal réel, l'accès du jury, la vidéo finale et la mise en page du one pager ne sont pas validés par ces corrections locales. Guardrails reste désactivé par défaut.

Le retour arrière restaure les fichiers de l'application. Le venv du serveur reste partagé : il ne restaure pas automatiquement les bibliothèques déjà modifiées par pip. Les contraintes fixent les versions attendues, sans constituer un verrouillage avec empreintes de tous les artefacts multiplateformes. La couverture des fonds et la calibration des hypothèses restent les limites décrites dans la documentation technique.
