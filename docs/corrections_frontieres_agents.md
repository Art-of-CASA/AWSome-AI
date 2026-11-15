# Correctifs des frontières d'agents

Les cinq défauts reproduits sur `6b7ef30408b21` sont corrigés dans cette branche :

- Une confirmation concerne uniquement la proposition présente au début du tour, dont l'identité et le contenu doivent rester inchangés.
- Les ajouts, retraits et réinitialisations demandés par le modèle sont autorisés par l'interprète déterministe de la phrase reçue. Le titre et la part proviennent de cette phrase. Une mutation identique ne s'exécute qu'une fois par tour. Les formulations non reconnues demandent une précision.
- Chaque appel est contrôlé contre les outils du rôle et leur schéma, avant le routeur. Les arguments supplémentaires sont refusés.
- Le plafond de douze demandes est vérifié avant chaque appel, y compris à l'intérieur d'un lot.
- L'installateur vérifie les entrées du ZIP, leurs empreintes et la version dérivée avant extraction ou installation. Il refuse les chemins dangereux, les doublons et les fichiers supplémentaires.

Le déploiement prend également un verrou exclusif. Chaque publication prépare un environnement Python distinct avec l'interpréteur du service existant ; en cas d'échec après activation, le chemin `venv` et les fichiers de l'application sont restaurés ensemble. Le service doit continuer à utiliser `/opt/awsome-ai/venv/bin/python`. La CI attend maintenant au-delà des 900 secondes accordées à SSM. Les anciens environnements sont conservés dans `venvs/` : leur suppression doit suivre une politique de rétention après vérification des versions encore utilisées.

Chaque événement du journal de recommandation porte désormais la version du contenu chargé. Les appels Converse conservent l'identifiant de requête AWS, le modèle et l'utilisation des jetons. Les questions, justifications, arguments bruts et diagnostics contenant du texte libre sont masqués dans les copies persistantes (fichier et DynamoDB), y compris lorsqu'ils sont imbriqués. Les détails restent disponibles uniquement dans la session courante. Cela ne supprime pas les anciens journaux déjà enregistrés.

## Validation

`python scripts/lancer_tests.py --timeout 300` découvre aussi `test_audit_controles.py`. Le test Bash du déploiement remplace AWS, pip, systemctl et HTTP par des substituts et couvre les échecs de démarrage, dépendances, santé, version et intégrité. Aucun de ces tests ne valide une exécution Bedrock réelle.

Résultats locaux du 15 novembre 2026 : 29/29 suites réussies ; après la dernière adaptation de l'installateur, ses 22 scénarios réussissent (ancien venv en dossier ou en lien symbolique). Les huit contrôles adversariaux de l'audit initial réussissent également, et le paquet altéré est rejeté avant activation. L'évaluation déterministe du corpus réussit sur 51 phrases et 88 paires. Les appels cloud sont substitués pendant ces contrôles.

## Contrôles AWS restant à effectuer avant certification

Ces correctifs locaux ne modifient pas le compte AWS. Les limites complémentaires de l'audit restent distinctes des cinq régressions :

- Lire la configuration effective du service, vérifier la version installée et effectuer les parcours fonctionnels réels, y compris voix et persistance. Les appels facturés nécessitent l'autorisation prévue par le cadre de l'audit.
- Restreindre l'origine au chemin CloudFront autorisé : la liste de préfixes CloudFront ne distingue pas les distributions. Préparer un mécanisme d'origine privée ou d'authentification d'origine après inspection du serveur effectif ; ne pas supposer que Cognito est branché.
- Si le Guardrail doit être obligatoire, choisir une version numérotée validée, configurer son usage effectif et l'imposer par les permissions. Son activation peut bloquer des échanges légitimes et doit être testée avant publication.
- Configurer les notifications budgétaires avec un destinataire approuvé ; un budget n'est pas une limite de dépense. Définir la rétention des traces et vérifier sur le service réel la minimisation et la corrélation ajoutées dans cette branche.
- La mémoire de conversation reste un état de session ; aucune reprise durable ou garantie d'idempotence distribuée n'est annoncée.

Les lectures d'inventaire Bedrock/AgentCore hors us-east-1 étaient refusées lors de l'audit. Une absence de déploiement dans ces régions reste non vérifiée.
